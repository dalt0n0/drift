# Drift Helm Chart

Kubernetes deployment chart — **Phase 6 deliverable**.

## Planned structure

```
helm/
  Chart.yaml
  values.yaml
  templates/
    deployment.yaml
    service.yaml
    ingress.yaml
    configmap.yaml
    secret.yaml
    persistentvolumeclaim.yaml
    hpa.yaml
```

## Quick install (Phase 6)

```bash
helm repo add Drift https://charts.Drift.io
helm install Drift Drift/Drift \
  --set secrets.secretKey=<value> \
  --set secrets.jwtSecret=<value> \
  --set postgresql.auth.password=<value>
```
