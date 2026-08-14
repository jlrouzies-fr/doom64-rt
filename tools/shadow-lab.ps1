# SHADOW LAB -- unattended capture of the MAP01 cage, alone in a dark room.
#
#   python tools\build_shadow_lab.py        (once, and after any --cage change)
#   .\tools\shadow-lab.ps1                  shipping values, one shot
#   .\tools\shadow-lab.ps1 -Sweep rt_ceiling_bulb_spacing -Values 16,32,64,128
#   .\tools\shadow-lab.ps1 -Extra '+rt_ceiling_edge_radius 0.5' -Tag panewide
#
# WHY A LAB. Every arm so far ran in MAP01's real room, which carries 283
# analytic lights plus a moon, wall strips, dynlights and a level of emissive GI.
# Moving one of those left the other 282 in place and the results could not be
# read (rt-lighting-practices 34c). MAP93 has ONE SFLATAS pane inside the cage
# and nothing else, so the only light is the one under test and the only occluder
# is the grating.
#
# EVERY RUN PRINTS THE LIGHT COUNT. rt_ceiling_edge_debug 1 is forced on and the
# console line is echoed next to the shot. A sweep whose "uploaded=N" does not
# move never reached the renderer, and its images mean nothing -- that mistake
# has been made three times on this problem, so it is checked automatically here
# rather than left to whoever reads the pictures.

param(
  [string]$Sweep = '',            # cvar to walk
  [string[]]$Values = @(),        # its values, one shot each
  [string]$Extra = '',            # extra +cvar args, applied to every shot
  [string]$Tag = 'base',          # label for the output folder when not sweeping
  [int]$Tics = 210                # 6 s: past the fade-in, before anything moves
)

$ErrorActionPreference = 'Stop'
$PROJ = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Lab  = Join-Path $PROJ 'Doom64-Retribution\d64rshadowlab.wad'
if (-not (Test-Path $Lab)) { throw "run: python tools\build_shadow_lab.py" }

$OutRoot = Join-Path $PROJ 'screen\_shadowlab'
New-Item -ItemType Directory -Force $OutRoot | Out-Null

# The pane's own lattice is the only light that may exist here. Everything else
# that can emit is pinned OFF, restated explicitly rather than trusted to the
# map, because these are CVAR_ARCHIVE and an earlier session's value follows you
# into this one (practices 9). rt_shadow_samples especially: it is a Quality-menu
# slider and has been left at 4 in this config before now.
$Fixed = @(
  '+rt_ceiling_edge_lamps 1','+rt_ceiling_edge_lattice 1','+rt_ceiling_edge_debug 1',
  '+rt_faux_lamps 0','+rt_solo_lamps 0','+rt_wall_strips 0','+rt_hang_lamps 0',
  '+rt_ceiling_lamps 0','+rt_sector_lights 0','+rt_spin_panels 0','+rt_switch_lights 0',
  '+rt_flame_light_on 0','+rt_lava_light_on 0','+rt_hand_light_on 0','+rt_dynlight 0',
  '+rt_sun 0','+rt_sky 0','+rt_flsh 0','+rt_gunglow 0','+rt_mzlflsh 0',
  '+rt_sector_emis 0','+rt_shadow_samples 1','+rt_debug_visibility 0'
) -join ' '

$runs = if ($Sweep) { $Values | ForEach-Object { @{ label = "$Sweep=$_"; arg = "+$Sweep $_" } } }
        else        { @(@{ label = $Tag; arg = '' }) }

$stamp = Get-Date -Format 'MMdd-HHmmss'
$dir   = Join-Path $OutRoot ($(if ($Sweep) { "$Sweep-$stamp" } else { "$Tag-$stamp" }))
New-Item -ItemType Directory -Force $dir | Out-Null

foreach ($r in $runs) {
  $safe = ($r.label -replace '[^\w.=-]','_')
  $sub  = Join-Path $dir $safe
  New-Item -ItemType Directory -Force $sub | Out-Null

  Write-Host ''
  Write-Host "=== $($r.label) ===" -ForegroundColor Cyan
  $log = Join-Path $sub 'console.log'
  & (Join-Path $PSScriptRoot 'shot.ps1') `
      -Map map93 -Tics $Tics -OutDir $sub -ExtraFiles 'd64rshadowlab.wad' `
      -LogFile $log `
      -Extra ("$Fixed $($r.arg) $Extra".Trim())

  # The light count is BURNED INTO THE FRAME, not read from a log. rt-console.log
  # lives next to whatever last ran from the repo root, and shot.ps1 runs with its
  # working directory in the build tree -- so parsing that file here returned the
  # PREVIOUS session's numbers, which is worse than no number at all. rt_verbose
  # is on for rt_ceiling_edge_debug, so the line is drawn on the notify overlay
  # and lands in the screenshot with the image it belongs to. The full console is
  # captured beside it as console.log, for the prints that are NOT drawn.
  if (Test-Path $log) {
    Select-String -Path $log -Pattern 'rt_ceiling_edge:|rt_prim_debug|RASTERIZED|in BLAS' |
      Select-Object -Last 4 | ForEach-Object { Write-Host ('    ' + $_.Line.Trim()) -ForegroundColor DarkGray }
  }
}

Write-Host ''
Write-Host "shots: $dir"
