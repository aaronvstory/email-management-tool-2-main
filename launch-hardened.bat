@echo off
setlocal EnableExtensions EnableDelayedExpansion

rem ===== Minimal, hardened launcher =====
set "PORT=%~1"
if not defined PORT set "PORT=5001"

echo ============================================================
echo    EMAIL MANAGEMENT TOOL - QUICK LAUNCHER
echo ============================================================

rem Kill anything listening on the chosen port (best effort)
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /r /c:":%PORT% .*LISTENING"') do (
  echo Killing PID %%P on port %PORT%...
  taskkill /F /PID %%P >NUL 2>&1
)

rem Prefer Python 3.11 if available
where py >NUL 2>&1 && py -3.11 -V >NUL 2>&1
if %ERRORLEVEL%==0 (
  set "PY=py -3.11"
) else (
  set "PY=python"
)

echo Starting server on port %PORT% ...
%PY% simple_app.py --port %PORT%
exit /b %ERRORLEVEL%
