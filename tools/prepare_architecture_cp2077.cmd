@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0prepare_architecture_cp2077.ps1" %*
exit /b %ERRORLEVEL%
