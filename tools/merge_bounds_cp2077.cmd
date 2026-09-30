@echo off
setlocal EnableExtensions
set "ROOT=%~dp0.."
set "GAME=%~1"
if "%GAME%"=="" set "GAME=F:\Games\CP2077\Cyberpunk 2077"
set "INPUT=%GAME%\bin\x64\plugins\cyber_engine_tweaks\mods\NCIGBoundsHarvester\data\architecture_bounds.json"
set "CATALOG=%~2"
if "%CATALOG%"=="" set "CATALOG=%ROOT%\build\real_architecture_remote\architecture_catalog.json"
set "OUT=%~3"
if "%OUT%"=="" set "OUT=%ROOT%\build\real_architecture_remote\architecture_catalog_bounded.json"

set "PYTHONEXE="
for /f "delims=" %%P in ('py -3 -c "import sys; print(sys.executable)" 2^>nul') do if not defined PYTHONEXE set "PYTHONEXE=%%P"
if not defined PYTHONEXE (
  for /f "delims=" %%P in ('where python.exe 2^>nul') do (
    echo %%P | findstr /I /C:"WindowsApps" /C:"MSYS2" /C:"devkitPro" /C:"Cygwin" /C:"MinGW" >nul
    if errorlevel 1 if not defined PYTHONEXE set "PYTHONEXE=%%P"
  )
)
if not defined PYTHONEXE (
  echo NCIG: no suitable Windows Python 3 installation found.
  exit /b 2
)
if not exist "%INPUT%" (
  echo NCIG: bounds output not found: %INPUT%
  exit /b 2
)
if not exist "%CATALOG%" (
  echo NCIG: catalog not found: %CATALOG%
  exit /b 2
)
set "PYTHONPATH=%ROOT%\src"
"%PYTHONEXE%" -m ncig.cli merge-bounds --catalog "%CATALOG%" --bounds "%INPUT%" --out "%OUT%" --report "%OUT%.report.json"
exit /b %ERRORLEVEL%
