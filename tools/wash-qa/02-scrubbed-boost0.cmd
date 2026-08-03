@echo off
rem [2/5] Control: same as 01 but mapboost 0 — walls MUST be clean (proves wash is INDIR emis).
set "WASH_TITLE=[2/5] CONTROL — mapboost 0 (wash must die)"
set "WASH_MAPBOOST=0"
set "WASH_SKY=80"
set "WASH_VARIANT=live"
call "%~dp0_launch_common.cmd"
