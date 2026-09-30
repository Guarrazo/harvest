@echo off
setlocal
cd /d "%~dp0.."
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0harvest_cp2077.ps1" %*
exit /b %ERRORLEVEL%
