@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM =====================================================================
REM  EMAIL MANAGEMENT TOOL - QUICK LAUNCHER (Developer Edition)
REM =====================================================================

cls
color 0A

set "SCRIPT_DIR=%~dp0"
pushd "%SCRIPT_DIR%" >nul

echo.
echo ============================================================
echo    EMAIL MANAGEMENT TOOL - QUICK LAUNCHER
echo ============================================================
echo.

REM ---------------------------------------------------------------------
REM  Resolve Python installation (prefer py launcher, fallback to python)
REM ---------------------------------------------------------------------
set "PYTHON_CMD="
for %%P in (py python) do (
    if not defined PYTHON_CMD (
        where %%P >nul 2>&1 && set "PYTHON_CMD=%%P"
    )
)

if not defined PYTHON_CMD (
    echo [ERROR] Python 3.9+ is required but was not found on PATH.
    echo         Install Python and ensure either ^"py^" or ^"python^" is available.
    goto :FAIL
)

REM ---------------------------------------------------------------------
REM  Ensure virtual environment exists
REM ---------------------------------------------------------------------
set "VENV_DIR=.venv"
set "VENV_PY=%VENV_DIR%\Scripts\python.exe"

if not exist "%VENV_PY%" (
    echo [SETUP] Creating virtual environment at %VENV_DIR%...
    call :CREATE_VENV "%PYTHON_CMD%" "%VENV_DIR%"
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        goto :FAIL
    )
    set "REFRESH_DEPS=1"
) else (
    set "REFRESH_DEPS=0"
)

set "PYTHON_BIN=%VENV_PY%"
if not exist "%PYTHON_BIN%" (
    echo [ERROR] Virtual environment python interpreter not found at %PYTHON_BIN%.
    goto :FAIL
)

REM ---------------------------------------------------------------------
REM  Install dependencies if needed (first run or requirements changed)
REM ---------------------------------------------------------------------
set "REQ_FILE=requirements.txt"
set "REQ_HASH_FILE=%VENV_DIR%\.requirements.hash"

if exist "%REQ_FILE%" (
    set "CURRENT_REQ_HASH="
    for /f "delims=" %%H in ('certutil -hashfile "%REQ_FILE%" MD5 ^| findstr /R /V "hash"') do (
        if not defined CURRENT_REQ_HASH set "CURRENT_REQ_HASH=%%H"
    )

    if not defined CURRENT_REQ_HASH (
        echo [WARN] Unable to compute requirements hash. Reinstalling dependencies.
        set "REFRESH_DEPS=1"
    )

    if not exist "%REQ_HASH_FILE%" (
        set "REFRESH_DEPS=1"
    ) else (
        set /p SAVED_REQ_HASH=<"%REQ_HASH_FILE%"
        if /I not "!CURRENT_REQ_HASH!"=="!SAVED_REQ_HASH!" set "REFRESH_DEPS=1"
    )

    if "!REFRESH_DEPS!"=="1" (
        echo [SETUP] Installing Python dependencies (this may take a moment)...
        "%PYTHON_BIN%" -m pip install --upgrade pip setuptools wheel >nul
        if errorlevel 1 (
            echo [ERROR] Failed to upgrade pip/setuptools.
            goto :FAIL
        )
        "%PYTHON_BIN%" -m pip install -r "%REQ_FILE%"
        if errorlevel 1 (
            echo [ERROR] Failed to install dependencies from %REQ_FILE%.
            goto :FAIL
        )
        echo !CURRENT_REQ_HASH!>"%REQ_HASH_FILE%"
    ) else (
        echo [SETUP] Dependencies already up to date.
    )
) else (
    echo [WARN] requirements.txt not found. Skipping dependency installation.
)

REM ---------------------------------------------------------------------
REM  Basic environment defaults for local development
REM ---------------------------------------------------------------------
if not defined FLASK_ENV set "FLASK_ENV=development"
if not defined FLASK_DEBUG set "FLASK_DEBUG=1"
set "PYTHONIOENCODING=utf-8"

REM ---------------------------------------------------------------------
REM  Detect existing running instance
REM ---------------------------------------------------------------------
call :CHECK_PORT 5001 APP_ONLINE
if /I "!APP_ONLINE!"=="HEALTHY" (
    echo [INFO] Email Management Tool is already running.
    echo [INFO] Opening dashboard in your default browser...
    start "" http://127.0.0.1:5001
    goto :SUCCESS
) else if /I "!APP_ONLINE!"=="BUSY" (
    echo [ERROR] Port 5001 is currently in use by another process.
    echo         Stop the other service or change FLASK_PORT before launching.
    goto :FAIL
)

call :CHECK_PORT 8587 SMTP_STATUS
if /I "!SMTP_STATUS!"=="BUSY" (
    echo [WARN] Port 8587 is currently in use. The SMTP proxy may fail to start.
)

REM ---------------------------------------------------------------------
REM  Launch application
REM ---------------------------------------------------------------------
echo [START] Booting Email Management Tool services...
start "Email Management Tool" "%PYTHON_BIN%" simple_app.py

REM Wait for health endpoint (up to 30 seconds)
echo [WAIT] Waiting for dev server to report healthy...
for /L %%S in (1,1,30) do (
    powershell -NoLogo -NoProfile -Command "try { (Invoke-WebRequest -Uri 'http://127.0.0.1:5001/healthz' -UseBasicParsing -TimeoutSec 2).StatusCode } catch { '' }" >"%TEMP%\emt_health.tmp"
    set /p STATUS_CODE=<"%TEMP%\emt_health.tmp"
    del "%TEMP%\emt_health.tmp" >nul 2>&1
    if "!STATUS_CODE!"=="200" goto :HEALTHY
    timeout /t 1 /nobreak >nul
)

echo [WARN] Health check did not respond in time. The app may still be starting.
goto :POST_LAUNCH

:HEALTHY
echo [OK] Dev server healthy on http://127.0.0.1:5001

:POST_LAUNCH
echo.
echo ============================================================
echo    WEB DASHBOARD:  http://127.0.0.1:5001
echo    SMTP PROXY:     localhost:8587
echo    LOGIN:          admin / admin123
echo ============================================================
echo.
echo The application is running in a separate console window.
echo Close that window or press Ctrl+C there to stop the server.
echo A browser window will open momentarily.

start "" http://127.0.0.1:5001
goto :SUCCESS

:CHECK_PORT
set "_PORT=%1"
set "_RESULT_VAR=%2"
set "_PORT_STATE=FREE"

powershell -NoLogo -NoProfile -Command "$port=%1; $baseUri='http://127.0.0.1:' + $port; $isHealthy=$false; try { $resp = Invoke-WebRequest -Uri ($baseUri + '/healthz') -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop; if ($resp.StatusCode -eq 200) { $isHealthy = $true } } catch {}; $listenerFound=$false; try { $netCmd = Get-Command Get-NetTCPConnection -ErrorAction Stop; if ($netCmd) { $listener = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue ^| Select-Object -First 1 -ExpandProperty OwningProcess; if ($listener) { $listenerFound = $true } } } catch {}; if (-not $listenerFound) { try { $netstatOutput = netstat -ano ^| Select-String ^(':' + $port^); if ($netstatOutput) { $listenerFound = $true } } catch {} }; if ($isHealthy) { Write-Host 'HEALTHY' } elseif ($listenerFound) { Write-Host 'BUSY' } else { Write-Host 'FREE' }" >"%TEMP%\emt_port_state.tmp"

set /p _PORT_STATE=<"%TEMP%\emt_port_state.tmp"
del "%TEMP%\emt_port_state.tmp" >nul 2>&1
set "%_RESULT_VAR%=%_PORT_STATE%"
exit /b 0

:CREATE_VENV
setlocal
set "_LAUNCHER=%~1"
set "_TARGET_DIR=%~2"
if /I "%_LAUNCHER%"=="py" (
    "%_LAUNCHER%" -3 -m venv "%_TARGET_DIR%" >nul 2>&1
) else (
    "%_LAUNCHER%" -m venv "%_TARGET_DIR%" >nul 2>&1
)
set "_EXITCODE=%ERRORLEVEL%"
endlocal & exit /b %_EXITCODE%

:SUCCESS
echo.
echo [DONE] All set! Happy moderating.
echo.
popd >nul
endlocal
exit /b 0

:FAIL
echo.
echo [FAILED] Unable to launch the Email Management Tool.
echo.
popd >nul
endlocal
exit /b 1
