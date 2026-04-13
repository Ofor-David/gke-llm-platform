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
CLUSTER_CONTEXT="gke_${PROJECT}_${ZONE}_${CLUSTER}"
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
# Cleanup — always runs on exit, interrupt, or error
# ---------------------------------------------------------------------------
cleanup() {
  local exit_code=$?

  if [[ -n "$TUNNEL_PID" ]] && kill -0 "$TUNNEL_PID" 2>/dev/null; then
    info "Stopping IAP tunnel (PID $TUNNEL_PID)..."
    kill "$TUNNEL_PID" 2>/dev/null || true
    # Give child processes a moment to exit
    sleep 1
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

trap cleanup EXIT INT TERM

# ---------------------------------------------------------------------------
# Preflight checks
# ---------------------------------------------------------------------------
for bin in gcloud kubectl nc; do
  command -v "$bin" &>/dev/null || die "'$bin' is not installed or not in PATH."
done

[[ -f ~/.kube/config ]] || die "~/.kube/config not found. Run 'gcloud container clusters get-credentials' first."

# ---------------------------------------------------------------------------
# Ensure kubeconfig has credentials for this cluster
# ---------------------------------------------------------------------------
if ! kubectl config get-contexts "$CLUSTER_CONTEXT" &>/dev/null; then
  warn "No kubeconfig context found for '$CLUSTER_CONTEXT'."
  info "Fetching cluster credentials..."
  gcloud container clusters get-credentials "$CLUSTER" \
    --location="$ZONE" \
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
  --zone="$ZONE" \
  --local-host-port="localhost:$LOCAL_PORT" &
TUNNEL_PID=$!

# ---------------------------------------------------------------------------
# Wait for tunnel to be ready — probe with nc 
# ---------------------------------------------------------------------------
info "Waiting for tunnel to be ready (timeout: ${TUNNEL_READY_TIMEOUT}s)..."
deadline=$(( $(date +%s) + TUNNEL_READY_TIMEOUT ))
tunnel_ready=false

while (( $(date +%s) < deadline )); do
  # Check the tunnel process is still alive
  if ! kill -0 "$TUNNEL_PID" 2>/dev/null; then
    die "IAP tunnel process exited unexpectedly. Check your IAP permissions and bastion config."
  fi

  # Probe the local port
  if nc -z localhost "$LOCAL_PORT" 2>/dev/null; then
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
echo "  Context : $CLUSTER_CONTEXT"
echo "  Tunnel  : localhost:$LOCAL_PORT → ${BASTION_HOST}:${TUNNEL_PORT}"
echo "  Backup  : $BACKUP"
echo ""
echo "  Try:  kubectl get nodes --context=$CLUSTER_CONTEXT"
echo ""
echo "  Press Ctrl+C to shut down the tunnel and restore"
echo "  your kubeconfig automatically."
echo "========================================================"
echo ""

# ---------------------------------------------------------------------------
# Block until the tunnel exits (or the user presses Ctrl+C)
# ---------------------------------------------------------------------------
wait "$TUNNEL_PID"