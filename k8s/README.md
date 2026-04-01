# Kubernetes Deployment

## Prerequisites
- kubectl configured to point to your cluster
- Container images built and pushed to a registry (update image names in manifests)

## Quick Deploy

```bash
# 1. Create namespace
kubectl apply -f k8s/namespace.yaml

# 2. Apply secrets (edit base64 values first!)
kubectl apply -f k8s/secrets.yaml

# 3. Apply config
kubectl apply -f k8s/configmap.yaml

# 4. Deploy storage + databases
kubectl apply -f k8s/postgres.yaml
kubectl apply -f k8s/redis.yaml

# 5. Deploy application services
kubectl apply -f k8s/django.yaml
kubectl apply -f k8s/frontend.yaml
kubectl apply -f k8s/nginx.yaml

# 6. Deploy Airflow
kubectl apply -f k8s/airflow.yaml

# 7. Deploy observability
kubectl apply -f k8s/prometheus.yaml
kubectl apply -f k8s/grafana.yaml
```

## Updating Images

Build and push your images, then roll out:
```bash
kubectl rollout restart deployment/django -n equities
kubectl rollout restart deployment/frontend -n equities
```

## Secrets

Edit `k8s/secrets.yaml` before applying. Generate base64 values:
```bash
echo -n 'your-secret-value' | base64
```
