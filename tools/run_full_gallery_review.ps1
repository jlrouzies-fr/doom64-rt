param(
  [int]$Start = 0,
  [int]$Count = 48,
  [int]$Total = 738
)

$ErrorActionPreference = 'Stop'
$py = 'C:\Users\Winter\AppData\Local\Programs\Python\Python313\python.exe'
$root = 'G:\AI\Doom64-RT'
$script = Join-Path $root 'tools\review_gallery_batch.ps1'

# Faster tour-only path inside review script via env
$env:GALLERY_TOUR_ONLY = '1'

for ($s = $Start; $s -lt $Total; $s += $Count) {
  $n = [Math]::Min($Count, $Total - $s)
  Write-Host "==== BATCH $s +$n ====" -ForegroundColor Cyan
  & $script -Start $s -Count $n
  $outDir = Join-Path $root ("tools\_gallery\batch_{0:d4}_{1:d4}" -f $s, ($s + $n - 1))
  & $py (Join-Path $root 'tools\auto_review_gallery_batch.py') --outdir $outDir --start $s --count $n
  # progress from md
  $md = Get-Content (Join-Path $root 'texture-status.md') -Raw
  $done = ([regex]::Matches($md, '\| `done` \|')).Count
  Write-Host "progress checkpoint batch end=$($s+$n-1)"
}

Write-Host "FULL PASS COMPLETE" -ForegroundColor Green
