#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Email Tool - Simple command wrapper for common operations

.DESCRIPTION
    Bulletproof helper that handles port conflicts, session management,
    and CSRF tokens automatically. Never fight PowerShell gotchas again.

.EXAMPLE
    .\scripts\et.ps1 start
    .\scripts\et.ps1 login
    .\scripts\et.ps1 get -path /healthz
    .\scripts\et.ps1 post -path /api/accounts/1/test
    .\scripts\et.ps1 stop

.EXAMPLE
    # Start with watchers enabled
    .\scripts\et.ps1 start -watchers 1

.EXAMPLE
    # Start on custom ports
    .\scripts\et.ps1 start -port 8080 -smtp 1025
#>

param(
  [Parameter(Position=0)]
  [ValidateSet('start','login','get','post','stop','base','help')]
  [string]$cmd = 'start',

  [Parameter(Position=1)]
  [string]$path = '/',

  [string]$user = 'admin',
  [string]$pass = 'admin123',
  [int]$port = 5010,
  [int]$smtp = 2525,
  [int]$watchers = 0,
  [int]$debugMode = 1,
  [string]$base = 'http://127.0.0.1:5010',
  [hashtable]$json = @{}
)

$ErrorActionPreference = 'Stop'

# Navigate to repo root (scripts folder -> parent)
$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptPath
Set-Location $repoRoot

function Kill-Port {
    param([int[]]$ports)

    Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue |
        Where-Object { $_.LocalPort -in $ports } |
        Select-Object -ExpandProperty OwningProcess -Unique |
        ForEach-Object {
            try {
                Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue
            } catch {}
        }
}

function Activate-Venv {
    if (!(Test-Path ".\.venv\Scripts\Activate.ps1")) {
        Write-Error "Virtual environment not found at .\.venv\Scripts\Activate.ps1"
        Write-Host "Run: python -m venv .venv" -ForegroundColor Yellow
        Write-Host "Then: .\.venv\Scripts\Activate.ps1" -ForegroundColor Yellow
        Write-Host "Then: pip install -r requirements.txt" -ForegroundColor Yellow
        throw "Missing virtual environment"
    }
    & ".\.venv\Scripts\Activate.ps1"
}

switch ($cmd) {
    'start' {
        Write-Host "`n=== Starting Email Tool ===" -ForegroundColor Cyan

        # Activate venv
        Write-Host "Activating virtual environment..." -ForegroundColor Yellow
        Activate-Venv

        # Kill zombie processes
        Write-Host "Cleaning up ports: 5001, $port, 8587, $smtp..." -ForegroundColor Yellow
        Kill-Port @(5001, $port, 8587, $smtp)
        Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue

        # Set environment
        $env:FLASK_HOST       = '127.0.0.1'
        $env:FLASK_PORT       = "$port"
        $env:SMTP_PROXY_PORT  = "$smtp"
        $env:ENABLE_WATCHERS  = "$watchers"
        $env:FLASK_DEBUG      = "$debugMode"
        $env:FLASK_SECRET_KEY = "dev-secret-change-me-0123456789abcdef0123456789abcdef"

        Write-Host "`n✓ Configuration:" -ForegroundColor Green
        Write-Host "  Flask:    http://127.0.0.1:$port" -ForegroundColor Gray
        Write-Host "  SMTP:     127.0.0.1:$smtp" -ForegroundColor Gray
        Write-Host "  Watchers: $(if($watchers -eq 1){'ON'}else{'OFF'})" -ForegroundColor Gray
        Write-Host "  Debug:    $(if($debugMode -eq 1){'ON'}else{'OFF'})" -ForegroundColor Gray
        Write-Host ""

        # Start app
        python .\simple_app.py
    }

    'stop' {
        Write-Host "`n=== Stopping Email Tool ===" -ForegroundColor Cyan
        Kill-Port @(5001, 5010, 5011, 5012, 2525, 1025, 8587, 8599)
        Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
        Write-Host "✓ Stopped all app processes and cleaned up ports" -ForegroundColor Green
    }

    'base' {
        $env:ET_BASE = $base.TrimEnd('/')
        Write-Host "✓ Base URL set to: $env:ET_BASE" -ForegroundColor Green
        Write-Host "  (Saved for this session only)" -ForegroundColor Gray
    }

    'login' {
        $baseUrl = if ($env:ET_BASE) { $env:ET_BASE } else { $base.TrimEnd('/') }

        Write-Host "`n=== Logging in to $baseUrl ===" -ForegroundColor Cyan

        try {
            # Get login page and form CSRF token
            $loginResp = Invoke-WebRequest "$baseUrl/login" -UseBasicParsing -SessionVariable sess
            $csrfForm = ($loginResp.Content | Select-String 'name="csrf_token" value="([^"]+)"').Matches[0].Groups[1].Value

            if (-not $csrfForm) {
                throw "Failed to extract form CSRF token"
            }

            # Login
            $body = "username=$user&password=$pass&csrf_token=$csrfForm"
            $loginPost = Invoke-WebRequest "$baseUrl/login" `
                -Method POST `
                -ContentType "application/x-www-form-urlencoded" `
                -Body $body `
                -WebSession $sess `
                -UseBasicParsing

            # Get meta CSRF token (NOTE: Not using $home - it's a PowerShell reserved variable!)
            $dashboardResp = Invoke-WebRequest "$baseUrl/dashboard" -WebSession $sess -UseBasicParsing
            $csrfMeta = ($dashboardResp.Content | Select-String 'meta name="csrf-token" content="([^"]+)"').Matches[0].Groups[1].Value

            if (-not $csrfMeta) {
                throw "Failed to extract meta CSRF token"
            }

            # Store in global scope so other commands can use it
            Set-Variable -Scope Global -Name ET_SESSION -Value $sess
            Set-Variable -Scope Global -Name ET_CSRF -Value $csrfMeta

            Write-Host "✓ Logged in successfully" -ForegroundColor Green
            Write-Host "  Session and CSRF token captured" -ForegroundColor Gray
        }
        catch {
            Write-Error "Login failed: $_"
            throw
        }
    }

    'get' {
        $baseUrl = if ($env:ET_BASE) { $env:ET_BASE } else { $base.TrimEnd('/') }

        if (-not $global:ET_SESSION) {
            Write-Error "Not logged in. Run: .\scripts\et.ps1 login"
            throw "Not authenticated"
        }

        Write-Host "GET $baseUrl$path" -ForegroundColor Gray
        Invoke-WebRequest "$baseUrl$path" -WebSession $global:ET_SESSION -UseBasicParsing
    }

    'post' {
        $baseUrl = if ($env:ET_BASE) { $env:ET_BASE } else { $base.TrimEnd('/') }

        if (-not $global:ET_SESSION) {
            Write-Error "Not logged in. Run: .\scripts\et.ps1 login"
            throw "Not authenticated"
        }

        if (-not $global:ET_CSRF) {
            Write-Error "CSRF token missing. Run: .\scripts\et.ps1 login"
            throw "Missing CSRF token"
        }

        $headers = @{
            'X-CSRFToken' = $global:ET_CSRF
            'Content-Type' = 'application/json'
        }

        $body = if ($json.Count -gt 0) {
            ($json | ConvertTo-Json -Depth 6)
        } else {
            '{}'
        }

        Write-Host "POST $baseUrl$path" -ForegroundColor Gray
        Invoke-WebRequest "$baseUrl$path" `
            -Method POST `
            -WebSession $global:ET_SESSION `
            -Headers $headers `
            -Body $body `
            -UseBasicParsing
    }

    'help' {
        Write-Host @"

Email Tool Helper Script - Quick Reference

BASIC USAGE:
  .\scripts\et.ps1 start          Start app (default: port 5010, SMTP 2525, debug on, watchers off)
  .\scripts\et.ps1 login          Login and capture session
  .\scripts\et.ps1 get -path /healthz                  GET request
  .\scripts\et.ps1 post -path /api/accounts/1/test    POST request
  .\scripts\et.ps1 stop           Stop app and clean up

EXAMPLES:
  # Standard workflow
  .\scripts\et.ps1 start
  # In new terminal:
  .\scripts\et.ps1 login
  (.\scripts\et.ps1 get -path /healthz).Content
  .\scripts\et.ps1 post -path /api/accounts/1/test | Select -Expand Content

  # Custom ports
  .\scripts\et.ps1 start -port 8080 -smtp 1025

  # Enable watchers (only after configuring accounts!)
  .\scripts\et.ps1 start -watchers 1

  # Production mode
  .\scripts\et.ps1 start -debugMode 0

  # Set custom base URL
  .\scripts\et.ps1 base -base http://127.0.0.1:8080

  # POST with JSON body
  `$accountData = @{ account_name = "Test"; email_address = "test@example.com" }
  .\scripts\et.ps1 post -path /api/accounts -json `$accountData

PARAMETERS:
  -port <int>       Flask port (default: 5010)
  -smtp <int>       SMTP proxy port (default: 2525)
  -watchers <0|1>   Enable IMAP watchers (default: 0)
  -debugMode <0|1>      Enable debug mode (default: 1)
  -user <string>    Username for login (default: admin)
  -pass <string>    Password for login (default: admin123)
  -base <string>    Base URL (default: http://127.0.0.1:5010)
  -path <string>    API path for get/post commands
  -json <hashtable> JSON body for POST requests

NOTES:
  • Use PowerShell, not cmd
  • Ports 5010 and 2525 are safe on Windows
  • Don't use `$home as a variable name (PowerShell reserved)
  • CSRF tokens and sessions are handled automatically
  • Run 'login' once per session, then use get/post freely

"@ -ForegroundColor White
    }

    default {
        Write-Error "Unknown command: $cmd"
        Write-Host "Run: .\scripts\et.ps1 help" -ForegroundColor Yellow
    }
}


