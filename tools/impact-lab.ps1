# THE IMPACT LAB. Plant one mark on a wall, photograph it, quit.
#
# WHY THIS EXISTS. The scorch was tuned for several rounds off screenshots taken
# while playing, and every one of them differed in a dozen ways at once: the mark
# landed wherever the rocket happened to hit, at whatever angle, with the blast's
# own smoke and light sitting on top of it, on whatever wall texture was there,
# at whatever range the player was standing. Changing one value and comparing two
# such captures cannot tell you what the value did.
#
# So this fixes everything except the thing being judged:
#   * `arc_here` plants ONE mark of a stated kind exactly at the crosshair
#     (rt_impacts.cpp), so no weapon is fired and nothing else happens
#   * rt_smoke off -- smoke in front of the mark is the single biggest source of
#     "it looks different this time", and it is never what is being judged here
#   * rt_spark off -- a hitscan shower would land in the same frame
#   * the same map, the same warp, the same aim, the same settle every run
#
# Usage:
#   .\tools\impact-lab.ps1                      # plasma mark, default framing
#   .\tools\impact-lab.ps1 -Kind ember          # rocket: scorch + embers
#   .\tools\impact-lab.ps1 -Kind bfg -Tag wide
#   .\tools\impact-lab.ps1 -Extra '+rt_arc_burn_mottle 0'
#   .\tools\impact-lab.ps1 -Play                # walk around it instead
#
# The capture lands in screen\lab\ named for the kind and tag, so a before/after
# pair is two files you can open side by side rather than two runs you have to
# remember.
param(
  # barrel / barrel-shards / barrel-scorch go through `barrel_here` instead of
  # `arc_here`, and take a DIFFERENT SEQUENCE (below): a barrel burst is thrown
  # into the air off the floor rather than burnt onto a wall, so there is
  # nothing to walk up to, and the two things worth looking at -- the plate in
  # flight and the plate at rest -- are seconds apart. That run captures both.
  [ValidateSet('plasma','bfg','arach','ember','barrel','barrel-shards','barrel-scorch')]
  [string]$Kind = 'plasma',
  # Free-text label for the capture filename -- put the thing you changed in it.
  [string]$Tag = '',
  # MAP96, the smoke lab's BRIGHT BEIGE room, and the choice matters. A scorch
  # is a decal: it works by REMOVING albedo, so it can only be judged against a
  # surface that had albedo to remove. On a dark wall it has almost nothing to
  # take away and looks like it is barely working -- the same trap that shipped
  # rt_sprite_ao_strength a third too low. MAP97 is the dark twin if the EMBERS
  # (which add light rather than removing it) are what is being looked at.
  [string]$Map = 'map96',
  # Tics to settle AFTER planting the mark. The path tracer needs time to
  # accumulate or the capture is noise rather than the effect; 120 is ~3.4 s.
  [int]$Settle = 120,
  [int]$Width = 1280,
  [int]$Height = 960,
  [string]$Extra = '',
  # Leave the game running for a human instead of capturing.
  [switch]$Play,
  # How close to stand. The mark is planted at the crosshair, so this decides how
  # much of the screen it fills -- point blank is where the tessellation shows.
  [int]$Approach = 150,
  # Tics of backing away AFTER planting the mark, before the settle.
  #
  # This is what makes the framing repeatable. Walking a fixed distance toward
  # the wall does not control anything useful: past about 60 tics the player is
  # already against it, so 95 and 150 give the identical view, and the mark ends
  # up filling the whole screen with no clean wall to judge it against. Walk all
  # the way in so the mark always lands on the same spot at the same angle, then
  # back off by this much to choose how big it is in frame.
  [int]$Back = 45
)

$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$OutDir = Join-Path $Root 'screen\lab'
$Wd   = Join-Path $Root 'sourcecode\gzdoom-rt\build\RelWithDebInfo'
$Exe  = Join-Path $Wd 'gzdoom.exe'
$Mods = Join-Path $Root 'Doom64-Retribution'
$Pins = Join-Path $Root 'tools\d64rt-pins.cfg'

if (-not (Test-Path $Exe)) { throw "no gzdoom.exe at $Exe -- build first" }
New-Item -ItemType Directory -Force $OutDir | Out-Null
Get-Process gzdoom, gzdoom-mod -ErrorAction SilentlyContinue |
  Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Milliseconds 400

$names = @(
  'D64RTR_v15.WAD','D64RTR_BRIGHTMAPS.PK3','d64r-lostsoul-rt.pk3','d64r-rt-flashlight.pk3',
  'D64MUS.PK3','d64r-3dfloor-rtfix.wad','d64r-seqlight-fix.wad','d64r-bulb-textures.wad',
  'd64r-sflatas-broken.wad','d64r-ctel-fix.wad','d64r-rt-sky.pk3','d64r-lava-fx.pk3',
  'd64r-blood-persist.pk3','d64r-widescreen-gfx.pk3','d64r-mugshot.pk3'
)
$files = $names | ForEach-Object { '"' + (Join-Path $Mods $_) + '"' }

# THE LAB ROOMS. Built by tools\build_smoke_lab.py -- MAP97 dark and cool,
# MAP96 bright and beige, MAP95 open to the moon, MAP94 lamp panes. Reused
# rather than rebuilt: they already exist, they are already plain rooms with
# nothing in them, and a second set would be a second thing to keep working.
foreach ($lab in @('d64rsmokelab.wad', 'd64r-smokelab-mapinfo.pk3')) {
  $p = Join-Path $Mods $lab
  if (-not (Test-Path $p)) { throw "missing lab wad $p -- run: python tools\build_smoke_lab.py" }
  $files += '"' + $p + '"'
}

# THE LAB'S OWN OVERRIDES, applied after the pins so they win. Everything here is
# about removing variables, not about looking good.
$lab = @(
  'rt_smoke 0',                 # the big one: nothing between camera and mark
  'rt_spark 0',                 # no hitscan shower in the same frame
  'rt_arc 1',
  'rt_arc_burn 1',
  'rt_ember 1',
  'rt_barrel 1',
  'rt_ember_smoke 0'            # embers still glow, but breathe nothing
  # NO `freeze` HERE, and it cost a run. It looks like exactly the right thing
  # for a still capture -- nothing moves, nothing wanders into frame -- but
  # `wait` counts TICS, and freezing the game stops the clock those tics come
  # from. The sequence reached `arc_here` (the log proved it: "ember mark at
  # 256 319 130, 1 live") and then simply stopped, because the `wait` after it
  # could never expire. `notarget` in the pins already keeps the monsters off.
) -join '; '

# ONE command string, semicolons not separate + arguments. `wait` defers only
# THE REST OF THE SAME string (c_dispatch.cpp:376) -- passing these as separate
# +args runs screenshot and quit at startup, before a frame has ever been
# presented, and the screenshot flag is set and never consumed.
$tag = if ($Tag) { "$Kind-$Tag" } else { $Kind }

$isBarrel = $Kind -like 'barrel*'

if ($isBarrel) {
  # THE BARREL RUN, and it differs from the mark run in three ways that all come
  # from the same fact: this effect is thrown into the room, not burnt onto a
  # wall.
  #
  #  1. NO APPROACH. `barrel_here` plants the burst 72 units in front of the
  #     camera on the floor; walking into a wall first would put it inside one.
  #  2. NO BACKING OFF EITHER -- the burst comes to the player rather than the
  #     player to it, so the framing is already fixed by that 72.
  #  3. TWO CAPTURES. Plate in flight and plate at rest are the two things worth
  #     judging and they are seconds apart, so one run takes both rather than
  #     two runs taking one each and differing in seed as well as in time.
  $sub = switch ($Kind) {
    'barrel-shards' { 'shards' }
    'barrel-scorch' { 'scorch' }
    default         { '' }
  }
  $seq = @(
    "wait 70",
    "sv_cheats 1",
    $lab,
    "barrel_here $sub",
    # ~0.7 s: still airborne, still tumbling. This is the frame that answers
    # "does it read as plate coming off a barrel" rather than as a spray.
    "wait 25",
    "screenshot",
    # Settled. This is the frame that answers "is it wreckage on the floor" --
    # whether pieces lie flat, whether they are sunk, whether the AO blobs sit
    # under them, and whether the scorch under it all is the right size.
    "wait $Settle",
    "screenshot"
  )
} else {
  $seq = @(
    "wait 70",                    # let the level finish loading
    "sv_cheats 1",
    $lab,
    "+forward",                   # walk up to the wall
    "wait $Approach",
    "-forward",
    "wait 10",
    "arc_here $Kind",
    "+back",
    "wait $Back",
    "-back",
    # The denoiser needs stationary history: a capture taken while still moving
    # is temporal smear, not the effect. The full settle runs AFTER the backing
    # off.
    "wait $Settle",
    # BARE `screenshot`, not `screenshot <name>`. With a name gzdoom writes that
    # exact filename relative to the working directory and -shotdir is not
    # consulted at all, so the capture lands in the build tree instead of the lab
    # folder and this script reports NO SCREENSHOT while the file exists. The
    # auto-numbered form honours -shotdir; the run is renamed below.
    "screenshot"
  )
}
if (-not $Play) { $seq += 'wait 20'; $seq += 'quit' }
$cmd = ($seq -join '; ')

$before = @(Get-ChildItem $OutDir -Filter '*.png' -ErrorAction SilentlyContinue |
            ForEach-Object { $_.Name })

# EVERYTHING BELOW FOLLOWS tools\shot.ps1 EXACTLY, and the two details that
# matter are both in docs/scripted-screenshots.md:
#
#  1. ONE ARGUMENT LINE, joined into a single string. Start-Process with an
#     ARRAY re-quotes each element, which splits the +"..." command string on
#     its spaces -- and then `wait` has nothing after it to defer, so screenshot
#     and quit both fire at startup before a frame has ever been presented. The
#     flag is set, never consumed, and nothing is printed. That is precisely the
#     failure this script hit on its first run.
#  2. -shotdir, not the screenshot_dir cvar. Destination precedence is
#     -shotdir -> screenshot_dir -> M_GetScreenshotsPath, and this project's
#     config points screenshot_dir at a smoke-lab folder, so an unqualified
#     capture lands somewhere non-obvious.
$LogPath = Join-Path $OutDir 'impact-lab.log'
$argLine = (@('-iwad', '"D:\Games\GZDoom\doom2.wad"', '-file') + $files + @(
  '-rtnolauncher', '-width', "$Width", '-height', "$Height",
  '-shotdir', ('"' + $OutDir + '"'),
  '+queryiwad', 'false', '+vid_fullscreen', '0',
  '+logfile', ('"' + $LogPath + '"'),
  '+exec', ('"' + $Pins + '"'),
  '+map', $Map,
  $Extra,
  "+`"$cmd`""
) | Where-Object { $_ -ne '' }) -join ' '

Write-Host "lab: $Kind -> $OutDir (settle $Settle tics)"
$p = Start-Process -FilePath $Exe -WorkingDirectory $Wd -ArgumentList $argLine -PassThru
if ($Play) { return }
$p | Wait-Process -Timeout 240 -ErrorAction SilentlyContinue
if (-not $p.HasExited) { $p | Stop-Process -Force; Write-Host 'TIMEOUT - killed' }

$new = @(Get-ChildItem $OutDir -Filter '*.png' -ErrorAction SilentlyContinue |
         Where-Object { $before -notcontains $_.Name } | Sort-Object LastWriteTime)
if ($new) {
  # Rename to something a before/after pair can be read from, since the capture
  # itself has to be auto-numbered (see the note on `screenshot` above). A run
  # may produce more than one -- the barrel takes two, in flight and at rest --
  # so they are numbered in the order they were taken rather than the last one
  # winning silently.
  $i = 0
  foreach ($shot in $new) {
    $i++
    $suffix = if ($new.Count -gt 1) { "-$i" } else { '' }
    $dest = Join-Path $OutDir "lab-$tag$suffix.png"
    if (Test-Path $dest) { Remove-Item $dest -Force }
    Move-Item $shot.FullName $dest
    "SHOT: $dest"
  }
} else { "NO SCREENSHOT -- see $LogPath" }
