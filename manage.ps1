#==============================================================================
#  EMAIL MANAGEMENT TOOL - POWERSHELL MANAGER
#==============================================================================
#  Professional management script for Email Management Tool
#  Handles starting, stopping, status checks, and maintenance
#==============================================================================

param(
    [Parameter(Position=0)]
    [ValidateSet('start', 'stop', 'restart', 'status', 'test', 'clean')]
    [string]$Action = 'start'
)

# Configuration
$AppName = "Email Management Tool"
$PythonScript = "simple_app.py"
$Port = 5001
$SMTPPort = 8587
$VenvPath = ".venv"

# Colors for output
function Write-Header {
    param([string]$Message)
    Write-Host ""
    Write-Host "========================================================" -ForegroundColor Cyan
    Write-Host "   $Message" -ForegroundColor Yellow
    Write-Host "========================================================" -ForegroundColor Cyan
    Write-Host ""
}

function Write-Success {
    param([string]$Message)
    Write-Host "[OK] " -NoNewline -ForegroundColor Green
    Write-Host $Message
}

function Write-Error {
    param([string]$Message)
    Write-Host "[ERROR] " -NoNewline -ForegroundColor Red
    Write-Host $Message
}

function Write-Info {
    param([string]$Message)
    Write-Host "[INFO] " -NoNewline -ForegroundColor Cyan
    Write-Host $Message
}

function Write-Warning {
    param([string]$Message)
    Write-Host "[WARN] " -NoNewline -ForegroundColor Yellow
    Write-Host $Message
}

# Check if virtual environment exists
function Test-VirtualEnv {
    if (Test-Path $VenvPath) {
        return $true
    }
    Write-Warning "Virtual environment not found at $VenvPath"
    Write-Info "Creating virtual environment..."
    python -m venv $VenvPath
    if ($LASTEXITCODE -eq 0) {
        Write-Success "Virtual environment created"
        return $true
    }
    Write-Error "Failed to create virtual environment"
    return $false
}

# Activate virtual environment
function Activate-VirtualEnv {
    $activateScript = Join-Path $VenvPath "Scripts\Activate.ps1"
    if (Test-Path $activateScript) {
        & $activateScript
        Write-Success "Virtual environment activated"
        return $true
    }
    Write-Error "Could not find activation script"
    return $false
}

# Install dependencies
function Install-Dependencies {
    Write-Info "Checking dependencies..."
    if (Test-Path "requirements.txt") {
        pip install -q -r requirements.txt
        if ($LASTEXITCODE -eq 0) {
            Write-Success "Dependencies installed/verified"
            return $true
        }
        Write-Error "Failed to install dependencies"
        return $false
    }
    Write-Warning "requirements.txt not found"
    return $true
}

# Check if application is running
function Test-AppRunning {
    try {
        $response = Invoke-WebRequest -Uri "http://127.0.0.1:$Port" -UseBasicParsing -TimeoutSec 2 -ErrorAction SilentlyContinue
        return $true
    } catch {
        return $false
    }
}

# Get Python processes running our app
function Get-AppProcesses {
    Get-Process python -ErrorAction SilentlyContinue | Where-Object {
        $_.CommandLine -like "*$PythonScript*"
    }
}

# Stop the application
function Stop-Application {
    Write-Header "STOPPING $AppName"

    $processes = Get-AppProcesses
    if ($processes) {
        foreach ($proc in $processes) {
            Write-Info "Stopping process $($proc.Id)..."
            Stop-Process -Id $proc.Id -Force
        }
        Start-Sleep -Seconds 2
        Write-Success "Application stopped"
    } else {
        Write-Info "Application is not running"
    }
}

# Start the application
function Start-Application {
    Write-Header "STARTING $AppName"

    # Check if already running
    if (Test-AppRunning) {
        Write-Warning "Application is already running on port $Port"
        Write-Info "Use 'manage.ps1 restart' to restart the application"
        return
    }

    # Setup environment
    if (-not (Test-VirtualEnv)) {
        Write-Error "Failed to setup virtual environment"
        return
    }

    if (-not (Activate-VirtualEnv)) {
        Write-Error "Failed to activate virtual environment"
        return
    }

    if (-not (Install-Dependencies)) {
        Write-Error "Failed to install dependencies"
        return
    }

    # Check if main script exists
    if (-not (Test-Path $PythonScript)) {
        Write-Error "$PythonScript not found in current directory"
        return
    }

    Write-Info "Starting Flask application..."

    # Start the application in a new window
    $startInfo = New-Object System.Diagnostics.ProcessStartInfo
    $startInfo.FileName = "python"
    $startInfo.Arguments = $PythonScript
    $startInfo.WorkingDirectory = Get-Location
    $startInfo.UseShellExecute = $true
    $startInfo.CreateNoWindow = $false

    try {
        $process = [System.Diagnostics.Process]::Start($startInfo)

        # Wait for app to start
        Write-Info "Waiting for application to start..."
        $maxWait = 30
        $waited = 0
        while ($waited -lt $maxWait -and -not (Test-AppRunning)) {
            Start-Sleep -Seconds 1
            $waited++
            Write-Host "." -NoNewline
        }
        Write-Host ""

        if (Test-AppRunning) {
            Write-Success "Application started successfully!"
            Write-Host ""
            Write-Host "  Services Running:" -ForegroundColor Cyan
            Write-Host "  ----------------" -ForegroundColor Cyan
            Write-Host "  Web Dashboard:  " -NoNewline
            Write-Host "http://127.0.0.1:$Port" -ForegroundColor Green
            Write-Host "  SMTP Proxy:     " -NoNewline
            Write-Host "localhost:$SMTPPort" -ForegroundColor Green
            Write-Host "  Login:          " -NoNewline
            Write-Host "admin / admin123" -ForegroundColor Yellow
            Write-Host ""
            Write-Info "Press Ctrl+C in the application window to stop"
        } else {
            Write-Error "Application failed to start within $maxWait seconds"
        }
    } catch {
        Write-Error "Failed to start application: $_"
    }
}

# Check application status
function Get-ApplicationStatus {
    Write-Header "$AppName STATUS"

    # Check if running
    if (Test-AppRunning) {
        Write-Success "Web Dashboard is RUNNING on port $Port"
    } else {
        Write-Warning "Web Dashboard is NOT RUNNING"
    }

    # Check SMTP port
    $smtpListener = Get-NetTCPConnection -LocalPort $SMTPPort -ErrorAction SilentlyContinue
    if ($smtpListener) {
        Write-Success "SMTP Proxy is LISTENING on port $SMTPPort"
    } else {
        Write-Warning "SMTP Proxy is NOT LISTENING"
    }

    # Check Python processes
    $processes = Get-AppProcesses
    if ($processes) {
        Write-Info "Python processes found:"
        foreach ($proc in $processes) {
            Write-Host "    PID: $($proc.Id), Memory: $([math]::Round($proc.WorkingSet64/1MB, 2)) MB"
        }
    } else {
        Write-Info "No Python processes found for $PythonScript"
    }

    # Check database
    if (Test-Path "email_manager.db") {
        $dbSize = (Get-Item "email_manager.db").Length / 1KB
        Write-Success "Database found (Size: $([math]::Round($dbSize, 2)) KB)"
    } else {
        Write-Warning "Database file not found"
    }
}

# Run tests
function Test-Application {
    Write-Header "TESTING $AppName"

    if (-not (Test-AppRunning)) {
        Write-Warning "Application is not running. Starting it first..."
        Start-Application
        Start-Sleep -Seconds 5
    }

    Write-Info "Running validation tests..."

    # Check if test script exists
    $testScripts = @("final_validation.py", "tests\test_complete_workflow.py")
    $testFound = $false

    foreach ($script in $testScripts) {
        if (Test-Path $script) {
            Write-Info "Running $script..."
            python $script
            $testFound = $true
            break
        }
    }

    if (-not $testFound) {
        Write-Warning "No test scripts found"
        Write-Info "Testing basic connectivity..."

        try {
            $response = Invoke-WebRequest -Uri "http://127.0.0.1:$Port/login" -UseBasicParsing
            if ($response.StatusCode -eq 200) {
                Write-Success "Login page accessible"
            }
        } catch {
            Write-Error "Failed to access login page"
        }
    }
}

# Clean workspace
function Clean-Workspace {
    Write-Header "CLEANING WORKSPACE"

    Write-Info "Cleaning Python cache..."
    Get-ChildItem -Path . -Include __pycache__ -Recurse -Directory | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    Get-ChildItem -Path . -Include *.pyc -Recurse -File | Remove-Item -Force -ErrorAction SilentlyContinue

    Write-Info "Cleaning test artifacts..."
    Get-ChildItem -Path . -Include test_results*.json -File | Remove-Item -Force -ErrorAction SilentlyContinue
    Get-ChildItem -Path . -Include validation_report*.json -File | Remove-Item -Force -ErrorAction SilentlyContinue

    Write-Success "Workspace cleaned"
}

# Main execution
Clear-Host

switch ($Action) {
    'start' {
        Start-Application
    }
    'stop' {
        Stop-Application
    }
    'restart' {
        Stop-Application
        Start-Sleep -Seconds 2
        Start-Application
    }
    'status' {
        Get-ApplicationStatus
    }
    'test' {
        Test-Application
    }
    'clean' {
        Clean-Workspace
    }
}

Write-Host ""
