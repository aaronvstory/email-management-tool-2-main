#!/usr/bin/env pwsh
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

Write-Host '🔐 Email Management Tool - Security Setup (PowerShell)' -ForegroundColor Cyan

Set-Location (Split-Path -Parent $MyInvocation.MyCommand.Path)

if (-not (Test-Path .env)) {
  Write-Host 'Creating .env from .env.example...'
  Copy-Item .env.example .env
} else {
  Write-Host '✓ .env file exists'
}

function New-SecretHex {
  $bytes = New-Object byte[] 32
  $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
  try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
  ($bytes | ForEach-Object { $_.ToString('x2') }) -join ''
}

$envPath = Join-Path (Get-Location) '.env'
$envContent = Get-Content $envPath -Raw
function Test-WeakSecret([string]$s) {
  if ([string]::IsNullOrWhiteSpace($s)) { return $true }
  if ($s.Length -lt 32) { return $true }
  $weakList = @(
    'dev-secret-change-in-production',
    'change-this-to-a-random-secret-key',
    'your-secret-here',
    'secret',
    'password',
    'flask-secret-key'
  )
  if ($weakList -contains $s) { return $true }
  return $false
}

$currentSecret = $null
if ($envContent -match '(?m)^FLASK_SECRET_KEY=(.*)$') {
  $currentSecret = $Matches[1].Trim()
}

if (-not $currentSecret -or (Test-WeakSecret $currentSecret)) {
  if ($currentSecret) {
    Write-Host 'Weak or placeholder FLASK_SECRET_KEY detected – regenerating...' -ForegroundColor Yellow
  } else {
    Write-Host 'Generating FLASK_SECRET_KEY...'
  }
  $secret = New-SecretHex
  if ($envContent -match '(?m)^FLASK_SECRET_KEY=') {
    ($envContent -replace '(?m)^FLASK_SECRET_KEY=.*$', "FLASK_SECRET_KEY=$secret") | Set-Content $envPath -NoNewline
  } else {
    Add-Content $envPath "`nFLASK_SECRET_KEY=$secret"
  }
  Write-Host '✓ SECRET_KEY generated'
} else {
  Write-Host '✓ SECRET_KEY already configured (looks strong)'
}

Write-Host ''
Write-Host '✅ Security setup complete!'
Write-Host ''
Write-Host 'Next steps:'
Write-Host '  1) Review .env and adjust values if needed'
Write-Host '  2) Start app: python simple_app.py'
Write-Host '  3) Run validation: .\validate_security.sh (Git Bash) or python -m scripts.validate_security'
