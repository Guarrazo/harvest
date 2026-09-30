@echo off
setlocal
cd /d "%~dp0.."
if "%~1"=="" (
  echo Usage: sync_harvest_github.cmd ^<github-repo-url^> [output-dir]
  echo Example: sync_harvest_github.cmd https://github.com/Guarrazo/harvest build\remote_harvest
  exit /b 2
)
set "SOURCE=%~1"
if "%~2"=="" (set "OUT=build\remote_harvest") else (set "OUT=%~2")

set "PYTHONEXE="
for /f "delims=" %%P in ('py -3 -c "import sys; print(sys.executable)" 2^>nul') do set "CAND=%%P"
if defined CAND if exist "%CAND%" set "PYTHONEXE=%CAND%"
if not defined PYTHONEXE for /f "delims=" %%P in ('where python.exe 2^>nul') do if not defined PYTHONEXE set "PYTHONEXE=%%P"
if not defined PYTHONEXE (
  echo NCIG: no usable Windows Python found.
  exit /b 1
)
set "PYTHONPATH=%CD%\src"
"%PYTHONEXE%" -m ncig.cli sync-harvest --source "%SOURCE%" --out "%OUT%"
exit /b %ERRORLEVEL%
