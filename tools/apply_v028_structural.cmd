@echo off
setlocal
cd /d "%~dp0.."
set "PYTHONPATH=%CD%\src"
set "PYTHONEXE="
for /f "delims=" %%P in ('py -3 -c "import sys; print(sys.executable)" 2^>nul') do if not defined PYTHONEXE set "PYTHONEXE=%%P"
if not defined PYTHONEXE (
  for /f "delims=" %%P in ('where python.exe 2^>nul') do if not defined PYTHONEXE set "PYTHONEXE=%%P"
)
if not defined PYTHONEXE (
  echo NCIG: Windows Python not found.
  exit /b 1
)
if not exist "build\generated_auto\layouts.json" (
  echo NCIG v0.28: build\generated_auto\layouts.json not found. Run the normal pipeline first.
  exit /b 2
)
set "CATALOG=build\real_architecture_remote\architecture_catalog_v0230_clean.json"
if not exist "%CATALOG%" set "CATALOG=build\real_architecture_remote\architecture_catalog_bounded.json"
if not exist "%CATALOG%" set "CATALOG=build\real_architecture_remote\architecture_catalog.json"
if not exist "%CATALOG%" (
  echo NCIG v0.28: architecture catalog not found.
  exit /b 2
)
if not exist "build\auto_building_candidates_access.json" (
  echo NCIG v0.28: access-audited candidate file not found. Falling back to no style profile metadata.
)

copy /y "build\generated_auto\layouts.json" "build\generated_auto\layouts_pre_v0280.json" >nul
"%PYTHONEXE%" -m ncig.structural_layout_upgrade --input build\generated_auto\layouts_pre_v0280.json --out build\generated_auto\layouts_v0280.json
if errorlevel 1 exit /b %ERRORLEVEL%
copy /y "build\generated_auto\layouts_v0280.json" "build\generated_auto\layouts.json" >nul

"%PYTHONEXE%" -m ncig.structural_connectivity --input build\generated_auto\layouts.json --out build\structural_connectivity_v0280.json
if errorlevel 1 exit /b %ERRORLEVEL%

if exist "build\auto_building_candidates_access.json" (
  echo NCIG v0.28: rebuilding style-aware architecture after structural upgrade.
  "%PYTHONEXE%" -m ncig.style_assembler --layouts build\generated_auto\layouts.json --profiles build\auto_building_candidates_access.json --catalog "%CATALOG%" --out build\real_architecture_remote\architecture_assembly_pre_v0280.json
  if errorlevel 1 exit /b %ERRORLEVEL%
) else (
  echo NCIG v0.28: rebuilding architecture without access profiles.
  "%PYTHONEXE%" -m ncig.cli architecture-assemble --layouts build\generated_auto\layouts.json --catalog "%CATALOG%" --out build\real_architecture_remote\architecture_assembly_pre_v0280.json
  if errorlevel 1 exit /b %ERRORLEVEL%
)
"%PYTHONEXE%" -m ncig.structural_assembly_upgrade --layouts build\generated_auto\layouts.json --assembly build\real_architecture_remote\architecture_assembly_pre_v0280.json --catalog "%CATALOG%" --out build\real_architecture_remote\architecture_assembly_auto_v0280.json
if errorlevel 1 exit /b %ERRORLEVEL%
copy /y "build\real_architecture_remote\architecture_assembly_auto_v0280.json" "build\real_architecture_remote\architecture_assembly_auto.json" >nul

echo NCIG v0.28 structural upgrade completed.
echo Layouts: build\generated_auto\layouts.json
echo Connectivity: build\structural_connectivity_v0280.json
echo Assembly: build\real_architecture_remote\architecture_assembly_auto.json
