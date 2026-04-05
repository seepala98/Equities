# Kubernetes Deployment

## Prerequisites
- Docker Desktop with Kubernetes enabled
- kubectl configured to point to your cluster

## Quick Deploy (Local Docker Kubernetes)

```bash
# 1. Build Docker images
docker build -t equities/web:latest ./web
docker build -t equities/frontend:latest ./frontend
docker build -t equities/airflow:latest -f ./web/airflow/Dockerfile.airflow ./web

# 2. Create namespace
kubectl apply -f k8s/namespace.yaml

# 3. Apply secrets and config
kubectl apply -f k8s/secrets.yaml
kubectl apply -f k8s/configmap.yaml

# 4. Deploy databases
kubectl apply -f k8s/postgres.yaml
kubectl apply -f k8s/redis.yaml

# 5. Deploy application services
kubectl apply -f k8s/django.yaml
kubectl apply -f k8s/frontend.yaml
kubectl apply -f k8s/nginx.yaml

# 6. Deploy Airflow (v3.0.0)
kubectl apply -f k8s/airflow.yaml

# 7. Wait for pods to be ready
kubectl get pods -n equities -w
```

## Accessing Services

After deployment:
| Service | URL | Port |
|---------|-----|------|
| App (nginx) | http://localhost | 80 |
| Airflow | http://localhost:8081 | 8080 (via kubectl port-forward) |

### Port Forward Commands
```bash
# Airflow
kubectl port-forward svc/airflow-webserver 8081:8080 -n equities

# Django API
kubectl port-forward svc/django 8000:8000 -n equities
```

## Resource Configuration

All deployments include resource requests and limits:

| Service | CPU Request | Memory Request | CPU Limit | Memory Limit |
|---------|-------------|----------------|-----------|--------------|
| Django | 250m | 512Mi | 1000m | 1Gi |
| Frontend | 50m | 64Mi | 500m | 256Mi |
| Nginx | 50m | 64Mi | 500m | 256Mi |
| Airflow Webserver | 500m | 1Gi | 1000m | 2Gi |
| Airflow Scheduler | 500m | 1Gi | 2000m | 2Gi |
| PostgreSQL | 100m | 256Mi | 1000m | 1Gi |
| Redis | 50m | 128Mi | 500m | 512Mi |

## Airflow 3.0.0 Notes

- Uses Python 3.11 instead of Python 3.9
- Requires Redis 4.x (not 5.x/7.x) due to provider compatibility
- Uses `airflow db migrate` instead of `airflow db init`
- Uses `airflow api-server` instead of `airflow webserver`
- Requires `AIRFLOW__DATABASE__SQL_ALCHEMY_CONN` instead of `AIRFLOW__CORE__SQL_ALCHEMY_CONN`

## Troubleshooting

```bash
# Check pod status
kubectl get pods -n equities

# View logs
kubectl logs <pod-name> -n equities

# Describe pod
kubectl describe pod <pod-name> -n equities

# Delete failing pod (will restart)
kubectl delete pod <pod-name> -n equities

# Restart deployment
kubectl rollout restart deployment/<deployment-name> -n equities

# Port forward for debugging
kubectl port-forward svc/airflow-webserver 8081:8080 -n equities
```

## Cleanup

```bash
kubectl delete -f k8s/
```
