param(
  [string]$OutDir = '',
  [int]$Width = 960,
  [int]$Height = 540,
  [ValidateSet('', 'before', 'after')]
  [string]$Tag = '',
  [string]$Indices = '',
  [int]$FlshIntensity = -1,
  [switch]$SkipExisting
)

$ErrorActionPreference = 'Stop'
$py = 'C:\Users\Winter\AppData\Local\Programs\Python\Python313\python.exe'
$root = 'G:\AI\Doom64-RT'
if (-not $OutDir) {
  $OutDir = Join-Path $root 'tools\_enemy_gallery\batch_eyes'
}
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

# Ensure map + full tour exist
& $py (Join-Path $root 'tools\build_enemy_gallery.py') | Out-Host

$booths = (Get-Content (Join-Path $root 'tools\_enemy_gallery\booths.json') -Raw | ConvertFrom-Json).booths
if ($Indices) {
  $indexList = @($Indices.Split(',') | ForEach-Object { [int]($_.Trim()) })
} else {
  $indexList = @(0..($booths.Count - 1))
}

$keep = @()
foreach ($idx in $indexList) {
  $name = if ($Tag) { "{0:d4}_{1}.png" -f $idx, $Tag } else { "{0:d4}.png" -f $idx }
  $p = Join-Path $OutDir $name
  if ($SkipExisting -and (Test-Path $p)) {
    Write-Host "skip existing $name"
    continue
  }
  if (Test-Path $p) { Remove-Item $p -Force }
  $keep += $idx
}
$indexList = $keep
if ($indexList.Count -eq 0) {
  Write-Host 'nothing to capture'
  exit 0
}

# Rewrite tour for sparse subset (absolute indices preserved in AbsIndex[])
$idxCsv = ($indexList -join ',')
& $py -c @"
import json, sys
from pathlib import Path
sys.path.insert(0, r'G:/AI/Doom64-RT/tools')
from build_enemy_gallery import write_tour_zscript
root = Path(r'G:/AI/Doom64-RT')
booths = json.loads((root/'tools/_enemy_gallery/booths.json').read_text(encoding='utf-8'))['booths']
idxs = [int(x) for x in '$idxCsv'.split(',') if x.strip() != '']
chunk = [dict(booths[i]) for i in idxs]
write_tour_zscript(chunk, abs_indices=idxs)
print('sparse enemy tour', idxs)
"@

$pkg = Join-Path $root 'tools\d64r-enemy-gallery-tour'
$pk3 = Join-Path $root 'Doom64-Retribution\d64r-enemy-gallery-tour.pk3'
Remove-Item $pk3 -Force -ErrorAction SilentlyContinue
Compress-Archive -Path "$pkg\*" -DestinationPath ($pk3 -replace '\.pk3$', '.zip') -Force
Move-Item -Force ($pk3 -replace '\.pk3$', '.zip') $pk3

Get-Process gzdoom -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Milliseconds 700

$wd = Join-Path $root 'sourcecode\gzdoom-rt\build\RelWithDebInfo'
$logName = if ($Tag) { "stdout_$Tag.txt" } else { 'stdout.txt' }
$log = Join-Path $OutDir $logName
Remove-Item $log -Force -ErrorAction SilentlyContinue
# After: dim flashlight so attached eye/fire lights read clearly
if ($FlshIntensity -lt 0) {
  $FlshIntensity = if ($Tag -eq 'after') { 35 } else { 200 }
}
Write-Host "enemy capture tag=$(if ($Tag) { $Tag } else { 'plain' }) flsh=$FlshIntensity"

$arg = @(
  '-iwad', 'D:\Games\GZDoom\doom2.wad', '-file',
  (Join-Path $root 'Doom64-Retribution\D64RTR_v15.WAD'),
  (Join-Path $root 'Doom64-Retribution\D64RTR_BRIGHTMAPS.PK3'),
  (Join-Path $root 'Doom64-Retribution\d64r-lostsoul-rt.pk3'),
  (Join-Path $root 'Doom64-Retribution\d64renemyg.wad'),
  (Join-Path $root 'Doom64-Retribution\d64r-enemygallery-mapinfo.pk3'),
  (Join-Path $root 'Doom64-Retribution\d64r-rt-sky.pk3'),
  $pk3,
  '-rtnolauncher', '-0',
  '-width', "$Width", '-height', "$Height", '-stdout',
  '-shotdir', $OutDir,
  '+vid_fullscreen', '0',
  '+win_maximized', '0',
  '+win_w', "$Width", '+win_h', "$Height",
  '+win_x', '0', '+win_y', '0',
  '+sv_cheats', '1', '+map', 'map98',
  '+freelook', 'false', '+freelook0_pitch0', 'true',
  '+enablescriptscreenshot', '1',
  '+screenshot_dir', $OutDir,
  '+screenshot_quiet', 'false',
  '+god', '+notarget', '+gl_noskyboxes', 'true',
  '+rt_mod_compat', '3', '+r_drawvoxels', '0',
  '+rt_dxgi', '1',
  '+rt_classic', '0', '+rt_autoexport', 'false', '+rt_fluid', 'false',
  '+rt_sky', '40', '+rt_sky_always', 'true', '+rt_upscale_dlss', '0',
  '+rt_sun', '0',
  '+rt_flsh', '1', '+rt_flsh_intensity', "$FlshIntensity",
  '+rt_emis_mapboost', '600',
  '+rt_emis_additive_dflt', '0.12',
  '+rt_emis_maxscrcolor', '4',
  '+rt_bloom_threshold', '20',
  '+rt_bloom_scale', '0.65',
  '+rt_normalmap_stren', '1', '+rt_heightmap_stren', '1'
)

$p = Start-Process -FilePath (Join-Path $wd 'gzdoom.exe') -WorkingDirectory $wd -ArgumentList $arg -RedirectStandardOutput $log -PassThru
Write-Host "started pid=$($p.Id)"

$deadline = (Get-Date).AddSeconds(50)
while (-not $p.HasExited) {
  $p.Refresh()
  if ($p.MainWindowHandle -ne [IntPtr]::Zero -and $p.MainWindowTitle -match 'Ray Traced') { break }
  Start-Sleep -Milliseconds 200
  if ((Get-Date) -gt $deadline) {
    Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
    throw 'window timeout'
  }
}
if ($p.HasExited) { throw "gzdoom exited early code=$($p.ExitCode)" }

Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class WinSizeE {
  [DllImport("user32.dll")] public static extern bool AdjustWindowRectEx(ref RECT r, uint style, bool menu, uint ex);
  [DllImport("user32.dll")] public static extern int GetWindowLong(IntPtr h, int n);
  [DllImport("user32.dll")] public static extern bool SetWindowPos(IntPtr h, IntPtr after, int x, int y, int cx, int cy, uint flags);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int cmd);
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left,Top,Right,Bottom; }
  public static void Force(IntPtr hwnd, int clientW, int clientH) {
    ShowWindow(hwnd, 9);
    uint style = (uint)GetWindowLong(hwnd, -16);
    uint ex = (uint)GetWindowLong(hwnd, -20);
    RECT r = new RECT { Left=0,Top=0,Right=clientW,Bottom=clientH };
    AdjustWindowRectEx(ref r, style, false, ex);
    SetWindowPos(hwnd, new IntPtr(-1), 0, 0, r.Right-r.Left, r.Bottom-r.Top, 0x0040);
  }
}
'@
$p.Refresh()
[WinSizeE]::Force($p.MainWindowHandle, $Width, $Height)
Start-Sleep -Milliseconds 500

function Wait-Log([string]$Pattern, [int]$TimeoutSec = 30) {
  $until = (Get-Date).AddSeconds($TimeoutSec)
  while ((Get-Date) -lt $until) {
    if ($p.HasExited) { return $false }
    if ((Test-Path $log) -and (Select-String -Path $log -Pattern $Pattern -Quiet)) { return $true }
    Start-Sleep -Milliseconds 100
  }
  return $false
}

if (-not (Wait-Log 'D64RtEnemyGalleryTour:' 40)) {
  Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
  throw 'tour did not start'
}

foreach ($idx in $indexList) {
  $label = $booths[$idx].label
  if (-not (Wait-Log "D64RtEnemyGalleryShot: $idx " 25)) {
    Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
    throw "ABORT: timeout waiting for native shot $idx"
  }
  Start-Sleep -Milliseconds 200
  $shot = Get-ChildItem $OutDir -Filter 'Screenshot_*.png' | Sort-Object LastWriteTime -Descending | Select-Object -First 1
  if (-not $shot) { throw "no screenshot for $idx" }
  $destName = if ($Tag) { "{0:d4}_{1}.png" -f $idx, $Tag } else { "{0:d4}.png" -f $idx }
  $dest = Join-Path $OutDir $destName
  Move-Item -Force $shot.FullName $dest
  Write-Host "shot $destName ($label)"
}

if (-not (Wait-Log 'D64RtEnemyGalleryTour: done' 40)) {
  Write-Host 'warn: done banner missing (shots may still be ok)'
}
Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
Write-Host "batch complete -> $OutDir tag=$Tag"
