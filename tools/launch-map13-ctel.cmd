@echo off
rem MAP13 CTEL alcove — launches map 13 with its OWN console log.
rem
rem The shared rt-console.log is written by every launcher, so with several agents
rem running maps at once it is overwritten constantly and reading it proves nothing
rem about a given run. It cost a wrong diagnosis (2026-08-10): a MAP01 startup from
rem another agent's session was read as evidence about a MAP13 test.
rem
rem The "--" passthrough lands AFTER the base launcher's own +logfile, and +commands
rem run in order, so this one wins and the transcript goes somewhere unambiguous.
rem
rem What to look for in rt-map13.log:
rem   "d64r-seqlight-fix_map13"  -> the patched MAP13 is the one in use.
rem     If it says d64r-3dfloor-rtfix_map13, that wad is winning the load order and
rem     none of the map changes apply.
rem
rem What to look for in game, in the 64x64 alcove at (864,-1312):
rem   - gems no longer cycle bright/dim on their own (ANIMDEFS pinned to CTEL5)
rem   - the panels no longer glow with nothing lighting them (sector 255 -> 180)
rem   - a red light pulses over ~4s (two PointLightPulse, radius 144 <-> 60)
setlocal EnableExtensions
call "%~dp0launch-retribution-rt.cmd" 13 -- +logfile "G:\AI\Doom64-RT\rt-map13.log" %*
