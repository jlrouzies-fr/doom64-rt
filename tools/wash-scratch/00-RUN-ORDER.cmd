@echo off
echo.
echo ============================================================
echo  WashScratch ladder — quit GZDoom between each step
echo ============================================================
echo.
echo  00-bootstrap.cmd          create isolated tree from stock rt + our gzdoom.exe
echo  S01-stock-baseline.cmd    stock Doom II mats @ boost 200 — note wash?
echo  S02-nuclear-scrub.cmd     strip ALL emis meta + quarantine _e — MUST be clean
echo  S03-patched-rtgl.cmd      stage live patched RTGL1 (INDIR*mult / no Saturate)
echo  S04-world-emis.cmd        authored world allowlist only
echo  S05-dynlights.cmd         + rt_dynlight on gallery
echo  S06-map01-play.cmd        Retribution MAP01 on WashScratch (+ world emis + enemy eyes)
echo.
echo  status.cmd                print current stage
echo  Play build stays at: sourcecode\gzdoom-rt\build\RelWithDebInfo
echo  Plan: gallery-emis-wall-wash-fix-plan.md  section WashScratch
echo.
pause
