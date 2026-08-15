@echo off
rem [7] After aggressive scrub (strip PLAY@4.25 etc — keep only authored overlays).
rem Expect: walls clean at mapboost 200; CRT/lava still glow when stared at.
set "WASH_TITLE=[7] FULL SCRUB — no stock albedo×mult (PLAY/FX body junk gone)"
set "WASH_MAPBOOST=200"
set "WASH_SKY=80"
set "WASH_VARIANT=live"
call "%~dp0_launch_common.cmd"
