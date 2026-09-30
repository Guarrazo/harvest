@echo off
setlocal
cd /d "%~dp0.."
if "%~3"=="" (
  echo Usage: prepare_native_architecture_remote.cmd ^<github-repo-url^> ^<mesh-probe.json^> ^<base-export.json^> [building_id] [with-decoration]
  echo Example: prepare_native_architecture_remote.cmd https://github.com/Guarrazo/harvest C:\Users\Guarrazo\Desktop\mesh_probe.json C:\Users\Guarrazo\Desktop\mesh_probe.json demo_shop_001
  exit /b 2
)
set "SOURCE=%~1"
set "PROBE=%~2"
set "BASE=%~3"
set "BUILDING=%~4"
set "WITH_DECORATION=%~5"
if not defined BUILDING set "BUILDING=demo_shop_001"
set "CACHE=build\remote_harvest"
set "TEMPLATES=build\native_templates.json"
set "REPORT=build\native_probe_report.json"
set "OUT=build\real_architecture_remote\native_architecture"
set "DECOR_CATALOG=build\real_architecture_remote\decoration_catalog.json"
set "DECOR_PLAN=build\real_architecture_remote\decoration\%BUILDING%.json"

call "%~dp0prepare_architecture_remote.cmd" "%SOURCE%"
if errorlevel 1 exit /b %ERRORLEVEL%

call "%~dp0native_probe_cp2077.cmd" "%PROBE%" "%REPORT%" "%TEMPLATES%" "%CACHE%\templates.json"
if errorlevel 1 exit /b %ERRORLEVEL%

if not exist "%OUT%" mkdir "%OUT%"
if errorlevel 1 (
  echo NCIG: no se pudo crear el directorio de salida: %OUT%
  exit /b 1
)

set "CATALOG=%OUT%\architecture_catalog.json"
set "ASSEMBLY=%OUT%\architecture_assembly.json"
if exist "%OUT%\architecture_catalog_bounded.json" (
  echo NCIG: using runtime-bounded architecture catalog.
  "%PYTHONEXE%" -m ncig.cli architecture-assemble --layouts "build\generated\layouts.json" --catalog "%OUT%\architecture_catalog_bounded.json" --out "%ASSEMBLY%"
  if errorlevel 1 exit /b %ERRORLEVEL%
) else (
  set "ASSEMBLY=%CACHE%\architecture_assembly.json"
)

if /I "%WITH_DECORATION%"=="with-decoration" (
  call "%~dp0prepare_decoration_remote.cmd" "%SOURCE%" "%BUILDING%"
  if errorlevel 1 exit /b %ERRORLEVEL%
  set "DECORARG=--decoration "%DECOR_PLAN%""
) else (
  set "DECORARG="
)
"%PYTHONEXE%" -m ncig.cli architecture-native-compose --layouts "build\generated\layouts.json" --assembly "%ASSEMBLY%" --templates "%TEMPLATES%" --base "%BASE%" --out "%OUT%\%BUILDING%.json" --report "%OUT%\%BUILDING%.report.json" --building-id "%BUILDING%" --streaming-margin 32 %DECORARG%
if errorlevel 1 exit /b %ERRORLEVEL%

set "AUDIT=%OUT%\%BUILDING%.audit.json"
"%PYTHONEXE%" -m ncig.cli architecture-native-audit --native "%OUT%\%BUILDING%.json" --layouts "build\generated\layouts.json" --assembly "%ASSEMBLY%" --templates "%TEMPLATES%" --out "%AUDIT%" --building-id "%BUILDING%" %DECORARG%
if errorlevel 1 exit /b %ERRORLEVEL%
if not exist "%AUDIT%" (
  echo NCIG: native audit command returned without creating: %AUDIT%
  exit /b 1
)

echo NCIG native architecture pipeline completed: %OUT%\%BUILDING%.json
echo NCIG native architecture audit: %AUDIT%
exit /b 0
