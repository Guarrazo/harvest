$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path

$arch = Join-Path $Root 'src\ncig\native_architecture.py'
$comp = Join-Path $Root 'src\ncig\native_composition.py'
$pyproject = Join-Path $Root 'pyproject.toml'
$changelog = Join-Path $Root 'CHANGELOG.md'

foreach ($p in @($arch, $comp)) {
    if (-not (Test-Path $p)) { throw "Required NCIG source file not found: $p" }
}

function Read-Utf8([string]$Path) {
    return [System.IO.File]::ReadAllText($Path, [System.Text.UTF8Encoding]::new($false))
}
function Write-Utf8([string]$Path, [string]$Text) {
    [System.IO.File]::WriteAllText($Path, $Text, [System.Text.UTF8Encoding]::new($false))
}

# Native sector path/name: F01 -> f01, removing WolvenKit's capital-letter warning.
$text = Read-Utf8 $arch
$old = 'f"{building_id}_sector_F{floor + 1:02d}"'
$new = 'f"{building_id}_sector_f{floor + 1:02d}"'
if ($text.Contains($old)) {
    $text = $text.Replace($old, $new)
    Write-Utf8 $arch $text
}
elseif (-not $text.Contains($new)) {
    throw 'Expected native sector naming line was not found.'
}

# Collision routing: accept either F01 or f01 in generated node refs.
$text = Read-Utf8 $comp
$old = 're.search(r"_F(\d{1,2})_R", ref)'
$new = 're.search(r"_f(\d{1,2})_r", ref, re.IGNORECASE)'
if ($text.Contains($old)) {
    $text = $text.Replace($old, $new)
    Write-Utf8 $comp $text
}
elseif (-not $text.Contains($new)) {
    throw 'Expected collision floor regex was not found.'
}

# Version update is best-effort: do not fail the code fix because a local checkout
# may already have a different NCIG version or quote style.
if (Test-Path $pyproject) {
    $text = Read-Utf8 $pyproject
    $updated = [regex]::Replace($text, '(?m)^version\s*=\s*["''][^"'']+["'']\s*$', 'version = "0.21.9"', 1)
    if ($updated -ne $text) {
        Write-Utf8 $pyproject $updated
        Write-Host 'Updated pyproject version to 0.21.9.'
    }
    elseif ($text -match '(?m)^version\s*=') {
        Write-Host 'pyproject version already set; leaving it unchanged.'
    }
    else {
        Write-Host 'Warning: pyproject version line was not found; source fix is still applied.'
    }
}

# Changelog is also best-effort.
if (Test-Path $changelog) {
    $text = Read-Utf8 $changelog
    $entry = @'
## v0.21.9

- Generate native Object Spawner sector filenames with lowercase floor identifiers (f01, f02, ...), avoiding WolvenKit install warnings about capital letters.
- Keep collision floor routing case-insensitive so existing F## references remain compatible.

'@
    if (-not $text.Contains('## v0.21.9')) {
        Write-Utf8 $changelog ($entry + $text)
        Write-Host 'Added v0.21.9 changelog entry.'
    }
}

Write-Host ''
Write-Host 'Applied NCIG v0.21.9 sector-name fix.'
Write-Host "Updated: $arch"
Write-Host "Updated: $comp"
Write-Host ''
Write-Host 'Next: rerun .\tools\architecture_test_compose_bounded_cp2077.cmd'
