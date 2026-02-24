#!/bin/bash

set -e
step certificate create root.linkerd.cluster.local ca.crt ca.key \
  --profile root-ca \
  --no-password \
  --insecure

helm install linkerd-control-plane \
  -n linkerd \
  --set-file identityTrustAnchorsPEM=ca.crt \
  --set identity.issuer.scheme=kubernetes.io/tls \
  linkerd-edge/linkerd-control-plane