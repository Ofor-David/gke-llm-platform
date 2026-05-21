#!/bin/bash
# =============================================================================
# gke-iap-tunnel.sh
# Establishes an IAP tunnel to a GKE cluster bastion and configures kubeconfig
# safely — with TLS preserved, proper cleanup, and error handling.
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration — edit these to match your environment
# ---------------------------------------------------------------------------
PROJECT="your-project-id"
ZONE="europe-west4-a"
CLUSTER="llm-cluster"
BASTION_HOST="bastion-host"
TUNNEL_PORT="8888"
LOCAL_PORT="8888"
TUNNEL_READY_TIMEOUT=30   # seconds to wait for tunnel to become ready

# ---------------------------------------------------------------------------
# Derived values — do not edit
# ---------------------------------------------------------------------------
CLUSTER_CONTEXT="gke_${PROJECT}_${LOCATION}_${CLUSTER}"
BACKUP=~/.kube/config.backup.$(date +%Y%m%d%H%M%S)
TUNNEL_PID=""

# ---------------------------------------------------------------------------
# Logging helpers
# ---------------------------------------------------------------------------
info()    { echo "[INFO]  $*"; }
success() { echo "[OK]    $*"; }
warn()    { echo "[WARN]  $*" >&2; }
die()     { echo "[ERROR] $*" >&2; exit 1; }

# ---------------------------------------------------------------------------
# Cleanup — always runs on exit, interrupt, or error.
# Intentionally restores kubeconfig on every exit so the tunnel-patched
# server URL never persists beyond this session.
# ---------------------------------------------------------------------------
cleanup() {
  local exit_code=$?

  if [[ -n "$TUNNEL_PID" ]] && kill -0 "$TUNNEL_PID" 2>/dev/null; then
    info "Stopping IAP tunnel (PID $TUNNEL_PID)..."
    kill "$TUNNEL_PID" 2>/dev/null || true
    # Wait up to 10 s for the process to exit, then force-kill
    local waited=0
    while kill -0 "$TUNNEL_PID" 2>/dev/null && (( waited < 10 )); do
      sleep 1
      (( waited++ )) || true
    done
    kill -0 "$TUNNEL_PID" 2>/dev/null && kill -9 "$TUNNEL_PID" 2>/dev/null || true
    success "Tunnel stopped."
  fi

  if [[ -f "$BACKUP" ]]; then
    info "Restoring original kubeconfig from $BACKUP..."
    cp "$BACKUP" ~/.kube/config
    success "kubeconfig restored."
  fi

  exit "$exit_code"
}

# Register trap before any side effects so cleanup always runs
trap cleanup EXIT INT TERM

# ---------------------------------------------------------------------------
# Preflight checks
# ---------------------------------------------------------------------------
gcloud container clusters get-credentials $CLUSTER --location=$LOCATION --project=$PROJECT &>/dev/null || die "Failed to get cluster credentials. Check your gcloud config and permissions."
for bin in gcloud kubectl; do
  command -v "$bin" &>/dev/null || die "'$bin' is not installed or not in PATH."
done

# nc is optional — we fall back to /dev/tcp if unavailable
NC_AVAILABLE=false
command -v nc &>/dev/null && NC_AVAILABLE=true

[[ -f ~/.kube/config ]] || die "~/.kube/config not found. Run 'gcloud container clusters get-credentials' first."

# ---------------------------------------------------------------------------
# Port probe helper — tries nc first, falls back to /dev/tcp
# ---------------------------------------------------------------------------
port_open() {
  local port="$1"
  if $NC_AVAILABLE; then
    nc -z localhost "$port" 2>/dev/null
  else
    (echo >/dev/tcp/localhost/"$port") 2>/dev/null
  fi
}

# ---------------------------------------------------------------------------
# Ensure kubeconfig has credentials for this cluster
# ---------------------------------------------------------------------------
if ! kubectl config get-contexts "$CLUSTER_CONTEXT" &>/dev/null; then
  warn "No kubeconfig context found for '$CLUSTER_CONTEXT'."
  info "Fetching cluster credentials..."
  gcloud container clusters get-credentials "$CLUSTER" \
    --location="$LOCATION" \
    --project="$PROJECT"
fi

# ---------------------------------------------------------------------------
# Backup kubeconfig with a timestamped name (never overwrite a prior backup)
# ---------------------------------------------------------------------------
info "Backing up kubeconfig to $BACKUP..."
cp ~/.kube/config "$BACKUP"
success "Backup created."

# ---------------------------------------------------------------------------
# Start IAP tunnel in background
# ---------------------------------------------------------------------------
info "Starting IAP tunnel: bastion=$BASTION_HOST, remote=$TUNNEL_PORT → localhost:$LOCAL_PORT..."
gcloud compute start-iap-tunnel "$BASTION_HOST" "$TUNNEL_PORT" \
  --project="$PROJECT" \
  --zone="$LOCATION" \
  --local-host-port="localhost:$LOCAL_PORT" &
TUNNEL_PID=$!

# ---------------------------------------------------------------------------
# Wait for tunnel to be ready
# ---------------------------------------------------------------------------
info "Waiting for tunnel to be ready (timeout: ${TUNNEL_READY_TIMEOUT}s)..."
deadline=$(( $(date +%s) + TUNNEL_READY_TIMEOUT ))
tunnel_ready=false

while (( $(date +%s) < deadline )); do
  if ! kill -0 "$TUNNEL_PID" 2>/dev/null; then
    die "IAP tunnel process exited unexpectedly. Check your IAP permissions and bastion config."
  fi

  if port_open "$LOCAL_PORT"; then
    tunnel_ready=true
    break
  fi

  sleep 1
done

$tunnel_ready || die "Tunnel did not become ready within ${TUNNEL_READY_TIMEOUT}s. Aborting."
success "Tunnel is live on localhost:$LOCAL_PORT."

# ---------------------------------------------------------------------------
# Configure kubeconfig to route through the tunnel
#
# We redirect --server to the tunnel endpoint but keep full TLS verification.
#
# The API server's cert is issued for internal SANs (kubernetes,
# kubernetes.default, etc.) — not for "localhost". Connecting via
# localhost:PORT would cause an x509 SAN mismatch and fail verification.
#
# --tls-server-name=kubernetes tells the TLS stack to verify the cert against
# the SAN "kubernetes" (which IS in the cert) while still dialling
# localhost:PORT. Full chain verification is preserved — no skipping.
# ---------------------------------------------------------------------------
info "Redirecting cluster API server to tunnel endpoint..."
kubectl config set-cluster "$CLUSTER_CONTEXT" \
  --server="https://localhost:$LOCAL_PORT" \
  --tls-server-name=kubernetes

success "kubeconfig updated. Context: $CLUSTER_CONTEXT"

# ---------------------------------------------------------------------------
# Usage summary
# ---------------------------------------------------------------------------
echo ""
echo "========================================================"
echo "  IAP tunnel active — kubectl is ready"
echo "========================================================"
echo "  Context  : $CLUSTER_CONTEXT"
echo "  Tunnel   : localhost:$LOCAL_PORT → ${BASTION_HOST}:${TUNNEL_PORT}"
echo "  Backup   : $BACKUP"
echo ""
echo "  Try:  kubectl get nodes --context=$CLUSTER_CONTEXT"
echo ""
echo "  Press Ctrl+C to shut down the tunnel and restore"
echo "  your kubeconfig automatically."
echo "========================================================"
echo ""

# ---------------------------------------------------------------------------
# Block until the tunnel exits or the user presses Ctrl+C.
# 'wait' returns the tunnel's exit code — cleanup handles the rest.
# ---------------------------------------------------------------------------
wait "$TUNNEL_PID"