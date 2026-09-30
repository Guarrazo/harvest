[CmdletBinding()]
param(
  [string]$GameRoot = 'F:\Games\CP2077\Cyberpunk 2077',
  [string]$OutDir = '.\build\user_harvest',
  [string]$EntSpawnerRoot = ''
)
$ErrorActionPreference = 'Stop'

$ProjectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path

function Resolve-EntSpawnerRoot([string]$GameRoot, [string]$ExplicitRoot) {
  if ($ExplicitRoot) {
    $candidate = [System.IO.Path]::GetFullPath($ExplicitRoot)
    if (-not (Test-Path -LiteralPath $candidate -PathType Container)) {
      throw "No se encontró entSpawner en la ruta indicada por -EntSpawnerRoot: $candidate"
    }
    return $candidate
  }

  $candidates = @(
    # EntsSpawner installed as a Cyber Engine Tweaks mod (actual common layout).
    (Join-Path $GameRoot 'bin\x64\plugins\cyber_engine_tweaks\mods\entSpawner'),
    # Legacy / alternate installation layout.
    (Join-Path $GameRoot 'bin\x64\plugins\entSpawner')
  )

  foreach ($candidate in $candidates) {
    if (Test-Path -LiteralPath $candidate -PathType Container) {
      return [System.IO.Path]::GetFullPath($candidate)
    }
  }

  # Last-resort discovery inside CET's mods directory, case-insensitive.
  $modsRoot = Join-Path $GameRoot 'bin\x64\plugins\cyber_engine_tweaks\mods'
  if (Test-Path -LiteralPath $modsRoot -PathType Container) {
    $found = Get-ChildItem -LiteralPath $modsRoot -Directory -ErrorAction SilentlyContinue |
      Where-Object { $_.Name -ieq 'entSpawner' } |
      Select-Object -First 1
    if ($found) { return $found.FullName }
  }

  throw @"
No se encontró entSpawner.

Rutas comprobadas:
  $(Join-Path $GameRoot 'bin\x64\plugins\cyber_engine_tweaks\mods\entSpawner')
  $(Join-Path $GameRoot 'bin\x64\plugins\entSpawner')

Puedes indicar la ruta exacta con:
  .\tools\harvest_cp2077.cmd -EntSpawnerRoot "C:\ruta\a\entSpawner"
"@
}

$Root = Resolve-EntSpawnerRoot $GameRoot $EntSpawnerRoot

$OutDirAbs = [System.IO.Path]::GetFullPath((Join-Path $ProjectRoot $OutDir))
New-Item -ItemType Directory -Force -Path $OutDirAbs | Out-Null
$SrcDir = Join-Path $ProjectRoot 'src'
$HarvestPath = Join-Path $OutDirAbs 'harvest.json'
$TemplatesPath = Join-Path $OutDirAbs 'templates.json'
$env:PYTHONPATH = $SrcDir

function Test-WindowsPythonNcig([string]$Exe) {
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
  if ($Candidate -and (Test-Path -LiteralPath $Candidate -PathType Leaf)) { $List.Add([System.IO.Path]::GetFullPath($Candidate)) }
}

$candidates = [System.Collections.Generic.List[string]]::new()

# 1) Windows Python launcher, if installed.
$pyCmd = Get-Command py.exe -ErrorAction SilentlyContinue
if ($pyCmd) {
  try {
    $paths = & $pyCmd.Source -3 -c "import sys; print(sys.executable)" 2>$null
    foreach ($p in $paths) { Add-Candidate $candidates $p.Trim() }
  } catch {}
}

# 2) PATH, but reject MSYS2/devkitPro/Cygwin/Mingw interpreters.
$pythonCmds = Get-Command python.exe -All -ErrorAction SilentlyContinue
foreach ($c in $pythonCmds) { Add-Candidate $candidates $c.Source }

# 3) Common per-user/system Python locations.
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

# 4) Registry install paths, including installations outside the common folders.
$regBases = @(
  'HKCU:\Software\Python\PythonCore',
  'HKLM:\Software\Python\PythonCore',
  'HKLM:\Software\WOW6432Node\Python\PythonCore'
)
foreach ($base in $regBases) {
  try {
    Get-ChildItem $base -ErrorAction SilentlyContinue | Sort-Object PSChildName -Descending | ForEach-Object {
      $install = Get-ItemProperty ($_.PSPath + '\InstallPath') -ErrorAction SilentlyContinue
      if ($install.InstallPath) { Add-Candidate $candidates (Join-Path $install.InstallPath 'python.exe') }
    }
  } catch {}
}

$PythonExe = $null
foreach ($candidate in ($candidates | Select-Object -Unique)) {
  if (Test-WindowsPythonNcig $candidate) { $PythonExe = $candidate; break }
}

if (-not $PythonExe) {
  $visible = ($candidates | Select-Object -Unique | ForEach-Object { "  $_" }) -join "`n"
  if (-not $visible) { $visible = '  (ninguno encontrado)' }
  throw @"
NCIG no encontró un Python 3.11+ de Windows capaz de importar su paquete.

Interpreters examinados:
$visible

Tu `python.exe` puede apuntar al Python de MSYS2/devkitPro. No uses ese intérprete para NCIG.
Comprueba con:
  py -3 --version
  py -3 -c "import sys; print(sys.executable)"

Si `py -3` no existe, instala Python 3.11+ para Windows y vuelve a ejecutar este script.
"@
}

Write-Host "NCIG: Python seleccionado: $PythonExe"
Write-Host "NCIG: entSpawner: $Root"
Write-Host "NCIG: salida: $OutDirAbs"

& $PythonExe -m ncig.cli harvest --root $Root --out $HarvestPath --templates-out $TemplatesPath
if ($LASTEXITCODE -ne 0) { throw "NCIG harvest terminó con código $LASTEXITCODE." }

Write-Host ""
Write-Host "NCIG harvest completado:"
Write-Host "  $HarvestPath"
Write-Host "  $TemplatesPath"
