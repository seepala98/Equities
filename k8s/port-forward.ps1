# Port Forward Script for Equities Kubernetes Cluster
# Run this script in PowerShell to enable access to all services
# Usage: .\port-forward.ps1

$ErrorActionPreference = "Stop"
$NAMESPACE = "equities"

Write-Host "================================================" -ForegroundColor Cyan
Write-Host "Starting port forwards for equities namespace" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan

# Function to start a port-forward in background
function Start-PortForward {
    param(
        [string]$Service,
        [string]$LocalPort,
        [string]$RemotePort
    )
    $jobName = "PortForward-$Service"
    Write-Host "[$Service] Starting on localhost:$LocalPort..." -ForegroundColor Yellow

    $job = Start-Job -ScriptBlock {
        param($svc, $lp, $rp, $ns)
        kubectl port-forward svc/$svc ${lp}:${rp} -n $ns
    } -ArgumentList $Service, $LocalPort, $RemotePort, $NAMESPACE

    return $job
}

# Start all port forwards
$jobs = @()

# Airflow Webserver (port 8081 because 8080 may be occupied by Docker Desktop)
$jobs += Start-PortForward -Service "airflow-webserver" -LocalPort 8081 -RemotePort 8080

# Django API
$jobs += Start-PortForward -Service "django" -LocalPort 8000 -RemotePort 8000

# PgAdmin
$jobs += Start-PortForward -Service "pgadmin" -LocalPort 5050 -RemotePort 8080

# Airflow Scheduler (log server on port 8793)
$jobs += Start-PortForward -Service "airflow-scheduler" -LocalPort 8793 -RemotePort 8793

# Redis (for debugging if needed)
$jobs += Start-PortForward -Service "redis" -LocalPort 6379 -RemotePort 6379

Write-Host ""
Write-Host "================================================" -ForegroundColor Green
Write-Host "All port forwards started!" -ForegroundColor Green
Write-Host "================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Access URLs:" -ForegroundColor White
Write-Host "  - Airflow UI:       http://localhost:8081" -ForegroundColor White
Write-Host "  - Django API:       http://localhost:8000" -ForegroundColor White
Write-Host "  - PgAdmin:          http://localhost:5050" -ForegroundColor White
Write-Host "  - Airflow Logs:     http://localhost:8793" -ForegroundColor White
Write-Host "  - Redis:            localhost:6379" -ForegroundColor White
Write-Host ""
Write-Host "Press Ctrl+C to stop all port forwards" -ForegroundColor Yellow
Write-Host "================================================" -ForegroundColor Cyan

# Wait for all jobs
try {
    Wait-Job $jobs | Out-Null
} catch {
    Write-Host "`nStopping port forwards..." -ForegroundColor Yellow
    Stop-Job $jobs
    Remove-Job $jobs
}

# Cleanup on Ctrl+C
Write-Host ""