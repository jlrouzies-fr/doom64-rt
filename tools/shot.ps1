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
  [switch]$Play
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
  'D64MUS.PK3','d64r-3dfloor-rtfix.wad','d64r-seqlight-fix.wad','d64r-bulb-textures.wad',
  'd64r-ctel-fix.wad','d64r-rt-sky.pk3','d64r-lava-fx.pk3','d64r-blood-persist.pk3',
  'd64r-widescreen-gfx.pk3','d64r-mugshot.pk3'
)
$files = $names | ForEach-Object { '"' + (Join-Path $Mods $_) + '"' }
$files += $ExtraFiles | ForEach-Object {
  $p = if ([System.IO.Path]::IsPathRooted($_)) { $_ } else { Join-Path $Mods $_ }
  if (-not (Test-Path $p)) { throw "ExtraFiles: not found - $p" }
  '"' + $p + '"'
}

$before = @(Get-ChildItem $OutDir -Filter '*.png' -ErrorAction SilentlyContinue | ForEach-Object { $_.Name })

# ONE command string. Semicolons, not separate + arguments.
$seq = if ($Play) { '' } else { "+`"wait $Tics; screenshot; wait 40; quit`"" }

$argLine = (@('-iwad','"D:\Games\GZDoom\doom2.wad"','-file') + $files + @(
  '-rtnolauncher', '-width', "$Width", '-height', "$Height",
  '-shotdir', ('"' + $OutDir + '"'),
  '+queryiwad','false','+vid_fullscreen','0',
  $(if ($LogFile) { '+logfile' } else { '' }),
  $(if ($LogFile) { '"' + $LogFile + '"' } else { '' }),
  '+exec', ('"' + $Pins + '"'),
  '+map', $Map,
  $Extra,
  $seq
) | Where-Object { $_ -ne '' }) -join ' '

if ($Play) { Write-Host "launching $Map to play (no capture)" }
else { Write-Host "launching $Map, settling $Tics tics ($([math]::Round($Tics/35.0,1))s) -> $OutDir" }
$p = Start-Process -FilePath $Exe -WorkingDirectory $Wd -ArgumentList $argLine -PassThru
if ($Play) { return }
$p | Wait-Process -Timeout 240 -ErrorAction SilentlyContinue
if (-not $p.HasExited) { $p | Stop-Process -Force; Write-Host 'TIMEOUT - killed' }

$after = Get-ChildItem $OutDir -Filter '*.png' -ErrorAction SilentlyContinue | Where-Object { $before -notcontains $_.Name }
if ($after) {
  $after | Sort-Object LastWriteTime | Select-Object -Last 1 | ForEach-Object {
    Write-Host "SHOT: $($_.FullName)"
  }
} else {
  Write-Host 'NO SCREENSHOT PRODUCED'
}
