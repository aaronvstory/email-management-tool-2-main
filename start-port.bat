@echo off
setlocal
set "PORT=%~1"
if not defined PORT set PORT=5001
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /r /c:":%PORT% .*LISTENING"') do taskkill /F /PID %%P
