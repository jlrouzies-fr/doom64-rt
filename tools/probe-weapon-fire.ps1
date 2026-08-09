# Drive a weapon's Fire animation with no user input and capture one screenshot per
# tic, to find out why the plasma rifle / BFG sprite disappears while shooting.
#
#   .\tools\probe-weapon-fire.ps1 -Weapon plasma
#
# Shots land in screen\weapon_probe_<weapon>\; the console transcript (rt-console.log)
# carries the matching "PROBE t=â€¦ spr=â€¦ frame=â€¦ alpha=â€¦" lines.
param(
  [ValidateSet('plasma-auto', 'plasma', 'plasma-live', 'plasma-dummy', 'bfg')]
  [string]$Weapon = 'plasma',
  [int]$Map = 1,
  [int]$WaitSeconds = 40,
  # Extra +cvar pins for an A/B arm, e.g. -Extra '+rt_mzlflsh','0'
  [string[]]$Extra = @(),
  # Suffix for the output dir so arms do not overwrite each other
  [string]$Tag = ''
)

$ErrorActionPreference = 'Stop'
$Root = 'G:\ai\Doom64-RT'
$Py = 'C:\Users\Winter\AppData\Local\Programs\Python\Python313\python.exe'
$Probe = Join-Path $Root 'Doom64-Retribution\d64r-weapon-fire-probe.pk3'
$suffix = if ($Tag) { "_$Tag" } else { '' }
$OutDir = Join-Path $Root "screen\weapon_probe_$Weapon$suffix"

Get-Process gzdoom, gzdoom-mod -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue

& $Py (Join-Path $Root 'tools\pack_weapon_fire_probe.py') $Weapon
if ($LASTEXITCODE -ne 0) { throw 'pack failed' }

if (Test-Path -LiteralPath $OutDir) { Remove-Item -Recurse -Force $OutDir }
New-Item -ItemType Directory -Force $OutDir | Out-Null

& (Join-Path $Root 'tools\launch-retribution-rt.cmd') $Map -- `
  -file $Probe `
  +enablescriptscreenshot 1 +screenshot_dir $OutDir +screenshot_quiet false +screenshot_type png `
  @Extra

Start-Sleep -Seconds $WaitSeconds
Get-Process gzdoom -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue

$shots = Get-ChildItem -LiteralPath $OutDir -Filter *.png -ErrorAction SilentlyContinue
Write-Output "shots: $($shots.Count) in $OutDir"
Select-String -LiteralPath (Join-Path $Root 'rt-console.log') -Pattern 'PROBE' |
  ForEach-Object { $_.Line }
