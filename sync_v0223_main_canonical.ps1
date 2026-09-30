$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Repo = 'https://raw.githubusercontent.com/Guarrazo/harvest/main'
$files = @(
  'src/ncig/generator.py',
  'src/ncig/architecture_assembler.py',
  'src/ncig/native_collision.py',
  'src/ncig/cli.py',
  'src/ncig/__init__.py',
  'pyproject.toml',
  'CHANGELOG.md',
  'tools/architecture_geometry_diagnostic.py',
  'tools/architecture_geometry_diagnostic_cp2077.cmd'
)
$stage = Join-Path $Root '.ncig_v0223_sync'
if (Test-Path $stage) { Remove-Item $stage -Recurse -Force }
New-Item -ItemType Directory -Path $stage | Out-Null
foreach ($rel in $files) {
  $dest = Join-Path $stage $rel
  New-Item -ItemType Directory -Path (Split-Path -Parent $dest) -Force | Out-Null
  Write-Host "Fetching $rel"
  Invoke-WebRequest -UseBasicParsing -Uri "$Repo/$rel" -OutFile $dest
}
$checks = @{
  'src/ncig/architecture_assembler.py' = 'def assemble_room('
  'src/ncig/generator.py' = 'margin = 0.0'
  'src/ncig/native_collision.py' = 'continuous_floor_per_floor_plus_room_shell_walls_with_door_openings'
  'src/ncig/cli.py' = '"generator_version": "0.22.3"'
  'src/ncig/__init__.py' = '__version__ = "0.22.3"'
  'pyproject.toml' = 'version = "0.22.3"'
}
foreach ($rel in $checks.Keys) {
  $txt = [IO.File]::ReadAllText((Join-Path $stage $rel))
  if (-not $txt.Contains($checks[$rel])) { throw "Validation failed for $rel" }
}
foreach ($rel in $files) {
  $target = Join-Path $Root $rel
  if (Test-Path $target) { [IO.File]::Copy($target, "$target.bak_v0223_sync2", $true) }
  New-Item -ItemType Directory -Path (Split-Path -Parent $target) -Force | Out-Null
  Copy-Item (Join-Path $stage $rel) $target -Force
  Write-Host "Synced: $rel"
}
Remove-Item $stage -Recurse -Force
$py = $null
try { $py = Get-Command py.exe -ErrorAction Stop | Select-Object -First 1 -ExpandProperty Source } catch {}
if ($py) {
  & $py -3 -m py_compile (Join-Path $Root 'src/ncig/generator.py') (Join-Path $Root 'src/ncig/architecture_assembler.py') (Join-Path $Root 'src/ncig/native_collision.py') (Join-Path $Root 'src/ncig/cli.py')
  if ($LASTEXITCODE -ne 0) { throw 'Python syntax verification failed.' }
  Write-Host 'Python syntax verification: OK'
}
Write-Host 'NCIG v0.22.3 canonical sync completed.'
