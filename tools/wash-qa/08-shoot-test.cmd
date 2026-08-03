@echo off
rem Shoot-test after FX GI dial-down. Spawns wallturned; fire pistol at the STONE2 wall.
rem Expect: brief local muzzle (rt_mzlflsh), NO far blotchy wash on bad yaw angles.
set "WASH_TITLE=[8] SHOOT TEST — FX emisMult~0, mapboost 200, mzlflsh ON"
set "WASH_MAPBOOST=200"
set "WASH_SKY=80"
set "WASH_VARIANT=live"
set "WASH_MZLFLSH=1"
call "%~dp0_launch_common.cmd"
