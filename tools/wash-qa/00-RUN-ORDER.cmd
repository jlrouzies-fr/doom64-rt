@echo off
echo.
echo ============================================================
echo  Gallery wall-wash QA — run in order (quit gzdoom between each)
echo ============================================================
echo.
echo  FIRST (once): build shader variants  ~several minutes
echo    powershell -NoProfile -ExecutionPolicy Bypass -File tools\wash-qa\prepare-variants.ps1
echo.
echo  Empty hall A/B (no booth emitters):
echo    09-empty-hall.cmd
echo    OR: tools\launch-empty-gallery-rt.cmd
echo.
echo  Earlier ladder (01-05) proved scrub-prefix + HitInfo kill insufficient:
echo    01..05 wash remained; only 02 mapboost 0 was clean.
echo    Root: albedo×emissiveMult else-path (PLAY 4.25), not only _e.
echo.
echo  Old ladder (for reference):
echo    01-scrubbed-boost200.cmd   prefix scrub only
echo    02-scrubbed-boost0.cmd     control — wash must vanish
echo    03-scrubbed-sky0.cmd       sky off
echo    04-indir-kill.cmd          shader _e INDIR=0 only
echo    05-with-clamp.cmd          clamp
echo    06-restore-live.cmd        put live RTGL back
echo.
echo  All spawn at wallturned pose on MAP99 (STONE2 on the right).
echo  Plan: gallery-emis-wall-wash-fix-plan.md
echo.
pause
