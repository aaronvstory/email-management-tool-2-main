@echo off
setlocal EnableExtensions

REM =====================================================================
REM  EMAIL MANAGEMENT TOOL - POLLING MODE LAUNCHER
REM =====================================================================

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

echo Starting Email Management Tool in POLLING mode...
echo    IMAP_DISABLE_IDLE=1
echo    IMAP_POLL_INTERVAL=15

set "IMAP_DISABLE_IDLE=1"
set "IMAP_POLL_INTERVAL=15"
set "FLASK_ENV=development"
set "FLASK_DEBUG=1"

call "%SCRIPT_DIR%launch.bat"

endlocal
exit /b 0
