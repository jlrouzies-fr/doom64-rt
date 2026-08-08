@echo off
setlocal EnableExtensions
rem ---------------------------------------------------------------------------
rem ONE lamp, nothing else. The decisive test for the missing bulb shadows.
rem
rem Where the investigation stands. rt_debug_visibility 1 shows nothing casts a
rem shadow from the bulb bands. A barrel explosion light standing right next to
rem those same bands, in the same room, with the same occluders and the same
rem denoiser, casts a shadow with no problem. That kills both remaining
rem theories at once:
rem   - not light COUNT: if some unoccluded lamp always filled the umbra, it
rem     would fill the barrel's umbra too, and it does not.
rem   - not the occluders or the shadow rays: the barrel proves both work here.
rem
rem So the difference is in OUR lights. This arm removes every other light in
rem the world and leaves exactly one flat bulb lamp, very bright, at the
rem dynlight source radius that is known to cast crisply.
rem
rem   rt_ceiling_edge_max 1 keeps the single NEAREST candidate (the walk sorts by
rem   distance before applying the cap), so it is the lamp in front of you.
rem
rem The result is unambiguous either way:
rem   shadow appears  -> a single lamp of ours is fine, and the fault is in how
rem                      MANY we upload or how they interact. Back to count, and
rem                      the earlier density nulls were bad experiments.
rem   still no shadow -> one of our lights cannot cast at all, and the cause is
rem                      in how it is uploaded or where it is placed. Compare
rem                      RgLightInfo/RgLightSphericalEXT against the dynlight
rem                      path in rt_main.cpp, and check the light is not inside
rem                      the ceiling geometry it sits against.
rem
rem Run with the debug view; judge black, not brightness:
rem   ab-onelamp.cmd 1 -- and look under +rt_debug_visibility 1
rem
rem Usage: ab-onelamp.cmd [map 1-32]
rem ---------------------------------------------------------------------------

set "MAP=%~1"
if "%MAP%"=="" set "MAP=1"

rem Everything that could contribute light, off. What remains is one lamp.
set "ARGS=+rt_ceiling_edge_lamps 1 +rt_ceiling_edge_max 1 +rt_ceiling_edge_intensity 3000"
set "ARGS=%ARGS% +rt_ceiling_edge_radius 0.08 +rt_ceiling_edge_debug 1"
set "ARGS=%ARGS% +rt_wall_strips 0 +rt_hang_lamps 0 +rt_pole_lamp_intensity 0"
set "ARGS=%ARGS% +rt_ceiling_lamps 0 +rt_sector_lights 0"
set "ARGS=%ARGS% +rt_sector_emis 0 +rt_emis_mapboost 0"
set "ARGS=%ARGS% +rt_dynlight 0 +rt_flsh 0"
set "ARGS=%ARGS% +rt_debug_visibility 1"

echo === ONE flat bulb lamp, everything else off, MAP%MAP% ===
echo     %ARGS%
echo     expect "uploaded=1 of N wanted" in the console -- if it is not 1, the arm did not apply
echo     stand so the fence is between you and that lamp; judge BLACK in the debug view
call "%~dp0launch-retribution-rt.cmd" %MAP% -- %ARGS%
exit /b %ERRORLEVEL%
