@echo off
rem Same as 08 but rt_mzlflsh off — if wash dies here, leftover is engine muzzle light not FX meta.
set "WASH_TITLE=[8b] SHOOT TEST — mzlflsh OFF (isolates analytic muzzle)"
set "WASH_MAPBOOST=200"
set "WASH_SKY=80"
set "WASH_VARIANT=live"
set "WASH_MZLFLSH=0"
call "%~dp0_launch_common.cmd"
