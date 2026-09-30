@echo off
setlocal
cd /d "%~dp0.."
if "%~1"=="" (
  echo Usage: native_probe_cp2077.cmd ^<export.json^> [report.json] [templates.json] [base_templates.json]
  echo Example: native_probe_cp2077.cmd C:\Users\Guarrazo\Desktop\mesh_probe.json
  exit /b 2
)
set "INPUT=%~1"
set "REPORT=%~2"
if not defined REPORT set "REPORT=build\mesh_probe_report.json"
set "TEMPLATES=%~3"
if not defined TEMPLATES set "TEMPLATES=build\templates_probe.json"
set "BASE=%~4"
if not defined BASE if exist "build\remote_harvest\templates.json" set "BASE=build\remote_harvest\templates.json"

set "PYTHONPATH=%CD%\src"
set "PYTHONEXE="
for /f "delims=" %%P in ('py -3 -c "import sys; print(sys.executable)" 2^>nul') do if not defined PYTHONEXE set "PYTHONEXE=%%P"
if not defined PYTHONEXE (
  echo NCIG: no Windows Python launcher found.
  exit /b 1
)

if defined BASE (
  "%PYTHONEXE%" -m ncig.cli native-probe --input "%INPUT%" --out "%REPORT%" --templates-out "%TEMPLATES%" --base-templates "%BASE%"
) else (
  "%PYTHONEXE%" -m ncig.cli native-probe --input "%INPUT%" --out "%REPORT%" --templates-out "%TEMPLATES%"
)
exit /b %ERRORLEVEL%
