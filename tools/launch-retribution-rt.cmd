@echo off
rem DelayedExpansion is needed to accumulate the "--" passthrough in a loop.
rem Safe here: no literal '!' appears anywhere else in this script.
setlocal EnableExtensions EnableDelayedExpansion
set "ENGINE=G:\AI\Doom64-RT\sourcecode\gzdoom-rt\build\RelWithDebInfo"
set "IWAD=D:\Games\GZDoom\doom2.wad"
set "MOD=G:\AI\Doom64-RT\Doom64-Retribution\D64RTR_v15.WAD"
set "BM=G:\AI\Doom64-RT\Doom64-Retribution\D64RTR_BRIGHTMAPS.PK3"
set "SKUL=G:\AI\Doom64-RT\Doom64-Retribution\d64r-lostsoul-rt.pk3"
set "FLSH=G:\AI\Doom64-RT\Doom64-Retribution\d64r-rt-flashlight.pk3"
set "FIX3D=G:\AI\Doom64-RT\Doom64-Retribution\d64r-3dfloor-rtfix.wad"
set "SEQL=G:\AI\Doom64-RT\Doom64-Retribution\d64r-seqlight-fix.wad"
set "BULBTEX=G:\AI\Doom64-RT\Doom64-Retribution\d64r-bulb-textures.wad"
set "CTELFIX=G:\AI\Doom64-RT\Doom64-Retribution\d64r-ctel-fix.wad"
set "SKY=G:\AI\Doom64-RT\Doom64-Retribution\d64r-rt-sky.pk3"
set "LAVAFX=G:\AI\Doom64-RT\Doom64-Retribution\d64r-lava-fx.pk3"
set "MUS=G:\AI\Doom64-RT\Doom64-Retribution\D64MUS.PK3"
rem Full console transcript (incl. startup) -> shareable log. `logfile` is
rem whitelisted to run at GS_STARTUP (c_dispatch.cpp), so it captures
rem everything from boot, including RTGL -rtdebug output.
set "LOGF=G:\AI\Doom64-RT\rt-console.log"

rem Usage: launch-retribution-rt.cmd [1-34] [debug] [-- +cvar val ...]
rem   Optional map number (default 1) → +map map01 … map34
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
set "MAPNUM=%~1"
if "%MAPNUM%"=="" set "MAPNUM=1"
set /a "N=MAPNUM" 2>nul
if errorlevel 1 goto :badmap
if %N% LSS 1 goto :badmap
rem 34, not 32: the WAD holds MAP00..MAP34. 33/34 are the two beyond the main
rem run, and MAP34 is the ONLY place in the game the BFLM/RFLM/YFLM/GFLM loose
rem fires are placed (one of each), so the cap used to make them unreachable.
if %N% GTR 34 goto :badmap
if %N% LSS 10 (set "MAPLUMP=map0%N%") else (set "MAPLUMP=map%N%")

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
rem d64r-lostsoul-rt.pk3: yellow SKUL sprites + LSGL offset-glow EventHandler.
rem d64r-rt-flashlight.pk3: stylized 5-cell battery HUD (rt_flsh_charge / battstate; F toggles)
rem  + battery sound cues (rt_flsh_flicker counter; d64rt_flsh_sound / _vol to mute or tune).
rem  Charge is persistent: switching off no longer refills the cell, it trickles back up at
rem  rt_flsh_idle_recharge x the post-burnout rate.
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
echo   map=%MAPLUMP%  +rt_upscale_dlss 2 +rt_rayreconstr 0 +rt_framegen 0

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
rem sourceless glow. Currently only MAP03's twin staircases; three more chains
rem are surveyed and awaiting playtest in docs/sequence-light-chains.md.
rem Load order note: MAP03 has no special-160 linedefs, so it is absent from
rem FIX3D and the two wads never touch the same map.
start "" gzdoom.exe ^
  -iwad "%IWAD%" ^
  -file "%MOD%" "%BM%" "%SKUL%" "%FLSH%" "%MUS%" "%FIX3D%" "%SEQL%" "%BULBTEX%" "%CTELFIX%" "%SKY%" -file "%LAVAFX%" ^
  -rtnolauncher -width 1280 -height 720 %RTDEBUG% ^
  +logfile "%LOGF%" ^
  +vid_fullscreen 0 +win_x -1 +win_y %WINY% +queryiwad false +sv_cheats 1 +god +notarget +map %MAPLUMP% ^
  +rt_mod_compat 1 +r_drawvoxels 0 ^
  +d64_enterfade 0 +d64_exitfade 0 ^
  +rt_fluid false +rt_autoexport false ^
  +rt_upscale_dlss 2 +rt_upscale_fsr2 0 +rt_rayreconstr 0 +rt_framegen 0 ^
  +gl_noskyboxes false ^
  +rt_sky 25 +rt_sky_always true +rt_sky_nowalls 0 ^
  +rt_sun 1 +rt_sun_intensity 90 +rt_sun_a 25 +rt_sun_b 135 +rt_sun_color B4C8FF +rt_sun_angdiam 0.5 ^
  +rt_moon_geo 1 +rt_moon_geo_size 12 ^
  +rt_moon_presets 1 ^
  +rt_clouds 0 +rt_clouds_presets 1 +rt_clouds_shells 6 +rt_clouds_horizon 9 +rt_clouds_curve 0.55 ^
  +rt_clouds_thick 0.7 +rt_clouds_tiles 6 +rt_clouds_alpha 0.9 +rt_clouds_dark 0.45 ^
  +rt_clouds_wind 0.014 +rt_clouds_wind_dir 30 +rt_clouds_shear 0.09 +rt_clouds_occlude 1 +rt_clouds_transmit 0.22 +rt_clouds_tint B4C0DC +rt_clouds_flash 2.2 ^
  +rt_lightning 1 +rt_lightning_intensity 2200 +rt_lightning_color C8D8FF ^
  +rt_lightning_decay 0.18 +rt_lightning_strokes 3 +rt_lightning_angdiam 6 ^
  +rt_lightning_alt_min 15 +rt_lightning_alt_max 40 ^
  +rt_lightning_bolt 1 +rt_lightning_bolt_size 55 ^
  +rt_lightning_sectorflash 1 +rt_lightning_debug 0 ^
  +rt_fog 1 +rt_fog_presets 1 +rt_fog_color 000000 +rt_fog_density -1 +rt_fog_density_mult 0.3 ^
  +rt_fog_density_far -1 +rt_fog_color_far 000000 +rt_fog_curve 1 ^
  +rt_fog_far 45 +rt_fog_ambient 0.02 +rt_fog_lightmult 1 +rt_fog_light_near 2 +rt_fog_illum 1 ^
  +rt_sun_leak_debug 0 +rt_sun_require_sky 1 ^
  +rt_classic 0 ^
  +rt_flsh 0 +rt_flsh_intensity 90 +rt_flsh_angle 42 +rt_flsh_pitch 22 ^
  +rt_flsh_battery 1 +rt_flsh_on_secs 30 +rt_flsh_die_secs 4 +rt_flsh_off_secs 5 ^
  +rt_flsh_idle_recharge 0.25 ^
  +rt_flsh_color ffbe82 ^
  +rt_gunglow 1 +rt_gunglow_intensity 90 +rt_gunglow_color 3355FF ^
  +rt_gunglow_radius 0.07 +rt_gunglow_f 0 +rt_gunglow_u 0 +rt_gunglow_pullback 0.5 ^
  +rt_gunglow_bob 0.012 +rt_gunglow_flicker 0.22 +rt_gunglow_fire_boost 2.2 ^
  +rt_wpn_solid_bright 1 +rt_wpn_debug 0 ^
  +rt_mzlflsh_perweapon 1 +rt_mzlflsh_color_plasma 3355FF +rt_mzlflsh_color_bfg A0FFA0 ^
  +rt_mzlflsh_color_unmaker FF1111 +rt_mzlflsh_color_chaingun 9677FF ^
  +rt_mzlflsh_luma_compensate 1 ^
  +rt_tnmp_ev100_min 2 +rt_tnmp_ev100_max 7.7 ^
  +rt_lightlevel_min 80 +rt_lightlevel_max 230 +rt_lightlevel_exp 2 ^
  +rt_illum_sens_direct 1 +rt_illum_sens_indirect 0.75 +rt_illum_sens_spec 1 ^
  +rt_shadowrays 4 ^
  +rt_emis_mapboost 200 +rt_emis_additive_dflt 0.15 +rt_emis_maxscrcolor 3 ^
  +rt_sector_tint_lights 0.85 +rt_sector_tint_albedo 1.0 ^
  +rt_sector_emis 0.35 +rt_sector_emis_minlight 160 +rt_sector_emis_margin 40 +rt_sector_emis_debug 0 ^
  +rt_sector_lights 0 +rt_sector_flicker 0 ^
  +rt_dynlight 1 +rt_dynlight_flicker 0 +rt_dynlight_intensity 40 +rt_dynlight_max 500 +rt_dynlight_rsoft 20 +rt_dynlight_stack_atten 1 +rt_dynlight_minradius 16 ^
  +rt_dynlight_debug 0 +rt_dynlight_debug_marks 0 +rt_wall_tex_debug 0 +rt_dynlight_radius 0.08 ^
  +rt_ceiling_lamps 0 +rt_ceiling_lamp_intensity 0 +rt_ceiling_lamp_radius 0.10 ^
  +rt_ceiling_lamp_off 0.12 +rt_ceiling_lamp_fade 40 +rt_ceiling_lamp_maxspan 128 ^
  +rt_hang_lamps 1 +rt_hang_lamp_intensity 220 +rt_hang_lamp_radius 0.09 +rt_hang_lamp_zofs 4 ^
  +rt_pole_lamp_intensity 300 +rt_pole_lamp_zfrac 0.88 ^
  +rt_wall_strips 1 +rt_wall_strip_intensity 180 +rt_wall_strip_minlight 120 ^
  +rt_wall_strip_seglen 64 +rt_wall_strip_radius 0.35 +rt_wall_strip_max 128 +rt_wall_strip_debug 0 +rt_wall_strip_debug_marks 0 ^
  +rt_ceiling_edge_lamps 1 +rt_ceiling_edge_intensity 180 +rt_ceiling_edge_seglen 64 ^
  +rt_ceiling_edge_radius 0.35 +rt_ceiling_edge_zofs 10 +rt_ceiling_edge_inset 10 ^
  +rt_ceiling_edge_max 320 +rt_ceiling_edge_maxdist 3072 ^
  +rt_ceiling_edge_lattice 1 ^
  +rt_ceiling_edge_debug 0 +rt_ceiling_edge_debug_marks 0 ^
  +rt_faux_lamps 1 +rt_faux_lamp_color 3C5078 +rt_faux_lamp_intensity 500 ^
  +rt_faux_lamp_max 256 +rt_faux_lamp_stride 2 ^
  +rt_spin_panels 1 +rt_spin_panel_color DC0602 +rt_spin_panel_intensity 200 ^
  +rt_spin_panel_radius 0.06 +rt_spin_panel_orbit 26.6 +rt_spin_panel_zofs 16 ^
  +rt_spin_panel_yaw 0 +rt_spin_panel_cw 1 +rt_spin_panel_max 64 +rt_spin_panel_debug 0 ^
  +rt_solo_lamps 1 +rt_solo_lamp_color FFFFFF +rt_solo_lamp_intensity 45 ^
  +rt_solo_lamp_radius 0.06 +rt_solo_lamp_zofs 8 +rt_solo_lamp_max 384 +rt_solo_lamp_stride 1 ^
  +rt_flame_light_on 1 +rt_flame_light_scale 1.0 +rt_flame_light_radius 0.09 ^
  +rt_flame_light_flicker 0.15 +rt_flame_light_speed 0.25 +rt_flame_light_wobble 2.0 ^
  +rt_flame_light_maxdist 3072 +rt_flame_light_max 64 +rt_flame_light_debug 0 ^
  +rt_switch_lights 1 +rt_switch_light_intensity 60 +rt_switch_light_radius 0.06 ^
  +rt_switch_light_ofs 2 +rt_switch_light_zofs 0 +rt_switch_light_maxdist 2048 ^
  +rt_switch_light_max 48 ^
  +rt_light_mark_intensity 25 +rt_light_mark_max 24 ^
  +rt_translucent_minalpha 0.72 ^
  +rt_spectre_alpha 0.20 +rt_nightmareimp_alpha 0.35 +rt_spectre_corpse_solid 1 +rt_ghost_solid 0 +rt_illum_volume 0 +rt_ghost_lightscale 1 ^
  +rt_rr_temporal 0 ^
  +rt_rr_disocc 1 +rt_rr_disocc_ratio 3.0 +rt_rr_disocc_mindelta 0.01 +rt_rr_disocc_show 0 ^
  +rt_rr_reset_on_lightcut 1 +rt_rr_reset_on_dynlight 1 +rt_rr_reset_delta 0.5 +rt_rr_reset_min_ms 250 ^
  +rt_rr_reset_hold 0 +rt_rr_reset_now 0 +rt_rr_reset_debug 0 ^
  +rt_restir_initial 32 ^
  +rt_lava_gi 40 +rt_lava_debug 0 +rt_lava_tint_r 255 +rt_lava_tint_g 140 +rt_lava_tint_b 76 ^
  +rt_lava_emis 6 +rt_lava_flow 0.45 +rt_lava_flow_speed 0.03 +rt_lava_flow_scale 0.12 ^
  +rt_lava_flow_pixel 0.25 +rt_lava_pulse 0.10 +rt_lava_pulse_speed 0.35 ^
  +rt_lava_light_on 0 +rt_lava_light_intensity 1800 +rt_lava_light_spacing 96 ^
  +rt_lava_light_radius 0.3 +rt_lava_light_z 40 +rt_lava_light_max 256 +rt_lava_light_dist 2048 ^
  +rt_lava_light_r 255 +rt_lava_light_g 90 +rt_lava_light_b 20 +rt_lava_light_debug 0 ^
  +rt_water_style 1 +rt_water_liquids 1 ^
  +rt_water_tint_r 1 +rt_water_tint_g 1 +rt_water_tint_b 15 ^
  +rt_water_crest_r 140 +rt_water_crest_g 204 +rt_water_crest_b 255 ^
  +rt_nukage_tint_r 2 +rt_nukage_tint_g 15 +rt_nukage_tint_b 4 ^
  +rt_nukage_crest_r 153 +rt_nukage_crest_g 255 +rt_nukage_crest_b 115 ^
  +rt_sludge_tint_r 15 +rt_sludge_tint_g 9 +rt_sludge_tint_b 2 ^
  +rt_sludge_crest_r 255 +rt_sludge_crest_g 204 +rt_sludge_crest_b 115 ^
  +rt_blood_tint_r 15 +rt_blood_tint_g 2 +rt_blood_tint_b 2 ^
  +rt_blood_crest_r 255 +rt_blood_crest_g 115 +rt_blood_crest_b 102 ^
  +rt_water_caustic 1.5 +rt_water_reflmin 0.1 +rt_water_reflmax 0.75 +rt_water_rough 0.1 ^
  +rt_water_glow 0.15 +rt_water_veinref 0.1 ^
  +rt_water_wavestren 0.4 +rt_water_wavespeed 0.2 +rt_water_areascale 0.35 ^
  +rt_water_caustics 1.2 +rt_water_caustic_scale 0.8 +rt_water_caustic_speed 0.35 ^
  +rt_water_caustic_dist 512 +rt_water_caustic_rise 64 +rt_water_caustic_slant 0.6 +rt_water_caustic_wall 4.0 ^
  +rt_water_debug 0 ^
  +rt_normalmap_stren 1 +rt_heightmap_stren 1 %EXTRA%
exit /b 0

:badmap
echo Usage: %~nx0 [1-34]
echo   Optional map number (default 1^). Example: %~nx0 5  -^> +map map05
exit /b 1
