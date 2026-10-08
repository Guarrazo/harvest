@echo off
setlocal
cd /d "%~dp0.."
if "%~1"=="" (
  echo Usage: prepare_decoration_remote.cmd ^<github-repo-url^> [building_id]
  exit /b 2
)
set "SOURCE=%~1"
set "BUILDING=%~2"
if not defined BUILDING set "BUILDING=demo_shop_001"
set "CACHE=build\remote_harvest"
set "CATALOG=build\real_architecture_remote\decoration_catalog.json"
set "LAYOUTS=build\generated_auto\layouts_v0280.json"
if not exist "%LAYOUTS%" set "LAYOUTS=build\generated_auto\layouts.json"
if not exist "%LAYOUTS%" set "LAYOUTS=build\generated\layouts.json"
set "OUT=build\real_architecture_remote\decoration"
set "PYTHONEXE="
for /f "delims=" %%P in ('py -3 -c "import sys; print(sys.executable)" 2^>nul') do if not defined PYTHONEXE set "PYTHONEXE=%%P"
if not defined PYTHONEXE for /f "delims=" %%P in ('where python.exe 2^>nul') do if not defined PYTHONEXE set "PYTHONEXE=%%P"
if not defined PYTHONEXE (
  echo NCIG: no Windows Python launcher found.
  exit /b 1
)
call "%~dp0prepare_architecture_remote.cmd" "%SOURCE%"
if errorlevel 1 exit /b %ERRORLEVEL%
if not exist "%LAYOUTS%" (
  "%PYTHONEXE%" -m ncig.cli generate --input examples\buildings.json --out build\generated
  if errorlevel 1 exit /b %ERRORLEVEL%
)
if not exist "%CATALOG%" (
  "%PYTHONEXE%" -m ncig.cli decoration-catalog --harvest "%CACHE%\harvest.json" --out "%CATALOG%"
  if errorlevel 1 exit /b %ERRORLEVEL%
)
if not exist "%OUT%" mkdir "%OUT%"
"%PYTHONEXE%" -m ncig.cli decoration-plan --layout "%LAYOUTS%" --catalog "%CATALOG%" --out "%OUT%\%BUILDING%.json" --building-id "%BUILDING%"
if errorlevel 1 exit /b %ERRORLEVEL%
echo NCIG decoration plan completed: %OUT%\%BUILDING%.json
exit /b 0
