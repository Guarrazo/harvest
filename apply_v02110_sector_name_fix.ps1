$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Arch = Join-Path $Root 'src\ncig\native_architecture.py'
$Py = Join-Path $Root 'pyproject.toml'
$Ch = Join-Path $Root 'CHANGELOG.md'

if (-not (Test-Path $Arch)) { throw "NCIG source not found: $Arch" }

$utf8 = [System.Text.UTF8Encoding]::new($false)
$text = [System.IO.File]::ReadAllText($Arch, $utf8)

if (-not $text.Contains('import re')) {
    $text = $text.Replace("import math`n", "import math`nimport re`n")
}

$old1 = '    out["name"] = str(layout_sector.get("id") or f"{building_id}_sector_F{floor + 1:02d}")'
$old2 = '    out["name"] = str(layout_sector.get("id") or f"{building_id}_sector_f{floor + 1:02d}")'
$new  = '    out["name"] = re.sub(r"[\s]+", "_", str(layout_sector.get("id") or f"{building_id}_sector_f{floor + 1:02d}").lower())'

if ($text.Contains($new)) {
    Write-Host 'Sector-name normalization is already present.'
}
elseif ($text.Contains($old1)) {
    $text = $text.Replace($old1, $new)
    [System.IO.File]::WriteAllText($Arch, $text, $utf8)
    Write-Host 'Updated uppercase sector-ID handling to normalized lowercase names.'
}
elseif ($text.Contains($old2)) {
    $text = $text.Replace($old2, $new)
    [System.IO.File]::WriteAllText($Arch, $text, $utf8)
    Write-Host 'Updated lowercase fallback handling to normalized sector names.'
}
else {
    throw 'Expected native sector-name line was not found; refusing to modify the file.'
}

if (Test-Path $Py) {
    $t = [System.IO.File]::ReadAllText($Py, $utf8)
    $u = [regex]::Replace($t, '(?m)^version\s*=\s*["''][^"'']+["'']\s*$', 'version = "0.21.10"', 1)
    if ($u -ne $t) { [System.IO.File]::WriteAllText($Py, $u, $utf8); Write-Host 'Set pyproject version to 0.21.10.' }
}

if (Test-Path $Ch) {
    $t = [System.IO.File]::ReadAllText($Ch, $utf8)
    if (-not $t.Contains('## v0.21.10')) {
        $entry = @'
## v0.21.10

- Normalize native Object Spawner sector names from layout IDs before export: lowercase letters and replace whitespace with underscores.
- Prevent existing `*_sector_F01` layout IDs from bypassing the lowercase fallback and triggering WolvenKit install warnings.

'@
        [System.IO.File]::WriteAllText($Ch, $entry + $t, $utf8)
    }
}

Write-Host ''
Write-Host 'Applied NCIG v0.21.10 sector-name normalization.'
Write-Host 'Next: .\tools\architecture_test_compose_bounded_cp2077.cmd'
