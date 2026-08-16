<#
DLSS RENDER PRESET LADDER, on the edge lab (MAP93).

WHY THIS ARM WAS NEVER RUN. docs/rt-volumetric-edge-outlines.md proved the dark
outline is drawn by the temporal upscaling pass and ruled out every froxel knob
by measurement. What it never varied is WHICH RECONSTRUCTION the upscaler uses:
RTGL1 hard-coded NVSDK_NGX_DLSS_Hint_Render_Preset_E for every quality mode
(DLSS2.cpp), so `dense8`, `dlssq`, `dlaa` and every ubias/postcomp/edgesoft arm
in that document are all the same preset. And rt\bin\nvngx_dlss.dll is 310.7 --
a DLSS 4 runtime, on which the SDK header marks E "Deprecated" (it selects the
legacy CNN model) and K "the transformer based default ... best image quality".

Presets A-D were removed by NVIDIA and silently revert to Default, so the ladder
is E (the shipping control), Default, J and K.

EACH ARM GETS ITS OWN CONTROL. measure_edge_outlines.py fits a smoked frame
against a smoke-free one; a control rendered through a different reconstruction
is a different image, and reusing one control across presets would measure the
preset's effect on the ROOM rather than on the artefact. Eight captures.

    .\tools\edge-preset-ladder.ps1

then

    py tools\measure_edge_outlines.py tools\_edgelab\arm-pk.png tools\_edgelab\ctrl-pk.png
    py tools\measure_edge_ringing.py  tools\_edgelab\ctrl-p*.png

Build the map first if it is missing:  py tools\build_edge_lab.py
#>
[CmdletBinding()]
param(
    # name -> raw NVSDK_NGX_DLSS_Hint_Render_Preset value
    [hashtable]$Ladder = [ordered]@{ pe = 5; pdef = 0; pj = 10; pk = 11 },
    [switch]$SkipControls
)

$ErrorActionPreference = 'Stop'
$proj = Split-Path -Parent $PSScriptRoot
$shots = Join-Path $proj 'tools\_edgelab'
$lab = Join-Path $PSScriptRoot 'edge-lab.cmd'
New-Item -ItemType Directory -Force $shots | Out-Null

# Capture, then claim the newest PNG under a stable name. shot.ps1 leaves the
# engine's own Screenshot_Doom_<timestamp>.png, so the rename has to be by
# mtime rather than by a name the launcher never writes.
function Invoke-Arm {
    param([string]$Out, [int]$Preset, [switch]$NoSmoke)

    $before = @(Get-ChildItem $shots -Filter '*.png' -ErrorAction SilentlyContinue |
        ForEach-Object { $_.Name })

    Write-Host ''
    Write-Host "=== $Out : rt_dlss_preset $Preset$(if ($NoSmoke) { ' (control, no smoke)' })" -ForegroundColor Cyan

    if ($NoSmoke) { & $lab off -- +rt_dlss_preset $Preset | Out-Host }
    else { & $lab -- +rt_dlss_preset $Preset | Out-Host }

    $new = Get-ChildItem $shots -Filter '*.png' -ErrorAction SilentlyContinue |
        Where-Object { $before -notcontains $_.Name } |
        Sort-Object LastWriteTime | Select-Object -Last 1
    if (-not $new) { Write-Warning "$Out : NO SCREENSHOT PRODUCED"; return }

    $dst = Join-Path $shots "$Out.png"
    Move-Item -Force $new.FullName $dst
    Write-Host "    -> $dst"
}

foreach ($name in $Ladder.Keys) {
    $preset = $Ladder[$name]
    Invoke-Arm -Out "arm-$name" -Preset $preset
    if (-not $SkipControls) { Invoke-Arm -Out "ctrl-$name" -Preset $preset -NoSmoke }
}

# VERIFY THE ARM WAS LIVE. RTGL1 logs the preset it actually created the DLSS
# feature with, edge-triggered, and a preset that failed to apply looks exactly
# like a preset that changed nothing. Read this before reading any number.
Write-Host ''
Write-Host '=== what RTGL1 actually created ===' -ForegroundColor Yellow
$log = Join-Path $shots 'edge-lab.log'
if (Test-Path $log) { Select-String -Path $log -Pattern 'render preset' | ForEach-Object { $_.Line } }
else { Write-Warning "no log at $log" }

Write-Host ''
Write-Host '=== now measure ===' -ForegroundColor Yellow
foreach ($name in $Ladder.Keys) {
    Write-Host "py tools\measure_edge_outlines.py tools\_edgelab\arm-$name.png tools\_edgelab\ctrl-$name.png"
}
