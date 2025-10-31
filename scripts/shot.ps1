#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Professional Playwright screenshot kit with interactive UI
.DESCRIPTION
    Captures full-page screenshots of all app routes with:
    - Interactive prompts for base URL, credentials, and preferences
    - Link discovery and selection UI
    - Desktop/mobile viewport presets
    - Timestamped output folders
    - Headed/headless browser modes
.EXAMPLE
    .\shot.ps1 -Interactive
    .\shot.ps1 -Base "http://localhost:5001" -Headless
    .\shot.ps1 -View both -Max 50
#>
param(
    [string]$Base = "",
    [string]$User = "",
    [string]$Pass = "",
    [switch]$Headless,
    [ValidateSet('desktop','mobile','both')] [string]$View = '',
    [int]$Max = 0,
    [string]$Include = "",
    [string]$Exclude = "",
    [switch]$Interactive,
    [switch]$Quick  # Skip link selection, shoot all discovered links
)

$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$py = Join-Path $here "shot.py"
$root = Split-Path -Parent $here

# ============================================================================
# Color Helpers
# ============================================================================
function Write-Header($text) {
    Write-Host "`n╔═══════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
    Write-Host "║  $($text.PadRight(59))  ║" -ForegroundColor Cyan
    Write-Host "╚═══════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
}

function Write-Step($num, $text) {
    Write-Host "`n[$num] " -ForegroundColor Yellow -NoNewline
    Write-Host $text -ForegroundColor White
}

function Write-Success($text) {
    Write-Host "✅ " -ForegroundColor Green -NoNewline
    Write-Host $text -ForegroundColor Gray
}

function Write-Info($text) {
    Write-Host "ℹ️  " -ForegroundColor Cyan -NoNewline
    Write-Host $text -ForegroundColor Gray
}

# ============================================================================
# Interactive Prompts
# ============================================================================
function Get-InteractiveConfig {
    Write-Header "📸 Screenshot Kit - Interactive Setup"

    # Base URL
    Write-Step 1 "Base URL Configuration"
    $defaultBase = "http://127.0.0.1:5001"
    $inputBase = Read-Host "  Enter base URL (default: $defaultBase)"
    $script:Base = if ($inputBase) { $inputBase.TrimEnd('/') } else { $defaultBase }
    Write-Success "Using: $script:Base"

    # Credentials
    Write-Step 2 "Authentication"
    $defaultUser = "admin"
    $inputUser = Read-Host "  Username (default: $defaultUser)"
    $script:User = if ($inputUser) { $inputUser } else { $defaultUser }

    $defaultPass = "admin123"
    $inputPass = Read-Host "  Password (default: $defaultPass)" -AsSecureString
    if ($inputPass.Length -eq 0) {
        $script:Pass = $defaultPass
    } else {
        $BSTR = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($inputPass)
        $script:Pass = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($BSTR)
    }
    Write-Success "Credentials configured"

    # Browser mode
    Write-Step 3 "Browser Mode"
    Write-Host "  1) Headed (visible browser)"
    Write-Host "  2) Headless (background)"
    $modeChoice = Read-Host "  Select mode (1-2, default: 1)"
    $script:Headless = ($modeChoice -eq "2")
    Write-Success "Mode: $(if ($script:Headless) {'Headless'} else {'Headed (visible)'})"

    # Viewport
    Write-Step 4 "Viewport Preset"
    Write-Host "  1) Desktop only (1920x1080)"
    Write-Host "  2) Mobile only (iPhone)"
    Write-Host "  3) Both (desktop + mobile)"
    $viewChoice = Read-Host "  Select viewport (1-3, default: 1)"
    $script:View = switch ($viewChoice) {
        "2" { "mobile" }
        "3" { "both" }
        default { "desktop" }
    }
    Write-Success "Viewport: $script:View"

    # Max links
    Write-Step 5 "Link Discovery"
    $defaultMax = 25
    $inputMax = Read-Host "  Max links to capture (default: $defaultMax)"
    $script:Max = if ($inputMax -match '^\d+$') { [int]$inputMax } else { $defaultMax }
    Write-Success "Will discover up to $script:Max links"

    # Include/Exclude (advanced)
    Write-Host "`n  Advanced filters (press Enter to use defaults):" -ForegroundColor Gray
    $inputInclude = Read-Host "  Include paths (comma-separated, e.g., /dashboard,/emails)"
    $script:Include = if ($inputInclude) { $inputInclude } else { "/" }

    $inputExclude = Read-Host "  Exclude paths (comma-separated)"
    $script:Exclude = if ($inputExclude) { $inputExclude } else { "/logout,/static,/api" }
}

# ============================================================================
# Link Selection UI
# ============================================================================
function Show-LinkSelection($links) {
    Write-Header "🔍 Discovered Links - Select which to capture"

    Write-Host "`nFound $($links.Count) links:" -ForegroundColor Cyan
    for ($i = 0; $i -lt $links.Count; $i++) {
        Write-Host "  [$($i+1)] " -ForegroundColor Yellow -NoNewline
        Write-Host $links[$i] -ForegroundColor Gray
    }

    Write-Host "`n📋 Selection Options:" -ForegroundColor Cyan
    Write-Host "  • Enter numbers (e.g., '1,3,5' or '1-10')"
    Write-Host "  • Type 'all' to capture all links"
    Write-Host "  • Press Enter to capture all"

    $choice = Read-Host "`nYour selection"

    if (-not $choice -or $choice -eq "all") {
        Write-Success "Selected all $($links.Count) links"
        return $links
    }

    # Parse selection (supports "1,3,5" and "1-10" syntax)
    $selected = @()
    $parts = $choice -split ','
    foreach ($part in $parts) {
        if ($part -match '^(\d+)-(\d+)$') {
            $start = [int]$matches[1]
            $end = [int]$matches[2]
            $selected += ($start..$end) | Where-Object { $_ -ge 1 -and $_ -le $links.Count }
        } elseif ($part -match '^\d+$') {
            $num = [int]$part
            if ($num -ge 1 -and $num -le $links.Count) {
                $selected += $num
            }
        }
    }

    $selectedLinks = $selected | Sort-Object -Unique | ForEach-Object { $links[$_ - 1] }
    Write-Success "Selected $($selectedLinks.Count) links"

    return $selectedLinks
}

# ============================================================================
# Main Execution
# ============================================================================

# Auto-detect interactive mode if no params provided
if (-not $Base -and -not $PSBoundParameters.ContainsKey('Interactive')) {
    $Interactive = $true
}

if ($Interactive) {
    Get-InteractiveConfig
} else {
    # Use provided params or defaults
    if (-not $Base) { $Base = "http://127.0.0.1:5001" }
    if (-not $User) { $User = "admin" }
    if (-not $Pass) { $Pass = "admin123" }
    if (-not $View) { $View = "desktop" }
    if ($Max -eq 0) { $Max = 25 }
    if (-not $Include) { $Include = "/" }
    if (-not $Exclude) { $Exclude = "/logout,/static,/api" }
}

Write-Header "🚀 Starting Screenshot Capture"

Write-Info "Base URL: $Base"
Write-Info "User: $User"
Write-Info "Mode: $(if ($Headless) {'Headless'} else {'Headed'})"
Write-Info "Viewport: $View"
Write-Info "Max Links: $Max"

# Ensure playwright is installed
Write-Host "`n⏳ Checking Playwright installation..." -ForegroundColor Cyan
$venvPy = Join-Path $root ".venv" "Scripts" "python.exe"
if (-not (Test-Path $venvPy)) {
    Write-Host "❌ Virtual environment not found at: $venvPy" -ForegroundColor Red
    Write-Host "   Run: python -m venv .venv" -ForegroundColor Yellow
    exit 1
}

& $venvPy -m pip install "playwright>=1.45,<2" --quiet 2>&1 | Out-Null
Write-Success "Playwright library ready"

Write-Host "⏳ Installing browser binaries..." -ForegroundColor Cyan
& $venvPy -m playwright install chromium 2>&1 | Out-Null
Write-Success "Chromium browser ready"

# Set environment variables for Python script
$env:SHOT_BASE = $Base
$env:SHOT_USER = $User
$env:SHOT_PASS = $Pass
$env:SHOT_HEADLESS = if ($Headless) {"1"} else {"0"}
$env:SHOT_VIEW = $View
$env:SHOT_MAX = "$Max"
$env:SHOT_INCLUDE = $Include
$env:SHOT_EXCLUDE = $Exclude
$env:SHOT_QUICK = if ($Quick) {"1"} else {"0"}

# Link selection mode (if not Quick)
if (-not $Quick -and $Interactive) {
    Write-Host "`n⏳ Discovering links (this may take a moment)..." -ForegroundColor Cyan
    $env:SHOT_DISCOVER_ONLY = "1"

    # Run discovery
    $discoveryOutput = & $venvPy $py 2>&1 | Out-String
    $env:SHOT_DISCOVER_ONLY = "0"

    # Parse discovered links from output
    if ($discoveryOutput -match 'DISCOVERED_LINKS_JSON:(.+)$') {
        $linksJson = $matches[1].Trim()
        $links = $linksJson | ConvertFrom-Json

        if ($links.Count -gt 0) {
            $selectedLinks = Show-LinkSelection $links
            $env:SHOT_SELECTED_LINKS = ($selectedLinks | ConvertTo-Json -Compress)
        }
    }
}

# Run the screenshot capture
Write-Host "`n📸 Capturing screenshots..." -ForegroundColor Cyan
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray

& $venvPy $py

# Check if successful
if ($LASTEXITCODE -eq 0) {
    Write-Host "`n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
    Write-Host "`n✅ Screenshots captured successfully!" -ForegroundColor Green

    # Find output directory
    $screenshotsRoot = Join-Path $root "screenshots"
    $latestDir = Get-ChildItem -Path $screenshotsRoot -Directory | Sort-Object Name -Descending | Select-Object -First 1

    if ($latestDir) {
        # Extract timestamp from folder name (format: YYYYMMDD_HHMMSS)
        $timestamp = $latestDir.Name
        $displayTime = try {
            $dt = [DateTime]::ParseExact($timestamp, "yyyyMMdd_HHmmss", $null)
            $dt.ToString("MMM dd, yyyy 'at' h:mm:ss tt")
        } catch {
            $timestamp
        }

        # Calculate folder size and file counts
        $desktopPath = Join-Path $latestDir "desktop"
        $mobilePath = Join-Path $latestDir "mobile"

        $desktopFiles = @(Get-ChildItem -Path $desktopPath -Filter "*.png" -ErrorAction SilentlyContinue)
        $mobileFiles = @(Get-ChildItem -Path $mobilePath -Filter "*.png" -ErrorAction SilentlyContinue)

        $desktopCount = $desktopFiles.Count
        $mobileCount = $mobileFiles.Count
        $totalCount = $desktopCount + $mobileCount

        # Calculate total size
        $totalSize = 0
        $desktopFiles | ForEach-Object { $totalSize += $_.Length }
        $mobileFiles | ForEach-Object { $totalSize += $_.Length }
        $sizeMB = [math]::Round($totalSize / 1MB, 2)

        # Beautiful summary box
        Write-Host "`n╔═══════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
        Write-Host "║                        📊 Summary                             ║" -ForegroundColor Cyan
        Write-Host "╚═══════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
        Write-Host ""
        Write-Host "  🕐 Timestamp:  " -ForegroundColor White -NoNewline
        Write-Host $displayTime -ForegroundColor Gray
        Write-Host ""
        Write-Host "  📸 Screenshots:" -ForegroundColor White
        if ($desktopCount -gt 0) {
            Write-Host "     Desktop:  " -ForegroundColor Gray -NoNewline
            Write-Host "$desktopCount files" -ForegroundColor Green
        }
        if ($mobileCount -gt 0) {
            Write-Host "     Mobile:   " -ForegroundColor Gray -NoNewline
            Write-Host "$mobileCount files" -ForegroundColor Green
        }
        Write-Host "     Total:    " -ForegroundColor Gray -NoNewline
        Write-Host "$totalCount files" -ForegroundColor Cyan
        Write-Host ""
        Write-Host "  💾 Size:       " -ForegroundColor White -NoNewline
        Write-Host "$sizeMB MB" -ForegroundColor Gray
        Write-Host ""
        Write-Host "  📁 Location:" -ForegroundColor White
        Write-Host "     $($latestDir.FullName)" -ForegroundColor Gray
        Write-Host ""

        # Auto-open folder (default: yes)
        Write-Host "  💡 " -ForegroundColor Yellow -NoNewline
        $openFolder = Read-Host "Open folder in Explorer? (Y/n)"

        # Default to yes (any input except 'n' or 'N' opens folder)
        if ($openFolder -ne 'n' -and $openFolder -ne 'N') {
            Write-Host "`n  🚀 Opening folder..." -ForegroundColor Cyan
            Start-Process explorer.exe $latestDir.FullName
            Start-Sleep -Milliseconds 500  # Brief pause so user sees the message
        } else {
            Write-Host "`n  ℹ️  Folder location saved above for later reference" -ForegroundColor Gray
        }

        Write-Host "`n╔═══════════════════════════════════════════════════════════════╗" -ForegroundColor Green
        Write-Host "║                  ✨ Screenshot kit complete! ✨               ║" -ForegroundColor Green
        Write-Host "╚═══════════════════════════════════════════════════════════════╝" -ForegroundColor Green
        Write-Host ""
    }
} else {
    Write-Host "`n❌ Screenshot capture failed (exit code: $LASTEXITCODE)" -ForegroundColor Red
    exit $LASTEXITCODE
}
