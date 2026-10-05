@echo off
setlocal EnableExtensions
cd /d "%~dp0.."
set "SRC=%~dp0..\src\ncig"

if "%~1"=="" (
  echo Usage: install_missing_v028_v029.cmd ^<NCIG repo root^>
  echo Example: install_missing_v028_v029.cmd C:\Users\Guarrazo\Desktop\NCIG
  exit /b 2
)
set "ROOT=%~1"

if not exist "%ROOT%\src\ncig" (
  echo NCIG: target repo not found: %ROOT%\src\ncig
  exit /b 2
)

set "BACKUP=%ROOT%\build\patch_backups\v028_v029_unified"
if not exist "%BACKUP%" mkdir "%BACKUP%"

for %%F in (city_index_detect.py structural_layout_upgrade.py structural_assembly_upgrade.py structural_connectivity.py) do (
  if exist "%ROOT%\src\ncig\%%F" copy /y "%ROOT%\src\ncig\%%F" "%BACKUP%\%%F.before_unified" >nul
)

copy /y "%SRC%\city_index_detect.py" "%ROOT%\src\ncig\city_index_detect.py" >nul || exit /b 1
copy /y "%SRC%\structural_layout_upgrade.py" "%ROOT%\src\ncig\structural_layout_upgrade.py" >nul || exit /b 1
copy /y "%SRC%\structural_assembly_upgrade.py" "%ROOT%\src\ncig\structural_assembly_upgrade.py" >nul || exit /b 1
copy /y "%SRC%\structural_connectivity.py" "%ROOT%\src\ncig\structural_connectivity.py" >nul || exit /b 1
copy /y "%~dp0apply_v028_structural.cmd" "%ROOT%\tools\apply_v028_structural.cmd" >nul || exit /b 1

set "PYTHONEXE="
for /f "delims=" %%P in ('py -3 -c "import sys; print(sys.executable)" 2^>nul') do if not defined PYTHONEXE set "PYTHONEXE=%%P"
if not defined PYTHONEXE (
  for /f "delims=" %%P in ('where python.exe 2^>nul') do if not defined PYTHONEXE set "PYTHONEXE=%%P"
)
if not defined PYTHONEXE (
  echo NCIG: Windows Python not found. Files installed; run syntax checks manually.
  exit /b 0
)

set "PYTHONPATH=%ROOT%\src"
"%PYTHONEXE%" -m py_compile "%ROOT%\src\ncig\city_index_detect.py" "%ROOT%\src\ncig\structural_layout_upgrade.py" "%ROOT%\src\ncig\structural_assembly_upgrade.py" "%ROOT%\src\ncig\structural_connectivity.py"
if errorlevel 1 (
  echo NCIG: syntax check failed. Restore files from %BACKUP% if needed.
  exit /b 3
)

echo.
echo NCIG unified missing-patches install complete.
echo Included: v0.28.0 structural + v0.29.0 disk-safe/resumable detector.
echo Backup: %BACKUP%
echo NOTE: this installer does NOT run detection or structural post-processing automatically.
echo.
exit /b 0
