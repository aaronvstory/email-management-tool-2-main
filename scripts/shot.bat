@echo off
REM ============================================================================
REM Professional Screenshot Kit Launcher
REM ============================================================================
REM
REM Usage:
REM   shot.bat                    - Interactive mode (prompts for everything)
REM   shot.bat quick              - Quick mode (auto-capture all links)
REM   shot.bat headless           - Headless mode
REM   shot.bat both               - Capture desktop + mobile
REM
REM Advanced:
REM   shot.bat BASE=http://... USER=admin PASS=secret VIEW=both
REM
REM ============================================================================

setlocal enabledelayedexpansion

set "SCRIPT_DIR=%~dp0"
set "PS_SCRIPT=%SCRIPT_DIR%shot.ps1"

REM Defaults (can be overridden)
set "BASE="
set "USER="
set "PASS="
set "HEADLESS=0"
set "VIEW="
set "MAX=25"
set "INCLUDE="
set "EXCLUDE="

REM Parse arguments
set "ARGS="
set "IS_QUICK=0"
set "IS_INTERACTIVE=1"

:parse_args
if "%~1"=="" goto check_interactive

REM Simple flags
if /i "%~1"=="quick" (
    set "ARGS=!ARGS! -Quick"
    set "IS_QUICK=1"
    set "IS_INTERACTIVE=0"
    shift
    goto parse_args
)
if /i "%~1"=="headless" (
    set "ARGS=!ARGS! -Headless"
    set "IS_INTERACTIVE=0"
    shift
    goto parse_args
)
if /i "%~1"=="both" (
    set "ARGS=!ARGS! -View both"
    set "VIEW=both"
    set "IS_INTERACTIVE=0"
    shift
    goto parse_args
)
if /i "%~1"=="mobile" (
    set "ARGS=!ARGS! -View mobile"
    set "VIEW=mobile"
    set "IS_INTERACTIVE=0"
    shift
    goto parse_args
)
if /i "%~1"=="desktop" (
    set "ARGS=!ARGS! -View desktop"
    set "VIEW=desktop"
    set "IS_INTERACTIVE=0"
    shift
    goto parse_args
)

REM Key=Value overrides (e.g., BASE=http://...)
echo %~1 | findstr /C:"=" >nul
if !errorlevel! equ 0 (
    set "%~1"
    set "IS_INTERACTIVE=0"
)

shift
goto parse_args

:check_interactive
REM If no arguments provided, use interactive mode
if !IS_INTERACTIVE!==1 (
    echo.
    echo ╔═══════════════════════════════════════════════════════════════╗
    echo ║             📸 Screenshot Kit - Interactive Mode             ║
    echo ╚═══════════════════════════════════════════════════════════════╝
    echo.
    pwsh -ExecutionPolicy Bypass -File "%PS_SCRIPT%" -Interactive
    goto end
)

:build_args
REM Build PowerShell arguments
if defined BASE set "ARGS=!ARGS! -Base '!BASE!'"
if defined USER set "ARGS=!ARGS! -User '!USER!'"
if defined PASS set "ARGS=!ARGS! -Pass '!PASS!'"
if "!HEADLESS!"=="1" set "ARGS=!ARGS! -Headless"
if defined VIEW set "ARGS=!ARGS! -View !VIEW!"
if defined MAX set "ARGS=!ARGS! -Max !MAX!"
if defined INCLUDE set "ARGS=!ARGS! -Include '!INCLUDE!'"
if defined EXCLUDE set "ARGS=!ARGS! -Exclude '!EXCLUDE!'"

:run
REM Run PowerShell script
echo Starting screenshot capture...
pwsh -ExecutionPolicy Bypass -Command "& '%PS_SCRIPT%' !ARGS!"

:end
if errorlevel 1 (
    echo.
    echo ❌ Screenshot capture failed
    pause
    exit /b 1
)

exit /b 0
