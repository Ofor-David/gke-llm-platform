#!/bin/bash

set -e

GATEWAY_API_VERSION="v1.4.1"
CRD_URL="https://github.com/kubernetes-sigs/gateway-api/releases/download/${GATEWAY_API_VERSION}/standard-install.yaml"

echo "Installing Gateway API CRDs ${GATEWAY_API_VERSION}..."

# Download CRDs
echo "Downloading CRDs..."
curl -fsSL -o /tmp/gateway-crds.yaml "$CRD_URL"

# Verify download
if [ ! -s /tmp/gateway-crds.yaml ]; then
    echo "ERROR: Download failed"
    exit 1
fi

# Apply CRDs
echo "Applying CRDs to cluster..."
kubectl apply --server-side -f /tmp/gateway-crds.yaml

# Wait for CRDs to be established
echo "Waiting for CRDs to be established..."
kubectl wait --for condition=established --timeout=60s crd \
    gatewayclasses.gateway.networking.k8s.io \
    gateways.gateway.networking.k8s.io \
    httproutes.gateway.networking.k8s.io \
    referencegrants.gateway.networking.k8s.io || true

# Verify
echo "Verifying installation..."
kubectl get crd | grep gateway.networking.k8s.io

echo "Done! Gateway API CRDs installed successfully."
