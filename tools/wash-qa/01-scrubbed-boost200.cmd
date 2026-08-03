@echo off
rem [1/5] Scrubbed global JSON + live RTGL + mapboost 200
rem Expect: if scrub alone fixed it, walls clean; CRTs still glow when stared at.
set "WASH_TITLE=[1/5] SCRUBBED META — mapboost 200 (live RTGL)"
set "WASH_MAPBOOST=200"
set "WASH_SKY=80"
set "WASH_VARIANT=live"
call "%~dp0_launch_common.cmd"
