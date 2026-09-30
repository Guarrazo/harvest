$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Repo = 'https://raw.githubusercontent.com/Guarrazo/harvest/main'
$files = @(
  'src/ncig/architecture_catalog.py',
  'src/ncig/architecture_assembler.py',
  'src/ncig/native_collision.py',
  'src/ncig/target_detector.py',
  'src/ncig/generator.py',
  'src/ncig/cli.py',
  'src/ncig/__init__.py',
  'src/ncig/io.py',
  'pyproject.toml',
  'CHANGELOG.md',
  'docs/V0.22.5_ENTRY_AND_DETECTION.md',
  'tools/prepare_detected_buildings_remote.cmd',
  'tests/test_v021_geometry.py',
  'tests/test_v021_collision_and_composition.py',
  'tests/test_v0225_entry_and_collision.py'
)
$stage = Join-Path $Root '.ncig_v0225_sync'
if (Test-Path $stage) { Remove-Item $stage -Recurse -Force }
New-Item -ItemType Directory -Path $stage | Out-Null

foreach ($rel in $files) {
  $dest = Join-Path $stage $rel
  New-Item -ItemType Directory -Path (Split-Path -Parent $dest) -Force | Out-Null
  Write-Host "Fetching $rel"
  Invoke-WebRequest -UseBasicParsing -Uri "$Repo/$rel" -OutFile $dest
}

$checks = @(
  @('src/ncig/architecture_assembler.py','DEFAULT_DOOR_WIDTH = 1.15'),
  @('src/ncig/architecture_assembler.py','DEFAULT_DOOR_HEIGHT = 2.10'),
  @('src/ncig/architecture_assembler.py','def _needs_backface'),
  @('src/ncig/architecture_assembler.py','wall_backface'),
  @('src/ncig/native_collision.py','DOOR_GAP = 1.15'),
  @('src/ncig/native_collision.py','opening_side = "north" if ry >= 0 else "south"'),
  @('src/ncig/target_detector.py','entry_local_x'),
  @('src/ncig/target_detector.py','def _oriented_bounds'),
  @('src/ncig/cli.py','"generator_version": "0.22.5"'),
  @('src/ncig/__init__.py','__version__ = "0.22.5"'),
  @('pyproject.toml','version = "0.22.5"')
)

foreach ($c in $checks) {
  $txt = [IO.File]::ReadAllText((Join-Path $stage $c[0]))
  if (-not $txt.Contains($c[1])) { throw "Validation failed for $($c[0]) marker $($c[1])" }
}

foreach ($rel in $files) {
  $target = Join-Path $Root $rel
  if (Test-Path $target) { [IO.File]::Copy($target, "$target.bak_v0225_sync", $true) }
  New-Item -ItemType Directory -Path (Split-Path -Parent $target) -Force | Out-Null
  Copy-Item (Join-Path $stage $rel) $target -Force
  Write-Host "Synced: $rel"
}

Remove-Item $stage -Recurse -Force

$py = $null
try { $py = Get-Command py.exe -ErrorAction Stop | Select-Object -First 1 -ExpandProperty Source } catch {}
if ($py) {
  $compileFiles = @(
    'src/ncig/architecture_catalog.py',
    'src/ncig/architecture_assembler.py',
    'src/ncig/native_collision.py',
    'src/ncig/target_detector.py',
    'src/ncig/generator.py',
    'src/ncig/cli.py',
    'src/ncig/io.py'
  )
  & $py -3 -m py_compile ($compileFiles | ForEach-Object { Join-Path $Root $_ })
  if ($LASTEXITCODE -ne 0) { throw 'Python syntax verification failed.' }
  Write-Host 'Python syntax verification: OK'
}
Write-Host 'NCIG v0.22.5 canonical sync completed.'
