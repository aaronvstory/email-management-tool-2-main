@echo off
REM ============================================================
REM    EMAIL MANAGEMENT TOOL - QUICK LAUNCHER
REM ============================================================
REM    One-click launcher that starts the app and opens browser
REM ============================================================

cls
color 0A

echo.
echo ============================================================
echo    EMAIL MANAGEMENT TOOL - PROFESSIONAL LAUNCHER
echo ============================================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python is not installed or not in PATH!
    echo Please install Python 3.8 or higher.
    pause
    exit /b 1
)

REM Check for port conflicts and clean up if needed
echo [PREFLIGHT] Checking for port conflicts...

REM Check port 5000 (Flask)
C:\Windows\System32\netstat.exe -ano | findstr :5000 >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [WARNING] Port 5000 is in use. Checking if it's our application...

    REM Try to access health endpoint
    curl -s http://localhost:5000/healthz >nul 2>&1
    if %ERRORLEVEL% EQU 0 (
        echo [INFO] Application is already running and healthy!
        echo.
        echo Opening dashboard in browser...
        timeout /t 2 /nobreak >nul
        start http://localhost:5000
        echo.
        echo [OK] Browser launched!
        timeout /t 3 /nobreak >nul
        exit /b 0
    ) else (
        echo [WARNING] Port 5000 occupied by unresponsive process.
        echo [ACTION] Attempting safe cleanup of our own Python process on port 5000...
        for /f "tokens=5" %%a in ('netstat -ano ^| findstr :5000') do (
            for /f "usebackq delims=" %%c in (`wmic process where "ProcessId=%%a" get CommandLine ^| findstr /I /C:"Email-Management-Tool"`) do (
                taskkill /F /PID %%a >nul 2>&1
            )
        )
        timeout /t 2 /nobreak >nul
    )
)

REM Check port 8587 (SMTP Proxy)
C:\Windows\System32\netstat.exe -ano | findstr :8587 >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [WARNING] Port 8587 is in use. Attempting safe cleanup...
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8587') do (
        for /f "usebackq delims=" %%c in (`wmic process where "ProcessId=%%a" get CommandLine ^| findstr /I /C:"Email-Management-Tool"`) do (
            taskkill /F /PID %%a >nul 2>&1
        )
    )
    timeout /t 2 /nobreak >nul
)

echo [OK] Ports are clear!

echo [STARTING] Email Management Tool...
echo.

REM Start the Flask application in background
echo [1/3] Starting Flask application...
start /min cmd /c "python simple_app.py"

REM Wait for application to initialize
echo [2/3] Waiting for services to initialize...
timeout /t 5 /nobreak >nul

REM Check if app started successfully
C:\Windows\System32\netstat.exe -an | findstr :5000 >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Failed to start application!
    echo Please check if port 5000 is available.
    pause
    exit /b 1
)

echo [3/3] Opening dashboard in browser...
echo.

REM Open the dashboard in default browser
start http://localhost:5000

echo ============================================================
echo    APPLICATION STARTED SUCCESSFULLY!
echo ============================================================
echo.
echo    Web Dashboard:  http://localhost:5000
echo    SMTP Proxy:     localhost:8587
echo    Login:          admin / admin123
echo.
echo    The dashboard has been opened in your browser.
echo    Keep this window open while using the application.
echo.
echo    Press Ctrl+C to stop the application.
echo ============================================================
echo.

REM Keep window open to show status
pause >nul