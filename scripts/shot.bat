@echo off
setlocal
REM ── defaults you can override on the command line ───────────────
set BASE=http://127.0.0.1:5010
set USER=admin
set PASS=admin123
set HEADLESS=0
set VIEW=desktop   REM desktop | mobile | both
set MAX=25         REM max pages to shoot after scan
set INCLUDE=/,/dashboard,/emails,/compose,/diagnostics,/watchers,/rules,/accounts,/import
set EXCLUDE=/logout,/static,/api

REM ── pass-through overrides (e.g., shot.bat BASE=http://... VIEW=both) ─────
for %%A in (%*) do set %%A

pwsh -NoProfile -ExecutionPolicy Bypass -File "%~dp0shot.ps1" -Base "%BASE%" -User "%USER%" -Pass "%PASS%" -Headless:$([bool]%HEADLESS%) -View "%VIEW%" -Max %MAX% -Include "%INCLUDE%" -Exclude "%EXCLUDE%"
endlocal
