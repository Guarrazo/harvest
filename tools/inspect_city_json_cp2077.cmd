@echo off
setlocal EnableExtensions
cd /d "%~dp0.."
if "%~1"=="" (
  echo Usage: inspect_city_json_cp2077.cmd ^<streamingsector-json^>
  echo Example: inspect_city_json_cp2077.cmd C:\CyberpunkExports\sectors\always_loaded_0.streamingsector.json
  exit /b 2
)
set "INPUT=%~1"
set "PYTHONPATH=%CD%\src"
if not exist "%INPUT%" (
  echo NCIG: input sector not found: %INPUT%
  exit /b 2
)
set "PYTHONEXE="
for /f "delims=" %%P in ('py -3 -c "import sys; print(sys.executable)" 2^>nul') do if not defined PYTHONEXE set "PYTHONEXE=%%P"
if not defined PYTHONEXE (
  for /f "delims=" %%P in ('where python.exe 2^>nul') do if not defined PYTHONEXE set "PYTHONEXE=%%P"
)
if not defined PYTHONEXE (
  echo NCIG: Windows Python 3.x not found.
  exit /b 1
)
"%PYTHONEXE%" -m ncig.cli inspect-city-json --input "%INPUT%" --out build\sector_inspection.json
if errorlevel 1 exit /b %ERRORLEVEL%
echo NCIG: inspection written to build\sector_inspection.json
