[CmdletBinding()]
param([string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path)
$ErrorActionPreference = 'Stop'
$env:PYTHONPATH = Join-Path $ProjectRoot 'src'

Write-Host "NCIG Python diagnostic"
Write-Host "Project: $ProjectRoot"
Write-Host "PYTHONPATH: $env:PYTHONPATH"

$pyCmd = Get-Command py.exe -ErrorAction SilentlyContinue
if ($pyCmd) {
  Write-Host "py.exe: $($pyCmd.Source)"
  & $pyCmd.Source -3 -c "import sys; print(sys.version); print(sys.executable)"
  if ($LASTEXITCODE -eq 0) {
    & $pyCmd.Source -3 -c "import ncig; print('NCIG OK:', ncig.__file__)"
    if ($LASTEXITCODE -eq 0) { exit 0 }
  }
} else { Write-Host 'py.exe: no disponible' }

$python = Get-Command python.exe -All -ErrorAction SilentlyContinue
if ($python) {
  foreach ($p in $python) {
    Write-Host "python.exe: $($p.Source)"
    & $p.Source -c "import sys; print(sys.version); print(sys.executable)" 2>$null
    & $p.Source -c "import ncig; print('NCIG OK:', ncig.__file__)" 2>$null
    if ($LASTEXITCODE -eq 0) { exit 0 }
  }
} else { Write-Host 'python.exe: no disponible' }

throw 'No hay un Python 3.11+ de Windows que pueda importar ncig. Usa py -3 o instala Python 3.11+ para Windows.'
