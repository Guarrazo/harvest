$ErrorActionPreference = "Stop"
$env:PYTHONPATH = "$PSScriptRoot\..\src"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

python -m pytest -q

Remove-Item -Recurse -Force build\v02_demo -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force build\v02_demo | Out-Null

python -m ncig.cli scan `
  --input examples\runtime_observations.example.json `
  --out build\v02_demo\scan_report.json `
  --anchors-out build\v02_demo\buildings.json `
  --district watson

python -m ncig.cli generate `
  --input build\v02_demo\buildings.json `
  --out build\v02_demo\generated

python -m ncig.cli validate `
  --layout build\v02_demo\generated\layouts.json

python -m ncig.cli routes `
  --buildings build\v02_demo\buildings.json `
  --scan examples\runtime_observations.example.json `
  --out build\v02_demo\routes.json

python -m ncig.cli viewer `
  --preview-dir build\v02_demo\generated\previews `
  --out build\v02_demo\index.html

Write-Host "NCIG v0.2 demo complete: build\v02_demo"
