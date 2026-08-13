# Repo root, derived from this script's own location.
$PROJ = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
param(
  [int]$Start = 0,
  [int]$Count = 10,
  [string]$OutDir = '',
  [int]$Width = 960,
  [int]$Height = 540
)

$ErrorActionPreference = 'Stop'
if ($Count -gt 30) { throw "Count max is 30 (got $Count)." }

$py = 'C:\Users\Winter\AppData\Local\Programs\Python\Python313\python.exe'
$root = '$PROJ'
$review = Join-Path $root 'tools\review_gallery_batch.ps1'
$apply = Join-Path $root 'tools\apply_batch_category_pbr.py'
if (-not $OutDir) {
  $OutDir = Join-Path $root ("tools\_gallery\batch_{0:d4}_{1:d4}" -f $Start, ($Start + $Count - 1))
}

Write-Host "== BEFORE: neutral stubs + capture =="
& $py $apply --start $Start --count $Count --mode neutral
powershell -NoProfile -ExecutionPolicy Bypass -File $review -Start $Start -Count $Count -OutDir $OutDir -Width $Width -Height $Height -Tag before

Write-Host "== AFTER: category PBR + capture =="
& $py $apply --start $Start --count $Count --mode pbr
powershell -NoProfile -ExecutionPolicy Bypass -File $review -Start $Start -Count $Count -OutDir $OutDir -Width $Width -Height $Height -Tag after

Write-Host "== auto-review using *_after.png =="
& $py (Join-Path $root 'tools\auto_review_gallery_batch.py') --outdir $OutDir --start $Start --count $Count
Write-Host "pair batch done -> $OutDir (NNNN_before.png / NNNN_after.png)"
