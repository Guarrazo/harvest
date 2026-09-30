$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Target = Join-Path $Root 'src\ncig\reference_nodes.py'

if (-not (Test-Path $Target)) {
    throw "NCIG reference_nodes.py not found: $Target"
}

$text = [System.IO.File]::ReadAllText($Target)
$old = '"Rotation": copy.deepcopy(q),'
$new = '"Rotation": {"$type": "Quaternion", **copy.deepcopy(q)},'

if ($text.Contains($new)) {
    Write-Host 'NCIG collision Quaternion fix already applied.'
    exit 0
}
if (-not $text.Contains($old)) {
    throw 'Expected collision Rotation line was not found; refusing to modify the file.'
}

$text = $text.Replace($old, $new)
[System.IO.File]::WriteAllText($Target, $text, [System.Text.UTF8Encoding]::new($false))
Write-Host 'Applied NCIG collision Quaternion fix:'
Write-Host $Target
Write-Host ''
Write-Host 'Next: rerun .\tools\architecture_test_compose_bounded_cp2077.cmd'
