$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$env:PYTHONPATH = Join-Path $root 'src'
python -m ncig.cli generate --input (Join-Path $root 'examples\buildings.json') --out (Join-Path $root 'build')
python -m ncig.cli validate --layout (Join-Path $root 'build\layouts.json')
Write-Host "Demo generated in $root\build"
