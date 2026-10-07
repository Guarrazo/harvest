@echo off
setlocal EnableExtensions
cd /d "%~dp0.."

set "EXPORT=%~1"
set "BUILDING=%~2"
if not defined BUILDING set "BUILDING=auto_10712_industrial"
set "SECTORS=C:\CyberpunkExports\sectors"
set "BASE=examples\ncig_probe_exported.json"

if defined EXPORT if exist "%EXPORT%" set "BASE=%EXPORT%"
if not exist "%SECTORS%" (
  echo NCIG v0.32: exported streamingsector directory not found:
  echo   %SECTORS%
  exit /b 2
)

set "LAYOUTS=build\generated_auto\layouts_v0280.json"
if not exist "%LAYOUTS%" set "LAYOUTS=build\generated_auto\layouts.json"
if not exist "%LAYOUTS%" set "LAYOUTS=build\generated\layouts.json"
if not exist "%LAYOUTS%" (
  echo NCIG v0.32: completed structural layouts not found.
  echo Expected build\generated_auto\layouts_v0280.json or build\generated_auto\layouts.json
  exit /b 3
)

set "ASSEMBLY=build\real_architecture_remote\architecture_assembly_auto.json"
if not exist "%ASSEMBLY%" set "ASSEMBLY=build\real_architecture_remote\architecture_assembly.json"
if not exist "%ASSEMBLY%" (
  echo NCIG v0.31: current architecture assembly not found.
  echo Expected build\real_architecture_remote\architecture_assembly_auto.json
  exit /b 4
)

set "CACHE=build\remote_harvest"
set "BASE_TEMPLATES=%CACHE%\templates.json"
set "TEMPLATES=build\native_test\native_templates.json"
set "OUTDIR=build\native_test"
set "NATIVE=%OUTDIR%\%BUILDING%.json"
set "REPORT=%OUTDIR%\%BUILDING%.report.json"
set "AUDIT=%OUTDIR%\%BUILDING%.audit.json"
set "DECOR_CATALOG=%OUTDIR%\decoration_catalog.json"
set "DECOR_PLAN=%OUTDIR%\%BUILDING%.decoration.json"
set "USE_DECOR=0"

if not exist "%OUTDIR%" mkdir "%OUTDIR%"

set "PYTHONEXE="
for /f "delims=" %%P in ('py -3 -c "import sys; print(sys.executable)" 2^>nul') do if not defined PYTHONEXE set "PYTHONEXE=%%P"
if not defined PYTHONEXE (
  echo NCIG v0.31: Windows Python 3 was not found.
  exit /b 5
)

echo.
echo === NCIG v0.32: native test pipeline ===
echo Building: %BUILDING%
echo Layouts:  %LAYOUTS%
echo Assembly: %ASSEMBLY%
echo Base:     %BASE%
echo Sectors:  %SECTORS%
echo.

"%PYTHONEXE%" -c "import json,sys; b=r'%BUILDING%'; l=json.load(open(r'%LAYOUTS%',encoding='utf-8')); a=json.load(open(r'%ASSEMBLY%',encoding='utf-8')); lm={str((x.get('building') or {}).get('id')) for x in l.get('layouts',[]) if isinstance(x,dict)}; am={str(x.get('id')) for x in a.get('buildings',[]) if isinstance(x,dict)}; sys.exit(0 if b in lm and b in am else 12)"
if errorlevel 12 (
  echo NCIG v0.31: selected building was not found in the completed outputs:
  echo   %BUILDING%
  exit /b 12
)

rem Prefer templates already harvested from the installed mod/export cache, then harvest directly
rem from the user's exported streamingsector JSONs. This removes the old dependency on a second
rem manually prepared World Builder mesh probe.
if defined EXPORT if exist "%EXPORT%" (
  call "%~dp0native_probe_cp2077.cmd" "%EXPORT%" "build\native_test\native_probe_report.json" "%TEMPLATES%" "%BASE_TEMPLATES%"
  if errorlevel 1 exit /b %ERRORLEVEL%
)

rem Always merge the sector-derived templates. This fills any missing node types
rem from an explicit World Builder probe instead of letting that probe become a gate.
set "MERGED_TEMPLATES=build\native_test\native_templates_merged.json"
if exist "%TEMPLATES%" (
  "%PYTHONEXE%" -m ncig.cli native-template-harvest --root "%SECTORS%" --out "%MERGED_TEMPLATES%" --base-templates "%TEMPLATES%" --max-files 2048
) else if exist "%BASE_TEMPLATES%" (
  "%PYTHONEXE%" -m ncig.cli native-template-harvest --root "%SECTORS%" --out "%TEMPLATES%" --base-templates "%BASE_TEMPLATES%" --max-files 2048
) else (
  "%PYTHONEXE%" -m ncig.cli native-template-harvest --root "%SECTORS%" --out "%TEMPLATES%" --max-files 2048
)
if errorlevel 1 exit /b %ERRORLEVEL%
if exist "%MERGED_TEMPLATES%" move /Y "%MERGED_TEMPLATES%" "%TEMPLATES%" >nul


rem Add real .ent decoration when the remote harvest is present.
if exist "%CACHE%\harvest.json" (
  if not exist "%DECOR_CATALOG%" (
    "%PYTHONEXE%" -m ncig.cli decoration-catalog --harvest "%CACHE%\harvest.json" --out "%DECOR_CATALOG%" --max-per-role 80
    if errorlevel 1 exit /b %ERRORLEVEL%
  )
  "%PYTHONEXE%" -m ncig.cli decoration-plan --layout "%LAYOUTS%" --catalog "%DECOR_CATALOG%" --out "%DECOR_PLAN%" --building-id "%BUILDING%" --density 0.85
  if errorlevel 1 exit /b %ERRORLEVEL%
  set "USE_DECOR=1"
)

if "%USE_DECOR%"=="1" (
  "%PYTHONEXE%" -m ncig.cli architecture-native-compose --layouts "%LAYOUTS%" --assembly "%ASSEMBLY%" --templates "%TEMPLATES%" --base "%BASE%" --out "%NATIVE%" --report "%REPORT%" --building-id "%BUILDING%" --streaming-margin 32 --decoration "%DECOR_PLAN%"
) else (
  "%PYTHONEXE%" -m ncig.cli architecture-native-compose --layouts "%LAYOUTS%" --assembly "%ASSEMBLY%" --templates "%TEMPLATES%" --base "%EXPORT%" --out "%NATIVE%" --report "%REPORT%" --building-id "%BUILDING%" --streaming-margin 32
)
if errorlevel 1 exit /b %ERRORLEVEL%

if "%USE_DECOR%"=="1" (
  "%PYTHONEXE%" -m ncig.cli architecture-native-audit --native "%NATIVE%" --layouts "%LAYOUTS%" --assembly "%ASSEMBLY%" --templates "%TEMPLATES%" --out "%AUDIT%" --building-id "%BUILDING%" --decoration "%DECOR_PLAN%"
) else (
  "%PYTHONEXE%" -m ncig.cli architecture-native-audit --native "%NATIVE%" --layouts "%LAYOUTS%" --assembly "%ASSEMBLY%" --templates "%TEMPLATES%" --out "%AUDIT%" --building-id "%BUILDING%"
)
if errorlevel 1 exit /b %ERRORLEVEL%

echo.
echo === NCIG v0.32: native test BUILD COMPLETE ===
echo Native JSON : %NATIVE%
echo Build report: %REPORT%
echo Audit report: %AUDIT%
if "%USE_DECOR%"=="1" echo Decoration  : %DECOR_PLAN%
echo.
echo Next step is WolvenKit import and an in-game test of this ONE building.
exit /b 0
