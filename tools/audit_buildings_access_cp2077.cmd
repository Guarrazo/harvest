@echo off
setlocal EnableExtensions
cd /d "%~dp0.."
set "CANDIDATES=%~1"
if not defined CANDIDATES set "CANDIDATES=build\auto_building_candidates_refined.json"
set "INDEX=%~2"
if not defined INDEX set "INDEX=build\world_physics_index.sqlite"
set "OUT=%~3"
if not defined OUT set "OUT=build\auto_building_candidates_access.json"
set "REMOVALS=%~4"
if not defined REMOVALS set "REMOVALS=build\collision_removal_manifest.json"
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
if not exist "%CANDIDATES%" ( echo NCIG: candidates not found: %CANDIDATES% & exit /b 2 )
if not exist "%INDEX%" ( echo NCIG: physics index not found: %INDEX% & echo Run .\tools\prepare_detected_buildings_remote.cmd once first. & exit /b 2 )
"%PYTHONEXE%" -m ncig.world_audit annotate-candidates --input "%CANDIDATES%" --physics-index "%INDEX%" --out "%OUT%" --removal-manifest "%REMOVALS%"
exit /b %ERRORLEVEL%
