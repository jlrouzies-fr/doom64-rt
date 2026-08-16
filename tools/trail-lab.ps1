<#
WEAPON TRAIL LAB runner -- unattended capture of the dark trails the super
shotgun's reload animation leaves in muzzle-lit fog. See
docs/rt-volumetric-weapon-trails.md.

    py tools\build_trail_lab.py            # build MAP94 first
    .\tools\trail-lab.ps1 -Arm fpfreeze-off
    .\tools\trail-lab.ps1 -All             # every arm, one after another

WHY A BURST AND NOT A SCREENSHOT. This artefact does not exist in a settled
frame. It is temporal history being discarded and refilled, so it only appears
while the sprite is moving, and it fades over roughly rt_volume_history frames
once it stops. A still capture taken after a four-second hold measures the one
state in which the bug is invisible -- the exact mistake S7.1 of
docs/rt-volumetric-edge-outlines.md records paying for.

The burst uses the engine's own map-time counters (rt_autoshot / _every /
rt_autoquit), so frame k of one arm is the same game state as frame k of
another: same tic, same weapon animation frame, same puffs. That is what makes
two arms comparable image for image rather than impression for impression.
#>
[CmdletBinding()]
param(
    [string]$Arm = 'trail-legacy',
    [switch]$All,
    # First capture at this map tic. 90 is just after +attack (see
    # tools/arms/trail-fire.cfg), so the burst starts on the first shot.
    [int]$Tics = 90,
    [int]$Burst = 20,
    [int]$BurstEvery = 3
)

$ErrorActionPreference = 'Stop'
$proj = Split-Path -Parent $PSScriptRoot
$labRoot = Join-Path $proj 'tools\_traillab'
$shot = Join-Path $PSScriptRoot 'shot.ps1'

$arms = if ($All) { @('trail-legacy', 'trail-fix', 'trail-fixnoss', 'trail-ssonly', 'trail-nogun') } else { @($Arm) }

foreach ($a in $arms) {
    $cfg = Join-Path $PSScriptRoot "arms\$a.cfg"
    if (-not (Test-Path $cfg)) { throw "no such arm: $cfg" }

    $out = Join-Path $labRoot $a
    if (Test-Path $out) { Remove-Item -Recurse -Force $out }
    New-Item -ItemType Directory -Force $out | Out-Null

    Write-Host ''
    Write-Host "=== arm $a -> $out" -ForegroundColor Cyan

    # The arm cfg first, then the trigger. Both are +exec, and both land AFTER
    # tools\d64rt-pins.cfg, so the arm beats the pins and the trigger beats
    # nothing (it sets no cvars, it only pulls the trigger).
    $extra = ('+exec "{0}" +exec "{1}"' -f $cfg, (Join-Path $PSScriptRoot 'arms\trail-fire.cfg'))

    & $shot -Map map94 -Tics $Tics -Burst $Burst -BurstEvery $BurstEvery `
        -ExtraFiles 'd64rtraillab.wad,d64r-traillab-mapinfo.pk3' `
        -OutDir $out `
        -LogFile (Join-Path $out 'trail-lab.log') `
        -Extra $extra | Out-Host

    $n = @(Get-ChildItem $out -Filter '*.png' -ErrorAction SilentlyContinue).Count
    Write-Host "    $n frames"
    if ($n -eq 0) { Write-Warning "$a produced no frames -- check $out\trail-lab.log" }
}

Write-Host ''
Write-Host '=== measure ===' -ForegroundColor Yellow
Write-Host 'py tools\measure_weapon_trails.py tools\_traillab\fpfreeze-off tools\_traillab\fpfreeze-on'
