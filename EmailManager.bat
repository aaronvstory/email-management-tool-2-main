@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM ============================================================
REM    EMAIL MANAGEMENT TOOL - ULTIMATE LAUNCHER
REM ============================================================
REM    Professional launcher with menu options
REM ============================================================

set "SCRIPT_DIR=%~dp0"
pushd "%SCRIPT_DIR%" >nul

set "APP_STATUS=UNKNOWN"
set "APP_STATUS_MSG="
set "SMTP_STATUS=UNKNOWN"

:MENU
cls
color 0D

echo.
echo    -----------------------------------------------------------------------------------------
echo.
echo                          EMAIL MANAGEMENT TOOL
echo                     Interception and Moderation System
echo.
echo    -----------------------------------------------------------------------------------------
echo.

call :REFRESH_STATUS
echo    STATUS: !APP_STATUS_MSG!

echo.
echo    -----------------------------------------------------------------------------------------
echo    MAIN MENU
echo    -----------------------------------------------------------------------------------------
echo.
echo    [1] Start Application and Open Dashboard
echo    [2] Open Dashboard Only (if already running)
echo    [3] Stop Application
echo    [4] Check Status
echo    [5] View Logs
echo    [6] Test Email Connections
echo    [7] Clean Temporary Files
echo    [Q] Quit
echo.
echo    -----------------------------------------------------------------------------------------
echo.

set /p CHOICE="   Enter your choice: "

if /i "%CHOICE%"=="1" goto START_APP
if /i "%CHOICE%"=="2" goto OPEN_BROWSER
if /i "%CHOICE%"=="3" goto STOP_APP
if /i "%CHOICE%"=="4" goto CHECK_STATUS
if /i "%CHOICE%"=="5" goto VIEW_LOGS
if /i "%CHOICE%"=="6" goto TEST_CONNECTIONS
if /i "%CHOICE%"=="7" goto CLEAN_TEMP
if /i "%CHOICE%"=="Q" goto EXIT

echo.
echo    [ERROR] Invalid choice! Please try again.
timeout /t 2 /nobreak >nul
goto MENU

:START_APP
cls
echo.
echo    -----------------------------------------------------------------------------------------
echo    STARTING EMAIL MANAGEMENT TOOL
echo    -----------------------------------------------------------------------------------------
echo.

call :REFRESH_STATUS

if /I "!APP_STATUS!"=="RUNNING" (
    echo    [WARN] Application is already running and healthy.
    echo.
    echo    Opening dashboard in browser...
    start "" http://127.0.0.1:5000
    echo    [OK] Dashboard opened!
    timeout /t 3 /nobreak >nul
    goto MENU
)

if /I "!APP_STATUS!"=="BUSY" (
    echo    [ERROR] Port 5000 is currently in use by another service.
    echo    Please free the port or set FLASK_PORT before starting.
    timeout /t 4 /nobreak >nul
    goto MENU
)

echo    [INFO] Delegating start sequence to launch.bat...
call "%SCRIPT_DIR%launch.bat"

echo.
echo    Returning to menu in 3 seconds...
timeout /t 3 /nobreak >nul
goto MENU

:OPEN_BROWSER
cls
echo.
echo    -----------------------------------------------------------------------------------------
echo    OPENING DASHBOARD
echo    -----------------------------------------------------------------------------------------
echo.
start "" http://127.0.0.1:5000
echo    [OK] Dashboard opened in default browser!
echo.
echo    Login Credentials:
echo    Username: admin
echo    Password: admin123
echo.
echo    Press any key to return to menu...
pause >nul
goto MENU

:STOP_APP
cls
echo.
echo    -----------------------------------------------------------------------------------------
echo    STOPPING APPLICATION
echo    -----------------------------------------------------------------------------------------
echo.

call :REFRESH_STATUS

if /I "!APP_STATUS!"=="STOPPED" (
    echo    [INFO] Application is not running.
    timeout /t 2 /nobreak >nul
    goto MENU
)

call :COLLECT_APP_PIDS
if not defined APP_PIDS (
    echo    [WARN] No Email Management Tool processes were detected.
    timeout /t 2 /nobreak >nul
    goto MENU
)

echo    Stopping application processes (!APP_PIDS!)...
for %%P in (!APP_PIDS!) do (
    taskkill /F /PID %%P >nul 2>&1
)

echo    [OK] Application stop signal sent.
call :REFRESH_STATUS
echo    Updated Status: !APP_STATUS_MSG!
echo.
echo    Press any key to return to menu...
pause >nul
goto MENU

:CHECK_STATUS
cls
echo.
echo    -----------------------------------------------------------------------------------------
echo    SYSTEM STATUS
echo    -----------------------------------------------------------------------------------------
echo.

call :REFRESH_STATUS
echo    [STATUS] Web Dashboard: !APP_STATUS_MSG!

set "SMTP_PORT_STATE="
call :CHECK_PORT 8587 SMTP_PORT_STATE
if /I "!SMTP_PORT_STATE!"=="BUSY" (
    set "SMTP_STATUS_MSG=[LISTENING] SMTP proxy is accepting connections on port 8587"
) else (
    set "SMTP_STATUS_MSG=[STOPPED] SMTP proxy not detected on port 8587"
)
echo    [STATUS] SMTP Proxy:   !SMTP_STATUS_MSG!

if exist "email_manager.db" (
    set "DB_SIZE_BYTES=0"
    for %%A in (email_manager.db) do set "DB_SIZE_BYTES=%%~zA"
    echo    [OK]    Database:     Found (Size: !DB_SIZE_BYTES! bytes)
) else (
    echo    [WARN]  Database:     NOT FOUND
)

set "PY_VER="
call :ENSURE_PYTHON
if not errorlevel 1 (
    for /f "usebackq tokens=*" %%V in (`"!PYTHON_BIN!" --version 2^>^&1`) do set "PY_VER=%%V"
    if defined PY_VER (
        echo    [OK]    Python:       !PY_VER!  [!PYTHON_BIN!]
    ) else (
        echo    [OK]    Python:       !PYTHON_BIN!
    )
) else (
    echo    [ERROR] Python:       NOT FOUND (install Python 3.9+)
)

echo.
echo    Press any key to return to menu...
pause >nul
goto MENU

:VIEW_LOGS
cls
echo.
echo    -----------------------------------------------------------------------------------------
echo    APPLICATION LOGS
echo    -----------------------------------------------------------------------------------------
echo.

set "LOG_PRIMARY=logs\email_moderation.log"
set "LOG_FALLBACK=app.log"

if exist "!LOG_PRIMARY!" (
    echo    Last 40 lines of !LOG_PRIMARY!:
    echo    ----------------------------------------
    powershell -NoLogo -NoProfile -Command "Get-Content '!LOG_PRIMARY!' -Tail 40"
) else if exist "!LOG_FALLBACK!" (
    echo    Last 40 lines of !LOG_FALLBACK!:
    echo    ----------------------------------------
    powershell -NoLogo -NoProfile -Command "Get-Content '!LOG_FALLBACK!' -Tail 40"
) else (
    echo    [INFO] No log file found (expected at !LOG_PRIMARY! or !LOG_FALLBACK!).
)

echo.
echo    Press any key to return to menu...
pause >nul
goto MENU

:TEST_CONNECTIONS
cls
echo.
echo    -----------------------------------------------------------------------------------------
echo    TESTING EMAIL CONNECTIONS
echo    -----------------------------------------------------------------------------------------
echo.

if exist "scripts\test_all_connections.py" (
    call :ENSURE_PYTHON
    if errorlevel 1 (
        echo    [ERROR] Python interpreter not found. Run the Start option first.
    ) else (
        echo    Running test_all_connections.py using !PYTHON_BIN! ...
        "!PYTHON_BIN!" scripts\test_all_connections.py
    )
) else (
    echo    [ERROR] Test script not found!
    echo    Looking for: scripts\test_all_connections.py
)

echo.
echo    Press any key to return to menu...
pause >nul
goto MENU

:CLEAN_TEMP
cls
echo.
echo    -----------------------------------------------------------------------------------------
echo    CLEANING TEMPORARY FILES
echo    -----------------------------------------------------------------------------------------
echo.

echo    Removing Python cache...
if exist "__pycache__" (
    rmdir /s /q __pycache__
    echo    [OK] __pycache__ removed
)

echo    Cleaning .pyc files...
del /s /q *.pyc >nul 2>&1
echo    [OK] .pyc files cleaned

echo    Removing temporary test files...
del /q test_*.json >nul 2>&1
del /q workflow_test_*.json >nul 2>&1
echo    [OK] Temporary test files cleaned

echo.
echo    [SUCCESS] Cleanup complete!
echo.
echo    Press any key to return to menu...
pause >nul
goto MENU

:EXIT
cls
echo.
echo    -----------------------------------------------------------------------------------------
echo    Thank you for using Email Management Tool!
echo    -----------------------------------------------------------------------------------------
echo.
timeout /t 2 /nobreak >nul
popd >nul
endlocal
exit /b 0

:REFRESH_STATUS
set "APP_STATUS=STOPPED"
set "APP_STATUS_MSG=[STOPPED] Application is not running"
set "SMTP_STATUS=STOPPED"

set "DASH_STATE="
call :CHECK_PORT 5000 DASH_STATE
if /I "%DASH_STATE%"=="HEALTHY" (
    set "APP_STATUS=RUNNING"
    set "APP_STATUS_MSG=[RUNNING] Healthy at http://127.0.0.1:5000"
) else if /I "%DASH_STATE%"=="BUSY" (
    set "APP_STATUS=BUSY"
    set "APP_STATUS_MSG=[UNKNOWN] Port 5000 in use (health check failed)"
)

set "SMTP_PORT_STATE="
call :CHECK_PORT 8587 SMTP_PORT_STATE
if /I "%SMTP_PORT_STATE%"=="BUSY" (
    set "SMTP_STATUS=LISTENING"
) else if /I "%SMTP_PORT_STATE%"=="HEALTHY" (
    set "SMTP_STATUS=LISTENING"
) else (
    set "SMTP_STATUS=STOPPED"
)
exit /b 0

:CHECK_PORT
set "_CP_PORT=%~1"
set "_CP_VAR=%~2"
set "_CP_STATE=FREE"

powershell -NoLogo -NoProfile -Command "
    $port = %1;
    $baseUri = 'http://127.0.0.1:' + $port;
    $isHealthy = $false;
    try {
        $resp = Invoke-WebRequest -Uri ($baseUri + '/healthz') -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop;
        if ($resp.StatusCode -eq 200) { $isHealthy = $true }
    } catch {}
    if ($isHealthy) { Write-Host HEALTHY; return }

    $listenerFound = $false;
    try {
        $netCmd = Get-Command Get-NetTCPConnection -ErrorAction Stop;
        if ($netCmd) {
            $listener = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue |
                        Select-Object -First 1 -ExpandProperty OwningProcess;
            if ($listener) { $listenerFound = $true }
        }
    } catch {}

    if (-not $listenerFound) {
        try {
            $netstatOutput = netstat -ano | Select-String (':' + $port);
            if ($netstatOutput) { $listenerFound = $true }
        } catch {}
    }

    if ($listenerFound) { Write-Host BUSY } else { Write-Host FREE }
" >"%TEMP%\emt_menu_port.tmp"

set /p _CP_STATE=<"%TEMP%\emt_menu_port.tmp"
del "%TEMP%\emt_menu_port.tmp" >nul 2>&1
set "%_CP_VAR%=%_CP_STATE%"
exit /b 0

:COLLECT_APP_PIDS
set "APP_PIDS="
for /f "usebackq tokens=*" %%P in (`powershell -NoLogo -NoProfile -Command "Get-WmiObject -Class Win32_Process | Where-Object { $_.Name -match 'python' -and $_.CommandLine -match 'simple_app.py' } | Select-Object -ExpandProperty ProcessId"`) do (
    if not defined APP_PIDS (
        set "APP_PIDS=%%P"
    ) else (
        set "APP_PIDS=!APP_PIDS! %%P"
    )
)
exit /b 0

:ENSURE_PYTHON
set "PYTHON_BIN="
if exist ".venv\Scripts\python.exe" (
    set "PYTHON_BIN=.venv\Scripts\python.exe"
) else (
    for %%P in (py python) do (
        if not defined PYTHON_BIN (
            where %%P >nul 2>&1 && set "PYTHON_BIN=%%P"
        )
    )
)

if not defined PYTHON_BIN (
    exit /b 1
)
exit /b 0
