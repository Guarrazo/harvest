@echo off
setlocal
cd /d "%~dp0.."
if "%~5"=="" (
  echo Usage: architecture_native_export_cp2077.cmd ^<layouts.json^> ^<assembly.json^> ^<templates.json^> ^<base_export.json^> ^<out.json^> [report.json] [building_id]
  exit /b 2
)
set "LAYOUTS=%~1"
set "ASSEMBLY=%~2"
set "TEMPLATES=%~3"
set "BASE=%~4"
set "OUT=%~5"
set "REPORT=%~6"
set "BUILDING=%~7"
set "PYTHONPATH=%CD%\src"
set "PYTHONEXE="
for /f "delims=" %%P in ('py -3 -c "import sys; print(sys.executable)" 2^>nul') do if not defined PYTHONEXE set "PYTHONEXE=%%P"
if not defined PYTHONEXE (
  echo NCIG: no Windows Python launcher found.
  exit /b 1
)
if defined BUILDING (
  if defined REPORT (
    "%PYTHONEXE%" -m ncig.cli architecture-native-export --layouts "%LAYOUTS%" --assembly "%ASSEMBLY%" --templates "%TEMPLATES%" --base "%BASE%" --out "%OUT%" --report "%REPORT%" --building-id "%BUILDING%"
  ) else (
    "%PYTHONEXE%" -m ncig.cli architecture-native-export --layouts "%LAYOUTS%" --assembly "%ASSEMBLY%" --templates "%TEMPLATES%" --base "%BASE%" --out "%OUT%" --building-id "%BUILDING%"
  )
) else if defined REPORT (
  "%PYTHONEXE%" -m ncig.cli architecture-native-export --layouts "%LAYOUTS%" --assembly "%ASSEMBLY%" --templates "%TEMPLATES%" --base "%BASE%" --out "%OUT%" --report "%REPORT%"
) else (
  "%PYTHONEXE%" -m ncig.cli architecture-native-export --layouts "%LAYOUTS%" --assembly "%ASSEMBLY%" --templates "%TEMPLATES%" --base "%BASE%" --out "%OUT%"
)
exit /b %ERRORLEVEL%
