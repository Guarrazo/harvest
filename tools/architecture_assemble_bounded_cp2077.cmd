@echo off
setlocal EnableExtensions
cd /d "%~dp0.."

set "LAYOUTS=%~1"
if not defined LAYOUTS set "LAYOUTS=build\generated\layouts.json"

set "CATALOG=%~2"
if not defined CATALOG set "CATALOG=build\real_architecture_remote\architecture_catalog_bounded.json"

set "OUT=%~3"
if not defined OUT set "OUT=build\real_architecture_remote\architecture_assembly_bounded.json"

if not exist "%LAYOUTS%" (
  echo NCIG: layouts not found: %LAYOUTS%
  exit /b 2
)
if not exist "%CATALOG%" (
  echo NCIG: bounded architecture catalog not found: %CATALOG%
  echo Run .\tools\merge_bounds_cp2077.cmd first.
  exit /b 2
)

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
"%PYTHONEXE%" -m ncig.cli architecture-assemble --layouts "%LAYOUTS%" --catalog "%CATALOG%" --out "%OUT%"
exit /b %ERRORLEVEL%
