@echo off
setlocal
cd /d "%~dp0.."
if "%~5"=="" (
  echo Usage: architecture_native_audit_cp2077.cmd ^<native.json^> ^<layouts.json^> ^<assembly.json^> ^<templates.json^> ^<out-report.json^> [building_id]
  exit /b 2
)
set "NATIVE=%~1"
set "LAYOUTS=%~2"
set "ASSEMBLY=%~3"
set "TEMPLATES=%~4"
set "OUT=%~5"
set "BUILDING=%~6"
set "PYTHONPATH=%CD%\src"
set "PYTHONEXE="
for /f "delims=" %%P in ('py -3 -c "import sys; print(sys.executable)" 2^>nul') do if not defined PYTHONEXE set "PYTHONEXE=%%P"
if not defined PYTHONEXE (
  echo NCIG: no Windows Python launcher found.
  exit /b 1
)
if defined BUILDING (
  "%PYTHONEXE%" -m ncig.cli architecture-native-audit --native "%NATIVE%" --layouts "%LAYOUTS%" --assembly "%ASSEMBLY%" --templates "%TEMPLATES%" --out "%OUT%" --building-id "%BUILDING%"
) else (
  "%PYTHONEXE%" -m ncig.cli architecture-native-audit --native "%NATIVE%" --layouts "%LAYOUTS%" --assembly "%ASSEMBLY%" --templates "%TEMPLATES%" --out "%OUT%"
)
exit /b %ERRORLEVEL%
