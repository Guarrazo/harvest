@echo off
setlocal EnableExtensions
cd /d "%~dp0.."
set "MANIFEST=%~1"
if not defined MANIFEST set "MANIFEST=build\collision_removal_manifest.json"
set "SECTORS=%~2"
if not defined SECTORS set "SECTORS=C:\CyberpunkExports\sectors"
set "OUT=%~3"
if not defined OUT set "OUT=build\collision_probes.json"
set "BUILDING=%~4"
set "LIMIT=%~5"
if not defined LIMIT set "LIMIT=1"
set "MODE="
if /I "%~6"=="--safe-only" set "MODE=--safe-only"
set "XLOUT=%~7"
set "XLOUT_ARG="
if defined XLOUT set XLOUT_ARG=--xl-out "%XLOUT%"

set "PYTHONEXE="
for /f "delims=" %%P in ('py -3 -c "import sys; print(sys.executable)" 2^>nul') do if not defined PYTHONEXE set "PYTHONEXE=%%P"
if not defined PYTHONEXE (
  for /f "delims=" %%P in ('where python.exe 2^>nul') do if not defined PYTHONEXE set "PYTHONEXE=%%P"
)
if not defined PYTHONEXE (
  echo NCIG: no Windows Python 3 installation found.
  exit /b 1
)
set "PYTHONPATH=%CD%\src"
if not exist "%MANIFEST%" (echo NCIG: manifest not found: %MANIFEST% & exit /b 2)
if not exist "%SECTORS%" (echo NCIG: sectors directory not found: %SECTORS% & exit /b 2)

if defined BUILDING (
  "%PYTHONEXE%" -m ncig.collision_probe --manifest "%MANIFEST%" --sectors "%SECTORS%" --out "%OUT%" --building-id "%BUILDING%" --limit "%LIMIT%" %MODE% %XLOUT_ARG%
) else (
  "%PYTHONEXE%" -m ncig.collision_probe --manifest "%MANIFEST%" --sectors "%SECTORS%" --out "%OUT%" --limit "%LIMIT%" %MODE% %XLOUT_ARG%
)
exit /b %ERRORLEVEL%
