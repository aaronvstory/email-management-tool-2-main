# scripts/launcher.ps1
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

# -------- Config defaults (editable in menu) --------
$cfg = [ordered]@{
  FlaskHost     = "127.0.0.1"
  FlaskPort     = 5010
  SmtpPort      = 1025
  Headless      = $false           # default headed
  Username      = "admin"
  Password      = "admin123"
  BaseUrl       = ""
  VenvDir       = ".\.venv"
  PyExe         = ""
  PlaywrightBin = ""               # auto-resolved
}

function Resolve-Python {
  if (Test-Path "$($cfg.VenvDir)\Scripts\python.exe") {
    $cfg.PyExe = Resolve-Path "$($cfg.VenvDir)\Scripts\python.exe"
    return
  }
  $py = (Get-Command py -ErrorAction SilentlyContinue)
  if ($py) { $cfg.PyExe = "$($py.Source) -3"; return }
  $python = (Get-Command python -ErrorAction SilentlyContinue)
  if ($python) { $cfg.PyExe = $python.Source; return }
  throw "Python not found. Install Python 3.9+."
}

function Ensure-Venv {
  if (-not (Test-Path "$($cfg.VenvDir)\Scripts\python.exe")) {
    Write-Host "Creating venv at $($cfg.VenvDir) ..." -ForegroundColor Yellow
    & py -3 -m venv $cfg.VenvDir 2>$null; if ($LASTEXITCODE) { & python -m venv $cfg.VenvDir }
  }
  Resolve-Python
}

function Install-Requirements {
  if (-not (Test-Path "requirements.txt")) { Write-Host "requirements.txt not found, skip." -ForegroundColor Yellow; return }
  Write-Host "Installing deps..." -ForegroundColor Cyan
  & $cfg.PyExe -m pip install --upgrade pip setuptools wheel
  & $cfg.PyExe -m pip install -r requirements.txt
}

function Start-App {
  $env:FLASK_ENV="development"
  $env:FLASK_DEBUG="1"
  $env:PYTHONIOENCODING="utf-8"

  $args = @("--host", $cfg.FlaskHost, "--port", $cfg.FlaskPort.ToString(), "--smtp-port", $cfg.SmtpPort.ToString())
  Write-Host "Starting app: simple_app.py $($args -join ' ')" -ForegroundColor Green
  Start-Process -FilePath $cfg.PyExe -ArgumentList @("simple_app.py") + $args -WindowStyle Normal
}

function Wait-Healthy {
  param([int]$TimeoutSec=30)
  $base = if ($cfg.BaseUrl) { $cfg.BaseUrl } else { "http://$($cfg.FlaskHost):$($cfg.FlaskPort)" }
  $deadline = (Get-Date).AddSeconds($TimeoutSec)
  Write-Host "Waiting for $base/healthz ..." -ForegroundColor Cyan
  while ((Get-Date) -lt $deadline) {
    try {
      $r = Invoke-WebRequest "$base/healthz" -UseBasicParsing -TimeoutSec 2
      if ($r.StatusCode -eq 200) { Write-Host "OK" -ForegroundColor Green; return $true }
    } catch {}
    Start-Sleep -Seconds 1
  }
  Write-Host "Health check timeout (may still be starting)" -ForegroundColor Yellow
  return $false
}

function Open-Browser {
  $base = if ($cfg.BaseUrl) { $cfg.BaseUrl } else { "http://$($cfg.FlaskHost):$($cfg.FlaskPort)" }
  Start-Process $base
}

function Login-And-Print {
  $base = if ($cfg.BaseUrl) { $cfg.BaseUrl } else { "http://$($cfg.FlaskHost):$($cfg.FlaskPort)" }
  Write-Host "Logging in to $base ..." -ForegroundColor Cyan
  $lp = Invoke-WebRequest "$base/login" -UseBasicParsing -SessionVariable sess
  $csrf = ([regex]'name="csrf_token"\s+value="([^"]+)"').Match($lp.Content).Groups[1].Value
  if (-not $csrf) { throw "CSRF not found on /login" }
  $body = "username=$($cfg.Username)&password=$($cfg.Password)&csrf_token=$csrf"
  Invoke-WebRequest "$base/login" -UseBasicParsing -WebSession $sess -Method POST -ContentType "application/x-www-form-urlencoded" -Body $body | Out-Null
  Write-Host "Logged in." -ForegroundColor Green
  $h = Invoke-WebRequest "$base/healthz" -UseBasicParsing -WebSession $sess
  Write-Host "Healthz:" -ForegroundColor DarkGray
  $h.Content | Write-Output
}

function Ensure-Playwright {
  try {
    & $cfg.PyExe -c "import playwright" 2>$null
  } catch {
    & $cfg.PyExe -m pip install playwright
    & $cfg.PyExe -m playwright install chromium
  }
}

function Run-Screenshot-Scan {
  Ensure-Playwright
  $env:BASE_URI = if ($cfg.BaseUrl) { $cfg.BaseUrl } else { "http://$($cfg.FlaskHost):$($cfg.FlaskPort)" }
  $env:ET_USER  = $cfg.Username
  $env:ET_PASS  = $cfg.Password
  $env:SHOT_HEADLESS = if ($cfg.Headless) { "1" } else { "0" }
  Write-Host "Running site scan + screenshots on $env:BASE_URI ..." -ForegroundColor Cyan
  & $cfg.PyExe ".\scripts\shot.py"
}

function Kill-Ports {
  param([int[]]$Ports)
  foreach ($p in $Ports) {
    $lines = netstat -ano | Select-String ":$p\s"
    if ($lines) {
      $pids = $lines -replace '.*\s+(\d+)$', '$1' | Select-Object -Unique
      foreach ($pid in $pids) {
        try { Stop-Process -Id $pid -Force -ErrorAction Stop; Write-Host "Killed PID $pid on :$p" -ForegroundColor Yellow } catch {}
      }
    }
  }
}

function Show-Menu {
  Clear-Host
  Write-Host ""
  Write-Host "============================================================" -ForegroundColor Green
  Write-Host "   EMAIL MANAGEMENT TOOL - QUICK LAUNCHER" -ForegroundColor Green
  Write-Host "============================================================" -ForegroundColor Green
  Write-Host ""
  $url = if ($cfg.BaseUrl) { $cfg.BaseUrl } else { "http://$($cfg.FlaskHost):$($cfg.FlaskPort)" }
  Write-Host ("  Base URL     : {0}" -f $url)
  Write-Host ("  Flask Host   : {0}" -f $cfg.FlaskHost)
  Write-Host ("  Flask Port   : {0}" -f $cfg.FlaskPort)
  Write-Host ("  SMTP Port    : {0}" -f $cfg.SmtpPort)
  Write-Host ("  Headless     : {0}" -f ($cfg.Headless ? "Yes" : "No"))
  Write-Host ("  Login        : {0} / {1}" -f $cfg.Username, $cfg.Password)
  Write-Host ""
  Write-Host "  [1] Clean start (kill ports, ensure venv, deps, start app)"
  Write-Host "  [2] Wait for health + open browser"
  Write-Host "  [3] Login & print /healthz JSON"
  Write-Host "  [4] Scan site + take screenshots (Playwright)  "
  Write-Host "  [5] Toggle headless (current: $($cfg.Headless))"
  Write-Host "  [6] Configure (host/port/login)"
  Write-Host "  [7] Stop ports (Flask+SMTP)"
  Write-Host "  [0] Exit"
  Write-Host ""
}

function Configure-Menu {
  Write-Host ""
  $h = Read-Host "Flask host [$($cfg.FlaskHost)]"
  if ($h) { $cfg.FlaskHost = $h }
  $p = Read-Host "Flask port [$($cfg.FlaskPort)]"
  if ($p) { $cfg.FlaskPort = [int]$p }
  $sp = Read-Host "SMTP port [$($cfg.SmtpPort)]"
  if ($sp) { $cfg.SmtpPort = [int]$sp }
  $u = Read-Host "Username [$($cfg.Username)]"
  if ($u) { $cfg.Username = $u }
  $pw = Read-Host "Password [$($cfg.Password)]"
  if ($pw) { $cfg.Password = $pw }
  $bu = Read-Host "Base URL (override) [$($cfg.BaseUrl)]"
  if ($bu -ne $null) { $cfg.BaseUrl = $bu }
}

# -------- Main loop --------
while ($true) {
  Show-Menu
  $choice = Read-Host "Choose"
  switch ($choice) {
    '1' {
      try {
        Kill-Ports -Ports @($cfg.FlaskPort, $cfg.SmtpPort)
        Ensure-Venv
        Install-Requirements
        Start-App
        Write-Host "Started." -ForegroundColor Green
      } catch {
        Write-Host "[ERROR] $($_.Exception.Message)" -ForegroundColor Red
      }
      Pause
    }
    '2' {
      if (Wait-Healthy -TimeoutSec 30) { Open-Browser }
      Pause
    }
    '3' {
      try {
        if (-not (Wait-Healthy -TimeoutSec 5)) { Write-Host "App not healthy yet." -ForegroundColor Yellow }
        Login-And-Print
      } catch {
        Write-Host "[ERROR] $($_.Exception.Message)" -ForegroundColor Red
      }
      Pause
    }
    '4' {
      try {
        if (-not (Wait-Healthy -TimeoutSec 5)) { Write-Host "App not healthy yet." -ForegroundColor Yellow }
        Run-Screenshot-Scan
      } catch {
        Write-Host "[ERROR] $($_.Exception.Message)" -ForegroundColor Red
      }
      Pause
    }
    '5' {
      $cfg.Headless = -not $cfg.Headless
    }
    '6' {
      Configure-Menu
    }
    '7' {
      Kill-Ports -Ports @($cfg.FlaskPort, $cfg.SmtpPort)
      Pause
    }
    '0' { break }
    default { }
  }
}
