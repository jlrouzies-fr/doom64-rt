param(
  [string]$Label = 'fix',
  [string]$ExtraFile = 'G:\AI\Doom64-RT\Doom64-Retribution\d64r-map01-rtfix.wad',
  [switch]$Screenshot
)

$wd = 'G:\AI\Doom64-RT\sourcecode\gzdoom-rt\build\RelWithDebInfo'
$mod = 'G:\AI\Doom64-RT\Doom64-Retribution\D64RTR_v15.WAD'
$bm = 'G:\AI\Doom64-RT\Doom64-Retribution\D64RTR_BRIGHTMAPS.PK3'
$shotDir = 'G:\AI\Doom64-RT\tools\_map_isol'
New-Item -ItemType Directory -Force -Path $shotDir | Out-Null

Get-Process gzdoom -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Milliseconds 250

$files = @($mod, $bm)
if ($ExtraFile -and (Test-Path -LiteralPath $ExtraFile)) { $files += $ExtraFile }

$arg = @(
  '-iwad', 'D:\Games\GZDoom\doom2.wad',
  '-file') + $files + @(
  '-rtnolauncher', '-nosound', '-width', '1280', '-height', '720',
  '+vid_fullscreen', '0', '+map', 'map01',
  '+rt_mod_compat', '3', '+r_drawvoxels', '0', '+d64_enterfade', '0',
  '+rt_classic', '1', '+rt_autoexport', 'false', '+rt_fluid', 'false', '+rt_upscale_dlss', '0'
) -join ' '

$p = Start-Process -FilePath "$wd\gzdoom.exe" -WorkingDirectory $wd -ArgumentList $arg -PassThru
$parts = @()
foreach ($sec in 3, 8, 15, 20) {
  while ([int]((Get-Date) - $p.StartTime).TotalSeconds -lt $sec -and -not $p.HasExited) {
    Start-Sleep -Milliseconds 150
  }
  try { $p.Refresh() } catch {}
  if ($p.HasExited) { $parts += "${sec}s=EXIT:$($p.ExitCode)"; break }
  else { $parts += "${sec}s=$($p.Responding)" }

  if ($Screenshot -and ($sec -eq 3 -or $sec -eq 8) -and -not $p.HasExited) {
    try {
      Add-Type -AssemblyName System.Windows.Forms, System.Drawing
      $bounds = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
      $bmp = New-Object System.Drawing.Bitmap $bounds.Width, $bounds.Height
      $g = [System.Drawing.Graphics]::FromImage($bmp)
      $g.CopyFromScreen($bounds.Location, [System.Drawing.Point]::Empty, $bounds.Size)
      $shot = Join-Path $shotDir ("shot_{0}_{1}s.png" -f $Label, $sec)
      $bmp.Save($shot, [System.Drawing.Imaging.ImageFormat]::Png)
      $g.Dispose(); $bmp.Dispose()
      Write-Host "shot $shot"
    } catch {
      Write-Host "shot_fail: $_"
    }
  }
}

Write-Output ("{0} : {1}" -f $Label, ($parts -join ' | '))
if (-not $p.HasExited) { Stop-Process -Id $p.Id -Force; 'killed' }
