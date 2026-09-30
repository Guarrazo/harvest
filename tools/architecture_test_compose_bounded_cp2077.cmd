@echo off
setlocal EnableExtensions
cd /d "%~dp0.."

set "LAYOUTS=%~1"
if not defined LAYOUTS set "LAYOUTS=build\generated\layouts.json"
set "ASSEMBLY=%~2"
if not defined ASSEMBLY set "ASSEMBLY=build\real_architecture_remote\architecture_assembly_bounded.json"
set "TEMPLATES=%~3"
if not defined TEMPLATES set "TEMPLATES=build\mesh_probe_templates.json"
set "BASE=%~4"
if not defined BASE set "BASE=C:\Users\Guarrazo\Desktop\mesh_probe.json"
set "BUILDING=%~5"
if not defined BUILDING set "BUILDING=demo_shop_001"
set "MARGIN=%~6"
if not defined MARGIN set "MARGIN=128"
set "OUT=%~7"
if not defined OUT set "OUT=build\real_architecture_remote\native_architecture\%BUILDING%_composed.json"
set "REPORT=%~8"
if not defined REPORT set "REPORT=build\real_architecture_remote\native_architecture\%BUILDING%_composed.report.json"

if not exist "%LAYOUTS%" ( echo NCIG: layouts not found: %LAYOUTS% & exit /b 2 )
if not exist "%ASSEMBLY%" ( echo NCIG: assembly not found: %ASSEMBLY% & exit /b 2 )
if not exist "%TEMPLATES%" ( echo NCIG: templates not found: %TEMPLATES% & exit /b 2 )
if not exist "%BASE%" ( echo NCIG: base export not found: %BASE% & exit /b 2 )

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
"%PYTHONEXE%" -m ncig.cli architecture-native-compose --layouts "%LAYOUTS%" --assembly "%ASSEMBLY%" --templates "%TEMPLATES%" --base "%BASE%" --out "%OUT%" --report "%REPORT%" --building-id "%BUILDING%" --streaming-margin %MARGIN%
exit /b %ERRORLEVEL%
