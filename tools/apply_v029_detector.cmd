@echo off
setlocal EnableExtensions
cd /d "%~dp0.."
set "PYTHONEXE="
for /f "delims=" %%P in ('py -3 -c "import sys; print(sys.executable)" 2^>nul') do if not defined PYTHONEXE set "PYTHONEXE=%%P"
if not defined PYTHONEXE (
  for /f "delims=" %%P in ('where python.exe 2^>nul') do if not defined PYTHONEXE set "PYTHONEXE=%%P"
)
if not defined PYTHONEXE (
  echo NCIG: Windows Python not found.
  exit /b 1
)
if "%~1"=="" (
  echo Usage: apply_v029_detector.cmd ^<NCIG repo root^>
  echo Example: apply_v029_detector.cmd C:\Users\Guarrazo\Desktop\NCIG
  exit /b 2
)
set "ROOT=%~1"
set "PYTHONPATH=%ROOT%\src"
if not exist "%ROOT%\src\ncig\city_index_detect.py" (
  echo NCIG: target repo not found: %ROOT%
  exit /b 2
)
if not exist "%ROOT%\build\city_world_index.sqlite" (
  echo NCIG: missing %ROOT%\build\city_world_index.sqlite
  exit /b 2
)
if exist "%ROOT%\src\ncig\city_index_detect.py.v0253.bak" del /q "%ROOT%\src\ncig\city_index_detect.py.v0253.bak"
copy /y "%ROOT%\src\ncig\city_index_detect.py" "%ROOT%\src\ncig\city_index_detect.py.v0253.bak" >nul
copy /y "%~dp0..\src\ncig\city_index_detect.py" "%ROOT%\src\ncig\city_index_detect.py" >nul
if errorlevel 1 exit /b %ERRORLEVEL%
pushd "%ROOT%"
"%PYTHONEXE%" -m ncig.city_index_detect --input build\city_world_index.sqlite --out build\auto_building_candidates.json --cache-windows 256
set "RC=%ERRORLEVEL%"
popd
exit /b %RC%
