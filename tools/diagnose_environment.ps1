[CmdletBinding()]
param([string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path)
$ErrorActionPreference = 'Continue'
$env:PYTHONPATH = Join-Path $ProjectRoot 'src'
Write-Host '=== NCIG environment diagnostic ==='
Write-Host "ProjectRoot: $ProjectRoot"
Write-Host "PYTHONPATH:  $env:PYTHONPATH"
Write-Host ''
Write-Host '--- py.exe ---'
Get-Command py.exe -All | Format-Table Source,CommandType -AutoSize
Write-Host '--- python.exe ---'
Get-Command python.exe -All | Format-Table Source,CommandType -AutoSize
Write-Host '--- py -3 ---'
$py = Get-Command py.exe -ErrorAction SilentlyContinue
if ($py) { & $py.Source -3 --version; & $py.Source -3 -c "import sys; print(sys.executable)" }
Write-Host '--- python ---'
$pythons = Get-Command python.exe -All -ErrorAction SilentlyContinue
foreach ($p in $pythons) { & $p.Source --version; & $p.Source -c "import sys; print(sys.executable)" }
Write-Host '--- NCIG import candidates ---'
foreach ($p in $pythons) { & $p.Source -c "import ncig; print(ncig.__file__)" 2>$null }
if ($py) { & $py.Source -3 -c "import ncig; print(ncig.__file__)" 2>$null }
