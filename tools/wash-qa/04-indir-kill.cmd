@echo off
rem [4/5] HitInfo INDIR emission forced to 0 (needs prepare-variants.ps1 first).
rem Expect: walls CLEAN, CRT/lava still glow when looked at (primary path).
set "WASH_TITLE=[4/5] INDIR KILL — shader emission=0 on INDIR (confirm path)"
set "WASH_MAPBOOST=200"
set "WASH_SKY=80"
set "WASH_VARIANT=indir_kill"
call "%~dp0_launch_common.cmd"
