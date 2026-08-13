# Repo root, derived from this script's own location.
$PROJ = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
param(
  [string]$Indices = '',
  [string]$OutDir = ''
)

$ErrorActionPreference = 'Stop'
$py = 'C:\Users\Winter\AppData\Local\Programs\Python\Python313\python.exe'
$root = '$PROJ'
$review = Join-Path $root 'tools\review_enemy_gallery_batch.ps1'
if (-not $OutDir) {
  $OutDir = Join-Path $root 'tools\_enemy_gallery\batch_eyes'
}

Write-Host '== build enemy gallery map =='
& $py (Join-Path $root 'tools\build_enemy_gallery.py')

Write-Host '== BEFORE: clear eye emissives =='
& $py (Join-Path $root 'tools\clear_enemy_eye_emissives.py')
$beforeArgs = @{
  OutDir = $OutDir
  Tag = 'before'
}
if ($Indices) { $beforeArgs.Indices = $Indices }
powershell -NoProfile -ExecutionPolicy Bypass -File $review @beforeArgs

Write-Host '== AFTER: generate eye emissives =='
& $py (Join-Path $root 'tools\gen_enemy_eye_emissives.py')

Write-Host '== AFTER capture =='
$afterArgs = @{
  OutDir = $OutDir
  Tag = 'after'
}
if ($Indices) { $afterArgs.Indices = $Indices }
powershell -NoProfile -ExecutionPolicy Bypass -File $review @afterArgs

Write-Host "done -> $OutDir"
Get-ChildItem $OutDir -Filter '*_*.png' | Sort-Object Name | Format-Table Name, Length -AutoSize
