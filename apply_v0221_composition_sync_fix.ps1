$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Target = Join-Path $Root 'src\ncig\native_composition.py'
if (-not (Test-Path $Target)) { throw "NCIG native_composition.py not found: $Target" }

$text = [System.IO.File]::ReadAllText($Target)
$newPolicy = '"collision_policy": "continuous_floor_per_floor_plus_room_shell_walls_with_door_openings" if include_collisions else "disabled"'
$oldPolicy = '"collision_policy": "room_shell_boxes_with_door_openings" if include_collisions else "disabled"'

if ($text.Contains($newPolicy)) {
    Write-Host 'native_composition.py already has the continuous-floor collision policy.'
    exit 0
}

if (-not $text.Contains($oldPolicy)) {
    throw 'Expected collision_policy line was not found; refusing to modify the file.'
}

$bak = "$Target.bak_v0221"
[System.IO.File]::Copy($Target, $bak, $true)
$text = $text.Replace($oldPolicy, $newPolicy)
[System.IO.File]::WriteAllText($Target, $text, [System.Text.UTF8Encoding]::new($false))

if (-not ([System.IO.File]::ReadAllText($Target)).Contains($newPolicy)) {
    throw 'Verification failed after patch.'
}

Write-Host 'Fixed native_composition.py collision policy.'
Write-Host "Backup: $bak"
Write-Host 'Next: rerun .\tools\architecture_test_compose_bounded_cp2077.cmd'
