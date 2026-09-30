$ErrorActionPreference = 'Stop'

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Target = Join-Path $Root 'src\\ncig\\architecture_assembler.py'

if (-not (Test-Path $Target)) {
    throw "NCIG architecture_assembler.py not found: $Target"
}

$text = [System.IO.File]::ReadAllText($Target)
$marker = "    return outdef build_architecture_assembly"

if (-not $text.Contains($marker)) {
    if ($text -match 'def build_architecture_assembly\\(' -and $text.TrimEnd().EndsWith('return out')) {
        Write-Host 'architecture_assembler.py is already repaired.'
        exit 0
    }
    throw 'Expected architecture assembler corruption marker was not found; refusing to modify the file.'
}

$bak = "$Target.bak_v0221_corruption"
[System.IO.File]::Copy($Target, $bak, $true)

$index = $text.IndexOf($marker)
$repaired = $text.Substring(0, $index) + "    return out`r`n"
[System.IO.File]::WriteAllText($Target, $repaired, [System.Text.UTF8Encoding]::new($false))

$verify = [System.IO.File]::ReadAllText($Target)
if ($verify.Contains($marker)) {
    throw 'Verification failed: corruption marker is still present.'
}

Write-Host 'Fixed architecture_assembler.py concatenation corruption.'
Write-Host "Backup: $bak"
Write-Host 'Next: rerun .\\tools\\architecture_test_compose_bounded_cp2077.cmd'
