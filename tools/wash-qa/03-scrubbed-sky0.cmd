@echo off
rem [3/5] Sky off — if blotches remain, sky is not the source.
set "WASH_TITLE=[3/5] SKY OFF — mapboost 200 (blotches should still match 01 if emis-driven)"
set "WASH_MAPBOOST=200"
set "WASH_SKY=0"
set "WASH_VARIANT=live"
call "%~dp0_launch_common.cmd"
