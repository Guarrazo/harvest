@echo off
setlocal
cd /d "%~dp0.."
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0architecture_catalog_cp2077.ps1" %*
exit /b %ERRORLEVEL%
