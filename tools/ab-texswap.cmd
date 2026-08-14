@echo off
setlocal EnableExtensions EnableDelayedExpansion
for %%I in ("%~dp0..") do set "PROJ=%%~fI"
rem ---------------------------------------------------------------------------
rem SINGLE-BULB PANES ON A REAL MAP: does the lab result survive MAP01?
rem
rem   python tools\build_shadow_swap.py     once, and after any --map change
rem   ab-texswap.cmd off                    stock MAP01 -- the reference
rem   ab-texswap.cmd on                     lamp panes swapped to SFLATCH
rem   ab-texswap.cmd on -- +rt_solo_lamp_intensity 900
rem
rem WHAT IS SWAPPED, and why it is not just an art change. MAP01's twelve lamp
rem pane CEILINGS (6 SFLATAS + 6 SFLATAQ) become SFLATCH, which paints ONE bulb
rem dead centre of its 64-unit tile. That moves them off the bulb-lattice path
rem (rt_ceiling_bulb_*, one light per painted bulb) and onto the SOLO path
rem (rt_solo_lamp_*, one light per tile) -- and the light family is the half that
rem matters. Floors are untouched: SFLATAS is used as a floor too, and a floor is
rem not a lamp pane.
rem
rem WHY IT SHOULD HELP, from MAP93 (the shadow lab):
rem
rem   1 light  radius 0.02   crisp diamond shadows on floor, walls and ceiling
rem   4 lights radius 0.02   shadows too, once rt_solo_lamp_intensity is raised
rem                          enough to beat the bounce fill
rem   16 lights any radius   nothing
rem
rem A grating shadow needs a compact source, and it needs the sources far enough
rem APART not to be -- Doom 64 paints its bulbs a metre or more apart, wider than
rem the mesh openings, so every extra bulb lays down an offset copy that fills in
rem the previous one's gaps. One bulb per pane sidesteps that entirely.
rem
rem NOTHING PERMANENT. The swap lives in d64r-shadow-swap.wad, loaded ONLY by this
rem script and after every other file so it wins. `off` does not load it at all.
rem
rem JUDGE:
rem   1. does the cage grating cast a readable shadow on the floor or the wall?
rem   2. does a pane read as ONE bulb rather than a lit panel? That is the cost,
rem      and it is a change to the game's look, not just its lighting.
rem   3. watch the console line: the panes must move from "+ N bulb lattice(s)"
rem      to "solo N flat(s)". If they do not, the wad is not winning the load
rem      order and the result is void.
rem
rem Usage: ab-texswap.cmd <off^|on^|swap> [map 1-32] [-- any +cvar ...]
rem ---------------------------------------------------------------------------

set "WHICH=%~1"
set "MAP=%~2"
if "%WHICH%"=="" set "WHICH=on"
if "%MAP%"==""  set "MAP=1"
if "%MAP%"=="--" set "MAP=1"
set "MAPARG=map0%MAP%"
if %MAP% GEQ 10 set "MAPARG=map%MAP%"

set "EXTRA="
set "SEEN="
for %%A in (%*) do (
  if defined SEEN set "EXTRA=!EXTRA! %%A"
  if "%%A"=="--" set "SEEN=1"
)

set "SWAP=%PROJ%\Doom64-Retribution\d64r-shadow-swap.wad"
set "ART=%PROJ%\Doom64-Retribution\d64r-single-bulb.wad"
set "FILES="
rem -ExtraFiles, NOT -file. This goes to shot.ps1, which appends to its single
rem -file list; a bare -file here is an unknown parameter to the script and the
rem overlay simply never loads -- which looks exactly like "the swap does
rem nothing" while the console still reports the stock panes. That cost a round
rem trip once already. Filename only: it resolves relative to Doom64-Retribution\.
if /i "%WHICH%"=="on" (
  if not exist "%ART%" (
    echo run: python tools\make_single_bulb_flat.py
    exit /b 1
  )
  set "FILES=-ExtraFiles d64r-single-bulb.wad"
) else if /i "%WHICH%"=="swap" (
  if not exist "%SWAP%" (
    echo run: python tools\build_shadow_swap.py
    exit /b 1
  )
  set "FILES=-ExtraFiles d64r-shadow-swap.wad"
) else if /i "%WHICH%"=="off" (
  rem no overlay -- stock panes
) else (
  echo Usage: %~nx0 ^<off^|on^|swap^> [map] [-- any +cvar ...]
  exit /b 1
)

rem Solo-path values, stated in BOTH arms so the only difference is the wad.
rem
rem 100, not the shipping 45 and not the 900 this started at. 45 is calibrated for
rem a level that still has every other fixture lighting it, and these panes have to
rem carry the room; 900 overshot and buried the shadow in its own bounce. 100 is
rem where it read right in play. Radius 0.02 is the flashlight's, and is what makes
rem a 4-unit fence wire cast at all (practices 34).
set "A=+rt_solo_lamps 1 +rt_solo_lamp_radius 0.02 +rt_solo_lamp_intensity 100"
set "A=%A% +rt_solo_lamp_stride 1 +rt_solo_lamp_max 384 +rt_ceiling_edge_debug 1"

rem Goes through shot.ps1 -Play rather than launch-retribution-rt.cmd, and for a
rem concrete reason: the launcher's passthrough lands AFTER its own -file list, so
rem the overlay would need a second -file on one command line. shot.ps1 appends to
rem the single list instead, which makes "loaded last, therefore wins" a fact
rem rather than a hope -- and that is the whole premise of this arm.
echo === texswap: %WHICH% %MAPARG% !EXTRA! ===
echo     judge: 1) fence shadow  2) does a pane still read as a lamp  3) console says "solo N flat(s)"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0shot.ps1" -Play -Map %MAPARG% %FILES% -Extra "%A%!EXTRA!"
exit /b %ERRORLEVEL%
