# Open issues — Retribution RT (2026-08-03)

Living punch list of **what still fails**, what we **tested**, and what **works**.  
Do not treat this as a progress cheer sheet — only unresolved / partially resolved items belong in §1.

**Related:** `AGENTS.md`, `compat-patches.md`, `material-authoring-spec.md`, `gallery-emis-wall-wash-fix-plan.md`, `gallery-emis-wall-wash-diagnostics.md`, **`rayreconstruction/rr-noise-investigation.md`** (DLSS-RR salt / PBR)

**Play path (canonical):** `tools/launch-retribution-rt.cmd` → `sourcecode/gzdoom-rt/build/RelWithDebInfo/`

---

## 1. Unfixed / incomplete

### 1.0 MAP04 first room wash — **DYNMAXRADIUS 2026-08-05** (needs rebuild + test)

| | |
|---|---|
| **Symptom** | `screen/level4lightingfirstroom.png` — flat bright yellow-brown wash, room 4× brighter than original. Ceiling at nearly white (brightness 244) vs original (brightness 38). Center of room brightness 93 vs original 23. |
| **Cause** | 4× type 9800 static PointLights at room corners (r=88, arg1=200 red). These are **decorative ceiling fixtures** (software colormap indicators, not real light sources). Since they're not FlickerLight (sector special=None), `rt_dynlight_flicker 0` does NOT skip them. Each gets ~103 intensity after rsoft rolloff, totaling ~412 in a small room = yellow-brown flood. Sector light 160 and `volumeLightMultiplier 3` are minor contributors — the dynlights dominate. |
| **Fix** | Engine: skip dynlights with radius > 40 on MAP04 only (checks `_map04` in map name). The 4 corner r=88 ceiling fixtures are decorative software-colormap markers. MAP01 spawn blink (r=24) and other maps are unaffected. No rebuild needed after engine patch. |
| **Confirm** | `tools/launch-retribution-rt.cmd 4` — first room dark with warm hanging-lamp pools. `tools/launch-retribution-rt.cmd 1` — MAP01 blink still works. |

### 1.1 / 1.3 Spawn blink + shadow-cast lights — **CEILING LAMPS 2026-08-03** (needs visual confirm)

| | |
|---|---|
| **Target** | Ceiling **head lights** over MAP01’s first zombies (`SFLATAS` secs 31/33) — **not** wall SMON terminals. |
| **Why wall terminals blinked** | Alcove secs **32/34** are `dLight_Flicker` (65) + green **9802** at the SMON. Dynlight upload (and any sector_flicker/lights) lightstyles those alcoves. |
| **Why `rt_sector_lights 1` looked dead for ceilings** | Booth ceilings have **special 0 / steady lightlevel 200** — sector lights never blink them. Enabling all-sector lights mostly adds steady fill; the only blink still comes from alcove 65 / 9802. |
| **Fix landed** | `RT_UploadCeilingInsetLamps()` under `SFLATAS*`/`SPORT*`. `rt_dynlight_flicker 0` skips 9802 wall flashers. `rt_sector_flicker 0`. Debug: `rt_ceiling_lamp_debug 1` → cyan markers + console. |
| **RR noise (2026-08-05)** | See **`rayreconstruction/rr-noise-investigation.md`**. Soft lamp fade landed; boiling + `rt_rr_temporal` both **failed** (worse / ghost). Follow-on: black world when Compose still read empty temporal buffers — **fixed** (ComposeNoisy raw-only). PBR suspected amp — do not strip. |

### 1.2 MAP01 directional wash / sky leak — **MITIGATED** (night sky 2026-08-03)

| | |
|---|---|
| **Symptom** | Inch forward ~2%: warm fill on left wall/floor, **casts shadows**, no lamp in view. |
| **Confirmed cause** | **`rt_sky`** through an aperture (not emis GI / dynlights). Amplified by bright `RSKY1` @ `rt_sky 200`. |
| **Fix landed** | `d64r-rt-sky.pk3` → **`SPACE`** night flat (not RSKY1); play launcher `+rt_sky 25`; sector skybox rooms **Ignored** under RT (`hw_walls`/`hw_flats` when `portalState.inskybox`) + `rt_sky_always` fills outdoor sky; `gl_noskyboxes false`. User: sky looks good. Residual geometric seams may still need hunting at very high sky intensity. |

### 1.2b MAP13 painted moonlight → a real moon — **LANDED 2026-08-10** (needs visual confirm)

| | |
|---|---|
| **Symptom** | `screen/level13fakeoutside light streaks.png` — parallel bands across the floor **and ceiling** of a large dark hall, reading as moonlight through a window, with no moon and nothing else casting them. |
| **Cause** | A fourth family of fake light, invisible to `scan_light_specials.py` because it never animates: **painted shafts**. MAP13 sectors 136/137 (west hall) and 134/135 (north colonnade) are wedge fans at `lightlevel 255` inside rooms at 170/180, identical to those rooms in floor height, ceiling height and both flats. MAP13's `rt_sector_emis` threshold is 200, so the wedges emit and the rooms do not. Each sector is the *whole* fan — non-contiguous, like MAP03's stairs — and spans the room's full height, which is why the ceiling streaks too. |
| **Found by** | `tools/scan_fake_lightshafts.py 13` — new; the geometric "identical but brighter" test. Whole game: 149 emitting shafts across 15 maps, only MAP13 acted on. |
| **Fix — half 1** | `tools/make_seqlight_fix.py` gained a `SHAFTS` table; the four sectors drop to their host rooms' lightlevel. MAP13 also gets 2 `Sector_Set3dFloor` linedefs re-stripped, since this wad now replaces MAP13 and loads after `d64r-3dfloor-rtfix.wad` (the load-order trap, and it bit here — MAP13 *is* in that wad). |
| **Fix — half 2** | The windows are **real** `F_SKY1`, so the light is given back rather than deleted: `MOONSKY` (`tools/gen_moon_sky.py` → `tools/pack_rt_sky.py`) paints a moon into the `SPACE` starfield tiled to 1024 wide, and the launcher pins `rt_sun 1 / 90 / a 25 / b 135 / B4C8FF` to cast the actual shafts. Disc and light must stay aimed alike — the RT sky cubemap is not importance-sampled, so the disc casts nothing usable at 1 spp. |
| **Watch** | `rt_sun` is **global**. Enclosed maps are unaffected (a directional light is occluded like any other), but any map with a geometric **sky leak** now gets a hard-edged directional wash where §1.2 previously left only diffuse `rt_sky` bleed. MAP01 is the first place to check. |
| **Confirm** | `tools\ab-moon.cmd moon 13` — halls lit by shafts raking in from the north-west windows, moon visible in the sky on the same bearing. `tools\ab-moon.cmd off 13` is the control (paint gone, nothing given back). If the shafts and the disc disagree on bearing, the sky's `u` sign is wrong: `python tools\gen_moon_sky.py --flip-u && python tools\pack_rt_sky.py`. |
| **Detail** | `docs/sequence-light-chains.md`, "The fourth family". |

### 1.2d Sky leaks — **CAUSE FOUND: the moon is a point light** (2026-08-10)

Supersedes the framing in §1.2c below. Bisect done (`ab-skyleak nosun` fixes it),
symptom shot `screen/level13skyleak.png`: a cold blue-white wash over a ceiling,
brightest at the wall/ceiling junction and fading across the ceiling — light
entering through a band at the **top of a wall**, not a floor crack or a doorway.

**Two facts, both from source, that together are the whole thing:**

1. RTGL1 excludes sky geometry from shadow rays outright —
   `VulkanDevice.cpp:514`, `rayCullMaskWorld_Shadow = INSTANCE_MASK_WORLD_0`,
   commented *"skip shadows for … WORLD_2 - 'sky' geometry"*. Doom's sky-hack
   bands (the strip at a wall top where GZDoom draws sky instead of an upper
   texture) are flagged as sky, so the moon passes straight through them. 916
   game-wide, **46 in MAP13**, 96–416 units.
2. `rt_sun_angdiam` was hardcoded **0.5°** — the real moon, i.e. a *point*. Its
   shadow test is one ray, yes or no, so a crack admits exactly as much light as
   a doorway.

**Why no per-surface rule can fix it.** MAP13's *wanted* moonlight also comes
through holes in walls — the `F_SKY1` window slots. Wanted and unwanted openings
are the same kind of geometry. "Sky walls occlude, sky flats don't" would have
killed the west hall's shafts, which are the thing the moon was built for.

**The fix is to stop treating the moon as a point.** `rt_sun_angdiam` is now a
cvar. Widen the disc and RTGL1's `sampleDirectionalLight` → `sampleDisk` samples
a point on it per shadow ray, so an opening admits light **in proportion to how
much of the disc it reveals**: a doorway reveals all of it and is unchanged, a
narrow band reveals a sliver and dims smoothly. And because an opening of size
`d` seen from `L` away subtends `d/L`, it falls off with **distance** — the band
still lights what is beside it and stops washing a ceiling 2000 units off, which
is exactly the wash in the screenshot.

Soft rolloff, **not** a cutoff. "Too small a hole" is only meaningful relative to
how far away you are standing, which is why a hard unit threshold could not have
been right at any value, and why this is an angle.

**Cost:** one knob, both effects — it softens the wanted shafts by the same
amount. The answer is the largest value whose shafts still look good.

**Tune:** `tools\ab-moonsize.cmd <real|soft|wide|huge|absurd>` (0.5 / 3 / 8 / 16
/ 40°), or live: `rt_sun_angdiam 8`. Launcher pins 0.5 for now — **unset until
tested**. The `absurd` arm is the falsifier: if the leak survives 40°, the light
is not squeezing through a small opening and this theory is wrong.

**Noise:** a wider disc makes shadow rays disagree more, so the penumbra is
noisier at 1 spp. Judge after the denoiser settles; if it stays grainy, raise
`rt_shadowrays` (launcher pins 4) rather than abandoning the angle.

### 1.2c Sky leaks — **superseded by 1.2d**, kept for the measurements

Reported: light arriving in rooms that look sealed, "maps are clearly not fully
well set". The natural request was a size gate — *only let gaps over N units in*.
**That does not work here, and the measurements say why.**

**How sky light physically enters.** GZDoom hands RTGL1 the sky portal's geometry
flagged `RG_MESH_PRIMITIVE_SKY_VISIBILITY`; RTGL1 puts it in the BLAS with
`INSTANCE_CUSTOM_INDEX_FLAG_SKY` (`ASManager.cpp`, `PV_WORLD_2`). Any ray that
hits it returns sky radiance. It is not a backdrop — it is an emitting surface.

**Why a size gate has nothing to bite on.** `HWWall::SkyTop` builds sky *walls*
spanning from the neighbouring ceiling to **z = 32768**, so gating on the sky
polygon's own size is meaningless — every one of them is enormous. The gate would
have to act on the *aperture*, and `tools/scan_sky_apertures.py` measured both
apertures that the map format can actually express:

| class | game-wide | MAP01 | small ones |
|---|---|---|---|
| Doom sky-hack ceiling steps (both sectors sky, upper left open) | 916 | **0** | only **4** are ≤32 units; median 128–384 |
| Missing upper texture facing a sky sector | **0** | 0 | — |

MAP01 — the map with the *documented* leak (§1.2) — has **zero** of either. A
`rt_sky_wallgap` threshold would close nothing small and would start destroying
genuine openings around 96 units. It was not shipped, deliberately.

What that leaves is sub-unit cracks at T-junctions and sector seams, which no
threshold can select because they are not in the map data at all — they are
floating-point gaps between polygons that a rasteriser never had to care about.

**So bisect instead.** `tools/ab-skyleak.cmd <nosun|nosky|dark|nowalls|full>`,
run from the same spot in the leaking room:

| result | meaning | cheapest fix |
|---|---|---|
| only `nosun` fixes it | the **moon** is finding a pinhole — a directional light needs one unblocked shadow ray, so it exposes cracks the dim dome never showed | give that map a `RT_MOON_PRESETS` row with **intensity 0** — no moon on that map, nothing else affected |
| only `nosky` fixes it | the **dome**, through a genuine opening | lower `rt_sky`, or close the aperture in the map |
| `nowalls` fixes it | **wall-class**: the sideways sky band at wall tops | `ML_NOSKYWALLS` on the offending linedefs, patched in like `make_seqlight_fix.py` does |
| nothing fixes it | not the sky | `rt_sector_emis` or an attached sprite light — `tools/scan_fake_lightshafts.py` |

`rt_sky_nowalls` (new, default **0**) is the `nowalls` arm: it applies GZDoom's
own `ML_NOSKYWALLS` to *every* two-sided line at once. Sky ceilings and one-sided
sky curtains are untouched, so you still see sky by looking up and outdoor areas
stay enclosed. It is blunt — it removes good bands with the bad — and exists to
answer *whether* a leak is wall-class before anyone spends time on a targeted fix.

**Most likely, given timing:** the moon (§1.2b) went in globally the same day this
was reported, and a directional light is exactly the thing that turns a tolerable
crack into a visible shaft. Run `nosun` first.

### 1.3 Map PointLightFlicker (9802) / wall SMON — gated off

9802s by wall terminals are **not** the desired spawn blink. Play launcher sets `rt_dynlight_flicker 0` so those Flicker lights are not uploaded; ceiling lamps handle §1.1.

### 1.4 Lost Souls buried in the floor + LSGL bubble — **FIXED 2026-08-08** (needs confirm)

| | |
|---|---|
| **Symptom** | `screen/lostsoulsstillbadandroundbubble.png` (MAP05) — every Lost Soul renders sunk into the floor; a white/pink round dome sits on the floor nearby. |
| **Cause** | **Lost sprite offsets.** All 40 original `SKUL*` lumps carry a PNG `grAb` chunk (e.g. `SKULA1` 56×62, offset `(27,65)`). `tone_skul_albedo()` round-trips each through PIL, which silently drops ancillary chunks, so every replacement shipped with **no** `grAb`. GZDoom falls back to a zero offset → the whole sprite hangs *below* the actor origin instead of above it. `LSGLA0` (synthetic, never had one) sank the same way, showing only its top half above the floor = the "bubble". |
| **Fix** | `png_set_grab()` in `pack_lostsoul_rt.py` re-inserts `grAb` before `IDAT`, carrying each lump's original offset; `LSGLA0` gets `(24,58)` to centre on the flame. Packer warns if any lump lacks `grAb`. Verified: 41/41 sprites in the pk3 match their source offsets. |
| **Blob removed** | The `LSGL` carrier disc is **gone** (2026-08-08). With offsets fixed it stopped being a floor dome and became a solid orange **ball** on each soul instead: the play launcher sets `rt_translucent_minalpha 0.72`, which *floors* translucent sprite alpha under PT, so no `Alpha` value can hide it. Dimming via `emissiveMult` fails too — RTGL1 derives the attached light from emissive coverage, so the cast light dies with it. **They are coupled knobs.** |
| **Light now** | Attached to the `SKUL` fire frames themselves — `lightIntensity` **900**, `emissiveMult` **0.35**, frames **A–F only** (`G0`+ = death/gib), **no `noShadow`**. The pk3 is sprites-only now: no ZSCRIPT, no MAPINFO, no extra actor. |
| **Confirm** | `tools\launch-retribution-rt.cmd 5` — souls float at head height, flame casts warm light on nearby walls, no ball. Tune with `SKUL_LIGHT`. |

> **Shared-tree hazard:** the global `rt/data/textures.json` lives in the gitignored build tree and is rewritten by *every* generator. A concurrent session clobbered the Lost Soul entry once during this fix (18:17 overwrote a 14:23 run), silently restoring old values and making a correct fix look broken. Re-check the live entry before concluding a lighting change did nothing.

**General rule:** any pk3 `sprites/` replacement generated through PIL must re-apply `grAb`, or it renders at the wrong height.

### 1.6 MAP02 yellow door + dark absorb room — **ENGINE FIX 2026-08-04** (needs confirm)

**Blue armor room follow-up (2026-08-07):** Retribution's MAP02 blue-room sectors use `lightcolor = 20735` (`0x0050FF`). The RT compatibility path intentionally whitened world vertex RGB to prevent yellow-door wash and black lightlevel-0 rooms, which also removed this room-wide blue filter. The engine now carries `FColormap.LightColor` into RT primitive state and restores a bounded blue surface tint only for the `map02` `0x0050FF` profile. It does not add a center light or affect other maps/sectors. Rebuild and visually confirm against `screen/level2-blueroom.png`.

| | |
|---|---|
| **Yellow door** | `SDOOR6` on sectors with `lightcolor` yellow + high `lightlevel` — not RT `_e`. Sector tint baked into vertex color → neon wash. |
| **Dark room** | Secs **35/40**: `SFLATAQ` ceil + `SPACECN` walls, `lightlevel` 0/10. Lamp blobs `_e` with `emissiveMult=0` (primary only); walls got **black** vertex color → flashlight/ceiling lamps absorbed. |
| **Fix** | `rt_main.cpp`: under `rt_mod_compat`, world prims upload **white RGB**. First pass only hit `ExportMap`; **doors are movable → not ExportMap** — extended to all non-sprite world (2026-08-04 eve). Rebuild gzdoom. |
| **Confirm** | `launch-retribution-rt.cmd 2`: yellow/red **key doors** not neon. Dark room: walls lit by flashlight/ceiling lamps. |
| **Sprites** | World fix left enemies + weapon black (`level2blackroomsprites.png`) — sprite path still multiplied sector lightlevel into albedo. **2026-08-05:** `ExportInstance` / FirstPerson keep `uObjectColor`, drop `uVertexColor` RGB. Rebuild gzdoom. |

### 1.6b MAP02 freeze at red-key approach — **FIX WAD 2026-08-05** (needs confirm)

| | |
|---|---|
| **Symptom** | Window freezes (audio still plays) when entering the red-key door approach on MAP02. |
| **Cause** | Same as MAP01: `Sector_Set3dFloor` (special **160**) — two linedefs, control sectors tag 1/2 with `F_SKY1`. RT live-upload hang when that geometry is in play. |
| **Fix** | Combined `d64r-3dfloor-rtfix.wad` strips special 160 on **all 28 maps** that had it (161 linedefs). Keeps `BEHAVIOR`/`ZNODES`. Regen: `python tools/make_map_3dfloor_rtfix.py`. |
| **Confirm** | `tools\launch-retribution-rt.cmd 2`, walk to red-key door room — should stay responsive. Outdoor 3D-floor prop may be missing until engine fix. |

### 1.6e MAP02 fake mid-ceiling blink blobs — **ENGINE FIX 2026-08-05** (needs confirm)

| | |
|---|---|
| **Symptom** | `screen/level2fakeceilinglights.png` — blinking white patches in empty mid-ceiling (circled); real fixtures are only edge inset blobs. |
| **Cause** | `RT_UploadCeilingInsetLamps` placed one analytic sphere at every `SFLATAQ`/`SFLATAS` **sector center**. Fine for MAP01 ~96×96 booths; large halls get a fake center lamp. |
| **Fix** | `rt_ceiling_lamp_maxspan` **128** — skip analytics if sector AABB width or height exceeds span. Texture `_e` still lights the real edge blobs. |
| **Confirm** | Mid-ceiling white blinks gone; edge inset lamps remain. A/B: `rt_ceiling_lamp_maxspan 0` restores old behavior. |

| | |
|---|---|
| **Symptom** | `screen/level2floorelementnocastlight.png` — raised `SFLATAQ` floor panels glow but cast nothing. |
| **Cause** | `_e` with `emissiveMult=0` (was ceiling-analytic-only). Floor analytic spheres looked bad — removed. |
| **Fix** | `gen_world_emissives.py`: `SFLATAS`/`SFLATAQ`/`SFLATAP`/`SPORT*` `emissiveMult` **1.0** so INDIR GI casts from blob `_e`. No floor analytic lights. |
| **Confirm** | Dark room panels light nearby walls via texture GI only. |

> **Superseded 2026-08-10 — see 1.6f.** That `emissiveMult 1.0` was only ever safe
> *while the `_e` masks existed*. They were deleted later (generic `SFLAT*` blobs
> spawned false emitters), and the mult was left behind — and then raised to 3.

### 1.6f MAP07 ceiling panel baked white — **DATA FIX 2026-08-10** (needs confirm)

| | |
|---|---|
| **Symptom** | `screen/level7fakelightsnoshadowscast.png` — the `SFLATAS` ceiling panel over the cage reads as a uniform blown-white slab: the tan brick *between* the lamp blobs glows as hard as the blobs. |
| **Cause** | `rt/data/textures.json` still carried `SFLATAS`/`SFLATAQ` `emissiveMult 3`, `SFLATAP` `1`, `SPACEAZ` `3` — with **no `_e.png` mask on disk** for any of them (`gen_world_emissives.py` deletes them, see 1.6e). `RsWorld.inl` falls back to `ldrEmis = ldrColor.rgb` when `emissiveTextureIndex == MATERIAL_NO_TEXTURE`, so the **whole albedo** emits at ×3, clamped to `rt_emis_maxscrcolor 3` on the primary and fed to GI at `rt_emis_mapboost 200`. Not a mask being too bright — a mask that isn't there. |
| **Why it survived** | The names were dropped from the authored allowlist, but the already-written global JSON was never regenerated, and `scrub_array_stale` only walks **scene** arrays, never `rt/data/textures.json`. |
| **Why removal is safe** | These four are exactly the engine's **analytic** lamp set — `RT_IsCeilingEdgeLampFlat` (`SFLATAS`/`SFLATAQ`, `rt_main.cpp:5417`) and `RT_IsWallStripTexture` (`SPACEAZ`/`SFLATAQ`/`SFLATAS`, `:5886`). The launcher runs `rt_ceiling_edge_lamps 1 @ 180` and `rt_wall_strips 1 @ 180`, so the fixtures keep real perimeter lights that cast. The emission was double-counting them. `SFLATAP` is in **neither** engine list (recessed grille, `:5872`) — its glow had no fixture at all. |
| **Fix** | Stripped `emissiveMult` from those four in the live `rt/data/textures.json` (backup `.pre_sflat_emis`). `gen_world_emissives.py` gains `LAMP_FLAT_NO_EMIS` + `strip_lamp_flat_emis()`, applied to the global JSON **unconditionally** — not behind `--no-scrub`, since this regression already shipped once. |
| **Confirm** | Panel resolves into brick + distinct bright blobs; room still lit from the panel perimeter. If it now reads dead, the answer is `rt_ceiling_edge_intensity` / `rt_wall_strip_intensity` above 180 — **not** putting the mult back. |
| **Not addressed** | 411 further `emissiveMult>0` entries have no `_e` mask, so they self-emit whole-albedo too. Most are sprites where that is intended (`FIRE*`, `TFOG*`, `BFLM*` — they pair it with `lightIntensity`). The suspicious ones are the flat-mult-1 world panels: `SMONF*`, `SMONLB*`. Unreviewed. |

> **Half-superseded 2026-08-10 — see 1.6g.** The unmasked-emission diagnosis stands.
> Stripping the mult and stopping there did not: it left the bulbs emitting nothing,
> and the "keeps real perimeter lights that cast" assurance does not hold for a tiled
> bulb lattice. `SFLATAP` stays stripped.

### 1.6g Bulb arrays dead after 1.6f — **DATA FIX 2026-08-10** (needs confirm)

| | |
|---|---|
| **Symptom** | Reported against `SFLATAS` (the 2×2 bulb ceiling): "doesn't emit light anymore, or ever so faintly." |
| **Cause A — no glow** | Two edits stacked. `e0fe5ef` deleted `SFLATAS_e.png`/`SFLATAQ_e.png`/`SFLATAP_e.png` as collateral in a generic `SFLAT*` blob cleanup — the only files that RR commit touched outside its own work. 1.6f then removed the dangling mult. Correct individually, dead in combination: no mask **and** no mult is zero emission. The deleted masks were *good* — I recovered `SFLATAS_e.png` from `e0fe5ef^` and it is four clean bulbs at (15.5,15.5) (47.5,15.5) (15.5,47.5) (47.5,47.5), 140px each. |
| **Cause B — barely any cast light** | 1.6f's "the fixtures keep real perimeter lights" is wrong for these textures. `RT_IsCeilingInsetLampTexture` (`rt_main.cpp:5775`) routes `SFLATAS`/`SFLATAQ` to the **perimeter walk** — a light every `rt_ceiling_edge_seglen` around the sector's linedefs. The `isFaux` branch immediately above it argues against exactly this: *"the perimeter walk … has no relation to where the art puts its bulbs … perimeter lights land between bulbs, in the middle of blank plate, and read as light coming from nowhere."* SFLATC/SPACECE were given `addLattice` for that reason; the real bulb arrays never were. Every bulb in a panel's interior casts nothing. Compounding it, the launcher pins `rt_ceiling_lamps 0 +rt_ceiling_lamp_intensity 0`, so the centre-sphere path is off too. |
| **Fix (glow)** | `tools/gen_bulb_flat_masks.py` — recovers the `SFLATAS`/`SFLATAQ` masks from `e0fe5ef^`, generates one for `SPACEAZ`, writes all three to `rt/mat`, `rt/mat_dev` and `Retribution-RT-Materials/rt/mat`. Then `set_bulb_emissive.py 30`. `LAMP_FLAT_NO_EMIS` drops to `("SFLATAP",)` and the three names go into `textures_world_emis.json` at mult 30, so `_authored_emis_keep` protects them from the scrubs and a regeneration reproduces the state instead of undoing it. |
| **SPACEAZ needed a new mask** | It has never had an `_e.png` in any commit. `_e_ceiling_blobs_from_albedo`'s absolute threshold (130) cannot make one: SFLATAS/SFLATAQ bulbs are near-white, SPACEAZ's are dull grey — peak luma **184**, socket body at 128, on brick running 96–136. At 130 it selected brick speckle and hit **no** socket (3.1% of pixels lit, scattered). `_bulb_lattice_mask()` works per 16-unit tile relative to that tile's own peak, and paints **full white** rather than sampling the albedo — the shader already multiplies emission by baseColor, so an albedo-sampled mask squares it and dull sockets stay dull. |
| **Despeckled** | The recovered masks carried ~45px of stray single-pixel brick hits each. Invisible at the mult they shipped with (3); at 30 each speck is its own emitter smeared over the brick — a diffuse version of the same bug. `despeckle()` drops components under 12px, wrapping at the edges since flats tile. Final coverage: SFLATAS 13.7%, SFLATAQ 9.4%, SPACEAZ 9.4%. The generator refuses to write any mask over 35%. |
| **Confirm** | Bulbs read as bright fixtures against dark brick, brick itself stays dark. If the *brick* glows, the mask is not being loaded (check `rt/mat_dev/` — developerMode loads PNG from there first). |
| **Still open** | Cause B is unfixed — it needs `SFLATAS`/`SFLATAQ` moved onto `addLattice` with per-tile bulb offsets (SFLATAS `{15.5, 47.5}²`, SFLATAQ a 4×4 at 16-unit spacing) instead of the perimeter walk. That is an engine change and a rebuild. Mult 30 makes the bulbs *look* lit and feeds GI; per §12 emission is collected only on indirect bounces, so **it cannot cast a pool of light or a shadow at any strength**. Do not read a bright panel as this being solved. |

### 1.6c MAP02 yellow door jamb lamps nuclear — **ENGINE FIX 2026-08-05** (needs confirm)

| | |
|---|---|
| **Symptom** | `screen/yellowdoor.png` — doorframe side strips bloom pure white / wash the hall. |
| **Cause** | Retribution stacks **3× PointLight (9800)** per jamb corner (heights 24/64/104), RGB yellow, radius 32. PT uploaded each at `radius × rt_dynlight_intensity` (~1280) and **added** them → ~3840/strip. |
| **Fix** | `rt_dynlight_stack_atten 1` divides by co-located XY count; `rt_dynlight_max 500` hard-caps. Rebuild gzdoom. |
| **Confirm** | `launch-retribution-rt.cmd 2` at yellow key door — soft yellow jamb glow, not white blowout. A/B: `rt_dynlight_stack_atten 0`. |
---

Working for brightmap-validated frames (TROO/TRO2, SARG/SAR2, FATT, CYBR, BSPI, …). **No** eyes for humans (POSS/SPOS/…) or clean HEAD/BOSS/PAIN masks. Auto detect stays **off**.

### 1.6 WashScratch / play tree drift — **PROCESS RISK**

Isolated `build/WashScratch` starts from stock `rt/` and must **re-stage** eyes/world emis each S06. Easy to think eyes/lights are “broken in engine” when only WashScratch is missing overlays. Prefer diagnosing blink/wash on **`launch-retribution-rt.cmd`**.

### 1.7 Phase packaging — **NOT STARTED**

Single overlay pk3 + clean install docs (Phase 5) still pending.

### 1.8 DLSS-RR residual sparkle / salt — **OPEN detail in `rayreconstruction/rr-noise-investigation.md`**

Short status: debug match = unfiltered diffuse direct; ceiling lamps confirmed amplifier; soft fades landed; boiling **reverted**; `rt_rr_temporal` **failed** (ghost) then left a **black world** when Compose still sampled empty DiffTemporary after `AccumulateForRR` was removed — ComposeNoisy is now **raw unfiltered only**. Full-tree PBR suspected — **do not strip**. Detail → **`rayreconstruction/rr-noise-investigation.md`**.

---

## 2. What was tested (high-signal)

| Test | Result | Takeaway |
|---|---|---|
| `rt_emis_mapboost 0` (gallery) | Wash gone | Wash is emissive-GI × mapboost path |
| `rt_sky 0` / yaw sweep | Wash remains | Not sky hole (after gallery winding fix) |
| Nuclear strip all emis meta + quarantine `*_e` | Wash gone | Needs some emission path to appear |
| HitInfo INDIR `_e` kill variant (wash-qa 04) | Wash remained (earlier ladder) | Not only `_e` sample path; albedo×mult else-path / contaminants mattered |
| Prefix scrub only | Insufficient | PLAY@4.25 etc. flooded GI |
| Fullscrub keep allowlist | Partial; wash still reported later | Contaminants + sector lights + mult>1 after clamp all layered |
| `emissiveMult` >1 with Saturate clamp | Mult ignored (effective 1) | Fixed TextureMeta + ASManager; then authored 4.2 washed MAP01 → dialed ~1.0 |
| SMON teal panel glass `_e` | Screens look bad | Reverted; BM LEDs + albedo RGB only |
| `lightIntensity` on wall monitors | Floating orbs | Forbidden for walls; floors (lava) only |
| Sector lights always on (`RT_UploadExportableSectorLights`) | Suspected fake fill | Gated `rt_sector_lights` **false** |
| WashScratch S01→S06 | S06 still had wash; eyes missing until staged | Ladder useful; eyes must be staged into WashScratch |
| Ceiling blob `_e` only | Glow yes; blink/shadow **no** | Confirms need dynlight (or attached light) for cast/blink |
| Global scrub + hygiene gate + QA (2026-08-03) | Orbit delta 0.2 / yaw delta 0.6 @ boost 200 (was ~88) | Gallery wash gone on verified-clean meta; see §1.2 |

---

## 3. What currently works (do not regress)

- Retribution loads on patched `gzdoom-rt` (`RT_MapName`, Steam soft gates).
- Native RT + DLSS-RR launchers; keep normal/height strength ≈ **1**.
- Enemy eyes: brightmap `_e`, `emissiveMult≈2`, red, **no** eye `lightIntensity`, **no** `noShadow` — regen: `gen_enemy_eye_emissives.py`.
- World allowlist emis: SMON/EXIT/CRT/keys/lava/logo + switch ON frames (`SWX*B` / GLDEFS) muted green — `gen_world_emissives.py`.
- Monster muzzle frames: `lightIntensity` via `gen_fx_emissives.py` (not Lost Soul).
- MAP01 hangy 3D floor fix wad (TEXTMAP + **BEHAVIOR**); night `SPACE` sky pk3 + `rt_sky 25`.
- Gallery halls: texture / emis / enemy / empty + wash-qa / WashScratch tooling.
- RR path firefly clamp in `CmNoisyCompose` + muzzle soft fade (`rt_mzlflsh_fade`).

---

## 4. Engine / cvar knobs that matter now

| Cvar | Play launcher | Role |
|---|---|---|
| `rt_emis_mapboost` | 200 | INDIR emission scale |
| `rt_emis_maxscrcolor` | 3 | Primary `_e` clamp (12 bleached EXIT) |
| `rt_mod_compat` | 1 | Bit2 brightmap→emis **off** |
| `rt_sector_lights` | **0** | All-sector fake fill — keep off |
| `rt_sector_flicker` | **0** | Off on play — was lighting wall SMON alcoves, not ceiling lamps |
| `rt_ceiling_lamps` | **1** | Blink+cast under `SFLATAS`/`SPORT*` ceilings (spawn head lights) |
| `rt_ceiling_lamp_intensity` | **700** | Peak intensity (soft fade + temporal prefilter) |
| `rt_ceiling_lamp_radius` | **0.10** | Source radius (meters) |
| `rt_ceiling_lamp_off` | **0.12** | Dim floor while “off” — keep light in ReSTIR/RR list |
| `rt_ceiling_lamp_fade` | **8** | Tics to ease on↔off (0 = instant) |
| `rt_ceiling_lamp_debug` | 0 | Cyan markers + console dump of ceiling lamp uploads |
| `rt_hang_lamps` | **1** | Warm cast lights at `LMP1`/`LMP2` hanging tech lamps (MAP04…) |
| `rt_hang_lamp_intensity` | **320** | Per-lamp intensity (dense halls — below ceiling 700) |
| `rt_hang_lamp_radius` | **0.09** | Source radius (meters) |
| `rt_hang_lamp_zofs` | **10** | Drop below SPAWNCEILING origin (map units) |
| `rt_hang_lamp_debug` | 0 | Yellow markers + console dump |
| `rt_translucent_minalpha` | **0.55** | Floor PT alpha for translucent sprites (64Spectre) |
| `rt_dynlight` | 1 | Upload GZDoom FDynamicLight (non-flicker by default) |
| `rt_dynlight_flicker` | **0** | Skip 9802 Flicker lights (wall SMON alcoves) |
| `rt_dynlight_intensity` | **40** | Peak scale for remaining dynlights |
| `rt_dynlight_debug` | 0 | Magenta marker spheres at uploaded GZDoom dynlights |
| `rt_sky` | **25** | Night sky intensity |
| `rt_flsh` | **0** | Toggle horror flashlight (`rt_flsh 1` in console) |
| `rt_flsh_intensity` | **90** | Dim warm beam |
| `rt_flsh_pitch` | **22** | Degrees tip toward ground |
| `rt_flsh_angle` | **42** | Cone width |
| `rt_flsh_color` | ffbe82 | Warm horror tint |
| `rt_flsh_battery` | **1** | On → dying flicker → recharge cycle |
| `rt_flsh_on_secs` / `die` / `off` | 30 / 4 / 5 | Battery phase lengths |
| `rt_flsh_charge` | (readout) | 0..1 for HUD bar |
| `rt_flsh_battstate` | (readout) | 0 off / 1 on / 2 dying / 3 recharge |
| `rt_illum_sens_direct` | **1** | Lighting-change sensitivity (direct) |
| `rt_illum_sens_indirect` | **0.75** | Lighting-change sensitivity (indirect) |
| `rt_illum_sens_spec` | **1** | Lighting-change sensitivity (specular) |
| `rt_mzlflsh_fade` | **5** | Soft fade-out tics after extralight ends (0 = hard cut) |
| `rt_rr_temporal` | **0** | Ghost + black-world hazard — keep off; Compose ignores temporal |

**Console:** `rt_dump_dynlights` — list active FDynamicLight positions / RGB / radius.

### Debug: show light sources?

| Tool | What it shows | Blobs? |
|---|---|---|
| `rt_dynlight_debug 1` | Extra **magenta** RT spheres at every uploaded GZDoom dynlight | **Yes** (engine-side; rebuild required) |
| `rt_dump_dynlights` | Console list of GZDoom lights | No |
| RTGL Dev → **Debug show → Light grid** | Light-grid debug buffer | Grid, not per-light markers |
| RTGL Dev → Diffuse direct / Diffuse indirect | Separates analytic vs GI wash | No |
| Stock “draw all lights as world sprites” | **Does not exist** in RTGL / gzdoom-rt | — |

Open Esc/`~` first so GZDoom releases mouse grab before clicking the RTGL Dev window.

---

## 5. Suggested order to close remaining light bugs

1. **MAP01 spawn A/B on play launcher:** `rt_ceiling_lamp_debug 1` — cyan markers should sit under `SFLATAS` over the zombies; wall SMON should stay quiet (`rt_dynlight_flicker 0`).
2. If no cyan markers: ceiling texture name mismatch — dump names from debug.
3. If markers but weak cast: raise `rt_ceiling_lamp_intensity` / lower `rt_ceiling_lamp_zofs`.
4. A/B: `rt_dynlight_flicker 1` should restore the old wall-terminal blink (wrong target).
5. WashScratch drift: prefer diagnosing on **`launch-retribution-rt.cmd`**.
6. Sky leak mitigated via night `SPACE` + `rt_sky 25`; optional later: find residual geometric aperture if wash returns at higher sky.

---

## 6. Session snapshot (authoring counts)

As of last regen on play tree:

- Enemy eye/fire metas: **143** (`textures_enemy_eyes.json`)
- World emis allowlist: **62** (`textures_world_emis.json`) including **10** `ceiling-blobs` sources
- Ceiling `_e` present: `SFLATAS`, `SPORT1`, … under `rt/mat_dev/`
- Global `rt/data/textures.json`: **669 emis entries = authored keep set exactly** (hygiene-gated; was ~670 incl. 42× PLAY @ 4.25 stock contaminants)
- Follow-up: `FIRELAV*`/`FIREWAL*` world textures now **non-emissive** (fx FIRE prefix leak fixed). If Retribution maps use them, author via world allowlist (lava policy) — check with `discover_world_emissives.py`.

---

*Update this file when an item moves to fixed or a test changes the conclusion. Prefer short factual rows over narrative.*
