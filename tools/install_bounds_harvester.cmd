@echo off
setlocal EnableExtensions EnableDelayedExpansion
set "GAME=%~1"
if "%GAME%"=="" set "GAME=F:\Games\CP2077\Cyberpunk 2077"
set "CATALOG=%~2"
if "%CATALOG%"=="" set "CATALOG=%CD%\build\real_architecture_remote\architecture_catalog.json"
set "PYTHONEXE="
where py >nul 2>nul && set "PYTHONEXE=py -3"
if not defined PYTHONEXE (
  for /f "delims=" %%P in ('where python.exe 2^>nul') do (
    echo %%P | findstr /I /C:"WindowsApps" /C:"MSYS2" /C:"devkitPro" /C:"Cygwin" /C:"MinGW" >nul
    if errorlevel 1 if not defined PYTHONEXE set "PYTHONEXE=%%P"
  )
)
if not defined PYTHONEXE (
  echo NCIG: no suitable Windows Python found.
  exit /b 2
)
if not exist "%CATALOG%" (
  echo NCIG: catalog not found: %CATALOG%
  exit /b 2
)
set "TARGET_DIR=%GAME%\bin\x64\plugins\cyber_engine_tweaks\mods\NCIGBoundsHarvester"
if not exist "%TARGET_DIR%\data" mkdir "%TARGET_DIR%\data"
copy /Y "%~dp0..\cet\NCIGBoundsHarvester\init.lua" "%TARGET_DIR%\init.lua" >nul || exit /b 3
"%PYTHONEXE%" -m ncig.cli bounds-targets --catalog "%CATALOG%" --out "%TARGET_DIR%\data\architecture_bounds_targets.json"
if errorlevel 1 exit /b %ERRORLEVEL%
echo NCIG bounds harvester installed at:
echo %TARGET_DIR%
echo Launch Cyberpunk once and leave CET running until the harvester reports completion.
