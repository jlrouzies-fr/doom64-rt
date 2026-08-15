# Repo root, derived from this script's own location.
$PROJ = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
param(
  [string]$OutDir = '',
  [string]$Mode = 'categories',
  [int]$Width = 1280,
  [int]$Height = 720,
  [int]$TimeoutSec = 150,
  [double]$EmisMapBoost = 200,
  [int]$ModCompat = 1
)

$ErrorActionPreference = 'Stop'
$py = 'C:\Users\Winter\AppData\Local\Programs\Python\Python313\python.exe'
$root = '$PROJ'
if (-not $OutDir) {
  $OutDir = Join-Path $root 'screen\emis_iso'
}

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
Get-ChildItem $OutDir -Filter 'Screenshot_*.png' -ErrorAction SilentlyContinue | Remove-Item -Force
Get-ChildItem $OutDir -Filter 'room_*.png' -ErrorAction SilentlyContinue | Remove-Item -Force

Get-Process gzdoom -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Milliseconds 500

Write-Host "Building emis-iso gallery (mode=$Mode)..."
& $py (Join-Path $root 'tools\build_emis_iso_gallery.py') --mode $Mode | Out-Host

$wad = Join-Path $root 'Doom64-Retribution\d64remisiso.wad'
$mapinfo = Join-Path $root 'Doom64-Retribution\d64r-emis-iso-mapinfo.pk3'
$tour = Join-Path $root 'Doom64-Retribution\d64r-emis-iso-tour.pk3'
$roomsJson = Join-Path $root 'tools\_emis_iso\rooms.json'
foreach ($p in @($wad, $mapinfo, $tour, $roomsJson)) {
  if (-not (Test-Path $p)) { throw "missing $p" }
}

$wd = Join-Path $root 'sourcecode\gzdoom-rt\build\RelWithDebInfo'
$log = Join-Path $OutDir 'stdout.txt'
Remove-Item $log -Force -ErrorAction SilentlyContinue

$roomCount = (Get-Content $roomsJson -Raw | ConvertFrom-Json).rooms.Count
Write-Host "emis-iso tour -> $OutDir ($roomCount rooms, mapboost=$EmisMapBoost, sky=0)"

$arg = @(
  '-iwad', 'D:\Games\GZDoom\doom2.wad', '-file',
  (Join-Path $root 'Doom64-Retribution\D64RTR_v15.WAD'),
  (Join-Path $root 'Doom64-Retribution\D64RTR_BRIGHTMAPS.PK3'),
  $wad,
  $mapinfo,
  (Join-Path $root 'Doom64-Retribution\d64r-rt-sky.pk3'),
  $tour,
  '-rtnolauncher', '-0',
  '-width', "$Width", '-height', "$Height", '-stdout',
  '-shotdir', $OutDir,
  '+vid_fullscreen', '0',
  '+win_maximized', '0',
  '+win_w', "$Width", '+win_h', "$Height",
  '+win_x', '0', '+win_y', '0',
  '+sv_cheats', '1', '+map', 'map97',
  '+freelook', 'false', '+freelook0_pitch0', 'true',
  '+enablescriptscreenshot', '1',
  '+screenshot_dir', $OutDir,
  '+screenshot_quiet', 'false',
  '+god', '+gl_noskyboxes', 'true',
  '+rt_mod_compat', "$ModCompat", '+r_drawvoxels', '0',
  '+rt_fluid', 'false', '+rt_autoexport', 'false',
  '+rt_upscale_dlss', '2', '+rt_rayreconstr', '1', '+rt_framegen', '0',
  '+rt_sky', '0', '+rt_sky_always', 'false',
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
    if ($txt -match 'D64RtEmisIsoTour: done') {
      $done = $true
      break
    }
  }
  if ($proc.HasExited) { break }
}

Start-Sleep -Milliseconds 800
Get-Process gzdoom -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue

$rooms = (Get-Content $roomsJson -Raw | ConvertFrom-Json).rooms
$shots = @(Get-ChildItem $OutDir -Filter 'Screenshot_*.png' | Sort-Object LastWriteTime, Name)
for ($i = 0; $i -lt $shots.Count; $i++) {
  $id = if ($i -lt $rooms.Count) { $rooms[$i].id } else { '{0:d2}' -f $i }
  $dest = Join-Path $OutDir ("room_{0:d2}_{1}.png" -f $i, $id)
  if (Test-Path $dest) { Remove-Item $dest -Force }
  Move-Item $shots[$i].FullName $dest
  Write-Host "  $($shots[$i].Name) -> room_$('{0:d2}' -f $i)_$id.png"
}

Write-Host "done=$done shots=$($shots.Count) expected=$roomCount out=$OutDir"
if (-not $done) { Write-Warning 'tour did not print done (timeout or early exit)' }
if ($shots.Count -lt $roomCount) { throw "expected $roomCount screenshots, got $($shots.Count)" }

& $py (Join-Path $root 'tools\score_emis_iso.py') $OutDir
exit $LASTEXITCODE
