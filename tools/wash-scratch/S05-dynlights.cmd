@echo off
setlocal
rem Assumes S04 already applied. Re-run S04 first if unsure.
set "WASH_TITLE=S05 world emis + dynlights"
set "WASH_MAPBOOST=200"
set "WASH_SKY=80"
set "WASH_MODE=gallery"
set "WASH_DYNLIGHT=1"
call "%~dp0_launch.cmd"
