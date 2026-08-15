@echo off
rem Empty hall (no pillars). Same cvars as full gallery wash-qa.
set "WASH_TITLE=[9] EMPTY HALL — dark (ll=24), no pillars — muzzle/sky should look PT"
set "WASH_MAPBOOST=200"
set "WASH_SKY=80"
set "WASH_VARIANT=live"
set "WASH_MZLFLSH=1"
set "WASH_EMPTY=1"
call "%~dp0_launch_common.cmd"
