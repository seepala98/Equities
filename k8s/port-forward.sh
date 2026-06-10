#!/bin/bash
# Port Forward Script for Equities Kubernetes Cluster
# Run this script in a terminal to enable access to all services
# Usage: ./port-forward.sh

set -e

NAMESPACE="equities"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Starting port forwards for equities namespace..."
echo "================================================"

cleanup() {
    echo ""
    echo "Cleaning up port forwards..."
    kill $AIRFLOW_PID $DJANGO_PID $PGADMIN_PID $SCHEDULER_PID $REDIS_PID 2>/dev/null || true
    echo "Port forwards stopped."
    exit 0
}

trap cleanup SIGINT SIGTERM

# Airflow Webserver (8081 because 8080 may be occupied)
echo "[1/5] Starting Airflow on localhost:8081..."
kubectl port-forward svc/airflow-webserver 8081:8080 -n "$NAMESPACE" &
AIRFLOW_PID=$!

# Django API
echo "[2/5] Starting Django API on localhost:8000..."
kubectl port-forward svc/django 8000:8000 -n "$NAMESPACE" &
DJANGO_PID=$!

# PgAdmin
echo "[3/5] Starting PgAdmin on localhost:5050..."
kubectl port-forward svc/pgadmin 5050:8080 -n "$NAMESPACE" &
PGADMIN_PID=$!

# Airflow Scheduler (log server on port 8793)
echo "[4/5] Starting Airflow Scheduler logs on localhost:8793..."
kubectl port-forward svc/airflow-scheduler 8793:8793 -n "$NAMESPACE" &
SCHEDULER_PID=$!

# Redis (for debugging if needed)
echo "[5/5] Starting Redis on localhost:6379..."
kubectl port-forward svc/redis 6379:6379 -n "$NAMESPACE" &
REDIS_PID=$!

echo ""
echo "================================================"
echo "All port forwards started!"
echo ""
echo "Access URLs:"
echo "  - Airflow UI:       http://localhost:8081"
echo "  - Django API:       http://localhost:8000"
echo "  - PgAdmin:          http://localhost:5050"
echo "  - Airflow Logs:     http://localhost:8793"
echo "  - Redis:            localhost:6379"
echo ""
echo "Press Ctrl+C to stop all port forwards"
echo "================================================"

# Wait for all background jobs
wait