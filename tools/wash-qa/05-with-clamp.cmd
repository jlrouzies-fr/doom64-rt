@echo off
rem [5/5] Preferred permanent fix: INDIR * emissiveMult + min(emission, 0.05) clamp.
rem Expect: walls clean at mapboost 200; CRTs glow; soft GI still present.
set "WASH_TITLE=[5/5] CLAMP — INDIR safety ceiling 0.05 (preferred fix)"
set "WASH_MAPBOOST=200"
set "WASH_SKY=80"
set "WASH_VARIANT=clamp"
call "%~dp0_launch_common.cmd"
