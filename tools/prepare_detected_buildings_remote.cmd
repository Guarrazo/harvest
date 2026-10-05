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
set "REBUILD_INDEX=0"
if not exist "build\city_world_index.sqlite" set "REBUILD_INDEX=1"
if not exist "build\city_world_index_manifest.json" set "REBUILD_INDEX=1"
if "%REBUILD_INDEX%"=="0" (
  findstr /C:"ncig-city-index-v3" "build\city_world_index_manifest.json" >nul
  if errorlevel 1 set "REBUILD_INDEX=1"
)
if "%REBUILD_INDEX%"=="1" (
  echo NCIG: building persistent city index. This is the expensive pass over the exported sectors.
  if exist "build\city_world_index.sqlite" del /f /q "build\city_world_index.sqlite"
  if exist "build\city_world_index_manifest.json" del /f /q "build\city_world_index_manifest.json"
  "%PYTHONEXE%" -m ncig.cli index-city-world --input "%SECTORS%" --out build\city_world_index.sqlite --manifest-out build\city_world_index_manifest.json
  if errorlevel 1 exit /b %ERRORLEVEL%
) else (
  echo NCIG: reusing compatible persistent city index: build\city_world_index.sqlite
)

set "REBUILD_PHYSICS=0"
if not exist "build\world_physics_index.sqlite" set "REBUILD_PHYSICS=1"
if exist "build\world_physics_index.json" (
  findstr /C:"ncig-world-physics-index-v1" "build\world_physics_index.json" >nul
  if errorlevel 1 set "REBUILD_PHYSICS=1"
) else set "REBUILD_PHYSICS=1"
if "%REBUILD_PHYSICS%"=="1" (
  echo NCIG 0.24.0: building persistent physics/proxy/door index. This is a one-time expensive pass.
  "%PYTHONEXE%" -m ncig.physics_index build --input "%SECTORS%" --out build\world_physics_index.sqlite --manifest-out build\world_physics_index.json
  if errorlevel 1 exit /b %ERRORLEVEL%
) else (
  echo NCIG: reusing compatible persistent physics index: build\world_physics_index.sqlite
)

"%PYTHONEXE%" -m ncig.city_index_detect --input build\city_world_index.sqlite --out build\auto_building_candidates.json
if errorlevel 1 exit /b %ERRORLEVEL%

echo NCIG 0.23.0: refining candidate buildability and rejecting likely false positives.
"%PYTHONEXE%" -m ncig.refine_pipeline candidates --input build\auto_building_candidates.json --out build\auto_building_candidates_refined.json
if errorlevel 1 exit /b %ERRORLEVEL%

echo NCIG 0.24.0: auditing proxies, explicit collision and real exterior door candidates.
"%PYTHONEXE%" -m ncig.world_audit annotate-candidates --input build\auto_building_candidates_refined.json --physics-index build\world_physics_index.sqlite --out build\auto_building_candidates_access.json --removal-manifest build\collision_removal_manifest.json
if errorlevel 1 exit /b %ERRORLEVEL%

"%PYTHONEXE%" -m ncig.cli candidates-to-buildings --input build\auto_building_candidates_access.json --out build\auto_buildings.json --min-score 72 --max-count %MAXCOUNT%
if errorlevel 1 exit /b %ERRORLEVEL%

"%PYTHONEXE%" -m ncig.cli generate --input build\auto_buildings.json --out build\generated_auto
if errorlevel 1 exit /b %ERRORLEVEL%

if exist "build\generated_auto\layouts.json" copy /y "build\generated_auto\layouts.json" "build\generated_auto\layouts_pre_v0230.json" >nul
if exist "build\generated_auto\layouts.json" (
  echo NCIG 0.23.0: refining interior topology/room variation while preserving the closed exterior envelope.
  "%PYTHONEXE%" -m ncig.refine_pipeline layouts --input build\generated_auto\layouts.json --out build\generated_auto\layouts_v0230.json
  if errorlevel 1 exit /b %ERRORLEVEL%
  copy /y "build\generated_auto\layouts_v0230.json" "build\generated_auto\layouts.json" >nul
)

set "CATALOG=build\real_architecture_remote\architecture_catalog_bounded.json"
if not exist "%CATALOG%" set "CATALOG=build\real_architecture_remote\architecture_catalog.json"
echo NCIG 0.23.0: filtering structural architecture assets: %CATALOG%
"%PYTHONEXE%" -m ncig.refine_pipeline catalog --input "%CATALOG%" --out build\real_architecture_remote\architecture_catalog_v0230_clean.json
if errorlevel 1 exit /b %ERRORLEVEL%
set "CATALOG=build\real_architecture_remote\architecture_catalog_v0230_clean.json"

echo NCIG 0.24.0: assembling architecture with exterior-style signatures from the real world.
"%PYTHONEXE%" -m ncig.style_assembler --layouts build\generated_auto\layouts.json --profiles build\auto_building_candidates_access.json --catalog "%CATALOG%" --out build\real_architecture_remote\architecture_assembly_auto.json
if errorlevel 1 exit /b %ERRORLEVEL%

echo NCIG 0.25.3: generating first exact collision probe from the safest removal target.
"%PYTHONEXE%" -m ncig.collision_probe --manifest "build\collision_removal_manifest.json" --sectors "%SECTORS%" --out "build\collision_probe_first_safe.json" --limit 1 --safe-only --xl-out "build\collision_probe_first_safe.archive.xl"
if errorlevel 1 echo NCIG: first collision probe could not resolve a safe target; continue with manual probe command.

echo NCIG automatic city target pipeline completed (v0.25.3 SQLite-spatial detector + collision probe layer).
echo Persistent city index: build\city_world_index.sqlite
echo Physics index: build\world_physics_index.sqlite
echo Physics manifest: build\world_physics_index.json
echo World manifest: build\world_manifest.json
echo Candidates: build\auto_building_candidates.json
echo Refined candidates: build\auto_building_candidates_refined.json
echo Access-audited candidates: build\auto_building_candidates_access.json
echo Collision removal evidence: build\collision_removal_manifest.json
echo First safe collision probe: build\collision_probe_first_safe.json
echo ArchiveXL draft (only generated with verified depot path): build\collision_probe_first_safe.archive.xl
echo Selected buildings: build\auto_buildings.json
echo Layouts: build\generated_auto\layouts.json
echo Clean architecture catalog: build\real_architecture_remote\architecture_catalog_v0230_clean.json
echo Style-aware assembly: build\real_architecture_remote\architecture_assembly_auto.json
