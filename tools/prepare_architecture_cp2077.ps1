param(
  [string]$NCIGRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path,
  [string]$Harvest = '',
  [string]$Layouts = '',
  [string]$Buildings = '',
  [string]$OutDir = ''
)
$ErrorActionPreference='Stop'
if ([string]::IsNullOrWhiteSpace($Harvest)) { $Harvest = Join-Path $NCIGRoot 'build\user_harvest\harvest.json' }
if ([string]::IsNullOrWhiteSpace($Layouts)) {
  $layoutCandidates = @(
    (Join-Path $NCIGRoot 'build\scanned_buildings.layouts.json'),
    (Join-Path $NCIGRoot 'build\layouts.json'),
    (Join-Path $NCIGRoot 'build\generated\layouts.json'),
    (Join-Path $NCIGRoot 'build\v016_demo\layouts.json')
  )
  foreach ($candidate in $layoutCandidates) {
    if (Test-Path -LiteralPath $candidate -PathType Leaf) { $Layouts = $candidate; break }
  }
}

if ([string]::IsNullOrWhiteSpace($OutDir)) { $OutDir = Join-Path $NCIGRoot 'build\real_architecture' }
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$catalog = Join-Path $OutDir 'architecture_catalog.json'
$assembly = Join-Path $OutDir 'architecture_assembly.json'
$SourceRoot = Join-Path $NCIGRoot 'src'
$env:PYTHONPATH = $SourceRoot

function Test-NcigPython([string]$Exe) {
  if (-not $Exe -or -not (Test-Path -LiteralPath $Exe -PathType Leaf)) { return $false }
  try {
    $full = [System.IO.Path]::GetFullPath($Exe)
    $norm = $full.ToLowerInvariant()
    if ($norm -match '\\(msys2|cygwin|mingw|devkitpro)\\') { return $false }
    & $full -c "import sys; raise SystemExit(0 if sys.platform == 'win32' and sys.version_info >= (3,11) else 1)" 1>$null 2>$null
    if ($LASTEXITCODE -ne 0) { return $false }
    & $full -c "import ncig" 1>$null 2>$null
    return ($LASTEXITCODE -eq 0)
  } catch { return $false }
}

$candidates = [System.Collections.Generic.List[string]]::new()
$pyCmd = Get-Command py.exe -ErrorAction SilentlyContinue
if ($pyCmd) {
  try {
    & $pyCmd.Source -3 -c "import sys; print(sys.executable)" 2>$null | ForEach-Object { if ($_){ $candidates.Add($_.Trim()) } }
  } catch {}
}
Get-Command python.exe -All -ErrorAction SilentlyContinue | ForEach-Object { $candidates.Add($_.Source) }
$roots=@((Join-Path $env:LOCALAPPDATA 'Programs\Python'),(Join-Path $env:ProgramFiles 'Python'),(Join-Path ${env:ProgramFiles(x86)} 'Python'))
foreach($r in $roots){
  if(Test-Path -LiteralPath $r -PathType Container){
    Get-ChildItem -LiteralPath $r -Directory -ErrorAction SilentlyContinue | Sort-Object Name -Descending | ForEach-Object { $candidates.Add((Join-Path $_.FullName 'python.exe')) }
  }
}
$PythonExe=$null
foreach($c in ($candidates | Select-Object -Unique)){ if(Test-NcigPython $c){$PythonExe=$c;break} }
if(-not $PythonExe){ throw 'NCIG no encontró un Python 3.11+ de Windows capaz de importar ncig. Ejecuta .\tools\diagnose_environment.ps1.' }

Write-Host "NCIG: Python seleccionado: $PythonExe"
Write-Host "NCIG: harvest = $Harvest"
Write-Host "NCIG: layouts = $Layouts"

if ([string]::IsNullOrWhiteSpace($Layouts) -or -not (Test-Path -LiteralPath $Layouts -PathType Leaf)) {
  if ([string]::IsNullOrWhiteSpace($Buildings)) { $Buildings = Join-Path $NCIGRoot 'examples\buildings.json' }
  if (-not (Test-Path -LiteralPath $Buildings -PathType Leaf)) {
    throw "No se encontró layouts.json ni un fichero de edificios para generarlo: $Buildings"
  }
  $generatedDir = Join-Path $NCIGRoot 'build\generated'
  New-Item -ItemType Directory -Force -Path $generatedDir | Out-Null
  Write-Host "NCIG: no había layouts; generando layouts desde: $Buildings"
  & $PythonExe -m ncig.cli generate --input $Buildings --out $generatedDir
  if ($LASTEXITCODE -ne 0) { throw "layout generation failed with code $LASTEXITCODE" }
  $Layouts = Join-Path $generatedDir 'layouts.json'
}
Write-Host "NCIG: layouts seleccionados = $Layouts"

Write-Host "NCIG: output = $OutDir"
& $PythonExe -m ncig.cli architecture-catalog --harvest $Harvest --out $catalog --interior-only
if ($LASTEXITCODE -ne 0) { throw "architecture-catalog failed with code $LASTEXITCODE" }
& $PythonExe -m ncig.cli architecture-assemble --layouts $Layouts --catalog $catalog --out $assembly
if ($LASTEXITCODE -ne 0) { throw "architecture-assemble failed with code $LASTEXITCODE" }
Write-Host 'NCIG architecture preparation completed.'
Write-Host "  $catalog"
Write-Host "  $assembly"
