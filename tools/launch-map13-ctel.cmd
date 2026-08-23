@echo off
rem Repo root, derived from this script's own location.
for %%I in ("%~dp0..") do set "PROJ=%%~fI"
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
rem     If it says d64rtr_v15_map13, the seqlight wad is not loaded and none of the
rem     map changes apply.
rem
rem What to look for in game, in the 64x64 alcove at (864,-1312):
rem   - gems no longer cycle bright/dim on their own (ANIMDEFS pinned to CTEL5)
rem   - the panels no longer glow with nothing lighting them (sector 255 -> 180)
rem   - a red light pulses over ~4s (two PointLightPulse, radius 144 <-> 60)
setlocal EnableExtensions
rem rt_tex_probe CTEL reports once a second, per animation frame, into the log above:
rem   rt_tex_probe CTEL5  file=d64r-ctel-fix.wad  lump=... lightlevel=180 sector_emis=0.000 ...
rem
rem Read it as three separate answers:
rem   file=      d64r-ctel-fix.wad -> the flattened frames are winning. If it says
rem              D64RTR_v15.WAD, the replacement is NOT in use and the painted fade is
rem              still the artwork on screen -- a load-order problem, not a value problem.
rem   the NAME   cycling CTEL1..CTEL8 across lines -> the animation (the rotation) runs.
rem              One name only -> something froze it.
rem   sector_emis nonzero -> the engine is making the surface self-emit regardless of any
rem              texture work, i.e. rt_sector_emis is still above threshold for it.
rem   lightlevel  should read 180. 255 means the patched MAP13 is not the one loaded.
rem
rem rt_dynlight_debug 1 additionally lists the dynamic lights actually uploaded, which is
rem how to confirm the two PointLightPulse things in the alcove exist and their radius.
rem rt_spin_panel_debug prints the orbiting light each second: which sector, which
rem animation frame it read, the bearing it derived and where it put the light. If the
rem light visibly leads or lags the lit gem, nudge +rt_spin_panel_yaw; if it travels the
rem wrong way round the panel, +rt_spin_panel_cw 0.
call "%~dp0launch-retribution-rt.cmd" 13 -- +logfile "%PROJ%\rt-map13.log" ^
  +rt_tex_probe CTEL +rt_spin_panel_debug 1 %*
