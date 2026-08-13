@echo off
rem DelayedExpansion is needed to accumulate the "--" passthrough in a loop.
rem Safe here: no literal '!' appears anywhere else in this script.
setlocal EnableExtensions EnableDelayedExpansion
rem Project root, derived from this script's own location, so a clone can live
rem anywhere. Nothing below may hardcode an absolute path into the repo.
for %%I in ("%~dp0..") do set "PROJ=%%~fI"
set "ENGINE=%PROJ%\sourcecode\gzdoom-rt\build\RelWithDebInfo"
rem The IWAD is the one path that cannot be derived from the repo. Override it with
rem the D64RT_IWAD environment variable rather than editing this line.
if not defined D64RT_IWAD set "D64RT_IWAD=D:\Games\GZDoom\doom2.wad"
set "IWAD=%D64RT_IWAD%"
set "MOD=%PROJ%\Doom64-Retribution\D64RTR_v15.WAD"
set "BM=%PROJ%\Doom64-Retribution\D64RTR_BRIGHTMAPS.PK3"
set "SKUL=%PROJ%\Doom64-Retribution\d64r-lostsoul-rt.pk3"
set "FLSH=%PROJ%\Doom64-Retribution\d64r-rt-flashlight.pk3"
set "FIX3D=%PROJ%\Doom64-Retribution\d64r-3dfloor-rtfix.wad"
set "SEQL=%PROJ%\Doom64-Retribution\d64r-seqlight-fix.wad"
set "BULBTEX=%PROJ%\Doom64-Retribution\d64r-bulb-textures.wad"
set "CTELFIX=%PROJ%\Doom64-Retribution\d64r-ctel-fix.wad"
set "SKY=%PROJ%\Doom64-Retribution\d64r-rt-sky.pk3"
set "LAVAFX=%PROJ%\Doom64-Retribution\d64r-lava-fx.pk3"
set "BLOODFX=%PROJ%\Doom64-Retribution\d64r-blood-persist.pk3"
set "WIDEGFX=%PROJ%\Doom64-Retribution\d64r-widescreen-gfx.pk3"
set "TITLOGO=%PROJ%\Doom64-Retribution\d64r-rt-titlelogo.pk3"
rem Doomguy mugshot. Must load AFTER %MOD%: it carries a full copy of
rem Retribution's SBARINFO (plus the DrawMugShot), and SBARINFO replaces
rem wholesale, so whichever copy loads last is the entire HUD.
set "MUGSHOT=%PROJ%\Doom64-Retribution\d64r-mugshot.pk3"
set "MUS=%PROJ%\Doom64-Retribution\D64MUS.PK3"
rem Full console transcript (incl. startup) -> shareable log. `logfile` is
rem whitelisted to run at GS_STARTUP (c_dispatch.cpp), so it captures
rem everything from boot, including RTGL -rtdebug output.
set "LOGF=%PROJ%\rt-console.log"
rem The ~325 STATIC cvar pins, exec'd rather than passed as "+name value" pairs.
rem See the note above the start command for why.
set "PINS=%PROJ%\tools\d64rt-pins.cfg"

rem Usage: launch-retribution-rt.cmd [1-34|menu] [debug] [-- +cvar val ...]
rem   Optional map number (default 1) → +map map01 … map34
rem   "menu" instead of a number → no +map, boot to the title screen
rem   Second arg "debug" → -rtdebug (RTGL messages to console: DLSS-RR init
rem     success/failure, shader load errors. Muted by default; rt_main.cpp
rem     sets allowedMessages=0 without it, so RR failing is otherwise silent.)
rem   Everything after "--" is appended verbatim to the command line, so it
rem     lands AFTER the cvars below and therefore wins. This is how A/B arms
rem     get pre-set (see ab-rr-guide.cmd) instead of being typed into the
rem     console: a hand-typed cvar is one forgotten keystroke from an invalid
rem     comparison, and CVAR_ARCHIVE then persists the mistake into later runs.
set "RTDEBUG="
if /i "%~2"=="debug" set "RTDEBUG=-rtdebug"

rem Collect the post-"--" passthrough without disturbing %1/%2 parsing above.
set "EXTRA="
set "SEEN_SEP="
for %%A in (%*) do (
  if defined SEEN_SEP (
    set "EXTRA=!EXTRA! %%~A"
  ) else (
    if "%%~A"=="--" set "SEEN_SEP=1"
  )
)
rem "menu" instead of a map number boots to the title screen and main menu with
rem the identical file list and pins. Needed because +map jumps straight into
rem play, so the title/menu/intermission 2D screens are otherwise unreachable
rem from this launcher -- and those are exactly what you look at to check
rem d64r-widescreen-gfx.pk3 (TITLEPIC, INTERPIC behind the score screen, and
rem the credits page).
set "MAPARG=+map"
set "MAPNUM=%~1"
if /i "%MAPNUM%"=="menu" (
  set "MAPARG="
  set "MAPLUMP="
  goto :launch
)
if "%MAPNUM%"=="" set "MAPNUM=1"
set /a "N=MAPNUM" 2>nul
if errorlevel 1 goto :badmap
if %N% LSS 1 goto :badmap
rem 34, not 32: the WAD holds MAP00..MAP34. 33/34 are the two beyond the main
rem run, and MAP34 is the ONLY place in the game the BFLM/RFLM/YFLM/GFLM loose
rem fires are placed (one of each), so the cap used to make them unreachable.
if %N% GTR 34 goto :badmap
if %N% LSS 10 (set "MAPLUMP=map0%N%") else (set "MAPLUMP=map%N%")

:launch

cd /d "%ENGINE%" || exit /b 1

rem Native RTGL1 path tracing. NOT RTX Remix, no -rtxremix.
rem
rem rt_rayreconstr 0 -- A-SVGF, not DLSS-RR. RR works and is correctly configured
rem (2026-08-07: identical jitter, MV scale and NGX feature flags to DLSS-SR), but
rem it stays measurably less stable in MOTION than A-SVGF on this content. Every
rem candidate cause was eliminated by measurement -- see RAYRECONSTRUCTION.md.
rem A-SVGF has a structural advantage here: it accumulates in linear radiance
rem BEFORE exposure and applies a variance-guided spatial filter, which suits
rem sparse 1-spp interiors with many small dynamic lights. Set +rt_rayreconstr 1
rem to compare; the tools/ab-rr-*.cmd arms all force RR on regardless.
rem
rem rt_restir_initial 32 (was 8) -- more RIS candidate lights per pixel. Traces NO
rem rays, so it is nearly free, and it improves light selection for BOTH denoisers.
rem Not yet A/B'd under A-SVGF specifically; use tools/ab-rr-quality.cmd to check
rem it and the other zero-ray ReSTIR knobs before assuming it helps.
rem
rem The expensive lever is rt_spp_direct / rt_spp_indirect [1..8], left at 1.
rem Measured ~20% improvement at 8, which is a poor trade -- and that result also
rem shows the residual motion noise is NOT Monte Carlo variance.
rem Requires tools\build-rtgl.cmd (RTGL1.dll + nvngx_dlssd.dll in rt\bin\).
rem All maps: d64r-3dfloor-rtfix.wad strips hangy Sector_Set3dFloor (special 160).
rem Sky: sector skyboxes ignored under RT (white/black fix), so rt_sky_always fills
rem  every F_SKY1 opening with the flat sky DOME and d64r-rt-sky's ZSCRIPT picks the
rem  dome texture PER MAP at WorldLoaded. Retribution sets no sky in MAPINFO at all --
rem  every map says sky1 = "ISUCK", a 64x64 dummy, and the real sky is the skybox room
rem  the engine now refuses to draw. The handler reads that room's intent back out:
rem   - fire maps (22/24/28, 23/32) -> FRSKYNRM / FRSKYGRN, the WAD's own 100-frame
rem     ANIMDEFS fire skies, which animate on the dome because hw_sky.cpp fetches the
rem     sky with GetGameTexture(tex, true);
rem   - void maps (25/26/31) -> VOIDSKY;
rem   - mountain and overcast maps -> SKYMTNA/B/C, SKYCLDPK/BR, SKYSTORM, baked by
rem     tools\gen_d64_skies.py from each room's own geometry (the MOUNT* ring
rem     composited at the altitude that room's radius and ceiling put it at --
rem     `--report` prints the survey);
rem   - everything else is a SPACE starfield room and stays on MOONSKY.
rem  A map's CLOUD comes from one of two places and never both: the volumetric deck
rem  if it is in RT_CLOUD_PRESETS, or painted into its dome texture if it is not.
rem  All twelve cloud maps are on the deck now, tinted to their own room's hue, so
rem  every baked sky above is a flat backdrop plus whatever mountain ring the room
rem  had. Take a map off that table and its sky must go back to a projected one in
rem  gen_d64_skies.py or it will have no cloud at all.
rem  Every one of these is 1024x128 like MOONSKY, so they all take the same branch of
rem  SetupMatrices and the horizon does not move from map to map.
rem  MOONSKY itself is the WAD's SPACE starfield tiled to 1024 wide (hw_skydome tiles
rem  anything narrower, so 256-wide SPACE wraps 4x and a painted moon would appear
rem  four times) -- tools\gen_moon_sky.py.
rem THE DOME'S OWN LIGHT (rt_sky) IS NOW PER MAP, and the 25 pinned below is only the
rem  fallback. It has to be: rt_sky 25 was chosen when every map wore the same
rem  near-black starfield, and the domes now span three orders of magnitude of mean
rem  linear radiance -- starfield 1x, SKYMTNA 12x, the cloud backdrops 30-45x,
rem  VOIDSKY 186x, FRSKYGRN 410x, FRSKYNRM 953x. One value cannot serve that. The
rem  per-map value is the `sky` field of RT_MOON_PRESETS (rt_main.cpp), negative
rem  meaning "keep this pin"; it is set on the VOIDSKY and fire maps and left alone
rem  everywhere else.
rem  On the FIRE maps the moon is gone entirely -- disc AND light -- and nothing
rem  replaces it, because the burning dome already is the light. Nothing about a
rem  fire sky is directional: the art is black at the top and bright at the bottom,
rem  so the fire is a RING at the horizon arriving from every azimuth at once, and
rem  any bearing chosen for a directional would rake shadows nothing on screen
rem  justifies. Settle the brightness with tools\ab-firesky.cmd; the shipping 1.2 /
rem  2.7 are parity arithmetic off those radiances, not values anyone has looked at.
rem The moon is a PAIR, and the two halves have to agree:
rem  - the disc you see is painted in MOONSKY at azimuth 135 (north-west);
rem  - the light you feel is rt_sun, an analytic directional light down the same
rem    bearing. RT's sky is a rasterised cubemap sampled on ray miss and is NOT
rem    importance-sampled, so the painted disc alone is far too noisy at 1 spp to
rem    light a room -- it is scenery, not a source. Move one, move the other.
rem  135/25 is not arbitrary: it is the one bearing that serves both of MAP13's
rem  window walls at once (west-facing slots need light travelling +x, the north
rem  colonnade needs it travelling -y; north-west gives both a 45-degree rake).
rem  This replaces the painted shafts d64r-seqlight-fix.wad removes from MAP13 --
rem  see docs/sequence-light-chains.md, "The fourth family". Tune with tools\ab-moon.cmd.
rem  In game, aim it with the `moon` CCMD: `moon 90`, `moon 90 35`, `moon 90 35 140`.
rem  The DISC is GEOMETRY drawn along the same rt_sun direction (rt_moon_geo, MOONDISC
rem  texture, RT_DrawMoonQuad in hw_skyportal.cpp), so it cannot drift from its own
rem  shafts and there is nothing to calibrate. It also has no altitude ceiling: the
rem  old painted moon could not go above the sky dome's 60 degrees, where Doom draws a
rem  flat averaged-colour cap with no texture on it, and got sliced by that boundary.
rem  `moon` alone prints the current aim.
rem rt_sun_require_sky 1 -- ON, and pinned here as well as compiled on, because a
rem  launcher pin overrides the compiled default and this line used to say 0.
rem  A shadow ray that hits nothing is scored LIT (RtMissShadowCheck.rmiss), and
rem  Doom maps are not watertight, so the moon washed sealed rooms. With this the
rem  ray must prove it reached SKY geometry, which is the only legitimate way out
rem  of a Doom map. Costs one extra ray, only on pixels the moon already lit.
rem  It gates the DIRECTIONAL light, so it covers the lightning strike too -- and
rem  matters more there: a strike is ~24x the moon's intensity, so a pinhole that
rem  never showed under moonlight is glaring under a bolt.
rem  THE REGRESSION TO WATCH is the opposite one: if a courtyard's sky geometry is
rem  not closed, legitimate light there is now rejected and it goes DARK. If a map
rem  loses its outdoor lighting, this is the first cvar to flip.
rem  Verify with +rt_sun_require_sky 1 +rt_sun_leak_debug 2: mode 2 composes with
rem  the fix, so ALL RED AND NO GREEN is the confirmation. Compare against stock
rem  with tools\ab-skyleak.cmd noreq. See docs/moon-and-sky-leaks.md.
rem  PER-MAP aim lives in RT_MOON_PRESETS (rt_main.cpp), applied at RT_OnLevelLoad --
rem  each map's windows face wherever its author pointed them, so one global bearing
rem  cannot serve them all. The rt_sun_a/b below is only the FALLBACK for maps with no
rem  entry; it is captured on the first level load so a preset cannot leak forward into
rem  the next map. MAP13 is set to 90. To add a map: aim it with `moon`, then type bare
rem  `moon` and paste the row it prints into the table. +rt_moon_presets 0 disables the
rem  whole table, which is what you want while hunting a bearing for a new map.
rem Clouds + lightning (rt_clouds_*, rt_lightning_*): the storm. MAP11 is the game's
rem  one `lightning` map (MAPINFO keyword -> DLightningThinker), and it is authored
rem  WITH clouds -- a CLOUDPRP skybox room scrolled by ACS script 670 -- that RT
rem  never draws, because sector skybox rooms are ignored. Both halves are rebuilt
rem  as sky GEOMETRY instead.
rem  Clouds are a VOLUME, not a backdrop: rt_clouds_shells horizontal discs stacked
rem  over the player, each drawing a different horizontal CUT (CLOUDV1..CLOUDV8 in
rem  d64r-rt-sky.pk3, 1 = cloud base) through one 3D density field baked by
rem  tools\gen_clouds.py. They are at genuinely different heights, so they parallax
rem  and occlude each other. A DECK rather than dome layers because a dome layer
rem  rotates about the viewer -- clouds orbit and come round again, identically
rem  wherever you stand; a deck translates along rt_clouds_wind_dir, linear and
rem  unbounded, and perspective crowds the far clouds to the horizon by itself.
rem  rt_clouds_shells is the cost knob (each shell is re-rasterised into all six
rem  cubemap faces every frame) AND the quality knob (at 1 there is no volume).
rem  PER-MAP and OPT-IN. rt_clouds is pinned 0 here; RT_CLOUD_PRESETS (rt_main.cpp)
rem  turns it on at level load for the maps that want it -- MAP11 and MAP14 do,
rem  MAP01 is listed explicitly OFF because its moon is straight overhead and a
rem  deck would attenuate the vertical roof-slot shafts the map is built around.
rem  A cloud layer is not neutral scenery: it changes what the moon does, so it is
rem  opt-in rather than global. The table also carries per-map TINT, alpha and
rem  wind. Authoring loop, same as `moon`: +rt_clouds_presets 0, tune with the
rem  `clouds` CCMD (`clouds on B4C0DC 0.9 0.014`), then type bare `clouds` and
rem  paste the row it prints. NOTE the table writes rt_clouds/_tint/_alpha/_wind
rem  at level load, so it overrides command-line pins on a listed map -- that is
rem  why every tools\ab-storm.cmd arm except `preset` sets rt_clouds_presets 0.
rem  rt_clouds_tint is the CLOUD COLOUR and also the colour moonlight takes on
rem  coming through them (rt_clouds_transmit is how much a solid patch still
rem  passes). The slice art is deliberately near-achromatic so the tint owns the
rem  hue outright -- a blue-baked texture cannot be tinted purple, only muddied,
rem  and several levels have a dark purple skybox.
rem  rt_clouds_occlude: the deck DIMS THE MOON. Sky geometry is never in the
rem  acceleration structure, so the clouds cannot cast a shadow on their own and the
rem  moon would pour through a solid overcast at full strength. Instead the moon's
rem  own ray is walked up through the shells and each slice's alpha sampled where it
rem  crosses (CPU, on a cached 64x64 reduction), and the product scales
rem  rt_sun_intensity -- so cloud drifting over the moon really does fade the shafts,
rem  and it moves with the wind. Floored at 0.12: taking a moon-lit map to zero is a
rem  worse failure than blocking too little.
rem  Lightning: on each strike, a BOLT quad plus an analytic DIRECTIONAL light down
rem  the same bearing. The bolt is scenery and the directional is the source --
rem  exactly the moon's arrangement, for exactly the moon's reason: RT's sky is a
rem  rasterised cubemap sampled on ray miss and is not importance-sampled, so
rem  painting something bright in it lights nothing at 1 spp. The strike TAKES OVER
rem  rt_sun's light rather than adding one: RTGL1 allows exactly one directional
rem  light and answers a second with a FATAL debug::Error. Test without waiting for
rem  the storm: the `thunder` CCMD forces a strike on any map. rt_lightning_debug 1
rem  prints bearing/strokes per strike.
rem  rt_lightning_sectorflash 1 keeps the stock F_SKY1 lightlevel flash (106 sectors
rem  on MAP11) -- under RT that is also rt_sector_emis surface emission, so it is
rem  the one knob to reach for if a strike washes the outdoors. See
rem  docs/rt-clouds-and-lightning.md and tools\ab-storm.cmd.
rem Fog (rt_fog_*): nine maps ask for fog in their own MAPINFO -- MAP26 wants
rem  `fade = "00 56 56"` at `fogdensity = 200`, a heavy cyan -- and the RT path never
rem  read either key, because both belong to the rasterizer's fog. What is built here
rem  is not that fog: rasterizer fog is a per-pixel lerp toward a colour and cannot be
rem  lit, so this is the MEDIUM instead, in RTGL1's froxel volume, which the level's
rem  own lamps and lava scatter through. The map supplies colour and density; the
rem  renderer supplies what the fog does with light.
rem  rt_fog_color 000000 and rt_fog_density -1 are SENTINELS meaning "use the map's
rem  own fade / fogdensity" -- pinned that way on purpose so the authored data stays
rem  the single source and no copy of it can go stale here.
rem  OPT-IN per map (RT_FOG_PRESETS in rt_main.cpp, MAP26 only today) for the reason
rem  the cloud deck is: fog changes every distance judgement in a level, and it costs
rem  a shadow ray per froxel cell.
rem  The shipping medium is a luminous VEIL, not an occluder: density 0.01 at the
rem  camera to 10 at the far plane, with rt_fog_ambient 1 -- fifty times the floor
rem  the first thick version used -- so the fog GLOWS and the level's lights
rem  modulate it rather than supply it. At these densities ~17% of a surface is
rem  fog by 1024 map units and nothing is hidden; the earlier 6 -> 190 profile is
rem  still one command away (toolsb-fog.cmd ramp2 / wall).
rem  NEAR and DISTANT fog are separate knobs: the medium is a ramp from
rem  rt_fog_density at the camera to rt_fog_density_far at rt_fog_far, shaped by
rem  rt_fog_curve (>1 = hold the near value longer, so the room you stand in stays
rem  clear and only the distance closes). rt_fog_color_far splits the tint the same
rem  way. Both far values carry the same "same as near" sentinels (-1 / 000000), so
rem  a map with no opinion gets a uniform medium. Console: `fog near 12`,
rem  `fog far 90`, `fog curve 2.5`.
rem  rt_fog_light_near 2 is what keeps the FLASHLIGHT usable in fog. A light at
rem  ~0 m lights the froxels in front of it by inverse square, so switching the
rem  torch on inside a medium whites out the screen -- physically what a headlight
rem  in fog does, and unplayable. In-scattering is faded within 2 m OF A LIGHT, so
rem  glare from a light you are HOLDING goes and the beam's shaft further down the
rem  corridor stays. 0 restores the physical (blinding) behaviour.
rem  rt_fog_illum 1 is the part that makes it worth doing. RTGL1's froxel pass
rem  scatters exactly ONE light -- whatever TryGetVolumetricLight picks, in practice
rem  the sun -- and MAP26's moon is deliberately off, so without this its fog would
rem  have no source at all and collapse to flat ambient. See docs/rt-fog.md and
rem  tools\ab-fog.cmd; `fog` in the console reports the medium.
rem LOCALISED SMOKE (rt_smoke_*): muzzle smoke as a REAL participating medium, in the
rem  same froxel volume the fog uses, so the muzzle flash that made it lights it from
rem  inside. Puffs are spheres simulated on the CPU -- the only side that can see the
rem  level, which is why a puff pools under a low ceiling instead of passing through.
rem  NOT A SPRITE, and not a second volume: the density is added per froxel, so
rem  CmVolumetricProcess's prefix sum gives it correct occlusion for free.
rem  rt_smoke_light_near 0 is deliberately the OPPOSITE of rt_fog_light_near 2. The fog
rem  needs the near-light fade or a carried light whites out the screen; the muzzle
rem  flash lighting the smoke at the barrel is the entire effect. Both are chosen PER
rem  FROXEL, so a smoke frame cannot retune a fogged map -- .\tools\ab-smoke.cmd fogsafe
rem  is the check, and it must be pixel-identical to .\tools\ab-fog.cmd ramp.
rem  rt_smoke_far 14 is a RESOLUTION knob, not a reach: the volume's 64 slices spread
rem  over it, so 14 m gives 0.22 m cells that can resolve a puff where rt_volume_far's
rem  30 gives 0.47 m and a puff reads as one slab. Short is free because the base
rem  density is 0 when smoke has the volume to itself. A FOGGED map always wins this.
rem  rt_mzlflsh 1 is pinned WITH the smoke, not near the other light cvars, because
rem  it gates both: a puff is born at the muzzle flash's resolved position -- already
rem  traced back out of any wall -- so the light and the smoke it lights are one
rem  point. rt_mzlflsh is CVAR_ARCHIVE and was not pinned before, so an ini value
rem  could have turned the smoke off with no rt_smoke_* cvar saying so.
rem  See docs/rt-smoke.md and .\tools\ab-smoke.cmd.
rem d64r-lostsoul-rt.pk3: yellow SKUL sprites + LSGL offset-glow EventHandler.
rem d64r-rt-flashlight.pk3: stylized 5-cell battery HUD (rt_flsh_charge / battstate; F toggles)
rem  + battery sound cues (rt_flsh_flicker counter; d64rt_flsh_sound / _vol to mute or tune).
rem  Charge is persistent: switching off no longer refills the cell, it trickles back up at
rem  rt_flsh_idle_recharge x the post-burnout rate.
rem  HOLD HEIGHT AND INTENSITY (2026-08-11): rt_flsh_u -0.7 -> -0.58 and intensity 90 -> 156.
rem  The low hold is deliberate horror framing, but it put the beam's centre on the floor only
rem  1.44 m ahead. The camera sits 41 map units = 1.28 m up, so -0.58 is 0.70 m above the floor
rem  against the old 0.58 m -- 1.206x. rt_flsh_pitch stays at 22 ON PURPOSE: with the angle
rem  fixed the triangle is merely SCALED, so the lit spot moves out by that same 1.206x to
rem  1.74 m. One number buys both the height and the reach; changing the pitch as well would
rem  compound them.
rem  The intensity is NOT a 73% brightness increase. Raising the source scales the lit footprint
rem  in both dimensions, so its AREA grows 1.456x and the same flux over it lands 0.687x as
rem  bright -- at the old 90 the higher hold would have made the pool DIMMER. 156 = 1.2x the
rem  light x 1.456x to pay for the move, i.e. about 1.19x brighter than before at the new spot.
rem  rt_flsh_u/_r/_f/_radius are now pinned above because they are CVAR_ARCHIVE and were NOT
rem  pinned before -- an ini value could silently override the hold position on every launch,
rem  which is the same trap that cost four arms on rt_tnmp_ev100_min/max.
rem  Tune with .\tools\ab-flsh.cmd (arms at 108 / 130 / 156 and the old and new hold heights).
rem Eye/fire mats: engine rt\mat\ + rt\data\textures.json (no extra -file).
rem DLSS-RR transient-light ghosting: rt_rr_reset_on_lightcut/on_dynlight flush RR's
rem  temporal history (InReset) on flashlight on/off and dynlight appear/disappear
rem  (barrel/rocket explosions etc; muzzle flash intentionally excluded, too frequent).
rem  rt_rr_disocc* is the separate per-pixel tile mask, still under investigation —
rem  see docs/rayreconstruction/flashlight-linger-fix-plan.md.
rem  The rt_rr_* diagnostics (reset_hold / reset_now / reset_debug) are forced to 0
rem  below on purpose: every RT_CVAR is CVAR_ARCHIVE, so one left at 1 in a console
rem  session silently persists in the ini and poisons every later A/B test. Set them
rem  from the console when testing, not here.
rem  rt_upscale_fsr2 0 is forced for the same reason and matters more: DLSS and FSR2
rem  share one upscaler slot, FSR2 is applied second, and Ray Reconstruction only
rem  runs under DLSS. A stale rt_upscale_fsr2=2 in the ini silently disabled RR on
rem  every launch while rt_rayreconstr still read 1 (2026-08-07).

if not exist "gzdoom.exe" (
  echo ERROR: missing gzdoom.exe under %ENGINE%
  exit /b 1
)
if not exist "rt\bin\RTGL1.dll" (
  echo ERROR: missing rt\bin\RTGL1.dll — run tools\build-rtgl.cmd
  exit /b 1
)
if not exist "rt\bin\nvngx_dlssd.dll" (
  echo ERROR: missing rt\bin\nvngx_dlssd.dll — run tools\build-rtgl.cmd
  exit /b 1
)
if not exist "%SKUL%" (
  echo ERROR: missing %SKUL% — run: python tools\pack_lostsoul_rt.py
  exit /b 1
)
if not exist "%FLSH%" (
  echo ERROR: missing %FLSH% — run: python tools\pack_rt_flashlight.py
  exit /b 1
)
if not exist "%MOD%" (
  echo ERROR: missing %MOD%
  exit /b 1
)
if not exist "%FIX3D%" (
  echo ERROR: missing %FIX3D% — run: python tools\make_map_3dfloor_rtfix.py
  exit /b 1
)
if not exist "%SEQL%" (
  echo ERROR: missing %SEQL% — run: python tools\make_seqlight_fix.py
  exit /b 1
)
if not exist "%CTELFIX%" (
  echo ERROR: missing %CTELFIX% — run with Python 3.13 ^(needs Pillow^):
  echo   C:\Users\Winter\AppData\Local\Programs\Python\Python313\python.exe tools\make_ctel_static_center.py
  exit /b 1
)
if not exist "%BULBTEX%" (
  echo ERROR: missing %BULBTEX% — run with Python 3.13 ^(needs Pillow^):
  echo   C:\Users\Winter\AppData\Local\Programs\Python\Python313\python.exe tools\make_bulb_textures.py
  exit /b 1
)

echo Native RT path tracing, A-SVGF denoiser (no Remix^)
if defined MAPLUMP (echo   map=%MAPLUMP%) else (echo   map=none ^(title screen^))
echo   +rt_upscale_dlss 2 +rt_rayreconstr 0 +rt_framegen 0

rem Place window ~300px above vertical center (Y grows down). Falls back to 0 (top).
set "WINY=0"
for /f %%i in ('powershell -NoProfile -Command "Add-Type -AssemblyName System.Windows.Forms; [Math]::Max(0, [int](([Windows.Forms.Screen]::PrimaryScreen.WorkingArea.Height-720)/2-300))"') do set "WINY=%%i"
echo win_y=%WINY%

rem rt_tnmp_ev100_min/max are forced because the ini had BOTH pinned to 1. Equal
rem bounds lock auto-exposure, and EV100 1 exposes the scene very bright, so every
rem region is lifted, no umbra ever reads dark, and shadows vanish globally --
rem independent of every lighting cvar. It survived from an ab-rr-exposure run:
rem CVAR_ARCHIVE wrote it once and it applied to every launch after. Four lighting
rem A/B arms (density x2, emissive fill, all-lights-off) all came back negative
rem because none of them could reach it. Same story for rt_lightlevel_min/max,
rem which the ini had at 200/1 -- min ABOVE max (2026-08-08).
rem
rem Combined 3D-floor strip for every Retribution map that had special 160.
rem
rem d64r-bulb-textures.wad repaints SFLATC's and SPACECE's bulb SOCKETS as lit bulbs,
rem so the faux lights have a fixture in the art to come from. Both live in the TX_
rem namespace, so the replacement lumps are wrapped in TX_START/TX_END. Matching
rem SFLATC_e/SPACECE_e emissive maps go to rt/mat so the painted bulbs actually emit.
rem
rem rt_faux_lamps: SFLATC (flat) and SPACECE (wall) are NOT lamp textures -- no bulbs in
rem the art, and the original game lights neither -- but they ceiling and clad rooms that
rem read as too dark under RT, MAP03's stair hall among them. SFLATC places on its own
rem bulb lattice (see d64r-bulb-textures.wad above); SPACECE still uses the wall strip
rem perimeter walk. Colour is a dark blue-grey, used RAW rather than hue-normalised, with
rem its own light budget so an invented fixture can never push a real one out of the
rem nearest-N set. Set rt_faux_lamps 0 to see the rooms as authored.
rem
rem Colour and intensity were raised together (2026-08-08): at the old 110 the tint was
rem too faint to read as deliberately blue-grey rather than dim-white. 500 is well above
rem the real bulb arrays' 180 -- these rooms needed more lift than the real fixtures give
rem elsewhere -- and the colour was resaturated from 6E7F94 to 3C5078 (channel spread
rem 1.35x -> 2.0x) to survive it: the colour is RAW radiance, not hue-normalised, so
rem scaling intensity scales all three channels together and a weakly-saturated colour
rem gets pushed toward the tonemapper's white clip point faster than a saturated one does.
rem
rem rt_solo_lamps: SFLATDE and SFLATCH are a DIFFERENT case from rt_faux_lamps above, not
rem the same feature reused -- these textures show a real lit bulb baked into the art (a
rem bright white blob centred in the housing), the base game just never wired a light to
rem it. So the light is white (not faux's invented blue-grey) and modest (90, well under
rem the real bulb arrays' 180 and faux's 500) -- "not too strong", per request. One light
rem per texture tile (both textures are a single bulb, not a grid), own colour/budget so
rem it can never crowd rt_faux_lamps or the real ceiling-edge walk. Found in MAP03's big
rem stepped-shaft room (sectors 24-30/43, tags 6-11) and reused in MAP08. Set
rem rt_solo_lamps 0 to see those ceilings as authored.
rem
rem rt_spin_panels: CTEL, the telemetry panel on MAP13's alcove floor and ceiling. Its eight
rem rim gems light in turn -- same luminance set shifted one frame each, total constant at 891
rem every frame -- so the art depicts a light that TRAVELS clockwise without pulsing. The
rem engine orbits one constant light at the measured bearing of whichever gem is currently
rem lit, reading the frame from the texture itself rather than a timer, so it cannot drift.
rem
rem Pinned here rather than left on its compiled defaults because every RT_CVAR is
rem CVAR_ARCHIVE: one console test value would otherwise persist into every later launch.
rem Colour is RAW, so it multiplies intensity -- DC0602 is 0.86x on the red channel by
rem itself. If the light leads or lags the lit gem, nudge rt_spin_panel_yaw; if it runs the
rem wrong way round the panel, rt_spin_panel_cw 0. rt_spin_panel_debug 1 prints frame,
rem bearing and position each second.
rem
rem C23 (MAP09's courtyard panel) has NO light pinned here, and that is the conclusion of a
rem false trail worth not repeating. It looked like an unwired lamp -- a yellow speckled
rem panel that lit nothing -- and got both a textures.json attached light and its own engine
rem light family before anyone opened the texture. There is no yellow in it. The mod's GLDEFS
rem brightmap marks six pixels, three pairs of dark red demon eyes, and gen_world_emissives.py
rem was painting 613 pixels of mortar highlight amber on top of them. The fixture was ours,
rem not the artist's; the mask is fixed at the source and no light is invented for it.
rem
rem rt_lava_light_*: the lava is a LIGHT, and it has to be an analytic one. All seven
rem lava entries in textures.json have carried lightIntensity 140 + lightColor since
rem the lava existed and it never lit anything: that meta only produces a light for
rem SPRITES. A flat's emissive shades the flat and nothing else, so a lava room
rem path-traced as a black box with a glowing net on the floor. Same conclusion as
rem the flames, same shape of fix -- except a flame is a point and a lake is an AREA,
rem so these are scattered on a WORLD-space grid over each lava sector (BSP-tested
rem per point, so concave lakes and the walkways beside them come out right) instead
rem of one per actor. Anchoring the grid to the world rather than to each sector's
rem own box matters: per-box grids double up along the seam between two sectors of
rem one lake and draw a bright line across it.
rem rt_lava_light_intensity is the brightness knob and rt_lava_light_spacing is the
rem evenness knob -- intensity is scaled by (spacing/96)^2 so changing the density
rem does not change how bright the room is. Radius is wide on purpose: a lake is an
rem area source, and a small radius gives every grid point its own hard shadow, which
rem reads as a row of lamps under the floor. tools\ab-lava.cmd has the arms, and
rem MAP15/20/21/34 are the maps with a lava FLOOR (1/2/2/3 sectors); MAP21 is the
rem big hall and MAP34 the only place D64LAVA1/2 appear.
rem The lava SURFACE is separate and is not a cvar at all -- _e/_n/_h/_orm baked by
rem tools\gen_lava_material.py (--apply / --revert). Keep the two apart when judging:
rem "the room is dark" is the light, "the lava looks wrong" is the surface.
rem
rem rt_water_style: Doom 64's LIQUID flats -- water (D64W1_/D64W2_), nukage
rem (D64N1_/D64N2_), sludge (D64S1_/D64S2_, e.g. the brown pools in MAP12) and
rem blood (D64B1_/D64B2_) -- are tagged
rem RG_MESH_PRIMITIVE_WATER engine-side by
rem a texture-name match in rt_main.cpp (l_waterflag), which hands them to RTGL's
rem refl/refr pass -- watch for the "RT water: tagging" line at map load. RTGL's
rem stock water there is physical -- refract into the media, absorb, mirror the
rem rest -- which reads far too real for this art AND is wrong for these maps:
rem they are opaque FLOOR flats, nothing exists under them to refract into.
rem Stylized mode keeps the surface opaque and spends the checkerboard split on
rem "lit water surface" vs "mirror reflection" instead of "refraction" vs
rem "reflection": a deep body colour carrying the flat's own
rem caustic veins, shimmering with the animated wave normal (rt_water_caustic,
rem rt_water_wavestren), under a Fresnel-weighted reflection capped by
rem rt_water_reflmax. rt_water_glow is a small unlit on-screen sheen so the
rem pattern still reads in near-black rooms -- it casts no light. A/B the whole
rem thing against stock physical water with tools\ab-water.cmd.
rem
rem All four liquids run the SAME shader and differ only in colour: each has a
rem body tint (rt_{water,nukage,sludge,blood}_tint_*) for where the flat is
rem black and a crest colour (..._crest_*) for its caustic veins. The crest is
rem not the body brightened -- water's body is deep blue but its crests are pale
rem cyan, which is what the source art's brightest texels are. rt_water_liquids 0
rem restricts the shader to water again.
rem FLOOR FLATS ONLY. The WFALL/SFALL/BFALL wall sheets were tagged too for one
rem revision and are not any more: RG_MESH_PRIMITIVE_WATER makes a primitive
rem refractive, and ASManager then rewrites its TLAS mask to INSTANCE_MASK_REFRACT
rem alone, dropping every INSTANCE_MASK_WORLD_* bit. A pool getting no shadow is
rem survivable; a WALL that stops blocking shadow rays is not -- MAP10's falls
rem leaked light straight through the solid lines they are painted on, and the
rem stylized surface reflected it back. Structural, not a tuning failure.
rem
rem rt_flame_light_*: every open flame in the game -- standing torches (TL*/TS*), wall
rem sconces (A030/A031/A032/GTCH), loose fires (BFLM/GFLM/RFLM/YFLM), the bonfire (FIRE)
rem and the candle
rem (CAND) -- is lit by an engine light, NOT by the sprite's attached light. Those sprites
rem carry lightIntensity 0 in textures.json on purpose, so rt_flame_light_on 0 means the
rem flames cast NOTHING; it is not a fallback to the old behaviour. Two reasons it had to
rem leave texture meta: RTGL1 anchors a sprite light to the CENTRE of the billboard quad
rem (a 100-unit torch lit the room from its own midriff, ~30 units under the flame, where
rem the mod's GLDEFS asks for +80), and meta is static, so the only data-only flicker is a
rem per-frame ramp across the A-E animation -- and every torch spawns at map load, so the
rem whole level would pulse in lockstep. See docs/sprite-illumination.md, Case 7.
rem flicker/speed were halved from the first pass at 0.28/0.42 (2026-08-10): a torch is
rem the ambient light of its room, so depth that looks right on an isolated campfire
rem swings the entire indirect bounce with it. rt_flame_light_flicker 0 gives a steady
rem light while KEEPING the corrected position -- that is the knob to reach for, not _on 0.
rem FIRE (64BigFire, 117 placements over nine maps -- by far the most common fire in the
rem game, plus the Mother Demon's fireball, which shares the sprite) was WRONGLY left out
rem of the table until 2026-08-10 on the claim that it is not a GLDEFS flame prop; the WAD
rem has flickerlight BIGFIRE at offset 0 32 0 bound to frame FIRE. The four ?FLM loose
rem fires exist exactly once each and only in MAP34, so MAP11/12/13/18/21/22 are where the
rem flame work is actually visible. See docs/flame-lighting.md for the placement census.
rem
rem rt_switch_light_*: a THROWN switch lights the wall it is set into. Retribution's
rem switches change art when used (ANIMDEFS CMPSW##A -> ON -> CMPSW##B) and the ON art has
rem lit eyes (SWXC's demon face) or a lit gem (SWXSG). Those texels glow via
rem gen_world_emissives.py, but emissive is NOT a light source under RTGL1, so until now
rem the switch lit up and the wall around it stayed black. The table is GENERATED by
rem tools/gen_switch_lights.py into rt_switch_lights.h -- position is the centroid of each
rem texture's own emissive mask and colour is that mask's hue, so cast light and glow are
rem measured from the same pixels. 67 rows: the bare 32x32 faces plus the 56 CMPSW* wall
rem panels that stamp them (41 bare vs 54 composite sidedefs, so the panels are the
rem majority and were the half that was broken).
rem Which frame is ON is NOT the A/B letter: SWXCL and SWXCKL light on A -- their eyes go
rem OUT when pressed. The generator keys off which textures have a mask, so that is right
rem by construction.
rem rt_switch_lights 0 is a true revert: the eyes still GLOW, they just light nothing.
rem The one convention here is the vertical placement (sidedef pegging + row offset). If
rem every marker sits a constant distance off its eyes, correct rt_switch_light_zofs; if
rem only some do, the pegging branch is wrong and the cvar will not save it. Verify with
rem tools\ab-switch.cmd debug.
rem
rem d64r-seqlight-fix.wad replaces maps to clear LightSequence chains -- phased
rem waves of light that travel along a run of sectors with no fixture casting
rem them. Under RT they are worse than in the original renderer: rt_sector_emis
rem makes any sector at/above minlight 160 a source, so the wave pulses as a
rem d64r-blood-persist.pk3: BLUD splats stay for the level instead of vanishing
rem after ~0.9 s. The lifetime was never a renderer setting -- it is the `Stop`
rem at the end of 64Blood's Spawn in the WAD's own DECORATE, so the pk3 replaces
rem those three actors with copies that end on `BLUD A -1`. rt_gore_life 32 puts
rem the stock behaviour back (the handler expires them; DECORATE cannot read a
rem cvar). rt_gore_max caps the live count, oldest first. Do not confuse
rem rt_gore_* with rt_blood_tint_* below -- the latter is the blood LIQUID
rem surface, nothing to do with splats. See docs/blood-persist.md.
rem
rem d64r-widescreen-gfx.pk3 overrides graphics/INTERPIC -- the demon-head plate
rem behind the end-of-level score screen (and the credits page). The WAD's copy
rem is 320x200, which GZDoom pillarboxes to a 4:3 box on a 16:9 window. The
rem replacement is 3328x936 -- exactly 32:9, so even a super-ultrawide fills
rem with no bars. CalcFullscreenScale (v_draw.cpp) crops the sides to fit
rem anything narrower, and 3328 is exactly 2x the 1664-wide core, so on a 16:9
rem screen the crop lands precisely on the original shot and the extension is
rem never seen. The sides are the outer 280 columns mirrored, stretched and
rem ramped down to 45% -- there is no art out there, only more of the same
rem dark stone. Height must NOT be 200 or 400: those two values are remapped
rem to 240/480 for the old non-square-pixel ratio and the aspect would come
rem out wrong. Load it last so it wins over the WAD.
rem
rem sourceless glow. Currently only MAP03's twin staircases; three more chains
rem are surveyed and awaiting playtest in docs/sequence-light-chains.md.
rem Load order note: MAP03 has no special-160 linedefs, so it is absent from
rem FIX3D and the two wads never touch the same map.
rem
rem rt_sector_tint_albedo is pinned at 1.0 but eleven maps do not run at 1.0, and
rem that is not a contradiction: the 1.0 here is the BASE that RT_TINT_PRESETS
rem lowers per map at level load, and the base is what every unlisted map gets
rem back. So `rt_sector_tint_albedo` in the console reads 0.63 on MAP13 and 1.0
rem on MAP01 -- read it there, not here.
rem
rem The table exists because the sector colormap hue is multiplied into surface
rem ALBEDO, and being peak-normalized it can only remove channels. On a cool map
rem it removes red, which is most of what a warm light is made of: the flashlight
rem (ffbe82) lands on MAP01's #FFAA82 as saturated orange and on MAP13's #6AADFF
rem as blue-dominant grey, 21% dimmer. Lowering the GLOBAL instead does not work
rem -- MAP02's switch-triggered blue room is the most saturated colormap in the
rem game, so any global reduction hits it hardest, and it is the effect the 1.0
rem default was chosen for. MAP02 therefore has no row and is untouched.
rem See RT_TINT_PRESETS in rt_main.cpp for the per-map numbers and .\tools\ab-tint.cmd
rem to compare arms (`ab-tint.cmd basefl 13` vs `ab-tint.cmd flsh 13`).
rem
rem rt_dynlight_flicker was 0, and that SUPPRESSED EVERY SMON PANEL LIGHT IN THE GAME.
rem RT_UploadGzDoomDynamicLights skips FlickerLight/RandomFlickerLight outright when this
rem is off, and the mod wires its wall monitors with 9802 PointLightFlicker things placed
rem 4-56 units off the panel face: SMONAA 88/88 wired, SMONDA 25/27, SMONCA 19/21,
rem SMONEA 6/6. Every one was dropped before upload, so the panels showed only their _e
rem emissive glow -- which casts nothing -- and read as animated but dead.
rem
rem Reported from play on MAP29 three separate ways, and the map data matches the report
rem exactly. Of MAP29's three SMONDA panels, lines 922 and 937 carry a 9802 (skipped)
rem while line 927 carries a 9801 PointLightPulse (not skipped, it is not a flicker type)
rem -- so EXACTLY ONE of the three emitted, which is "only one seemed to have proper light
rem emit, despite the others also being animated". SMONAA's 88 lights are all pure green
rem (0,255,0), which is the "should emit more green, i think there is already but its very
rem dim" half: the green was the _e mask alone, with the actual green light suppressed.
rem
rem Blast radius measured before flipping it: 205 9802 things game-wide, 199 of them
rem beside a SMON panel and 6 anything else, so this turns on the monitors and virtually
rem nothing else. The cvar's own doc defers ceiling head lights to rt_ceiling_lamps, and
rem that family is pinned 0 below -- so nothing gets double-lit either.
rem Compare arms with .\tools\ab-smon.cmd (2026-08-11).
rem The ~325 STATIC cvar pins now live in tools/d64rt-pins.cfg and are applied
rem with +exec. They used to be spelled out here as "+name value" pairs, which
rem made this command line 8016 characters -- and cmd.exe truncates at 8191, so
rem the "-- +cvar" passthrough at the very end was silently dropped, along with
rem the last few pins. An A/B arm then ran with default values while looking
rem like it had applied its own. Keep this line short.
rem
rem Order matters and is preserved: the pins (including god/notarget) run BEFORE
rem +map, exactly as they did inline, and %EXTRA% runs LAST so an arm still wins.
start "" gzdoom.exe ^
  -iwad "%IWAD%" -file "%MOD%" "%BM%" "%SKUL%" "%FLSH%" "%MUS%" "%FIX3D%" "%SEQL%" "%BULBTEX%" "%CTELFIX%" "%SKY%" -file "%LAVAFX%" "%BLOODFX%" "%WIDEGFX%" "%MUGSHOT%" "%TITLOGO%" -rtnolauncher -width 1280 -height 720 %RTDEBUG% ^
  +logfile "%LOGF%" ^
  +win_y %WINY% ^
  +exec "%PINS%" ^
  %MAPARG% %MAPLUMP% %EXTRA%
exit /b 0

:badmap
echo Usage: %~nx0 [1-34]
echo   Optional map number (default 1^). Example: %~nx0 5  -^> +map map05
echo   Or "menu" to boot to the title screen with no +map.
exit /b 1
