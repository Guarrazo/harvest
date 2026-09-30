@echo off
setlocal EnableExtensions
cd /d "%~dp0.."
if "%~2"=="" (
  echo Usage: prepare_detected_buildings_remote.cmd ^<github-repo-url^> ^<streamingsector-json-directory^> [max_count]
  echo Example: prepare_detected_buildings_remote.cmd https://github.com/Guarrazo/harvest C:\CyberpunkExports\sectors 10
  exit /b 2
)
set "SOURCE=%~1"
set "SECTORS=%~2"
set "MAXCOUNT=%~3"
if not defined MAXCOUNT set "MAXCOUNT=10"
set "PYTHONPATH=%CD%\src"
if not exist "%SECTORS%" (
  echo NCIG: sector directory not found: %SECTORS%
  exit /b 2
)
set "PYTHONEXE="
for /f "delims=" %%P in ('py -3 -c "import sys; print(sys.executable)" 2^>nul') do if not defined PYTHONEXE set "PYTHONEXE=%%P"
if not defined PYTHONEXE (
  for /f "delims=" %%P in ('where python.exe 2^>nul') do if not defined PYTHONEXE set "PYTHONEXE=%%P"
)
if not defined PYTHONEXE (
  echo NCIG: Windows Python not found.
  exit /b 1
)
call "%~dp0prepare_architecture_remote.cmd" "%SOURCE%"
if errorlevel 1 exit /b %ERRORLEVEL%
"%PYTHONEXE%" -m ncig.cli detect-buildings --input "%SECTORS%" --out build\auto_building_candidates.json
if errorlevel 1 exit /b %ERRORLEVEL%
"%PYTHONEXE%" -m ncig.cli candidates-to-buildings --input build\auto_building_candidates.json --out build\auto_buildings.json --min-score 75 --max-count %MAXCOUNT%
if errorlevel 1 exit /b %ERRORLEVEL%
"%PYTHONEXE%" -m ncig.cli generate --input build\auto_buildings.json --out build\generated_auto
if errorlevel 1 exit /b %ERRORLEVEL%
"%PYTHONEXE%" -m ncig.cli architecture-assemble --layouts build\generated_auto\layouts.json --catalog build\real_architecture_remote\architecture_catalog.json --out build\real_architecture_remote\architecture_assembly_auto.json
if errorlevel 1 exit /b %ERRORLEVEL%
echo NCIG automatic target pipeline completed.
echo Candidates: build\auto_building_candidates.json
echo Selected buildings: build\auto_buildings.json
echo Layouts: build\generated_auto\layouts.json
echo Assembly: build\real_architecture_remote\architecture_assembly_auto.json
