$root = Split-Path -Parent $PSScriptRoot
Set-Location "$root\apps\api"

$qdrantUrl = $env:WORKBENCH_QDRANT_URL
$useReload = $true

if (-not $qdrantUrl) {
  Write-Host "WORKBENCH_QDRANT_URL not set. The API will use embedded Qdrant by default."
  $useReload = $false
} elseif ($qdrantUrl -eq "embedded") {
  $useReload = $false
}

if (-not (Test-Path ".venv")) {
  Write-Host "Python virtual environment not found at apps/api/.venv"
  Write-Host "Create one before starting the API."
  exit 1
}

if (Test-Path ".venv\Scripts\Activate.ps1") {
  . ".venv\Scripts\Activate.ps1"
}

$uvicornArgs = @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8010")
if ($useReload) {
  $uvicornArgs = @("-m", "uvicorn", "app.main:app", "--reload", "--host", "127.0.0.1", "--port", "8010")
} else {
  Write-Host "Embedded Qdrant detected. Starting API without --reload to avoid local storage lock conflicts."
}

& ".venv\Scripts\python" @uvicornArgs
