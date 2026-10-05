@echo off
setlocal EnableExtensions
if "%~1"=="" (
  echo Usage: apply_v0301_detector_hotfix.cmd ^<NCIG repo root^>
  exit /b 2
)
set "ROOT=%~1"
if not exist "%ROOT%\src\ncig" (
  echo NCIG source directory not found: %ROOT%\src\ncig
  exit /b 2
)
set "SRC=%~dp0..\src\ncig\city_index_detect.py"
set "DST=%ROOT%\src\ncig\city_index_detect.py"
set "BACKUP=%ROOT%\build\patch_backups\v0301_detector_hotfix"
if not exist "%BACKUP%" mkdir "%BACKUP%"
if exist "%DST%" copy /y "%DST%" "%BACKUP%\city_index_detect.py.before_v0301" >nul
copy /y "%SRC%" "%DST%" >nul || exit /b 1
set "PYTHONEXE="
for /f "delims=" %%P in ('py -3 -c "import sys; print(sys.executable)" 2^>nul') do if not defined PYTHONEXE set "PYTHONEXE=%%P"
if not defined PYTHONEXE (
  echo NCIG v0.30.1: file installed, but Windows Python was not found for syntax verification.
  exit /b 0
)
set "PYTHONPATH=%ROOT%\src"
"%PYTHONEXE%" -m py_compile "%DST%"
if errorlevel 1 exit /b 3
echo NCIG v0.30.1 detector hotfix installed successfully.
exit /b 0
