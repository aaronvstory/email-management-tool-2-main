@echo off
REM ============================================================
REM    EMAIL MANAGEMENT TOOL - ULTIMATE LAUNCHER
REM ============================================================
REM    Professional launcher with menu options
REM ============================================================

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

REM Check if app is running
netstat -an | findstr :5000 >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo    STATUS: [RUNNING] Application is active on port 5000
    set APP_STATUS=RUNNING
) else (
    echo    STATUS: [STOPPED] Application is not running
    set APP_STATUS=STOPPED
)

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

if "%APP_STATUS%"=="RUNNING" (
    echo    [WARN] Application is already running!
    echo.
    echo    Opening dashboard in browser...
    start http://localhost:5000
    echo    [OK] Dashboard opened!
    timeout /t 3 /nobreak >nul
    goto MENU
)

echo    [1/4] Checking Python installation...
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo    [ERROR] Python is not installed!
    pause
    goto MENU
)
echo    [OK] Python found

echo    [2/4] Starting Flask application...
start /min cmd /c "python simple_app.py"

echo    [3/4] Waiting for services to initialize...
timeout /t 5 /nobreak >nul

echo    [4/4] Opening dashboard in browser...
start http://localhost:5000

echo.
echo    -----------------------------------------------------------------------------------------
echo    [SUCCESS] Application started successfully!
echo    -----------------------------------------------------------------------------------------
echo.
echo    Web Dashboard:  http://localhost:5000
echo    SMTP Proxy:     localhost:8587
echo    Login:          admin / admin123
echo.
echo    Press any key to return to menu...
pause >nul
goto MENU

:OPEN_BROWSER
cls
echo.
echo    -----------------------------------------------------------------------------------------
echo    OPENING DASHBOARD
echo    -----------------------------------------------------------------------------------------
echo.
start http://localhost:5000
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

if "%APP_STATUS%"=="STOPPED" (
    echo    [INFO] Application is not running.
    timeout /t 2 /nobreak >nul
    goto MENU
)

echo    Stopping Python processes...
for /f "tokens=2" %%i in ('tasklist ^| findstr python') do (
    taskkill /F /PID %%i >nul 2>&1
)

echo    [OK] Application stopped successfully!
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

REM Check Flask app
netstat -an | findstr :5000 >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo    [OK]    Web Dashboard:    RUNNING on port 5000
) else (
    echo    [WARN]  Web Dashboard:    NOT RUNNING
)

REM Check SMTP proxy
netstat -an | findstr :8587 >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo    [OK]    SMTP Proxy:       LISTENING on port 8587
) else (
    echo    [WARN]  SMTP Proxy:       NOT LISTENING
)

REM Check database
if exist "email_manager.db" (
    for %%A in (email_manager.db) do set SIZE=%%~zA
    echo    [OK]    Database:         Found (Size: %SIZE% bytes)
) else (
    echo    [WARN]  Database:         NOT FOUND
)

REM Check Python
python --version >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo    [OK]    Python:           INSTALLED
) else (
    echo    [ERROR] Python:           NOT FOUND
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

if exist "app.log" (
    echo    Last 20 lines of app.log:
    echo    -------------------------
    powershell -command "Get-Content app.log -Tail 20"
) else (
    echo    [INFO] No log file found.
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
    python scripts\test_all_connections.py
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
exit /b 0