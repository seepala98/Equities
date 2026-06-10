#!/bin/bash
# ─────────────────────────────────────────────────────────────
# reset.sh — Nuke and rebuild the equities Kubernetes namespace
# Usage: ./reset.sh
# ─────────────────────────────────────────────────────────────

set -e

NAMESPACE="equities"
K8S_DIR="k8s"

echo "🔴 [1/6] Deleting all resources in namespace: $NAMESPACE..."
kubectl delete all --all -n $NAMESPACE --ignore-not-found

echo "🔴 [2/6] Deleting PVCs, ConfigMaps, and Secrets..."
kubectl delete pvc --all -n $NAMESPACE --ignore-not-found
kubectl delete configmap --all -n $NAMESPACE --ignore-not-found
kubectl delete secret --all -n $NAMESPACE --ignore-not-found

echo "⚡ [3/6] Force deleting any stuck/terminating pods..."
kubectl delete pods --all -n $NAMESPACE --force --grace-period=0 2>/dev/null || true

echo "⏳ [4/6] Waiting for namespace to clear..."
sleep 5

echo "✅ [5/6] Verifying namespace is clean..."
kubectl get all -n $NAMESPACE

echo "🚀 [6/6] Reapplying manifests from ./$K8S_DIR ..."
kubectl apply -f $K8S_DIR/secrets.yaml
kubectl apply -f $K8S_DIR/postgres.yaml
kubectl apply -f $K8S_DIR/airflow.yaml

echo ""
echo "✅ Done! Checking pod status..."
kubectl get pods -n $NAMESPACE --watch