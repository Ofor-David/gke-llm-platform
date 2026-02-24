#!/bin/bash

set -e

PRIVATE_GKE_ENDPOINT="__PRIVATE_GKE_ENDPOINT__"
FORWARD_PORT="8888"

echo "Updating system..."
apt-get update -y

echo "Installing socat..."
apt-get install -y socat

echo "Creating systemd service..."

cat <<EOF > /etc/systemd/system/gke-forward.service
[Unit]
Description=Forward traffic to Private GKE Control Plane
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/socat TCP-LISTEN:${FORWARD_PORT},fork,reuseaddr TCP:${PRIVATE_GKE_ENDPOINT}:443
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

echo "Reloading systemd..."
systemctl daemon-reload

echo "Enabling service..."
systemctl enable gke-forward

echo "Starting service..."
systemctl start gke-forward

echo "Bootstrap completed successfully."
