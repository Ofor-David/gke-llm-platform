# Troubleshooting

## General Diagnostics

### Check All Pods

```bash
kubectl get pods -A
kubectl get pods -A -o wide
```

### Describe Resources

```bash
kubectl describe pod <pod-name> -n <namespace>
kubectl describe deployment <name> -n <namespace>
```

### View Logs

```bash
# All pods in namespace
kubectl logs -n <namespace> -l app=<app-name>

# Previous container logs (if restarted)
kubectl logs -n <namespace> <pod-name> --previous

# Follow logs
kubectl logs -n <namespace> <pod-name> -f
```

## Linkerd Issues

### Diagnose Linkerd

```bash
linkerd check
```

### View Linkerd Dashboard

```bash
linkerd viz dashboard
```

## Helm Issues

### List Releases

```bash
helm list -A
```

### Get Release Status

```bash
helm status <release-name> -n <namespace>
```

## Certificate Issues

### Check Certificates

```bash
kubectl get certificates -A
kubectl describe certificate -n <namespace>
```

### Check Cert-Manager Pods

```bash
kubectl get pods -n cert-manager
kubectl logs -n cert-manager -l app.kubernetes.io/name=cert-manager
```

## Autoscaling Issues (KEDA)

### Check ScaledObjects

```bash
kubectl get scaledobject -n inference
kubectl describe scaledobject ollama -n inference
```

### Check KEDA Pods

```bash
kubectl get pods -n keda
kubectl logs -n keda -l app=keda-operator
```

## Network Issues

### Test Service Connectivity

```bash
# From a pod
kubectl exec -it <pod-name> -n <namespace> -- curl http://<service>.<namespace>.svc.cluster.local:<port>

# Port forward
kubectl port-forward -n <namespace> svc/<service> <local-port>:<service-port>
```


## Common Issues

### Pod Stuck in Pending

```bash
kubectl describe pod <pod-name> -n <namespace>
# Check: insufficient resources, PVC not bound, node selectors
```

### Pod Stuck in CrashLoopBackOff

```bash
kubectl logs <pod-name> -n <namespace>
kubectl describe pod <pod-name> -n <namespace>
# Check: missing environment variables, wrong image, config errors
```

### ImagePullBackOff

```bash
# Check image exists and registry is accessible
kubectl describe pod <pod-name> -n <namespace>
# Verify image repository, tag, and pull policy
```

### Service Not Responding

```bash
# Check endpoints
kubectl get endpoints <service-name> -n <namespace>

# Check Linkerd proxy
linkerd check --proxy
```
