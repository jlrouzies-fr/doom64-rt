@echo off
setlocal EnableExtensions
rem Gallery emissive QA (root-cause oriented):
rem   1) offline hygiene (allowlist / no solid stub _e)
rem   2) orbit-inward at stock mapboost 200 — must NOT wash toward center
rem      (this is the failure mode lowering mapboost was papering over)
rem   3) center yaw at mapboost 200 — directional wash check
rem
rem Requires rebuilt RTGL with HitInfo INDIR applying emissiveMult to _e maps.
rem Exit 0 = pass, 2 = fail
set "ROOT=G:\AI\Doom64-RT"
set "PY=C:\Users\Winter\AppData\Local\Programs\Python\Python313\python.exe"
set "ORBIT=%ROOT%\screen\orbit_sweep"
set "YAW=%ROOT%\screen\yaw_sweep"

cd /d "%ROOT%" || exit /b 1

echo === [1/4] emissive hygiene ===
"%PY%" "%ROOT%\tools\check_emis_hygiene.py" || exit /b 2

echo === [2/4] sync baseline PBR mats ===
"%PY%" "%ROOT%\tools\sync_gallery_pbr_set.py" baseline || exit /b 1

echo === [3/4] orbit-inward mapboost=200 (center-directed GI) ===
powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%\tools\run_gallery_orbit_sweep.ps1" ^
  -OutDir "%ORBIT%" -EmisMapBoost 200 -MaxDelta 12 -MaxBrightFrac 0.03 -MaxMean 20
if errorlevel 1 (
  echo FAIL: orbit-inward wash at stock mapboost
  exit /b 2
)

echo === [4/4] center yaw-sweep mapboost=200 ===
powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%\tools\run_gallery_yaw_sweep.ps1" ^
  -OutDir "%YAW%" -EmisMapBoost 200 -MaxDelta 12 -MaxBrightFrac 0.03
if errorlevel 1 (
  echo FAIL: center yaw wash at stock mapboost
  exit /b 2
)

echo PASS: gallery emissive QA (stock mapboost + per-tex GI mult)
exit /b 0
