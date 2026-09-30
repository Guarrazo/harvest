$ErrorActionPreference = 'Stop'

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path

function Patch-File([string]$relativePath, [scriptblock]$patcher) {
    $path = Join-Path $Root $relativePath
    if (-not (Test-Path $path)) { throw "NCIG file not found: $path" }
    $text = [System.IO.File]::ReadAllText($path)
    $original = $text
    $text = & $patcher $text
    if ($text -eq $original) {
        Write-Host "No textual change needed: $relativePath"
        return
    }
    $bak = "$path.bak_v0223"
    [System.IO.File]::Copy($path, $bak, $true)
    [System.IO.File]::WriteAllText($path, $text, [System.Text.UTF8Encoding]::new($false))
    Write-Host "Patched: $relativePath"
    Write-Host "Backup: $bak"
}

Patch-File 'src\ncig\generator.py' {
    param($text)
    if ($text.Contains('    margin = 0.0') -and $text.Contains('        w = bay_width')) {
        return $text
    }
    $old = @'
    margin = 0.5
    corridor = 1.6
    usable_w = anchor.width_m - 2 * margin
    usable_d = anchor.depth_m - 2 * margin
    if usable_w < 4.0 or usable_d < 4.0:
        raise ValueError(f"building {anchor.id}: footprint too small")

    # The generator uses a deterministic corridor-and-bays layout.
    # This is deliberately conservative: connectivity is more valuable than maximal packing.
    rooms: list[Room] = []
    rules = TEMPLATES[ALIASES.get(template_name, template_name)]

    # For narrow buildings, make one side of rooms; for wider buildings, use both sides.
    double_sided = usable_d >= 9.0
    side_depth = (usable_d - corridor) / 2 if double_sided else usable_d
    rows = max(1, int(round(usable_w / 3.6)))
    target_rows = min(6, max(1, rows))
    bay_width = usable_w / target_rows

    banned_once: set[str] = set()
    room_counter = 0
    for i in range(target_rows):
        x = -anchor.width_m / 2 + margin + i * bay_width
        w = bay_width - 0.18
        for side in ([-1, 1] if double_sided else [1]):
            y = side * corridor / 2
            if double_sided:
                y0 = y if side > 0 else -corridor / 2 - side_depth
            else:
                y0 = -anchor.depth_m / 2 + margin
            d = side_depth - 0.18
            if w < 1.4 or d < 1.4:
                continue
            rule = weighted_rule(rng, rules, banned_once if room_counter < 4 else set())
            if room_counter < 1:
                rule = next((r for r in rules if r.kind in {"shopfloor", "living", "open_office", "workshop"}), rule)
            room_w = min(w, rng.uniform(rule.min_w, rule.max_w))
            room_d = min(d, rng.uniform(rule.min_d, rule.max_d))
            room = Room(
                id=f"{anchor.id}_F{floor+1}_R{room_counter+1:02d}",
                kind=rule.kind,
                floor=floor,
                x=x + (w - room_w) / 2,
                y=y0 + (d - room_d) / 2,
                width=room_w,
                depth=room_d,
            )
'@
    if (-not $text.Contains($old)) { throw "Expected generator room-grid block not found; refusing to modify." }
    $new = @'
    # Keep the generated structural grid flush with the building footprint.
    # Shrinking individual bays creates gaps that make walls, doors and floors detach
    # from each other. Room kinds can still vary without changing the structural grid.
    margin = 0.0
    corridor = 1.6
    usable_w = anchor.width_m - 2 * margin
    usable_d = anchor.depth_m - 2 * margin
    if usable_w < 4.0 or usable_d < 4.0:
        raise ValueError(f"building {anchor.id}: footprint too small")

    rooms: list[Room] = []
    rules = TEMPLATES[ALIASES.get(template_name, template_name)]

    double_sided = usable_d >= 9.0
    side_depth = (usable_d - corridor) / 2 if double_sided else usable_d
    rows = max(1, int(round(usable_w / 3.6)))
    target_rows = min(6, max(1, rows))
    bay_width = usable_w / target_rows

    banned_once: set[str] = set()
    room_counter = 0
    for i in range(target_rows):
        x = -anchor.width_m / 2 + margin + i * bay_width
        w = bay_width
        for side in ([-1, 1] if double_sided else [1]):
            y = side * corridor / 2
            if double_sided:
                y0 = y if side > 0 else -corridor / 2 - side_depth
            else:
                y0 = -anchor.depth_m / 2 + margin
            d = side_depth
            if w < 1.4 or d < 1.4:
                continue
            rule = weighted_rule(rng, rules, banned_once if room_counter < 4 else set())
            if room_counter < 1:
                rule = next((r for r in rules if r.kind in {"shopfloor", "living", "open_office", "workshop"}), rule)
            room = Room(
                id=f"{anchor.id}_F{floor+1}_R{room_counter+1:02d}",
                kind=rule.kind,
                floor=floor,
                x=x,
                y=y0,
                width=w,
                depth=d,
            )
'@
    return $text.Replace($old, $new)
}

Patch-File 'src\ncig\architecture_assembler.py' {
    param($text)
    $oldBounds = @'
def _floor_bounds(rooms: list[Room]) -> tuple[float, float, float, float]:
    return (
        min(r.x for r in rooms),
        max(r.x + r.width for r in rooms),
        min(r.y for r in rooms),
        max(r.y + r.depth for r in rooms),
    )
'@
    if ($text.Contains($oldBounds)) {
        $newBounds = @'
def _floor_bounds(rooms: list[Room], building: Any | None = None) -> tuple[float, float, float, float]:
    if building is not None:
        width = float(getattr(building, "width_m", 0.0))
        depth = float(getattr(building, "depth_m", 0.0))
        if width > 0.0 and depth > 0.0:
            return (-width * 0.5, width * 0.5, -depth * 0.5, depth * 0.5)
    return (
        min(r.x for r in rooms),
        max(r.x + r.width for r in rooms),
        min(r.y for r in rooms),
        max(r.y + r.depth for r in rooms),
    )
'@
        $text = $text.Replace($oldBounds, $newBounds)
    }
    $text = $text.Replace('_floor_bounds(floor_rooms)', '_floor_bounds(floor_rooms, layout.building)')

    if (-not $text.Contains('def assemble_room(')) {
        $marker = [Environment]::NewLine + [Environment]::NewLine + 'def build_architecture_assembly(layouts: list[Layout], catalog: dict[str, Any]) -> dict[str, Any]:'
        if (-not $text.Contains($marker)) { throw "Cannot restore assemble_room: build_architecture_assembly marker not found." }
        $assemble = @'

def assemble_room(layout: Layout, room: Room, catalog: dict[str, Any], family: str | None,
                  class_families: dict[str, str] | None = None) -> list[dict[str, Any]]:
    """Assemble room shell/details; floor and ceiling are generated once per floor."""
    placements: list[dict[str, Any]] = []
    fm = class_families or {}
    door_gap, _ = _door_and_frame(
        layout, room, catalog, placements,
        fm.get("door_frame", family), fm.get("door_piece", family),
    )
    wall_family = fm.get("wall_piece", family)
    if room.y >= 0:
        _wall_run(layout, room, catalog, placements, side="south", x0=room.x, y0=room.y + room.depth,
                  length=room.width, rotation_deg=0.0, family=wall_family)
        _wall_run(layout, room, catalog, placements, side="north", x0=room.x, y0=room.y,
                  length=room.width, rotation_deg=0.0, opening=door_gap, family=wall_family)
    else:
        _wall_run(layout, room, catalog, placements, side="north", x0=room.x, y0=room.y,
                  length=room.width, rotation_deg=0.0, family=wall_family)
        _wall_run(layout, room, catalog, placements, side="south", x0=room.x, y0=room.y + room.depth,
                  length=room.width, rotation_deg=0.0, opening=door_gap, family=wall_family)
    _wall_run(layout, room, catalog, placements, side="west", x0=room.x, y0=room.y,
              length=room.depth, rotation_deg=90.0, family=wall_family)
    _wall_run(layout, room, catalog, placements, side="east", x0=room.x + room.width, y0=room.y,
              length=room.depth, rotation_deg=90.0, family=wall_family)
    _window(layout, room, catalog, placements, fm.get("window_piece", family))
    return placements
'@
        $text = $text.Replace($marker, $assemble + $marker)
    }
    if (-not $text.Contains('def assemble_room(')) {
        throw "Verification failed: assemble_room is still missing."
    }
    return $text
}

Patch-File 'src\ncig\native_collision.py' {
    param($text)
    if ($text.Contains('building_width = float(building.get("width_m", 0.0))')) { return $text }
    $old = @'
        min_y = min(float(r.get("y", 0.0)) for r in floor_rooms)
        max_y = max(float(r.get("y", 0.0)) + float(r.get("depth", 0.0)) for r in floor_rooms)
        w = max(0.1, max_x - min_x)
        d = max(0.1, max_y - min_y)
'@
    if (-not $text.Contains($old)) { throw "Expected collision floor envelope block not found; refusing to modify." }
    $new = @'
        building_width = float(building.get("width_m", 0.0))
        building_depth = float(building.get("depth_m", 0.0))
        if building_width > 0.0 and building_depth > 0.0:
            min_x, max_x = -building_width * 0.5, building_width * 0.5
            min_y, max_y = -building_depth * 0.5, building_depth * 0.5
        else:
            min_y = min(float(r.get("y", 0.0)) for r in floor_rooms)
            max_y = max(float(r.get("y", 0.0)) + float(r.get("depth", 0.0)) for r in floor_rooms)
        w = max(0.1, max_x - min_x)
        d = max(0.1, max_y - min_y)
'@
    return $text.Replace($old, $new)
}

Patch-File 'pyproject.toml' {
    param($text)
    if ($text.Contains('version = "0.22.3"')) { return $text }
    if (-not $text.Contains('version = "0.22.2"')) { throw "Expected pyproject v0.22.2 not found." }
    return $text.Replace('version = "0.22.2"', 'version = "0.22.3"')
}

$py = $null
try { $py = Get-Command py.exe -ErrorAction Stop | Select-Object -First 1 -ExpandProperty Source } catch {}

if ($py) {
    & $py -3 -m py_compile (Join-Path $Root 'src\ncig\generator.py'), (Join-Path $Root 'src\ncig\architecture_assembler.py'), (Join-Path $Root 'src\ncig\native_collision.py')
    if ($LASTEXITCODE -ne 0) { throw "Python syntax verification failed." }
    Write-Host 'Python syntax verification: OK'
} else {
    Write-Host 'WARNING: py.exe not found; skipped Python syntax verification.'
}

Write-Host ''
Write-Host 'NCIG v0.22.3 structural footprint patch applied.'
Write-Host 'Next: regenerate with .\tools\architecture_test_compose_bounded_cp2077.cmd'
