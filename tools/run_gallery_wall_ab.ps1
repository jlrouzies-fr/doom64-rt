# Repo root, derived from this script's own location.
$PROJ = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
param(
  [string]$Side = 'west',
  [string]$OutDir = '',
  [double]$EmisMapBoost = 200,
  [double]$Sky = 80,
  [double]$AutoExportLight = 50,
  [double]$Flsh = 0,
  [string]$Tag = '',
  [int]$Width = 1280,
  [int]$Height = 720,
  [int]$TimeoutSec = 90
)

$ErrorActionPreference = 'Stop'
$py = 'C:\Users\Winter\AppData\Local\Programs\Python\Python313\python.exe'
$root = '$PROJ'
if (-not $Tag) { $Tag = "${Side}_sky${Sky}_boost${EmisMapBoost}" }
if (-not $OutDir) { $OutDir = Join-Path $root "screen\endwall_$Tag" }

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
Get-ChildItem $OutDir -Filter 'Screenshot_*.png' -ErrorAction SilentlyContinue | Remove-Item -Force
Get-ChildItem $OutDir -Filter 'wall_*.png' -ErrorAction SilentlyContinue | Remove-Item -Force
Get-Process gzdoom -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Milliseconds 400

& $py (Join-Path $root 'tools\pack_gallery_wall_ab.py') --side $Side | Out-Host
$pk3 = Join-Path $root 'Doom64-Retribution\d64r-gallery-wall-ab.pk3'
$wd = Join-Path $root 'sourcecode\gzdoom-rt\build\RelWithDebInfo'
$log = Join-Path $OutDir 'stdout.txt'
Remove-Item $log -Force -ErrorAction SilentlyContinue

$skyAlways = if ($Sky -gt 0) { 'true' } else { 'false' }
Write-Host "endwall MOVE+shot side=$Side sky=$Sky boost=$EmisMapBoost flsh=$Flsh -> $OutDir"

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
  '-shotdir', $OutDir,
  '+vid_fullscreen', '0', '+win_maximized', '0',
  '+win_w', "$Width", '+win_h', "$Height",
  '+sv_cheats', '1', '+map', 'map99',
  '+freelook', 'false', '+freelook0_pitch0', 'true',
  '+enablescriptscreenshot', '1', '+screenshot_dir', $OutDir,
  '+god', '+gl_noskyboxes', 'true',
  '+rt_mod_compat', '1', '+r_drawvoxels', '0',
  '+rt_fluid', 'false', '+rt_autoexport', 'false',
  '+rt_upscale_dlss', '2', '+rt_rayreconstr', '1', '+rt_framegen', '0',
  '+rt_sky', "$Sky", '+rt_sky_always', $skyAlways,
  '+rt_sun', '0',
  '+rt_autoexport_light', "$AutoExportLight",
  '+rt_emis_mapboost', "$EmisMapBoost",
  '+rt_emis_additive_dflt', '0.15',
  '+rt_emis_maxscrcolor', '12',
  '+rt_classic', '0', '+rt_flsh', "$Flsh",
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

$shots = @(Get-ChildItem $OutDir -Filter 'Screenshot_*.png' | Sort-Object LastWriteTime, Name)
if ($shots.Count -lt 1) { throw "no screenshot tag=$Tag" }
$dest = Join-Path $OutDir "wall_$Tag.png"
if (Test-Path $dest) { Remove-Item $dest -Force }
Move-Item $shots[0].FullName $dest
Write-Host "done=$done -> $dest"

& $py -c @"
from PIL import Image
from pathlib import Path
p = Path(r'$dest')
im = Image.open(p).convert('RGB')
w,h = im.size
# exclude window chrome / HUD
g = im.crop((8, 48, w-8, h-70)); gw,gh = g.size
def band(y0,y1):
    c = g.crop((gw//10, y0, gw*9//10, y1)); d=list(c.getdata())
    ll=[0.2126*r+0.7152*g+0.0722*b for r,g,b in d]
    return sum(ll)/len(ll)
top=band(0, gh//3); mid=band(gh//3, 2*gh//3); bot=band(2*gh//3, gh)
print(f'tag=$Tag top={top:.1f} mid={mid:.1f} bot={bot:.1f} game={band(0,gh):.1f}')
"@
