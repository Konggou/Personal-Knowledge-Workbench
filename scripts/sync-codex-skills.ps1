param(
  [string]$RepoUrl = "https://github.com/Konggou/my_skills.git",
  [string]$Ref = "main",
  [string]$Destination = "$env:USERPROFILE\.codex\skills",
  [switch]$KeepTemp
)

$ErrorActionPreference = "Stop"

function Get-SkillDirectories {
  param([string]$Root)

  Get-ChildItem -Path $Root -Recurse -Filter "SKILL.md" -File |
    Where-Object { $_.Directory.Name -ne "template" } |
    ForEach-Object { $_.Directory } |
    Group-Object FullName |
    ForEach-Object { $_.Group[0] } |
    Sort-Object Name
}

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
  Write-Error "git is required but was not found in PATH."
}

if (-not (Test-Path $Destination)) {
  New-Item -ItemType Directory -Path $Destination | Out-Null
}

$tempRoot = Join-Path $env:TEMP ("codex-skills-sync-" + [guid]::NewGuid().ToString())
$backupRoot = Join-Path $env:TEMP ("codex-skills-backup-" + (Get-Date -Format "yyyyMMdd-HHmmss"))

Write-Host "Cloning $RepoUrl ..."
git clone --depth 1 --branch $Ref --recurse-submodules $RepoUrl $tempRoot | Out-Host

$skills = Get-SkillDirectories -Root $tempRoot
if (-not $skills) {
  Write-Error "No skills with SKILL.md were found in $RepoUrl."
}

New-Item -ItemType Directory -Path $backupRoot | Out-Null

$created = New-Object System.Collections.Generic.List[string]
$updated = New-Object System.Collections.Generic.List[string]

foreach ($skill in $skills) {
  $name = $skill.Name
  $target = Join-Path $Destination $name

  if (Test-Path $target) {
    $backupPath = Join-Path $backupRoot $name
    Copy-Item -Recurse -Force $target $backupPath
    Remove-Item -Recurse -Force $target
    $updated.Add($name) | Out-Null
  } else {
    $created.Add($name) | Out-Null
  }

  Copy-Item -Recurse -Force $skill.FullName $target
}

Write-Host ""
Write-Host "Skills sync complete."
Write-Host "Destination: $Destination"
Write-Host "Created: $($created.Count)"
if ($created.Count -gt 0) {
  Write-Host ("  " + ($created -join ", "))
}
Write-Host "Updated: $($updated.Count)"
if ($updated.Count -gt 0) {
  Write-Host ("  " + ($updated -join ", "))
}
Write-Host "Backup: $backupRoot"

if (-not $KeepTemp) {
  Remove-Item -Recurse -Force $tempRoot
} else {
  Write-Host "Temporary clone kept at: $tempRoot"
}

Write-Host "Restart Codex to pick up new skills."
