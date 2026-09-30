@echo off
setlocal
cd /d "%~dp0.."
if "%~1"=="" (
  echo Usage: prepare_architecture_remote.cmd ^<github-repo-url^> [rebuild-catalog]
  echo Example: prepare_architecture_remote.cmd https://github.com/Guarrazo/harvest
  exit /b 2
)
set "SOURCE=%~1"
set "CACHE=build\remote_harvest"
call "%~dp0sync_harvest_github.cmd" "%SOURCE%" "%CACHE%"
if errorlevel 1 exit /b %ERRORLEVEL%
set "PYTHONPATH=%CD%\src"
set "HARVEST=%CD%\%CACHE%\harvest.json"
set "REMOTE_CATALOG=%CD%\%CACHE%\architecture_catalog.json"
set "LAYOUTS=%CD%\build\generated\layouts.json"
set "OUT=build\real_architecture_remote"
if not exist "%OUT%" mkdir "%OUT%"
if errorlevel 1 (
  echo NCIG: no se pudo crear el directorio de salida: %OUT%
  exit /b 1
)

set "PYTHONEXE="
for /f "delims=" %%P in ('py -3 -c "import sys; print(sys.executable)" 2^>nul') do if not defined PYTHONEXE set "PYTHONEXE=%%P"
if not defined PYTHONEXE for /f "delims=" %%P in ('where python.exe 2^>nul') do if not defined PYTHONEXE set "PYTHONEXE=%%P"
if not defined PYTHONEXE (
  echo NCIG: no Windows Python launcher found.
  exit /b 1
)
if not exist "%LAYOUTS%" (
  "%PYTHONEXE%" -m ncig.cli generate --input examples\buildings.json --out build\generated
  if errorlevel 1 exit /b %ERRORLEVEL%
)
if /I "%~2"=="rebuild-catalog" goto :REBUILD
if exist "%REMOTE_CATALOG%" (
  echo NCIG: reusing remote architecture catalog: %REMOTE_CATALOG%
  copy /Y "%REMOTE_CATALOG%" "%OUT%\architecture_catalog.json" >nul
  if errorlevel 1 (
    echo NCIG: no se pudo copiar el catalogo remoto al directorio de salida.
    exit /b 1
  )
  goto :ASSEMBLE
)
:REBUILD
"%PYTHONEXE%" -m ncig.cli architecture-catalog --harvest "%HARVEST%" --out "%OUT%\architecture_catalog.json" --interior-only
if errorlevel 1 exit /b %ERRORLEVEL%
:ASSEMBLE
"%PYTHONEXE%" -m ncig.cli architecture-assemble --layouts "%LAYOUTS%" --catalog "%OUT%\architecture_catalog.json" --out "%OUT%\architecture_assembly.json"
if errorlevel 1 exit /b %ERRORLEVEL%
"%PYTHONEXE%" -m ncig.cli architecture-audit --catalog "%OUT%\architecture_catalog.json" --assembly "%OUT%\architecture_assembly.json" --templates "%CACHE%\templates.json" --out "%OUT%\architecture_audit.json"
exit /b %ERRORLEVEL%
