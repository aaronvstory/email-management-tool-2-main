@echo off
setlocal EnableExtensions
REM Simple launcher that delegates to PowerShell (no complex batch logic)

REM If PowerShell 7+ exists use pwsh, otherwise fall back to Windows PowerShell
where pwsh >nul 2>&1
if %ERRORLEVEL%==0 (
  pwsh -NoLogo -NoProfile -File ".\scripts\launcher.ps1"
  goto :eof
)

where powershell >nul 2>&1
if %ERRORLEVEL%==0 (
  powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -File ".\scripts\launcher.ps1"
  goto :eof
)

echo [ERROR] PowerShell not found. Please install PowerShell and try again.
exit /b 1
