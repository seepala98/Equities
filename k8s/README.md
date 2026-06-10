# Kubernetes Deployment

## Prerequisites
- Docker Desktop with Kubernetes enabled
- kubectl configured to point to your cluster

## Quick Deploy (Local Docker Kubernetes)

### Using Startup Scripts (Recommended)

**Windows:**
```powershell
# Build images and deploy all services
.\k8s\start-all.ps1

# In another terminal, set up port forwards
.\k8s\port-forward.ps1
```

**Linux/Mac/Git Bash:**
```bash
# Build images and deploy all services
./k8s/start-all.sh

# In another terminal, set up port forwards
./k8s/port-forward.sh
```

### Manual Deploy

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

# 6. Deploy Airflow (v3.2.1)
kubectl apply -f k8s/airflow.yaml

# 7. Run Django migrations
kubectl exec -n equities deployment/django -- python manage.py migrate

# 8. Wait for pods to be ready
kubectl get pods -n equities -w
```

## Accessing Services

### Quick Start Scripts

**Windows (PowerShell):**
```powershell
# Start all services
.\k8s\start-all.ps1

# In another terminal, set up port forwards
.\k8s\port-forward.ps1
```

**Linux/Mac/Git Bash:**
```bash
# Start all services
./k8s/start-all.sh

# In another terminal, set up port forwards
./k8s/port-forward.sh
```

### Manual Port Forward Commands

If you prefer to run port forwards manually:

```bash
# Airflow Webserver (port 8081 because 8080 is often occupied)
kubectl port-forward svc/airflow-webserver 8081:8080 -n equities

# Django API
kubectl port-forward svc/django 8000:8000 -n equities

# PgAdmin
kubectl port-forward svc/pgadmin 5050:8080 -n equities

# Airflow Scheduler Logs
kubectl port-forward svc/airflow-scheduler 8793:8793 -n equities

# Redis (for debugging)
kubectl port-forward svc/redis 6379:6379 -n equities
```

### Service URLs

| Service | URL | Default Port |
|---------|-----|-------------|
| App (nginx) | http://localhost | 80 |
| Airflow UI | http://localhost:8081 | 8080 |
| Django API | http://localhost:8000 | 8000 |
| PgAdmin | http://localhost:5050 | 5050 |
| Airflow Logs | http://localhost:8793 | 8793 |
| Redis | localhost:6379 | 6379 |

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

## Airflow 3.2.1 Notes

- Uses Python 3.11
- Requires Redis 4.x or 5.x
- Uses `airflow db migrate` instead of `airflow db init`
- Uses `airflow api-server` instead of `airflow webserver`
- Uses `AIRFLOW__API_AUTH__JWT_SECRET` for JWT signing (not `AIRFLOW__API__SECRET_KEY`)
- LocalExecutor uses execution API at `/execution/task-instances/<id>/run` for task state updates
- Scheduler and webserver must share the same JWT secret key (minimum 64 bytes)

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

# Restart all services
.\k8s\start-all.ps1  # Windows
# or
./k8s/start-all.sh   # Linux/Mac/Git Bash
```

## Cleanup

```bash
kubectl delete -f k8s/
```
