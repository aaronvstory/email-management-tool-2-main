param(
  [int]$Port = 5001
)

Write-Host "============================================================"
Write-Host "   EMAIL MANAGEMENT TOOL - QUICK LAUNCHER (PowerShell)"
Write-Host "============================================================"

# Kill anything listening on $Port (best effort)
$pn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($pn) {
  $pids = $pn.OwningProcess | Select-Object -Unique
  foreach ($procId in $pids) {
    try { Stop-Process -Id $procId -Force -ErrorAction Stop; Write-Host "Killed PID $procId" } catch {}
  }
}

# Pick python - skip broken venv, prefer system Python
$pyCmd = $null
$pyArgs = @()

# Check if venv exists AND is not marked as broken
if ((Test-Path ".venv\Scripts\python.exe") -and -not (Test-Path ".venv.broken")) {
    # Test if venv Python actually works (quick sanity check)
    try {
        $testResult = & .venv\Scripts\python.exe --version 2>&1
        if ($LASTEXITCODE -eq 0) {
            $pyCmd = ".venv\Scripts\python.exe"
            Write-Host "Using virtual environment Python ($testResult)"
        } else {
            Write-Host "⚠ Virtual environment Python is broken, using system Python"
            $pyCmd = $null
        }
    } catch {
        Write-Host "⚠ Virtual environment Python crashed, using system Python"
        $pyCmd = $null
    }
}

# If venv didn't work, use system Python
if (-not $pyCmd) {
    if (Test-Path ".venv.broken") {
        Write-Host "⚠ Virtual environment is corrupted (.venv.broken exists)"
    }

    # Try py launcher with 3.11 first
    try {
        $null = & py -3.11 -V 2>&1
        if ($LASTEXITCODE -eq 0) {
            $pyCmd = "py"
            $pyArgs = @("-3.11")
            Write-Host "Using py -3.11 launcher"
        }
    } catch {}

    # Fallback to system python
    if (-not $pyCmd) {
        try {
            $null = & python --version 2>&1
            if ($LASTEXITCODE -eq 0) {
                $pyCmd = "python"
                Write-Host "Using system python"
            }
        } catch {}
    }

    # Last resort: just python
    if (-not $pyCmd) {
        $pyCmd = "python"
        Write-Host "Using python (last resort)"
    }
}

Write-Host "Starting server on port $Port ..."
Write-Host "Command: $pyCmd $pyArgs simple_app.py --port $Port"
& $pyCmd @pyArgs "simple_app.py" "--port" $Port

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "ERROR: Application failed to start (exit code: $LASTEXITCODE)" -ForegroundColor Red
    Write-Host "Press any key to continue..."
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
}
