param(
  [string]$Indices = '0,1,2,3,4',
  [string]$OutDir = '',
  [int]$Width = 960,
  [int]$Height = 540,
  [float]$Strength = 4.5,
  [float]$HeightCrazy = 3.0,
  [float]$NormalMapStren = 3.5,
  [ValidateSet('heuristic', 'iid', 'solid')]
  [string]$Orm = 'heuristic',
  [ValidateSet('front', 'corner')]
  [string]$View = 'corner',
  [switch]$SkipExistingBefore
)

$ErrorActionPreference = 'Stop'
$pyAi = 'G:\AI\Doom64-RT\tools\.venv-ai\Scripts\python.exe'
$root = 'G:\AI\Doom64-RT'
$review = Join-Path $root 'tools\review_gallery_batch.ps1'
$gen = Join-Path $root 'tools\gen_ai_pbr.py'
if (-not $OutDir) {
  $OutDir = Join-Path $root 'tools\_gallery\batch_ai_corner_0000_0004'
}

$idx = $Indices
Write-Host "== BEFORE maps (solid ORM, no normals) =="
& $pyAi $gen --indices $idx --mode solid
Write-Host "== BEFORE capture view=$View =="
$beforeArgs = @(
  '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $review,
  '-Indices', $idx, '-OutDir', $OutDir, '-Width', $Width, '-Height', $Height,
  '-Tag', 'before', '-Classic', '0', '-View', $View
)
if ($SkipExistingBefore) { $beforeArgs += '-SkipExisting' }
powershell @beforeArgs

Write-Host "== AFTER maps (Marigold normals + ORM=$Orm height=$HeightCrazy -> mat_dev) =="
& $pyAi $gen --indices $idx --mode ai --orm $Orm --strength $Strength --height-crazy $HeightCrazy --steps 4

Write-Host "== AFTER capture view=$View normalmap_stren=$NormalMapStren =="
powershell -NoProfile -ExecutionPolicy Bypass -File $review `
  -Indices $idx -OutDir $OutDir -Width $Width -Height $Height `
  -Tag after -Classic '0' -View $View -NormalMapStren $NormalMapStren

Write-Host "done -> $OutDir"
Get-ChildItem $OutDir -Filter '*_*.png' | Sort-Object Name | Format-Table Name, Length -AutoSize
