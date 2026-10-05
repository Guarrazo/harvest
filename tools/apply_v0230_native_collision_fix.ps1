param(
  [string]$Repo = (Get-Location).Path
)
$ErrorActionPreference = 'Stop'
$path = Join-Path $Repo 'src\ncig\native_collision.py'
if (-not (Test-Path $path)) { throw "native_collision.py not found: $path" }
$text = Get-Content -Raw -LiteralPath $path
$old1 = 'center_axis=center_axis, gap=entry_opening[1] - entry_opening[0],'
$old2 = 'center_axis=center_axis, gap=entry_opening[1] - entry_opening[0],'
$replaced = $text.Replace($old1, 'gap=entry_opening[1] - entry_opening[0],')
$replaced = $replaced.Replace($old2, 'gap=entry_opening[1] - entry_opening[0],')
if ($replaced -eq $text) {
  Write-Host 'NCIG v0.23.0: no lateral-entry header bug pattern found; file already patched or layout path not present.'
  exit 0
}
Copy-Item -LiteralPath $path -Destination ($path + '.bak_v0230') -Force
Set-Content -LiteralPath $path -Value $replaced -Encoding UTF8
Write-Host "NCIG v0.23.0: patched $path (backup: native_collision.py.bak_v0230)"
