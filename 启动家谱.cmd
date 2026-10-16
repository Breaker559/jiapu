@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1" -OpenBrowser %*
set "jiapuExitCode=%errorlevel%"
pause
exit /b %jiapuExitCode%
