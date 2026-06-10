# Kubernetes Startup Script for Equities Application
# Run this script in PowerShell to start all services in the equities namespace
# Usage: .\start-all.ps1

param(
    [switch]$SkipBuild,
    [switch]$SkipMigrate
)

$ErrorActionPreference = "Stop"
$NAMESPACE = "equities"
$SCRIPT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "================================================" -ForegroundColor Cyan
Write-Host "Starting Equities Kubernetes Cluster" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan

# Check if namespace exists
Write-Host "`n[Setup] Checking namespace..." -ForegroundColor Yellow
$nsCheck = kubectl get namespace $NAMESPACE 2>$null
if (-not $nsCheck) {
    Write-Host "Creating namespace $NAMESPACE..." -ForegroundColor Yellow
    kubectl apply -f "$SCRIPT_DIR\namespace.yaml"
}

# Build Docker images if not skipped
if (-not $SkipBuild) {
    Write-Host "`n[Build] Building Docker images..." -ForegroundColor Yellow

    Write-Host "  Building web image..." -ForegroundColor Gray
    docker build -t equities/web:latest ./

    Write-Host "  Building frontend image..." -ForegroundColor Gray
    docker build -t equities/frontend:latest ./frontend

    Write-Host "  Building airflow image..." -ForegroundColor Gray
    docker build -t equities/airflow:latest -f ./web/airflow/Dockerfile.airflow ./web
}

# Apply secrets and config
Write-Host "`n[Config] Applying secrets and config..." -ForegroundColor Yellow
kubectl apply -f "$SCRIPT_DIR\secrets.yaml"
kubectl apply -f "$SCRIPT_DIR\configmap.yaml"

# Apply databases
Write-Host "`n[Database] Deploying PostgreSQL..." -ForegroundColor Yellow
kubectl apply -f "$SCRIPT_DIR\postgres.yaml"
Write-Host "[Database] Deploying Redis..." -ForegroundColor Yellow
kubectl apply -f "$SCRIPT_DIR\redis.yaml"

# Wait for databases to be ready
Write-Host "`n[Database] Waiting for databases to be ready..." -ForegroundColor Yellow
Start-Sleep -Seconds 10

# Apply application services
Write-Host "`n[App] Deploying Django..." -ForegroundColor Yellow
kubectl apply -f "$SCRIPT_DIR\django.yaml"
Write-Host "[App] Deploying Frontend..." -ForegroundColor Yellow
kubectl apply -f "$SCRIPT_DIR\frontend.yaml"
Write-Host "[App] Deploying Nginx..." -ForegroundColor Yellow
kubectl apply -f "$SCRIPT_DIR\nginx.yaml"

# Apply Airflow
Write-Host "`n[Airflow] Deploying Airflow..." -ForegroundColor Yellow
kubectl apply -f "$SCRIPT_DIR\airflow.yaml"

# Wait for all pods to be ready
Write-Host "`n================================================" -ForegroundColor Cyan
Write-Host "Waiting for all pods to be ready..." -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan

$startTime = Get-Date
$timeout = 180

# Wait for deployments
$deployments = @("django", "frontend", "nginx", "airflow-webserver", "airflow-scheduler")
foreach ($deploy in $deployments) {
    Write-Host "Waiting for $deploy..." -ForegroundColor Gray
    $ready = $false
    while (-not $ready -and ((Get-Date) - $startTime).TotalSeconds -lt $timeout) {
        $status = kubectl get deployment $deploy -n $NAMESPACE 2>$null | Select-Object -Last 1
        if ($status -match "(\d+)/(\d+)" -and $Matches[1] -eq $Matches[2]) {
            $ready = $true
        } else {
            Start-Sleep -Seconds 5
        }
    }
}

# Run migrations if not skipped
if (-not $SkipMigrate) {
    Write-Host "`n[Database] Running Django migrations..." -ForegroundColor Yellow
    kubectl exec -n $NAMESPACE deployment/django -- python manage.py migrate 2>$null
}

# Show status
Write-Host "`n================================================" -ForegroundColor Cyan
Write-Host "Deployment Status" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
kubectl get pods -n $NAMESPACE

Write-Host "`n================================================" -ForegroundColor Green
Write-Host "Deployment complete!" -ForegroundColor Green
Write-Host "================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Run '.\port-forward.ps1' in another PowerShell window to access services" -ForegroundColor Yellow
Write-Host ""
Write-Host "Service URLs (after port-forward):" -ForegroundColor White
Write-Host "  - Airflow UI:       http://localhost:8081" -ForegroundColor White
Write-Host "  - Django API:       http://localhost:8000" -ForegroundColor White
Write-Host "  - App (nginx):      http://localhost:80" -ForegroundColor White
Write-Host "  - PgAdmin:          http://localhost:5050" -ForegroundColor White
Write-Host "================================================" -ForegroundColor Cyan