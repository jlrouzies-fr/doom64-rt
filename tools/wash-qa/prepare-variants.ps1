# Repo root, derived from this script's own location.
$PROJ = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
# Build three RTGL binary stashes for sequential wash QA (01-05 launchers).
# Variants: live (current HitInfo), indir_kill (INDIR emission=0), clamp (min 0.05).
# Takes several minutes (3× RTGL rebuild). Quit gzdoom before running.

$ErrorActionPreference = 'Stop'
$Root = '$PROJ'
$HitInfo = Join-Path $Root 'deps\RTGL\Source\Shaders\HitInfo.inl'
$Cache = Join-Path $Root 'deps\RTGL\Source\Shaders\Build\GenerateShadersCache.txt'
$EngineRt = Join-Path $Root 'sourcecode\gzdoom-rt\build\RelWithDebInfo\rt'
$VarRoot = Join-Path $Root 'tools\wash-qa\variants'
$BuildCmd = Join-Path $Root 'tools\build-rtgl.cmd'
$Py = 'C:\Users\Winter\AppData\Local\Programs\Python\Python313\python.exe'

$MarkStart = '    #if defined( HITINFO_INL_INDIR )'
$MarkEnd = '    #endif'

$Blocks = @{
  live = @"
    #if defined( HITINFO_INL_INDIR )
        emission *= tr.emissiveMult;
    #endif
"@
  indir_kill = @"
    #if defined( HITINFO_INL_INDIR )
        emission = vec3(0.0);  // wash-qa: kill surface-emission GI
    #endif
"@
  clamp = @"
    #if defined( HITINFO_INL_INDIR )
        emission *= tr.emissiveMult;
        emission = min(emission, vec3(0.05));  // wash-qa: GI ceiling
    #endif
"@
}

function Set-IndirBlock([string]$Name) {
  $text = [IO.File]::ReadAllText($HitInfo)
  # Replace the INDIR emission *= block (with optional clamp / kill lines)
  $pattern = '(?ms)    #if defined\( HITINFO_INL_INDIR \)\r?\n(?:        emission[^\r\n]*\r?\n)+    #endif'
  if ($text -notmatch $pattern) {
    throw "Could not find HITINFO_INL_INDIR emission block in HitInfo.inl"
  }
  $newText = [regex]::Replace($text, $pattern, $Blocks[$Name].TrimEnd() + "`r`n", 1)
  [IO.File]::WriteAllText($HitInfo, $newText)
  Write-Host "HitInfo.inl -> $Name"
}

function Clear-ShaderCache {
  if (Test-Path $Cache) { Remove-Item -Force $Cache }
  $spvs = @(
    'RtRaygenIndirectInit.rgen.spv',
    'RtRaygenIndirectFinal.comp.spv'
  )
  foreach ($s in $spvs) {
    $p = Join-Path $EngineRt "shaders\$s"
    if (Test-Path $p) { Remove-Item -Force $p }
  }
  # Also wipe RTGL Build shaders so copy is fresh
  $buildSpv = Join-Path $Root 'deps\RTGL\Build\shaders'
  if (Test-Path $buildSpv) {
    Get-ChildItem $buildSpv -Filter 'RtRaygenIndirect*.spv' -ErrorAction SilentlyContinue |
      Remove-Item -Force
  }
}

function Invoke-RtglBuild {
  Clear-ShaderCache
  Write-Host '=== build-rtgl.cmd ==='
  & cmd /c "`"$BuildCmd`""
  if ($LASTEXITCODE -ne 0) { throw "build-rtgl failed: $LASTEXITCODE" }
}

function Save-Variant([string]$Name) {
  $dest = Join-Path $VarRoot $Name
  New-Item -ItemType Directory -Force -Path $dest | Out-Null
  Copy-Item -Force (Join-Path $EngineRt 'bin\RTGL1.dll') (Join-Path $dest 'RTGL1.dll')
  $shaderDir = Join-Path $EngineRt 'shaders'
  foreach ($s in @('RtRaygenIndirectInit.rgen.spv', 'RtRaygenIndirectFinal.comp.spv')) {
    $src = Join-Path $shaderDir $s
    if (Test-Path $src) { Copy-Item -Force $src (Join-Path $dest $s) }
  }
  $dll = Get-Item (Join-Path $dest 'RTGL1.dll')
  Write-Host ("Stashed {0}  RTGL1.dll {1:yyyy-MM-dd HH:mm:ss}" -f $Name, $dll.LastWriteTime)
}

# Ensure scrubbed meta is current before any playtest
Write-Host '=== scrub global textures.json ==='
& $Py (Join-Path $Root 'tools\gen_world_emissives.py')
if ($LASTEXITCODE -ne 0) { throw 'gen_world_emissives failed' }

$backup = "$HitInfo.wash-qa.bak"
Copy-Item -Force $HitInfo $backup
Write-Host "Backup: $backup"

try {
  foreach ($name in @('live', 'indir_kill', 'clamp')) {
    Write-Host ""
    Write-Host "######## VARIANT: $name ########"
    Set-IndirBlock $name
    Invoke-RtglBuild
    Save-Variant $name
  }
}
finally {
  # Leave source on preferred clamp so a normal build-rtgl keeps the safety net.
  Set-IndirBlock 'clamp'
  Write-Host 'HitInfo.inl left on clamp (preferred). Backup at .wash-qa.bak'
}

# Deploy live for steps 01-03
$liveDll = Join-Path $VarRoot 'live\RTGL1.dll'
Copy-Item -Force $liveDll (Join-Path $EngineRt 'bin\RTGL1.dll')
Get-ChildItem (Join-Path $VarRoot 'live') -Filter '*.spv' | ForEach-Object {
  Copy-Item -Force $_.FullName (Join-Path $EngineRt "shaders\$($_.Name)")
}
Write-Host ''
Write-Host 'Ready. Engine has LIVE variant deployed.'
Write-Host 'Run tools\wash-qa\00-RUN-ORDER.cmd then 01..05 in order.'
