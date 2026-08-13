# Repo root, derived from this script's own location.
$PROJ = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
param(
  [string]$OutDir = '',
  [int]$Width = 1280,
  [int]$Height = 720,
  [int]$TimeoutSec = 120,
  [double]$MaxDelta = 25,
  [double]$MaxBrightFrac = 0.08,
  [double]$MinMean = 5,
  [int]$ModCompat = 1,
  [double]$EmisMapBoost = 200
)

$ErrorActionPreference = 'Stop'
$py = 'C:\Users\Winter\AppData\Local\Programs\Python\Python313\python.exe'
$root = '$PROJ'
if (-not $OutDir) {
  $OutDir = Join-Path $root 'screen\yaw_sweep'
}

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
Get-ChildItem $OutDir -Filter 'Screenshot_*.png' -ErrorAction SilentlyContinue | Remove-Item -Force
Get-ChildItem $OutDir -Filter 'yaw_*.png' -ErrorAction SilentlyContinue | Remove-Item -Force

Get-Process gzdoom -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Milliseconds 500

& $py (Join-Path $root 'tools\pack_gallery_yaw_sweep.py') | Out-Host
$pk3 = Join-Path $root 'Doom64-Retribution\d64r-gallery-yaw-sweep.pk3'
if (-not (Test-Path $pk3)) { throw "missing $pk3" }

$wd = Join-Path $root 'sourcecode\gzdoom-rt\build\RelWithDebInfo'
$log = Join-Path $OutDir 'stdout.txt'
Remove-Item $log -Force -ErrorAction SilentlyContinue

Write-Host "yaw sweep -> $OutDir (8 angles, mod_compat=$ModCompat mapboost=$EmisMapBoost)"

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
  '+vid_fullscreen', '0',
  '+win_maximized', '0',
  '+win_w', "$Width", '+win_h', "$Height",
  '+win_x', '0', '+win_y', '0',
  '+sv_cheats', '1', '+map', 'map99',
  '+freelook', 'false', '+freelook0_pitch0', 'true',
  '+enablescriptscreenshot', '1',
  '+screenshot_dir', $OutDir,
  '+screenshot_quiet', 'false',
  '+god', '+gl_noskyboxes', 'true',
  '+rt_mod_compat', "$ModCompat", '+r_drawvoxels', '0',
  '+rt_fluid', 'false', '+rt_autoexport', 'false',
  '+rt_upscale_dlss', '2', '+rt_rayreconstr', '1', '+rt_framegen', '0',
  '+rt_sky', '80', '+rt_sky_always', 'true',
  '+rt_sun', '0',
  '+rt_autoexport_light', '50',
  '+rt_emis_mapboost', "$EmisMapBoost",
  '+rt_emis_additive_dflt', '0.15',
  '+rt_emis_maxscrcolor', '12',
  '+rt_classic', '0',
  '+rt_flsh', '0',
  '+rt_normalmap_stren', '1', '+rt_heightmap_stren', '1'
)

$proc = Start-Process -FilePath (Join-Path $wd 'gzdoom.exe') -WorkingDirectory $wd `
  -ArgumentList $arg -PassThru -RedirectStandardOutput $log
Write-Host "pid=$($proc.Id)"

$deadline = (Get-Date).AddSeconds($TimeoutSec)
$done = $false
while ((Get-Date) -lt $deadline) {
  Start-Sleep -Milliseconds 500
  if (Test-Path $log) {
    $txt = Get-Content $log -Raw -ErrorAction SilentlyContinue
    if ($txt -match 'D64RtYawSweep: done') {
      $done = $true
      break
    }
  }
  if ($proc.HasExited) { break }
}

Start-Sleep -Milliseconds 800
Get-Process gzdoom -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue

$shots = @(Get-ChildItem $OutDir -Filter 'Screenshot_*.png' | Sort-Object LastWriteTime, Name)
$angles = @(0, 45, 90, 135, 180, 225, 270, 315)
for ($i = 0; $i -lt $shots.Count; $i++) {
  $ang = if ($i -lt $angles.Count) { $angles[$i] } else { $i * 45 }
  $dest = Join-Path $OutDir ('yaw_{0:d3}.png' -f $ang)
  if (Test-Path $dest) { Remove-Item $dest -Force }
  Move-Item $shots[$i].FullName $dest
  Write-Host "  $($shots[$i].Name) -> yaw_$('{0:d3}' -f $ang).png"
}

Write-Host "done=$done shots=$($shots.Count) out=$OutDir"
if (-not $done) { Write-Warning 'tour did not print done (timeout or early exit)' }
if ($shots.Count -lt 8) { throw "expected 8 screenshots, got $($shots.Count)" }

& $py (Join-Path $root 'tools\score_yaw_sweep.py') $OutDir `
  --max-delta $MaxDelta `
  --max-bright-frac $MaxBrightFrac `
  --max-mean 70 `
  --max-p95 160
exit $LASTEXITCODE
