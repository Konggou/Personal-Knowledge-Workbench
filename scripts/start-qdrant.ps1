$root = Split-Path -Parent $PSScriptRoot
$storagePath = "$root\data\qdrant"

if (-not (Test-Path $storagePath)) {
  New-Item -ItemType Directory -Path $storagePath | Out-Null
}

$qdrantBin = $env:WORKBENCH_QDRANT_BIN
if (-not $qdrantBin) {
  $command = Get-Command qdrant -ErrorAction SilentlyContinue
  if ($command) {
    $qdrantBin = $command.Source
  }
}

if (-not $qdrantBin) {
  Write-Host "Qdrant binary not found."
  Write-Host "No action is required for the default embedded mode."
  Write-Host "Only install or start an external Qdrant binary if you want WORKBENCH_QDRANT_URL to point to a standalone server."
  Write-Host "Set WORKBENCH_QDRANT_BIN to the qdrant executable path, or add qdrant to PATH, then rerun this script."
  exit 0
}

Write-Host "Starting Qdrant with storage path: $storagePath"
& $qdrantBin --storage-path $storagePath
