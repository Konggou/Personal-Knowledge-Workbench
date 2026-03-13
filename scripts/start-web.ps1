$root = Split-Path -Parent $PSScriptRoot
Set-Location "$root\apps\web"
corepack pnpm dev
