#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Clean startup script for Email Management Tool with proper port handling
.DESCRIPTION
    Kills zombie processes, sets safe environment variables, and starts the app
    on configurable ports with watchers disabled by default.

    Automatically finds safe ports if defaults are blocked by Windows.

.EXAMPLE
    .\start-clean.ps1
    # Starts with debug mode, auto-selects safe ports

.EXAMPLE
    .\start-clean.ps1 -Production -EnableWatchers
    # Production mode with IMAP watchers enabled

.EXAMPLE
    .\start-clean.ps1 -SmtpPort 1025
    # Use specific SMTP port
#>

param(
    [string]$FlaskHost = "127.0.0.1",
    [int]$FlaskPort = 5001,
    [int]$SmtpPort = 0,  # 0 = auto-select safe port
    [switch]$EnableWatchers,
    [switch]$Production,  # Use -Production to disable debug mode
    [switch]$NoSmtp  # Skip SMTP proxy entirely
)

Write-Host "`n==============================================================================" -ForegroundColor Cyan
Write-Host "  Email Management Tool - Clean Startup" -ForegroundColor Cyan
Write-Host "==============================================================================" -ForegroundColor Cyan

# Navigate to script directory
Set-Location $PSScriptRoot

# Helper function to check if port is actually available
function Test-PortAvailable {
    param([int]$Port)

    $listener = $null
    try {
        $listener = New-Object System.Net.Sockets.TcpListener([System.Net.IPAddress]::Loopback, $Port)
        $listener.Start()
        $listener.Stop()
        return $true
    } catch {
        return $false
    } finally {
        if ($listener) { $listener.Stop() }
    }
}

# Helper function to find next available port from a list of candidates
function Find-SafePort {
    param(
        [int[]]$Candidates,
        [string]$Purpose
    )

    foreach ($port in $Candidates) {
        if (Test-PortAvailable -Port $port) {
            Write-Host "  ✓ Found safe port for ${Purpose}: $port" -ForegroundColor Green
            return $port
        }
    }

    # If all candidates fail, find any available port in safe range
    for ($p = 10025; $p -lt 10100; $p++) {
        if (Test-PortAvailable -Port $p) {
            Write-Host "  ✓ Auto-selected port for ${Purpose}: $p" -ForegroundColor Yellow
            return $p
        }
    }

    throw "Could not find any available port for $Purpose. Check firewall settings."
}

# Auto-select SMTP port if not specified
if ($SmtpPort -eq 0) {
    # Try common safe SMTP ports in order of preference
    $smtpCandidates = @(2525, 1025, 2526, 3025, 10025, 1587, 2587)
    Write-Host "`n[Auto] Searching for available SMTP port..." -ForegroundColor Cyan
    $SmtpPort = Find-SafePort -Candidates $smtpCandidates -Purpose "SMTP"
}

# Verify Flask port is available
if (-not (Test-PortAvailable -Port $FlaskPort)) {
    Write-Host "`n[Auto] Flask port $FlaskPort is in use, finding alternative..." -ForegroundColor Yellow
    $flaskCandidates = @(5001, 5000, 5010, 5011, 5012, 8080, 8081)
    $FlaskPort = Find-SafePort -Candidates $flaskCandidates -Purpose "Flask"
}

# Step 1: Kill any processes using target ports
Write-Host "`n[1/6] Checking for zombie processes on ports $FlaskPort and $SmtpPort..." -ForegroundColor Yellow

$portsToClean = @($FlaskPort, $SmtpPort)
foreach ($port in $portsToClean) {
    $connections = Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue |
        Where-Object { $_.LocalPort -eq $port }

    if ($connections) {
        $pids = $connections | Select-Object -ExpandProperty OwningProcess -Unique
        foreach ($pid in $pids) {
            try {
                $process = Get-Process -Id $pid -ErrorAction SilentlyContinue
                if ($process) {
                    Write-Host "  ⚠ Killing process $($process.Name) (PID: $pid) using port $port" -ForegroundColor Red
                    Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
                    Start-Sleep -Milliseconds 500
                }
            } catch {
                Write-Host "  ✗ Failed to kill process $pid : $_" -ForegroundColor Red
            }
        }
    } else {
        Write-Host "  ✓ Port $port is free" -ForegroundColor Green
    }
}

# Kill only Email Manager Python processes (not all Python!)
$pythonProcs = Get-Process -Name python -ErrorAction SilentlyContinue | Where-Object {
    $_.CommandLine -match 'simple_app\.py'
}
if ($pythonProcs) {
    Write-Host "  ⚠ Found $(@($pythonProcs).Count) Email Manager process(es), cleaning up..." -ForegroundColor Yellow
    $pythonProcs | ForEach-Object {
        Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Milliseconds 500
} else {
    Write-Host "  ✓ No stray Email Manager processes found" -ForegroundColor Green
}

Start-Sleep -Seconds 1

# Step 2: Verify ports are actually available after cleanup
Write-Host "`n[2/6] Verifying ports are available..." -ForegroundColor Yellow
$flaskOk = Test-PortAvailable -Port $FlaskPort
$smtpOk = Test-PortAvailable -Port $SmtpPort

if (-not $flaskOk) {
    Write-Host "  ✗ Flask port $FlaskPort still blocked! Finding alternative..." -ForegroundColor Red
    $FlaskPort = Find-SafePort -Candidates @(5010, 5011, 5012, 5000, 8080) -Purpose "Flask"
}
if (-not $smtpOk) {
    Write-Host "  ✗ SMTP port $SmtpPort still blocked! Finding alternative..." -ForegroundColor Red
    $SmtpPort = Find-SafePort -Candidates @(2525, 1025, 2526, 10025) -Purpose "SMTP"
}

Write-Host "  ✓ Flask will use port: $FlaskPort" -ForegroundColor Green
Write-Host "  ✓ SMTP will use port: $SmtpPort" -ForegroundColor Green

# Step 2: Determine Python executable to use
Write-Host "`n[3/6] Checking Python environment..." -ForegroundColor Yellow

$pythonExe = $null

# Try venv first (but only if .venv.broken doesn't exist)
if ((Test-Path ".\.venv\Scripts\python.exe") -and -not (Test-Path ".\.venv.broken")) {
    $pythonExe = ".\.venv\Scripts\python.exe"
    Write-Host "  ✓ Using virtual environment Python" -ForegroundColor Green
    Write-Host "  ✓ Path: $pythonExe" -ForegroundColor Gray
} else {
    if (Test-Path ".\.venv.broken") {
        Write-Host "  ⚠ Virtual environment is broken (renamed to .venv.broken)" -ForegroundColor Yellow
    } else {
        Write-Host "  ⚠ Virtual environment not found" -ForegroundColor Yellow
    }
    Write-Host "  → Using system Python instead" -ForegroundColor Cyan

    # Find system Python
    foreach ($cmd in @("python", "py -3.11", "py")) {
        try {
            $testCmd = $cmd.Split()[0]
            $ver = & $testCmd --version 2>&1 | Out-String
            if ($LASTEXITCODE -eq 0) {
                $pythonExe = $cmd
                Write-Host "  ✓ Found system Python: $ver" -ForegroundColor Green
                break
            }
        } catch {}
    }

    if (-not $pythonExe) {
        Write-Host "  ✗ No Python found! Install Python 3.9+ or rebuild venv" -ForegroundColor Red
        Write-Host "  → To rebuild venv: python -m venv .venv" -ForegroundColor Yellow
        exit 1
    }
}

# Step 3: Set environment variables
Write-Host "`n[4/6] Configuring environment..." -ForegroundColor Yellow

$env:FLASK_HOST = $FlaskHost
$env:FLASK_PORT = $FlaskPort.ToString()
$env:SMTP_PROXY_HOST = $FlaskHost
$env:SMTP_PROXY_PORT = $SmtpPort.ToString()
$env:FLASK_SECRET_KEY = "dev-secret-change-me-0123456789abcdef0123456789abcdef"
$env:ENABLE_WATCHERS = if ($EnableWatchers) { "1" } else { "0" }
$env:FLASK_DEBUG = if ($Production) { "0" } else { "1" }  # Debug ON by default
$env:IMAP_ONLY = if ($NoSmtp) { "1" } else { "0" }

Write-Host "  • FLASK_HOST       = $env:FLASK_HOST" -ForegroundColor Cyan
Write-Host "  • FLASK_PORT       = $env:FLASK_PORT" -ForegroundColor Cyan
Write-Host "  • SMTP_PROXY_PORT  = $env:SMTP_PROXY_PORT" -ForegroundColor Cyan
Write-Host "  • ENABLE_WATCHERS  = $env:ENABLE_WATCHERS" -ForegroundColor Cyan
Write-Host "  • FLASK_DEBUG      = $env:FLASK_DEBUG" -ForegroundColor Cyan
Write-Host "  • IMAP_ONLY        = $env:IMAP_ONLY" -ForegroundColor Cyan

if ($Production -and $env:FLASK_SECRET_KEY -like "*dev-secret*") {
    Write-Host "`n  ⚠ WARNING: Production mode requires a strong SECRET_KEY!" -ForegroundColor Red
    Write-Host "  Set FLASK_SECRET_KEY environment variable before running:" -ForegroundColor Yellow
    Write-Host '  $env:FLASK_SECRET_KEY = "your-64-character-random-string"' -ForegroundColor Yellow
    Write-Host "  Or run without -Production flag for development mode" -ForegroundColor Yellow
    exit 1
}

# Step 4: Verify database exists
Write-Host "`n[5/6] Checking database..." -ForegroundColor Yellow

if (Test-Path ".\email_manager.db") {
    Write-Host "  ✓ Database found: email_manager.db" -ForegroundColor Green
} else {
    Write-Host "  ⚠ Database will be created on first run" -ForegroundColor Yellow
}

# Step 5: Start the application
Write-Host "`n[6/6] Starting application..." -ForegroundColor Yellow
Write-Host "`n==============================================================================" -ForegroundColor Cyan
Write-Host ""

# Save port info to file for easy reference
$portInfo = @"
# Auto-generated port configuration - $(Get-Date)
Flask Dashboard: http://${FlaskHost}:${FlaskPort}
SMTP Proxy: ${FlaskHost}:${SmtpPort}
Login: admin / admin123

Environment:
- FLASK_DEBUG=$($env:FLASK_DEBUG)
- ENABLE_WATCHERS=$($env:ENABLE_WATCHERS)
- IMAP_ONLY=$($env:IMAP_ONLY)
- Python: $pythonExe
"@
$portInfo | Out-File -FilePath ".last-ports.txt" -Encoding UTF8

Write-Host "`n[Starting] $pythonExe .\simple_app.py --host $FlaskHost --port $FlaskPort --smtp-port $SmtpPort" -ForegroundColor Cyan
Write-Host ""

# Execute with explicit Python and capture exit code
& $pythonExe .\simple_app.py --host $FlaskHost --port $FlaskPort --smtp-port $SmtpPort

if ($LASTEXITCODE -ne 0 -and $null -ne $LASTEXITCODE) {
    Write-Host ""
    Write-Host "═══════════════════════════════════════════════════════════════════" -ForegroundColor Red
    Write-Host "  ✗ Application exited with error code: $LASTEXITCODE" -ForegroundColor Red
    Write-Host "═══════════════════════════════════════════════════════════════════" -ForegroundColor Red
    Write-Host ""
    Write-Host "Common issues:" -ForegroundColor Yellow
    Write-Host "  • Port $FlaskPort or $SmtpPort already in use" -ForegroundColor Gray
    Write-Host "  • Missing dependencies - run: pip install -r requirements.txt" -ForegroundColor Gray
    Write-Host "  • Corrupted database - check logs/app_*.log" -ForegroundColor Gray
    Write-Host ""
    exit $LASTEXITCODE
}

# Note: The script will continue running the Flask app until Ctrl+C
