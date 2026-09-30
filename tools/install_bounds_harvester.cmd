@echo off
setlocal EnableExtensions

rem NCIG bounds harvester installer.
rem Resolve the repository root from this script, not from the caller's current directory.
set "ROOT=%~dp0.."
set "GAME=%~1"
if "%GAME%"=="" set "GAME=F:\Games\CP2077\Cyberpunk 2077"
set "CATALOG=%~2"
if "%CATALOG%"=="" set "CATALOG=%ROOT%\build\real_architecture_remote\architecture_catalog.json"

rem Resolve a real Python executable. Do not put "py -3" into a variable that is
rem later quoted as one executable path (that was the source of the previous error).
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
  echo NCIG: install Python 3.11+ or make py.exe available in PATH.
  exit /b 2
)

if not exist "%CATALOG%" (
  echo NCIG: catalog not found: %CATALOG%
  exit /b 2
)

set "TARGET_DIR=%GAME%\bin\x64\plugins\cyber_engine_tweaks\mods\NCIGBoundsHarvester"
if not exist "%TARGET_DIR%\data" mkdir "%TARGET_DIR%\data"
if errorlevel 1 exit /b 3

copy /Y "%ROOT%\cet\NCIGBoundsHarvester\init.lua" "%TARGET_DIR%\init.lua" >nul || exit /b 3

set "PYTHONPATH=%ROOT%\src"
"%PYTHONEXE%" -m ncig.cli bounds-targets --catalog "%CATALOG%" --out "%TARGET_DIR%\data\architecture_bounds_targets.json"
if errorlevel 1 exit /b %ERRORLEVEL%

echo NCIG bounds harvester installed at:
echo %TARGET_DIR%
echo Launch Cyberpunk once and leave CET running until the harvester reports completion.
