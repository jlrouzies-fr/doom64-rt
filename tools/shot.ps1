# Launch Retribution-RT, let it settle, take a screenshot, quit.
#
# The one thing that makes this work: `wait` only defers THE REST OF THE SAME
# command string (c_dispatch.cpp:376). Passing `+wait 300 +screenshot +quit` as
# separate arguments - or one command per line in an exec'd cfg - runs
# screenshot and quit IMMEDIATELY at startup, before a frame has ever been
# presented, so `screenshot` sets its flag and nothing ever consumes it. The
# whole sequence has to be a single semicolon-separated string.
#
# Usage:
#   .\tools\shot.ps1                     # map01, default 9s settle
#   .\tools\shot.ps1 -Map map05 -Tics 420
#   .\tools\shot.ps1 -Extra '+rt_flsh 1'
param(
  [string]$Map = 'map01',
  [int]$Tics = 300,            # 35 tics = 1 second of game time
  [int]$Width = 1920,
  [int]$Height = 820,
  # Empty = <repo>\screen\shots. It cannot default to a $PROJ-derived path here:
  # param() must be the FIRST statement in the file, so $PROJ does not exist yet
  # when the defaults are evaluated. It was written as '$PROJ\screen\shots' in
  # single quotes, which does not expand and produced a literal '$PROJ' folder.
  [string]$OutDir = '',
  [string]$Extra = '',
  # Extra PWADs appended to the -file list, for lab maps that are not part of the
  # shipping set (the shadow lab's d64rshadowlab.wad, say). Paths are relative to
  # Doom64-Retribution\ unless rooted. Kept separate from -Extra because that one
  # is +cvar arguments and lands AFTER -file, where a filename would be read as a
  # command and silently ignored.
  [string[]]$ExtraFiles = @(),
  # Where to write the engine's console log. `logfile` is a CCMD, not a
  # command-line switch -- `-logfile` is silently ignored and produces nothing
  # (launch-retribution-rt.cmd:643 does it the same way). It is placed BEFORE
  # +exec so the pins and everything after them are captured.
  #
  # It has to be explicit: the repo-root rt-console.log belongs to whatever last
  # ran from the repo root, and this script's working directory is the build
  # tree, so reading that file after a run here returns the PREVIOUS session's
  # numbers -- worse than having no log.
  [string]$LogFile = '',
  # Launch and LEAVE IT RUNNING for a human, instead of settling + screenshotting
  # + quitting. Same file list, same pins, same extras -- so what you walk around
  # in is exactly what the captures were taken from.
  [switch]$Play,
  # Turn in place before the screenshot: tics of held +left (negative = +right).
  # The MAP01 cage is 90 degrees LEFT of the spawn view, so a straight-ahead
  # settle-and-shoot frames the wrong wall entirely. Keyboard turning has the
  # classic Doom slow-start (~2 deg/tic for 6 tics, ~5 deg/tic after), so the
  # tic count is calibrated by looking at the shot, not computed.
  [int]$Turn = 0,
  # Teleport the player to "x y" right after load (gzdoom `warp` cheat; needs
  # sv_cheats, added automatically). Coordinates come from the map data --
  # sector bounds out of the wad -- not from squinting at screenshots.
  [string]$WarpTo = '',
  # Tics of held +lookup (negative = +lookdown) before the settle. A ceiling
  # fixture is the subject of most of this work and it is ABOVE the horizon, so
  # a straight-ahead capture shows the shadow it casts but never the fixture
  # itself -- which is the half that answers "is the light on the painted bulb".
  [int]$Pitch = 0,
  # BURST: take this many screenshots instead of one, every -BurstEvery tics,
  # the first at -Tics. For measuring anything TEMPORAL -- noise, boiling,
  # ghosting, history loss -- which a single settled frame cannot see at all:
  # after a few seconds standing still the temporal history has converged and
  # throwing it away costs almost nothing, so a still reads "no cost" for a
  # change whose entire cost is in motion. That mistake has been made once here
  # (docs/rt-volumetric-edge-outlines.md S7.1) and this is the instrument that
  # stops it being made twice.
  [int]$Burst = 0,
  [int]$BurstEvery = 4,
  # Hold +left from this many tics BEFORE the first shot until the run ends, so
  # the whole burst happens under motion. Not cosmetic: a temporal upscaler
  # keeps its history when nothing moves, so the artefacts that only appear when
  # history is rejected -- which is the interesting class -- need the camera
  # turning to show up at all. The motion is deterministic (same map, same
  # tics, same key), so two arms are comparable frame for frame.
  [int]$BurstTurn = 0
)

$ErrorActionPreference = 'Stop'
# Repo root, derived from this script's own location. Must come AFTER param().
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
if (-not $OutDir) { $OutDir = Join-Path $Root 'screen\shots' }
$Mods = Join-Path $Root 'Doom64-Retribution'
$Wd   = Join-Path $Root 'sourcecode\gzdoom-rt\build\RelWithDebInfo'
$Exe  = Join-Path $Wd 'gzdoom.exe'
$Pins = Join-Path $Root 'tools\d64rt-pins.cfg'

New-Item -ItemType Directory -Force $OutDir | Out-Null
Get-Process gzdoom, gzdoom-mod -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Milliseconds 400

# Same file list as tools\launch-retribution-rt.cmd
$names = @(
  'D64RTR_v15.WAD','D64RTR_BRIGHTMAPS.PK3','d64r-lostsoul-rt.pk3','d64r-rt-flashlight.pk3',
  'D64MUS.PK3','d64r-seqlight-fix.wad','d64r-bulb-textures.wad',
  'd64r-sflatas-broken.wad',
  'd64r-ctel-fix.wad','d64r-rt-sky.pk3','d64r-lava-fx.pk3','d64r-poison-fx.pk3','d64r-blood-persist.pk3',
  'd64r-widescreen-gfx.pk3','d64r-mugshot.pk3'
)
$files = $names | ForEach-Object { '"' + (Join-Path $Mods $_) + '"' }
# Split on commas as well as taking a real array. `powershell -File script.ps1
# -ExtraFiles a,b` passes "a,b" as ONE literal string -- -File does no argument
# parsing -- so a .cmd wrapper cannot hand over two wads without this.
$ExtraFiles = @($ExtraFiles | ForEach-Object { $_ -split ',' } | Where-Object { $_ })
$files += $ExtraFiles | ForEach-Object {
  $p = if ([System.IO.Path]::IsPathRooted($_)) { $_ } else { Join-Path $Mods $_ }
  if (-not (Test-Path $p)) { throw "ExtraFiles: not found - $p" }
  '"' + $p + '"'
}

$before = @(Get-ChildItem $OutDir -Filter '*.png' -ErrorAction SilentlyContinue | ForEach-Object { $_.Name })

# ONE command string. Semicolons, not separate + arguments.
$turnCmd = ''
if ($WarpTo) {
  # `warp` is a cheat CCMD, so sv_cheats has to be on first. It goes BEFORE the
  # aim block and before the settle, so the denoiser accumulates at the final
  # position rather than smearing the teleport into the captured frame.
  $turnCmd = "sv_cheats 1; warp $WarpTo; "
}
if ($Turn -ne 0 -or $Pitch -ne 0) {
  # Aim EARLY (after 30 tics), then let the full settle run with the final view:
  # the denoiser needs stationary history, and a turn just before the screenshot
  # would capture a frame of smeared temporal accumulation.
  $turnCmd += 'wait 30; '
  $spent = 30
  if ($Turn -ne 0) {
    $dir = if ($Turn -gt 0) { 'left' } else { 'right' }
    $t = [math]::Abs($Turn)
    $turnCmd += "+$dir; wait $t; -$dir; "
    $spent += $t
  }
  if ($Pitch -ne 0) {
    $pdir = if ($Pitch -gt 0) { 'lookup' } else { 'lookdown' }
    $p = [math]::Abs($Pitch)
    $turnCmd += "+$pdir; wait $p; -$pdir; "
    $spent += $p
  }
  $Tics = [math]::Max(60, $Tics - $spent)
}
# BURST uses the engine's own map-time counters (rt_autoshot / _every /
# rt_autoquit) rather than a console `wait` chain, because they count MAP time:
# the shots land at known tics whatever the load took, and two arms line up
# frame for frame. The turn is still a console command, held to the end of the
# run rather than released.
$burstCvars = ''
if ($Burst -gt 0 -and -not $Play) {
  $last = $Tics + ($Burst - 1) * $BurstEvery
  $burstCvars = "+rt_autoshot $Tics +rt_autoshot_every $BurstEvery +rt_autoquit $($last + 20)"
}

$seq = if ($Play) { '' }
       elseif ($Burst -gt 0) {
         if ($BurstTurn -gt 0) { "+`"wait $([math]::Max(1, $Tics - $BurstTurn)); +left`"" } else { '' }
       }
       else { "+`"$turnCmd" + "wait $Tics; screenshot; wait 40; quit`"" }

$argLine = (@('-iwad','"D:\Games\GZDoom\doom2.wad"','-file') + $files + @(
  '-rtnolauncher', '-width', "$Width", '-height', "$Height",
  '-shotdir', ('"' + $OutDir + '"'),
  '+queryiwad','false','+vid_fullscreen','0',
  $(if ($LogFile) { '+logfile' } else { '' }),
  $(if ($LogFile) { '"' + $LogFile + '"' } else { '' }),
  '+exec', ('"' + $Pins + '"'),
  '+map', $Map,
  $Extra,
  $burstCvars,
  $seq
) | Where-Object { $_ -ne '' }) -join ' '

if ($Play) { Write-Host "launching $Map to play (no capture)" }
elseif ($Burst -gt 0) {
  Write-Host ("launching $Map, BURST of $Burst every $BurstEvery tics from $Tics" +
              $(if ($BurstTurn -gt 0) { " (turning from tic $($Tics - $BurstTurn))" } else { '' }) +
              " -> $OutDir")
}
else { Write-Host "launching $Map, settling $Tics tics ($([math]::Round($Tics/35.0,1))s) -> $OutDir" }
$p = Start-Process -FilePath $Exe -WorkingDirectory $Wd -ArgumentList $argLine -PassThru
if ($Play) { return }
$p | Wait-Process -Timeout 240 -ErrorAction SilentlyContinue
if (-not $p.HasExited) { $p | Stop-Process -Force; Write-Host 'TIMEOUT - killed' }

$after = Get-ChildItem $OutDir -Filter '*.png' -ErrorAction SilentlyContinue | Where-Object { $before -notcontains $_.Name }
if ($after) {
  if ($Burst -gt 0) {
    Write-Host "BURST: $(@($after).Count) frames in $OutDir"
  } else {
    $after | Sort-Object LastWriteTime | Select-Object -Last 1 | ForEach-Object {
      Write-Host "SHOT: $($_.FullName)"
    }
  }
} else {
  Write-Host 'NO SCREENSHOT PRODUCED'
}
