#!/bin/bash
# Kubernetes Startup Script for Equities Application
# Run this script to start all services in the equities namespace
# Usage: ./start-all.sh

set -e

NAMESPACE="equities"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "================================================"
echo "Starting Equities Kubernetes Cluster"
echo "================================================"

# Check if namespace exists
echo ""
echo "[Setup] Checking namespace..."
kubectl get namespace "$NAMESPACE" >/dev/null 2>&1 || {
    echo "Creating namespace $NAMESPACE..."
    kubectl apply -f "$SCRIPT_DIR/namespace.yaml"
}

# Apply secrets and config
echo ""
echo "[1/8] Applying secrets and config..."
kubectl apply -f "$SCRIPT_DIR/secrets.yaml"
kubectl apply -f "$SCRIPT_DIR/configmap.yaml"

# Apply databases
echo ""
echo "[2/8] Deploying PostgreSQL..."
kubectl apply -f "$SCRIPT_DIR/postgres.yaml"
echo "[3/8] Deploying Redis..."
kubectl apply -f "$SCRIPT_DIR/redis.yaml"

# Wait for databases to be ready
echo ""
echo "[4/8] Waiting for databases to be ready..."
kubectl wait --for=condition=available --timeout=120s deployment/postgres -n "$NAMESPACE" 2>/dev/null || true
kubectl wait --for=condition=available --timeout=120s deployment/redis -n "$NAMESPACE" 2>/dev/null || true

# Apply application services
echo ""
echo "[5/8] Deploying Django..."
kubectl apply -f "$SCRIPT_DIR/django.yaml"
echo "[6/8] Deploying Frontend..."
kubectl apply -f "$SCRIPT_DIR/frontend.yaml"
echo "[7/8] Deploying Nginx..."
kubectl apply -f "$SCRIPT_DIR/nginx.yaml"

# Apply Airflow
echo ""
echo "[8/8] Deploying Airflow..."
kubectl apply -f "$SCRIPT_DIR/airflow.yaml"

# Wait for all pods to be ready
echo ""
echo "================================================"
echo "Waiting for all pods to be ready..."
echo "================================================"

kubectl wait --for=condition=available --timeout=180s deployment/django -n "$NAMESPACE" 2>/dev/null || true
kubectl wait --for=condition=available --timeout=180s deployment/frontend -n "$NAMESPACE" 2>/dev/null || true
kubectl wait --for=condition=available --timeout=180s deployment/nginx -n "$NAMESPACE" 2>/dev/null || true
kubectl wait --for=condition=available --timeout=180s deployment/airflow-webserver -n "$NAMESPACE" 2>/dev/null || true
kubectl wait --for=condition=available --timeout=180s deployment/airflow-scheduler -n "$NAMESPACE" 2>/dev/null || true

# Run Django migrations if needed
echo ""
echo "================================================"
echo "Checking services status..."
echo "================================================"

kubectl get pods -n "$NAMESPACE"

echo ""
echo "================================================"
echo "Deployment complete!"
echo "================================================"
echo ""
echo "Run './port-forward.sh' in another terminal to access services"
echo ""
echo "Service URLs (after port-forward):"
echo "  - Airflow UI:       http://localhost:8081"
echo "  - Django API:       http://localhost:8000"
echo "  - App (nginx):      http://localhost:80"
echo "  - PgAdmin:          http://localhost:5050"
echo "================================================"