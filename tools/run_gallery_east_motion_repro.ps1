# Repo root, derived from this script's own location.
$PROJ = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
param(
  [string]$OutDir = '',
  [double]$EmisMapBoost = 200,
  [double]$Sky = 80,
  [double]$Flsh = 0,
  [string]$Tag = 'east_motion_repro',
  [int]$Width = 1280,
  [int]$Height = 720,
  [int]$TimeoutSec = 300
)

$ErrorActionPreference = 'Stop'
$py = 'C:\Users\Winter\AppData\Local\Programs\Python\Python313\python.exe'
$root = '$PROJ'
if (-not $OutDir) { $OutDir = Join-Path $root "screen\endwall_$Tag" }

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
Get-ChildItem $OutDir -Filter 'Screenshot_*.png' -ErrorAction SilentlyContinue | Remove-Item -Force
Get-ChildItem $OutDir -Filter 'step_*.png' -ErrorAction SilentlyContinue | Remove-Item -Force
Get-Process gzdoom -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Milliseconds 500

& $py (Join-Path $root 'tools\pack_gallery_wall_ab.py') | Out-Host
$pk3 = Join-Path $root 'Doom64-Retribution\d64r-gallery-wall-ab.pk3'
$wd = Join-Path $root 'sourcecode\gzdoom-rt\build\RelWithDebInfo'
$log = Join-Path $OutDir 'stdout.txt'
Remove-Item $log -Force -ErrorAction SilentlyContinue

$skyAlways = if ($Sky -gt 0) { 'true' } else { 'false' }
Write-Host "east motion repro sky=$Sky boost=$EmisMapBoost flsh=$Flsh -> $OutDir"

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
  # One tic ≈ one present so MakeScreenShot HWND grab isn't stale
  '+cl_capfps', 'true', '+vid_maxfps', '35',
  '+sv_cheats', '1', '+map', 'map99',
  '+freelook', 'false', '+freelook0_pitch0', 'true',
  '+enablescriptscreenshot', '1', '+screenshot_dir', $OutDir,
  '+god', '+gl_noskyboxes', 'true',
  '+rt_mod_compat', '1', '+r_drawvoxels', '0',
  '+rt_fluid', 'false', '+rt_autoexport', 'false',
  '+rt_upscale_dlss', '2', '+rt_rayreconstr', '1', '+rt_framegen', '0',
  '+rt_sky', "$Sky", '+rt_sky_always', $skyAlways,
  '+rt_sun', '0',
  '+rt_autoexport_light', '50',
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
Start-Sleep -Milliseconds 700
Get-Process gzdoom -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue

# Labels filled generically — many burst frames per yaw
$shots = @(Get-ChildItem $OutDir -Filter 'Screenshot_*.png' | Sort-Object LastWriteTime, Name)
Write-Host "done=$done shots=$($shots.Count)"
# Parse t= from stdout if present; else sequential
$logTxt = if (Test-Path $log) { Get-Content $log -Raw } else { '' }
$ts = [regex]::Matches($logTxt, 'D64RtWallAbShot:\s+(?:hist mid-hall t=(\d+)|(\d+)\s+(\S+)\s+yaw=(\d+)\s+t=(\d+))')
for ($i = 0; $i -lt $shots.Count; $i++) {
  if ($i -lt $ts.Count) {
    $m = $ts[$i]
    if ($m.Groups[1].Success) {
      $lab = 'hist_t{0:d02}' -f [int]$m.Groups[1].Value
    } else {
      $lab = '{0}_t{1:d02}' -f $m.Groups[3].Value, [int]$m.Groups[5].Value
    }
  } else {
    $lab = '{0:d2}' -f $i
  }
  $dest = Join-Path $OutDir ("step_{0:d2}_{1}.png" -f $i, $lab)
  if (Test-Path $dest) { Remove-Item $dest -Force }
  Move-Item $shots[$i].FullName $dest
  Write-Host "  -> $($dest | Split-Path -Leaf)"
}

& $py -c @"
from PIL import Image
from pathlib import Path
d = Path(r'$OutDir')
for p in sorted(d.glob('step_*.png')):
    im = Image.open(p).convert('RGB'); w,h = im.size
    g = im.crop((8, 48, w-8, h-70)); gw,gh = g.size
    def band(y0,y1):
        c = g.crop((gw//10, y0, gw*9//10, y1)); px=list(c.getdata())
        return sum(0.2126*r+0.7152*g+0.0722*b for r,g,b in px)/len(px)
    print(f'{p.name}: top={band(0,gh//3):.1f} mid={band(gh//3,2*gh//3):.1f} bot={band(2*gh//3,gh):.1f} all={band(0,gh):.1f}')
"@
