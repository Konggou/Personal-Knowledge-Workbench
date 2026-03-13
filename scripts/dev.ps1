Write-Host "Starting Personal Knowledge Workbench v1 development environment..."
Write-Host "This script opens API and Web in separate PowerShell windows."
Write-Host "The API now defaults to embedded Qdrant, so a separate Qdrant service is optional."

$root = Split-Path -Parent $PSScriptRoot

Start-Process powershell -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-File", "`"$root\scripts\start-api.ps1`""
Start-Sleep -Seconds 1
Start-Process powershell -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-File", "`"$root\scripts\start-web.ps1`""
Write-Host "If you want to run an external Qdrant server, start scripts/start-qdrant.ps1 manually and set WORKBENCH_QDRANT_URL."
