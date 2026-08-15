# Repo root, derived from this script's own location.
$PROJ = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
param(
  [string]$OutRoot = '$PROJ\screen\wallturned_ab',
  [int]$Width = 1280,
  [int]$Height = 720,
  [int]$TimeoutSec = 90
)

$ErrorActionPreference = 'Stop'
$py = 'C:\Users\Winter\AppData\Local\Programs\Python\Python313\python.exe'
$root = '$PROJ'
$wd = Join-Path $root 'sourcecode\gzdoom-rt\build\RelWithDebInfo'
$pk3 = Join-Path $root 'Doom64-Retribution\d64r-gallery-wall-ab.pk3'

Get-Process gzdoom -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Milliseconds 400
& $py (Join-Path $root 'tools\pack_gallery_wall_ab.py') | Out-Host

$cases = @(
  @{ Tag = 'rr1_boost200'; Rr = 1; Dlss = 2; Boost = 200; Sky = 80 },
  @{ Tag = 'rr0_boost200'; Rr = 0; Dlss = 0; Boost = 200; Sky = 80 },
  @{ Tag = 'rr1_boost0';   Rr = 1; Dlss = 2; Boost = 0;   Sky = 80 },
  @{ Tag = 'rr1_sky0';     Rr = 1; Dlss = 2; Boost = 200; Sky = 0 }
)

New-Item -ItemType Directory -Force -Path $OutRoot | Out-Null

function Run-Case($c) {
  $out = Join-Path $OutRoot $c.Tag
  New-Item -ItemType Directory -Force -Path $out | Out-Null
  Get-ChildItem $out -Filter '*.png' -ErrorAction SilentlyContinue | Remove-Item -Force
  $log = Join-Path $out 'stdout.txt'
  Remove-Item $log -Force -ErrorAction SilentlyContinue
  $skyAlways = if ($c.Sky -gt 0) { 'true' } else { 'false' }
  Write-Host "=== $($c.Tag) rr=$($c.Rr) dlss=$($c.Dlss) boost=$($c.Boost) sky=$($c.Sky) ==="

  $arg = @(
    '-iwad', 'D:\Games\GZDoom\doom2.wad', '-file',
    (Join-Path $root 'Doom64-Retribution\D64RTR_v15.WAD'),
    (Join-Path $root 'Doom64-Retribution\D64RTR_BRIGHTMAPS.PK3'),
    (Join-Path $root 'Doom64-Retribution\d64rtexg.wad'),
    (Join-Path $root 'Doom64-Retribution\d64r-texgallery-mapinfo.pk3'),
    (Join-Path $root 'Doom64-Retribution\d64r-rt-sky.pk3'),
    $pk3,
    '-rtnolauncher', '-0',
    '-width', "$Width", '-height', "$Height", '-stdout',
    '-shotdir', $out,
    '+vid_fullscreen', '0', '+win_maximized', '0',
    '+win_w', "$Width", '+win_h', "$Height",
    '+cl_capfps', 'true', '+vid_maxfps', '35',
    '+sv_cheats', '1', '+map', 'map99',
    '+freelook', 'false', '+freelook0_pitch0', 'true',
    '+enablescriptscreenshot', '1', '+screenshot_dir', $out,
    '+god', '+gl_noskyboxes', 'true',
    '+rt_mod_compat', '1', '+r_drawvoxels', '0',
    '+rt_fluid', 'false', '+rt_autoexport', 'false',
    '+rt_upscale_dlss', "$($c.Dlss)", '+rt_rayreconstr', "$($c.Rr)", '+rt_framegen', '0',
    '+rt_sky', "$($c.Sky)", '+rt_sky_always', $skyAlways,
    '+rt_sun', '0',
    '+rt_emis_mapboost', "$($c.Boost)",
    '+rt_emis_additive_dflt', '0.15',
    '+rt_emis_maxscrcolor', '12',
    '+rt_classic', '0', '+rt_flsh', '0',
    '+rt_normalmap_stren', '1', '+rt_heightmap_stren', '1'
  )

  $proc = Start-Process -FilePath (Join-Path $wd 'gzdoom.exe') -WorkingDirectory $wd `
    -ArgumentList $arg -PassThru -RedirectStandardOutput $log
  $deadline = (Get-Date).AddSeconds($TimeoutSec)
  $done = $false
  while ((Get-Date) -lt $deadline) {
    Start-Sleep -Milliseconds 400
    if (Test-Path $log) {
      $txt = Get-Content $log -Raw -ErrorAction SilentlyContinue
      if ($txt -match 'D64RtWallAb: done') { $done = $true; break }
    }
    if ($proc.HasExited) { break }
  }
  Start-Sleep -Milliseconds 600
  Get-Process gzdoom -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue

  $shots = @(Get-ChildItem $out -Filter 'Screenshot_*.png' | Sort-Object LastWriteTime, Name)
  Write-Host "  done=$done shots=$($shots.Count)"
  if ($shots.Count -ge 1) {
    $dest = Join-Path $out 'wallturned.png'
    if (Test-Path $dest) { Remove-Item $dest -Force }
    Move-Item $shots[-1].FullName $dest
    Get-ChildItem $out -Filter 'Screenshot_*.png' -ErrorAction SilentlyContinue | Remove-Item -Force
  }
}

foreach ($c in $cases) { Run-Case $c }

& $py -c @"
from PIL import Image
from pathlib import Path
root = Path(r'$OutRoot')
for d in sorted(root.iterdir()):
    if not d.is_dir(): continue
    p = d / 'wallturned.png'
    if not p.exists():
        print(f'{d.name}: MISSING'); continue
    im = Image.open(p).convert('RGB'); w,h = im.size
    g = im.crop((8, 48, w-8, h-70)); gw,gh = g.size
    # right-half wall + mid band (ignore title/hud)
    c = g.crop((gw//2, gh//5, gw*9//10, gh*4//5)); px = list(c.getdata())
    L = [0.2126*r+0.7152*gg+0.0722*b for r,gg,b in px]
    bright = sum(1 for x in L if x > 40) / len(L)
    print(f'{d.name}: wall_mean={sum(L)/len(L):.1f} max={max(L):.1f} bright>40={bright*100:.1f}%')
"@
