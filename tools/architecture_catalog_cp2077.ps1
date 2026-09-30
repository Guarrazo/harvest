[CmdletBinding()]
param(
  [string]$GameRoot = 'F:\Games\CP2077\Cyberpunk 2077',
  [string]$Harvest = '.\build\user_harvest\harvest.json',
  [string]$Out = '.\build\architecture_catalog.json',
  [int]$MaxPerClass = 250,
  [int]$MaxTotal = 0,
  [switch]$InteriorOnly
)
$ErrorActionPreference = 'Stop'
$ProjectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$HarvestAbs = [System.IO.Path]::GetFullPath((Join-Path $ProjectRoot $Harvest))
$OutAbs = [System.IO.Path]::GetFullPath((Join-Path $ProjectRoot $Out))
if (-not (Test-Path -LiteralPath $HarvestAbs -PathType Leaf)) {
  throw "No se encontró el harvest: $HarvestAbs`nEjecuta primero .\tools\harvest_cp2077.cmd"
}
New-Item -ItemType Directory -Force -Path ([System.IO.Path]::GetDirectoryName($OutAbs)) | Out-Null
$SrcDir = Join-Path $ProjectRoot 'src'
$env:PYTHONPATH = $SrcDir

function Test-NcigPython([string]$Exe) {
  if (-not $Exe -or -not (Test-Path -LiteralPath $Exe -PathType Leaf)) { return $false }
  try {
    $resolved = [System.IO.Path]::GetFullPath($Exe)
    $normalized = $resolved.ToLowerInvariant()
    if ($normalized -match '\\(msys2|cygwin|mingw|devkitpro)\\') { return $false }
    & $resolved -c "import sys; raise SystemExit(0 if sys.platform == 'win32' and sys.version_info >= (3,11) else 1)" 1>$null 2>$null
    if ($LASTEXITCODE -ne 0) { return $false }
    & $resolved -c "import ncig" 1>$null 2>$null
    return ($LASTEXITCODE -eq 0)
  } catch { return $false }
}

function Add-Candidate([System.Collections.Generic.List[string]]$List, [string]$Candidate) {
  if ($Candidate -and (Test-Path -LiteralPath $Candidate -PathType Leaf)) {
    $List.Add([System.IO.Path]::GetFullPath($Candidate))
  }
}

$candidates = [System.Collections.Generic.List[string]]::new()
$pyCmd = Get-Command py.exe -ErrorAction SilentlyContinue
if ($pyCmd) {
  try {
    $paths = & $pyCmd.Source -3 -c "import sys; print(sys.executable)" 2>$null
    foreach ($p in $paths) { Add-Candidate $candidates $p.Trim() }
  } catch {}
}
foreach ($c in (Get-Command python.exe -All -ErrorAction SilentlyContinue)) { Add-Candidate $candidates $c.Source }
$roots = @(
  (Join-Path $env:LOCALAPPDATA 'Programs\Python'),
  (Join-Path $env:ProgramFiles 'Python'),
  (Join-Path ${env:ProgramFiles(x86)} 'Python')
) | Where-Object { $_ -and (Test-Path -LiteralPath $_ -PathType Container) }
foreach ($r in $roots) {
  Get-ChildItem -LiteralPath $r -Directory -ErrorAction SilentlyContinue | Sort-Object Name -Descending | ForEach-Object {
    Add-Candidate $candidates (Join-Path $_.FullName 'python.exe')
  }
}

$PythonExe = $null
foreach ($candidate in ($candidates | Select-Object -Unique)) {
  if (Test-NcigPython $candidate) { $PythonExe = $candidate; break }
}
if (-not $PythonExe) {
  throw "NCIG no encontró un Python 3.11+ de Windows capaz de importar su paquete. Ejecuta .\tools\diagnose_environment.ps1"
}

$args = @('-m','ncig.cli','architecture-catalog','--harvest',$HarvestAbs,'--out',$OutAbs,'--max-per-class',[string]$MaxPerClass)
if ($MaxTotal -gt 0) { $args += @('--max-total',[string]$MaxTotal) }
if ($InteriorOnly) { $args += '--interior-only' }
Write-Host "NCIG: Python seleccionado: $PythonExe"
Write-Host "NCIG: harvest: $HarvestAbs"
Write-Host "NCIG: catálogo: $OutAbs"
& $PythonExe @args
if ($LASTEXITCODE -ne 0) { throw "NCIG architecture-catalog terminó con código $LASTEXITCODE." }
Write-Host "NCIG architecture catalog completado:"
Write-Host "  $OutAbs"
