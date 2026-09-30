@echo off
setlocal EnableExtensions
set "GAME=%~1"
if "%GAME%"=="" set "GAME=F:\Games\CP2077\Cyberpunk 2077"
set "INPUT=%GAME%\bin\x64\plugins\cyber_engine_tweaks\mods\NCIGBoundsHarvester\data\architecture_bounds.json"
set "CATALOG=%~2"
if "%CATALOG%"=="" set "CATALOG=%CD%\build\real_architecture_remote\architecture_catalog.json"
set "OUT=%~3"
if "%OUT%"=="" set "OUT=%CD%\build\real_architecture_remote\architecture_catalog_bounded.json"
if not exist "%INPUT%" (
  echo NCIG: bounds output not found: %INPUT%
  exit /b 2
)
py -3 -m ncig.cli merge-bounds --catalog "%CATALOG%" --bounds "%INPUT%" --out "%OUT%" --report "%OUT%.report.json"
