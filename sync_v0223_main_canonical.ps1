$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Repo = 'https://raw.githubusercontent.com/Guarrazo/harvest/main'
$files = @('src/ncig/generator.py','src/ncig/architecture_assembler.py','src/ncig/native_collision.py','pyproject.toml','CHANGELOG.md')
$stage = Join-Path $Root '.ncig_v0223_sync'
if (Test-Path $stage) { Remove-Item $stage -Recurse -Force }
New-Item -ItemType Directory -Path $stage | Out-Null
foreach ($rel in $files) {
  $dest = Join-Path $stage $rel
  New-Item -ItemType Directory -Path (Split-Path -Parent $dest) -Force | Out-Null
  $url = "$Repo/$rel"
  Write-Host "Fetching $rel"
  Invoke-WebRequest -UseBasicParsing -Uri $url -OutFile $dest
  if (-not (Test-Path $dest)) { throw "Failed to fetch $rel" }
}
$arch = [IO.File]::ReadAllText((Join-Path $stage 'src/ncig/architecture_assembler.py'))
$gen = [IO.File]::ReadAllText((Join-Path $stage 'src/ncig/generator.py'))
$coll = [IO.File]::ReadAllText((Join-Path $stage 'src/ncig/native_collision.py'))
$proj = [IO.File]::ReadAllText((Join-Path $stage 'pyproject.toml'))
if (-not $arch.Contains('def assemble_room(')) { throw 'Canonical architecture_assembler.py lacks assemble_room.' }
if ($arch.Contains('return outdef build_architecture_assembly')) { throw 'Canonical architecture_assembler.py is corrupted.' }
if (-not $arch.Contains('_floor_bounds(floor_rooms, layout.building)')) { throw 'Canonical architecture_assembler.py lacks full-footprint bounds.' }
if (-not $gen.Contains('margin = 0.0')) { throw 'Canonical generator.py lacks flush footprint grid.' }
if (-not $coll.Contains('building_width = float(building.get("width_m", 0.0))')) { throw 'Canonical native_collision.py lacks full-footprint collision.' }
if (-not $proj.Contains('version = "0.22.3"')) { throw 'Canonical pyproject.toml is not v0.22.3.' }
foreach ($rel in $files) {
  $target = Join-Path $Root $rel
  if (Test-Path $target) { [IO.File]::Copy($target, "$target.bak_v0223_sync", $true); Write-Host "Backup: $target.bak_v0223_sync" }
  Copy-Item (Join-Path $stage $rel) $target -Force
  Write-Host "Synced from main: $rel"
}
Remove-Item $stage -Recurse -Force
$py = $null
try { $py = Get-Command py.exe -ErrorAction Stop | Select-Object -First 1 -ExpandProperty Source } catch {}
if ($py) { & $py -3 -m py_compile (Join-Path $Root 'src/ncig/generator.py') (Join-Path $Root 'src/ncig/architecture_assembler.py') (Join-Path $Root 'src/ncig/native_collision.py'); if ($LASTEXITCODE -ne 0) { throw 'Python syntax verification failed.' }; Write-Host 'Python syntax verification: OK' } else { Write-Host 'WARNING: py.exe not found; skipped Python syntax verification.' }
Write-Host 'NCIG v0.22.3 canonical main sync completed.'
Write-Host 'Next: rerun .\tools\architecture_assemble_bounded_cp2077.cmd and .\tools\architecture_test_compose_bounded_cp2077.cmd'
