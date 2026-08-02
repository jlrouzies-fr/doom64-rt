param(
  [int]$Start = 0,
  [int]$Count = 30,
  [string]$OutDir = '',
  [int]$Width = 960,
  [int]$Height = 540,
  # before | after | '' (plain 0000.png). Keeps the other tag when capturing.
  [ValidateSet('', 'before', 'after')]
  [string]$Tag = '',
  # Optional sparse indices, e.g. "0,2,5,6,8" (overrides Start/Count for tour list).
  [string]$Indices = '',
  # Skip indices that already have this tag's PNG (do not recapture / delete them).
  [switch]$SkipExisting,
  [string]$Classic = '0',
  # front = face-on pillar (default). corner = SW angle showing south+east faces.
  [ValidateSet('front', 'corner')]
  [string]$View = 'front',
  [float]$NormalMapStren = 3
)

$ErrorActionPreference = 'Stop'
if ($Count -gt 30 -and -not $Indices) { throw "Count max is 30 (got $Count)." }

$py = 'C:\Users\Winter\AppData\Local\Programs\Python\Python313\python.exe'
$root = 'G:\AI\Doom64-RT'

$indexList = @()
if ($Indices) {
  $indexList = @($Indices.Split(',') | ForEach-Object { [int]($_.Trim()) })
  if ($indexList.Count -gt 30) { throw "Indices max is 30 (got $($indexList.Count))." }
  if (-not $OutDir) {
    $OutDir = Join-Path $root ("tools\_gallery\batch_idx_{0}" -f ($indexList -join '-'))
  }
} else {
  $indexList = @($Start..($Start + $Count - 1))
  if (-not $OutDir) {
    $OutDir = Join-Path $root ("tools\_gallery\batch_{0:d4}_{1:d4}" -f $Start, ($Start + $Count - 1))
  }
}

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
Get-ChildItem $OutDir -Filter 'Screenshot_*.png' -ErrorAction SilentlyContinue | Remove-Item -Force

# Drop indices that already have the requested tag when SkipExisting is set.
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
  Write-Host "nothing to capture (all $($Tag) shots already exist in $OutDir)"
  exit 0
}
$logName = if ($Tag) { "stdout_$Tag.txt" } else { 'stdout.txt' }

Get-Process gzdoom -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Milliseconds 700
if (Get-Process gzdoom -ErrorAction SilentlyContinue) { throw 'gzdoom still running after kill' }

if ($Indices) {
  $env:GALLERY_INDICES = ($indexList -join ',')
  Remove-Item Env:GALLERY_BATCH_START -ErrorAction SilentlyContinue
  Remove-Item Env:GALLERY_BATCH_COUNT -ErrorAction SilentlyContinue
} else {
  Remove-Item Env:GALLERY_INDICES -ErrorAction SilentlyContinue
  $env:GALLERY_BATCH_START = "$Start"
  $env:GALLERY_BATCH_COUNT = "$Count"
}
$env:GALLERY_VIEW = $View
& $py (Join-Path $root 'tools\write_gallery_tour_only.py') | Out-Host

$pkg = Join-Path $root 'tools\d64r-gallery-tour'
$pk3 = Join-Path $root 'Doom64-Retribution\d64r-gallery-tour.pk3'
Remove-Item $pk3 -Force -ErrorAction SilentlyContinue
Compress-Archive -Path "$pkg\*" -DestinationPath ($pk3 -replace '\.pk3$', '.zip') -Force
Move-Item -Force ($pk3 -replace '\.pk3$', '.zip') $pk3

$wd = Join-Path $root 'sourcecode\gzdoom-rt\build\RelWithDebInfo'
$log = Join-Path $OutDir $logName
Remove-Item $log -Force -ErrorAction SilentlyContinue
Write-Host "capture tag=$(if ($Tag) { $Tag } else { 'plain' }) log=$logName"

# Native engine screenshots via Level.MakeScreenShot (RTFrameBuffer HWND grab).
# -0 keeps a small top-left window; no focus required for native shots.
# Corner view needs non-zero pitch; disable the freelook0→pitch0 clamp.
$lookArgs = if ($View -eq 'corner') {
  @('+freelook', 'true', '+freelook0_pitch0', 'false')
} else {
  @('+freelook', 'false', '+freelook0_pitch0', 'true')
}
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
  '+sv_cheats', '1', '+map', 'map99'
) + $lookArgs + @(
  '+enablescriptscreenshot', '1',
  '+screenshot_dir', $OutDir,
  '+screenshot_quiet', 'false',
  '+god', '+gl_noskyboxes', 'true',
  '+rt_mod_compat', '3', '+r_drawvoxels', '0',
  '+rt_dxgi', '1',
  '+rt_classic', "$Classic", '+rt_autoexport', 'false', '+rt_fluid', 'false',
  '+rt_sky', '80', '+rt_sky_always', 'true', '+rt_upscale_dlss', '0',
  '+rt_sun', '1', '+rt_sun_intensity', '35', '+rt_sun_a', '50', '+rt_sun_b', '20',
  '+rt_flsh', '1', '+rt_flsh_intensity', '450',
  '+rt_normalmap_stren', "$NormalMapStren",
  '+rt_heightmap_stren', "$NormalMapStren"
)

$p = Start-Process -FilePath (Join-Path $wd 'gzdoom.exe') -WorkingDirectory $wd -ArgumentList $arg -RedirectStandardOutput $log -PassThru
Write-Host "started pid=$($p.Id) target=${Width}x${Height}"

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

# Engine often ignores -width/-height (archived win_* / DPI). Force client size.
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class WinSize2 {
  [DllImport("user32.dll")] public static extern bool AdjustWindowRectEx(ref RECT r, uint style, bool menu, uint ex);
  [DllImport("user32.dll")] public static extern int GetWindowLong(IntPtr h, int n);
  [DllImport("user32.dll")] public static extern bool SetWindowPos(IntPtr h, IntPtr after, int x, int y, int cx, int cy, uint flags);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int cmd);
  [DllImport("user32.dll")] public static extern bool GetClientRect(IntPtr h, out RECT r);
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left,Top,Right,Bottom; }
  public static string Force(IntPtr hwnd, int clientW, int clientH) {
    ShowWindow(hwnd, 9); // SW_RESTORE
    uint style = (uint)GetWindowLong(hwnd, -16);
    uint ex = (uint)GetWindowLong(hwnd, -20);
    RECT r = new RECT { Left=0, Top=0, Right=clientW, Bottom=clientH };
    AdjustWindowRectEx(ref r, style, false, ex);
    int ww = r.Right - r.Left, wh = r.Bottom - r.Top;
    SetWindowPos(hwnd, new IntPtr(-1), 0, 0, ww, wh, 0x0040); // TOPMOST + SHOWWINDOW
    RECT c; GetClientRect(hwnd, out c);
    return (c.Right - c.Left) + "x" + (c.Bottom - c.Top);
  }
}
'@
$p.Refresh()
$client = [WinSize2]::Force($p.MainWindowHandle, $Width, $Height)
Start-Sleep -Milliseconds 500
Write-Host "window ready hwnd=$($p.MainWindowHandle) client=$client (requested ${Width}x${Height})"

function Wait-Log([string]$Pattern, [int]$TimeoutSec = 25) {
  $until = (Get-Date).AddSeconds($TimeoutSec)
  while ((Get-Date) -lt $until) {
    if ($p.HasExited) { return $false }
    if ((Test-Path $log) -and (Select-String -Path $log -Pattern $Pattern -Quiet)) { return $true }
    Start-Sleep -Milliseconds 100
  }
  return $false
}

function Shot-Mean([string]$Path) {
  return [int](& $py -c @"
from PIL import Image
from pathlib import Path
im=Image.open(Path(r'$($Path -replace '\\','/')')).convert('RGB')
w,h=im.size
c=im.crop((int(w*0.15),int(h*0.2),int(w*0.85),int(h*0.85))).resize((48,48))
px=list(c.getdata())
print(int(sum(sum(t) for t in px)/(len(px)*3)))
"@)
}

function Claim-NewScreenshot([string[]]$BeforeNames, [string]$Dest) {
  $until = (Get-Date).AddSeconds(12)
  while ((Get-Date) -lt $until) {
    $candidates = @(Get-ChildItem $OutDir -Filter 'Screenshot_*.png' -ErrorAction SilentlyContinue |
      Where-Object { $_.Length -gt 8000 -and ($BeforeNames -notcontains $_.Name) } |
      Sort-Object LastWriteTime -Descending)
    if ($candidates.Count -ge 1) {
      Move-Item -Force $candidates[0].FullName $Dest
      return $true
    }
    # Also accept Captured path messages / delayed flush
    Start-Sleep -Milliseconds 120
  }
  return $false
}

$bad = 0
for ($i = 0; $i -lt $indexList.Count; $i++) {
  $idx = $indexList[$i]
  if (-not (Wait-Log -Pattern "D64RtGalleryTour:\s+$idx\b" -TimeoutSec 25)) {
    Get-Process gzdoom -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    throw "ABORT: timeout waiting for tour index $idx"
  }
  $before = @(Get-ChildItem $OutDir -Filter 'Screenshot_*.png' -ErrorAction SilentlyContinue | ForEach-Object Name)
  if (-not (Wait-Log -Pattern "D64RtGalleryShot:\s+$idx\b" -TimeoutSec 15)) {
    Get-Process gzdoom -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    throw "ABORT: timeout waiting for native shot $idx"
  }
  $shotName = if ($Tag) { "{0:d4}_{1}.png" -f $idx, $Tag } else { "{0:d4}.png" -f $idx }
  $shot = Join-Path $OutDir $shotName
  if (-not (Claim-NewScreenshot -BeforeNames $before -Dest $shot)) {
    Get-Process gzdoom -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    throw "ABORT: missing Screenshot_*.png for index $idx (see stdout)"
  }
  $mean = Shot-Mean $shot
  $sz = (Get-Item $shot).Length
  Write-Host "shot $shotName mean=$mean bytes=$sz"
  if ($i -eq 0 -and $mean -lt 18) {
    Get-Process gzdoom -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    throw "ABORT: first shot too dark (mean=$mean)"
  }
  if ($mean -lt 18) { $bad++ }
  if ($bad -ge 3) {
    Get-Process gzdoom -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    throw "ABORT: 3+ dark shots in batch"
  }
}

# Manifest: for sparse indices, pair each absolute index individually via env
$env:GALLERY_INDICES = ($indexList -join ',')
& $py -c @"
import json, os
from pathlib import Path
import sys
sys.path.insert(0, r'$root\tools')
from pathlib import Path
root = Path(r'$root')
out = Path(r'$OutDir')
tag = r'$Tag'
booths = json.loads((root/'tools/_gallery/booths.json').read_text(encoding='utf-8'))['booths']
idxs = [int(x) for x in os.environ['GALLERY_INDICES'].split(',') if x.strip()]
manifest_path = out/'manifest.json'
by = {}
if manifest_path.exists():
    for row in json.loads(manifest_path.read_text(encoding='utf-8')):
        by[int(row['index'])] = row
for idx in idxs:
    name = booths[idx]['texture']
    row = by.get(idx, {'index': idx, 'texture': name})
    row['texture'] = name
    if tag:
        shot = out / f'{idx:04d}_{tag}.png'
        row[f'shot_{tag}'] = shot.name if shot.exists() else None
        row[f'exists_{tag}'] = shot.exists()
        row[f'size_{tag}'] = shot.stat().st_size if shot.exists() else 0
        if tag == 'after' and shot.exists():
            row['shot'] = shot.name
            row['exists'] = True
            row['size'] = shot.stat().st_size
    else:
        shot = out / f'{idx:04d}.png'
        row['shot'] = shot.name if shot.exists() else None
        row['exists'] = shot.exists()
        row['size'] = shot.stat().st_size if shot.exists() else 0
    by[idx] = row
rows = [by[i] for i in sorted(by)]
manifest_path.write_text(json.dumps(rows, indent=2)+'\n', encoding='utf-8')
print('manifest', len(rows), '->', manifest_path)
"@
Get-Process gzdoom -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Milliseconds 400
Write-Host "batch complete -> $OutDir tag=$(if ($Tag) { $Tag } else { 'plain' }) indices=$($indexList -join ',')"
