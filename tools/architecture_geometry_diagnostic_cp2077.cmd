@echo off
setlocal EnableExtensions
cd /d "%~dp0.."

set "PYTHONEXE="
for /f "delims=" %%P in ('py -3 -c "import sys; print(sys.executable)" 2^>nul') do if not defined PYTHONEXE set "PYTHONEXE=%%P"
if not defined PYTHONEXE (
  for /f "delims=" %%P in ('where python.exe 2^>nul') do (
    echo %%P | findstr /I /C:"WindowsApps" /C:"MSYS2" /C:"devkitPro" /C:"Cygwin" /C:"MinGW" >nul
    if errorlevel 1 if not defined PYTHONEXE set "PYTHONEXE=%%P"
  )
)
if not defined PYTHONEXE (
  echo NCIG: no suitable Windows Python 3 installation found.
  exit /b 1
)

set "PYTHONPATH=%CD%\src"
"%PYTHONEXE%" tools\architecture_geometry_diagnostic.py %*
exit /b %ERRORLEVEL%
