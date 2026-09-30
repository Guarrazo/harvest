$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$RawBase = 'https://raw.githubusercontent.com/Guarrazo/harvest/main/'
$Stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$BackupDir = Join-Path $Root ('.ncig_backup_v0221_' + $Stamp)

$Files = @(
    'src/ncig/runtime_geometry.py',
    'src/ncig/architecture_assembler.py',
    'src/ncig/native_collision.py',
    'src/ncig/native_composition.py',
    'tests/test_v021_geometry.py',
    'tests/test_v021_collision_and_composition.py',
    'pyproject.toml',
    'CHANGELOG.md'
)

New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null

foreach ($rel in $Files) {
    $target = Join-Path $Root ($rel -replace '/', '\\')
    $parent = Split-Path -Parent $target
    if (-not (Test-Path $parent)) {
        New-Item -ItemType Directory -Force -Path $parent | Out-Null
    }

    if (Test-Path $target) {
        $backup = Join-Path $BackupDir ($rel -replace '/', '\\')
        $backupParent = Split-Path -Parent $backup
        New-Item -ItemType Directory -Force -Path $backupParent | Out-Null
        Copy-Item -LiteralPath $target -Destination $backup -Force
    }

    $uri = $RawBase + $rel
    $tmp = $target + '.ncig_v0221_tmp'
    try {
        Invoke-WebRequest -UseBasicParsing -Uri $uri -OutFile $tmp
        if (-not (Test-Path $tmp)) {
            throw "Download completed without creating $tmp"
        }
        Move-Item -LiteralPath $tmp -Destination $target -Force
        Write-Host "Synced $rel"
    }
    catch {
        if (Test-Path $tmp) { Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue }
        throw "Failed to sync $rel from $uri. $($_.Exception.Message)"
    }
}

$py = Get-Content -Raw -Encoding UTF8 (Join-Path $Root 'pyproject.toml')
if ($py -notmatch '(?m)^version\s*=\s*["'']0\.22\.1["'']\s*$') {
    throw 'Verification failed: pyproject.toml is not at version 0.22.1.'
}

$arch = Get-Content -Raw -Encoding UTF8 (Join-Path $Root 'src\ncig\architecture_assembler.py')
if ($arch -notmatch 'from \.runtime_geometry import' -or
    $arch -notmatch 'def _floor_surface' -or
    $arch -notmatch 'def _ceiling_surface' -or
    $arch -notmatch 'linear_fit\(item, span=actual') {
    throw 'Verification failed: runtime geometry changes are missing from architecture_assembler.py.'
}

$coll = Get-Content -Raw -Encoding UTF8 (Join-Path $Root 'src\ncig\native_collision.py')
if ($coll -notmatch 'continuous_floor_per_floor_plus_room_shell_walls_with_door_openings' -or
    $coll -notmatch 'Simple Environment Collision|concrete\.physmat') {
    throw 'Verification failed: continuous collision geometry is missing.'
}

$ref = Get-Content -Raw -Encoding UTF8 (Join-Path $Root 'src\ncig\reference_nodes.py')
# reference_nodes.py is already maintained by main; only verify its valid defaults.
if ($ref -notmatch 'preset: str = "Simple Environment Collision"' -or
    $ref -notmatch 'material: str = "concrete\.physmat"') {
    throw 'Verification failed: valid collision defaults are missing from reference_nodes.py.'
}

Write-Host ''
Write-Host 'NCIG v0.22.1 geometry/collision update applied successfully.'
Write-Host "Backup: $BackupDir"
Write-Host ''
Write-Host 'Next:'
Write-Host '  .\tools\architecture_test_compose_bounded_cp2077.cmd'
