# AGENTS.md — Doom 64 Retribution Path Tracing

## Read first

Living project plan (progress, checkboxes, corrections, next steps):

→ **`doom64-retribution-pathtracing-plan.md`**

Engine hardcoding / patch log:

→ **`compat-patches.md`**

Who wrote what we build on (RTGL1, gzdoom-rt, GZDoom, Retribution, Doom 64) — take
attributions from here, never from memory, and update it when a new dependency lands:

→ **`CREDITS.md`**

Material / emissive authoring rules:

→ **`material-authoring-spec.md`**

Hand-labelling every texture's surface class and roughness (the categorisation
gallery, its export format, and the two appliers that consume it):

→ **`docs/plan-metal-labelling.md`** — how to run it and how the JSON is applied

→ **`docs/skill-texture-material-labeller.md`** — how to rebuild the page from
  scratch: image sources, the 16 MB budget, and the decisions worth keeping

Open lighting bugs / test log (wash, blink, ceiling lamps):

→ **`open-issues-rt-lighting.md`**

Water (stylized surface + projected caustics, all cvars, four traps):

→ **`docs/rt-water.md`**

Coagulated blood pools and the poison / sludge art — new flats from reference
images, authored relief on a liquid (which the water wave used to overwrite),
and a FLOW MAP so liquid visibly moves along the veins (the phase-pulse version
was rejected as flicker; the doc says why). Also why WATER IS NOW THE ONLY
LIQUID THAT PROJECTS CAUSTICS, why the new art needs the crest colours retuned
down, and the frame-01 `textures.json` bug this uncovered in all eight liquid
families. **The whole liquid look family is `RT_CVAR_NOARCH` as of 2026-08-25** —
the wave is GLOBAL and the per-liquid relief is the only thing that removes it,
so `rt_blood_relief` / `rt_sludge_relief` were the entire difference between a
coagulated pool and water with red paint on it, held up by one `+exec` of the
pins. **NOARCH alone was not enough** — `FGameConfigFile::ReadCVars` applies every
key in the ini by name and never looks at `CVAR_ARCHIVE`, so un-archiving a cvar
stopped it being written but not being read, and the stale line then survived
every clean exit; `gameconfigfile.cpp` now skips a key whose cvar is not archived
(self-cleaning, and it removed a live stale `rt_clouds_volumetric` nobody knew
about). The look can no longer be carried by a stale `gzdoom-rt2.ini` or lost by
a launch that skips the launcher; the pins are now a restatement, not a source of
truth. `package_release.py` refuses to ship a stale exe, a drifted or orphaned
liquid pin, or an `rt/mat_dev` missing the relief maps, and every level load
prints one `RT liquid:` line into `rt-console.log` naming what the shader got.
**Poison keeps the wave on purpose** — no `rt_nukage_relief`, no `D64N*` `_n`:

→ **`docs/rt-blood-pools.md`**

The moon, and the sky leaks it exposed (`rt_sun_*`, `rt_moon_*`, per-map aim,
`rt_sun_require_sky`, the red/green leak debug, four wrong answers):

→ **`docs/moon-and-sky-leaks.md`**

The sky's clouds — the painted shell deck and the storm it lights (`rt_clouds_*`),
and the ray-marched slab that **replaced it as the shipping path** on every cloud
map (`rt_clouds_volumetric`, `rt_vclouds_*`), plus the hell maps' fire sky built
on top of it (`rt_fireskies_new`, `rt_firesky_*`):

→ **`docs/plan-volumetric-clouds.md`** — the march: why it went in the sky
  cubemap, what it reuses, and §5 for the bug that switched it on for everyone
  without anyone deciding to

→ **`docs/rt-clouds-and-lightning.md`** (the deck, now the fallback),
  **`docs/plan-fire-skies.md`** (the five hell maps)

**The lesson from that §5 is not about clouds.** `rt_clouds_volumetric` is
`CVAR_ARCHIVE` and `rt_firesky.cpp` assigns it at runtime, so quitting on a hell
map archived a value nothing ever reset — and for two releases every machine
here rendered the march on MAP12 while a player with a clean ini got the deck.
**An archived cvar that engine code writes is not a setting, it is a diary, and
whichever session you last quit in becomes everyone's configuration.** Pin it to
its compiled default, or make it `RT_CVAR_NOARCH`. `tools/check_pins.py` now
fails on any that is neither.

Per-map fog (`rt_fog_*`, `RT_FOG_PRESETS`, the two RTGL1 froxel changes it
needed, the near/far ramp, the flashlight, and why MAP26's moon is off):

→ **`docs/rt-fog.md`** — what it is, which maps, how to tune it

→ **`docs/rt-fog-implementation.md`** — the code path end to end, and its four traps

Localised volumetric smoke (`rt_smoke_*`, muzzle smoke as a real medium in the
fog's froxel volume, and why the sim is on the CPU):

→ **`docs/rt-smoke.md`**

Light shafts from **ordinary lamps**, not just the moon (`rt_volume_shaft_*`) —
the froxel pass shadow-tests exactly ONE light, which is why beams only ever
happened outdoors; this hands it a short explicit list of ceiling and solo-bulb
fixtures as well, and why `rt_fog_illum` is **not** the answer even though it
looks like it:

→ **`docs/plan-light-shafts.md`**

Impact sparks and wall debris (`rt_spark_*`) — the hitscan hook in `P_LineAttack`
that *is* a real game hook, the PUFF palette the look comes from, per-material
debris driven by the **texture surface classification**, and four bugs that each
looked like the opposite of what they were (`trace.HitTexture` is not filled in
for walls; a rasterized primitive is fullbright; `.pNext` omitted drops a light
silently; `rt/data/` is not in the lump filesystem):

→ **`docs/rt-impact-fx.md`**

Blood splats that stay on the floor (`rt_gore_*`, why the one-second lifetime
was in the WAD's DECORATE and not in the renderer, the explosion burst, and
per-monster blood colour + the RT material-naming bug that hid it):

→ **`docs/blood-persist.md`**

Console noise (`rt_verbose`, why quiet is the default, and where a new `Printf`
belongs) — read before adding any print to the RT path:

→ **`docs/rt-verbose.md`**

GI bounce depth (`rt_gi_bounces`, `rt_gi_bounce_legacy`, `rt_gi_bounce_shadows`) —
RTGL1 shipped **two bounces, hardcoded and unrolled**, the second of which sampled
**no analytic lights** under the live `rt_shadowrays 2` and was **~2π too bright**
(radiance × 1/pdf with no BRDF or cosine — the "diffuse very red" TODO). Read
before touching anything indirect, and before believing "lights don't bounce":

→ **`docs/rt-gi-bounces.md`** — the finding, the loop, and the `gi-*` ladder

Anything DLSS Ray Reconstruction:

→ **`RAYRECONSTRUCTION.md`** (root — start here, always)

It carries the working rules and the five faults that cost days. The full history is
`docs/rayreconstruction/`; those files are large, so only open one when
`RAYRECONSTRUCTION.md` points you at it. The 2026-08-17 pre-exposure reorder (why RR
was fed the wrong signal, what changed, the A/B) is planned in
`docs/plan-rayreconstruction-secondpass.md` and recorded in `compat-patches.md`; the
NRD-in-RTGL1 fallback, gated on that A/B's verdict, is `docs/plan-nrd-denoiser.md`.

Update those when phases complete or facts change. Do not invent parallel trackers.

## A surface looks wrongly lit — do this first

**If the report names a PLACE ("the cage", "the panel by the door"), get the sector
from the game before theorising — aim at it and type `whatsthat`:**

    whatsthat: sector 150  lightlevel 255  tag 0  middle texture 'C53'
               threshold 220 -> ABOVE: this surface SELF-EMITS
               brightest neighbour: sector 0 at 180  (delta +75)

Identifying a surface by rendering candidate textures and matching the screenshot got
`C921`/`HDOR10` right and `C52`/`C53` wrong, a round trip each. A screenshot carries no
sector index. See `docs/rt-lighting-practices.md` §30.

**Do not skip an element because a fixture is near it.** That test pointed the wrong way
four times out of four — including a `64BigFire` *inside* the MAP12 cages. Under RT the
fire is a real light, so the painted 255 is a second, sourceless copy of it. The strong
signal is the **host**: what the element sits inside, and whether that is darker (§31).

**If it BLINKS, PULSES or SWEEPS, go straight to `rt_lightlevel_watch`.** It prints
every sector whose lightlevel moves, as it moves, needing no texture or tag to aim it:

    .\tools\launch-retribution-rt.cmd 13 -- +rt_lightlevel_watch 1

    rt_lightlevel_watch: sector 126   200 -> 255      <- names the sector outright
    rt_lightlevel_watch: thinker DGlow sector 0 tag=29   (dumped at level load)

Lines appear → a sector is being animated, and you now know which. Nothing appears →
no sector is changing, so it is a light or the denoiser. Either way it is one run.

**A quarter of this game's ACS light calls are invisible to signature scanning.** A call
with computed arguments — `Light_Fade(tag, random(220,255), tics)` — has no literal
argument run in the lump, so `scan_light_specials.py` and `acs_call_signature()` cannot
see it *at all*. Scan the opcode pair instead (`LSPECn` = `3+argc`, special is the next
byte). Game-wide: 147 computed vs 488 literal. This cost most of a day on MAP13 and is
written up in `docs/sequence-light-chains.md` and `rt-lighting-practices.md` §27.

## A surface looks wrongly lit — the static checklist

Most of a day was lost on MAP13 skipping these three steps. In order, before
forming any theory and before touching a texture:

    python tools/scan_light_specials.py 13      # sequence chains + blinks + ACS light calls
    python tools/scan_fake_lightshafts.py 13    # sectors painted bright with no source

Then ask the running game about the actual surface:

    .\tools\launch-retribution-rt.cmd 13 -- +rt_tex_probe CTEL

`rt_tex_probe <prefix>` prints, once a second per texture name: the **file** the
texture came from (so you know whether your replacement wad is winning the load
order at all), the animation **frame** on screen, the **lightlevel in use at
runtime** (not what the map data says), and the **`sector_emis`** the engine is
applying. See `docs/rt-lighting-practices.md` §25.

Three rules that came out of that day, all of them in §24:

- The light animating a sector is very often ACS installed by an `OPEN` script.
  It is invisible in the map geometry — no sector special to find.
- **Do not hand-roll a parser for a project format.** `acs_call_signature()` in
  `make_seqlight_fix.py` defines the ACS encoding; a broken five-line scan
  reported "no ACS on that tag" and sent the work into the texture for three
  rounds.
- A negative from a scanner you just wrote is weaker evidence than what the
  person watching the screen tells you. When they disagree, distrust the tool.

If both scanners come back clean, **widen the test by hand** before suspecting the
texture — `scan_fake_lightshafts.py` only finds sectors that match their
neighbour's flats, so it misses every alcove and door recess:

```python
if lv[i] > threshold and lv[i] - max(lv[n] for n in adj[i]) >= 30: ...
```

On MAP13 that finds 38 candidates where the two scanners find 4. Then triage each
one the way the MAP05 pylons were: **is there anything in the room the light could
be coming from?** A real fixture cannot light a recess and leave its own wall black.

And for the static half, the full survey rather than one map at a time:

    python tools/scan_painted_light.py 13 --entries   # painted brightness + painted colour

It reports what the other two scanners miss — alcoves and door recesses (which never
match their neighbour's flats) and sectors painted a different **colour** from their
room — with a **fixture-distance** column derived from GLDEFS+DECORATE (39 placeable
light-bearing actors), so "is there anything in the room the light could come from"
is a number. Game-wide it finds 1128 candidates.

Repairs go in `tools/make_seqlight_fix.py` — **nine families, one wad** — see
`docs/sequence-light-chains.md`:

| family | what it does |
|---|---|
| `CHAINS` | sequence chains (travelling waves) |
| `BLINKS` | per-sector blink specials |
| `SCRIPTED` | ACS light calls with **literal** args |
| `SCRIPTED_COMPUTED` | ACS light calls with **computed** args — the invisible class |
| `SHAFTS` | sectors painted brighter than their room |
| `TINTS` | sectors painted a different colour from their room |
| `LAMPS` | **adds** — a light thing at a SECTOR centre, keyed on its flat |
| `PANEL_LAMPS` | **adds** — a light thing per WALL PANEL, keyed on its texture |
| `STATIC_ANIMS` | ANIMDEFS animations that paint their own lighting (all disabled) |

To make a fixture cast light, add a light **thing** to the map (`LAMPS` /
`PANEL_LAMPS`); texture metadata cannot do it. **Never strip `Light_Stop`** — it turns
effects off, and removing it leaves them running.

`PANEL_LAMPS` is the wall-monitor family. Retribution lights its animated panels with a
9802 `PointLightFlicker` **8 units off the face**, one per 64×64 tile — in **both** axes,
so a 128-tall band is two stacked panels and gets two lights — placed at the **`_e` mask's
lit centroid** within the tile and coloured to match it. Never texture metadata.
**SMONBA was the one monitor
family in the game with no light of its own** (8 of 78 faces, and those eight are a
neighbouring SMONAA's light at a median 64u against 8u everywhere else), so it read as
animated but dead; it now gets a white flicker, white because its `_e` is neutral
(146,146,146) where SMONAA's is green. **48 lights across 8 maps.** Four traps, all paid
for:

- **Only single-tile-WIDE faces are lit.** 62 of the 78 SMONBA faces are MAP07's clad band
  — 128/192/256-unit runs — and SMONAA's density there would add ~105 flickering lights to
  one map. That is §20 exactly. `max_len` excludes them, as Retribution's own authors did.
- **Front sidedef is the RIGHT of `v1→v2`.** A sector-**centroid** sign test put 25 of 38
  lights inside solid geometry, because a sprawling sector's centroid is not inside it.
  Measured against the mod's 169 authored monitor lights: 157 sit on the right normal (§32).
- **A tall band is a STACK of panels, and the screen is not mid-tile.** One light at 0.50
  of a 128-unit band lands on the seam between two tiles, on bare panelling —
  `screen/pointlightinthemiddlebad.png`. Tile vertically too, and put the light at the
  `_e` centroid: SMONBA's screen is at **0.688**, not 0.5, which is why the six panels the
  mod itself wired sit at 0.625–0.688 while SMONAA's 94 sit at 0.500.
- **A duplicate test must match the axes you tile on.** `min_gap` was 2D, so the second
  light on a tile column read as a duplicate and was dropped — the count stayed at 38 and
  the vertical tiling looked inert.

Derive the per-map counts with `--panels` (never by hand — it found a SMONBA panel on
MAP34 that a MAP01–32 survey missed); retune brightness with `--panel-radii=hi/lo`.

**SMONBA is the game's only `9804` `PointLightFlickerRandom`, and that is deliberate.**
`rt_dynlight_blink_floor` (0.8) is global to every flicker light, so it cannot let one
family swing harder — but Retribution ships 9800/9801/9802 and **no 9804 at all**, so
that class got its own floor, `rt_dynlight_rndflicker_floor` (0.3), which by construction
cannot disturb an existing fixture. 9802 is a *binary* toggle; 9804 holds a *random*
radius for `angle` tics, which at 2 tics is a noise signal — TV static. Two consequences:

- **Peak brightness is at `hi == rt_dynlight_rsoft`, not above it.** Intensity goes as
  `hi` but is rolled off by `(rsoft/hi)²` past `rsoft`, so the product peaks at 20 → 200.
  `hi=32` gives 125. The panels were made brighter by moving their radius **down**.
- The thing's `angle` is a **period, not a bearing**, for 9801/9802/9804 alike.

A/B: `.\tools\ab-smon.cmd <static|statichard|staticcalm|staticoff> [map]` — these vary
only `rt_dynlight_rndflicker_floor`, so every 9802 monitor is identical between them.

## The moon, and sky light that leaks

**Read `docs/moon-and-sky-leaks.md` before touching `rt_sun_*`, `rt_moon_*` or
anything sky.** MAP13's painted shafts were replaced by a real moon: a disc in
the sky texture (`tools/gen_moon_sky.py`) plus `rt_sun`, the directional light,
aimed alike — the disc alone casts nothing usable, because RT's sky cubemap is
not importance-sampled. Aim it with the **`moon`** CCMD, never by setting
`rt_sun_a/b` directly; per-map aim lives in `RT_MOON_PRESETS` (MAP13 = 90).

Three things that will otherwise cost you a day:

- **A shadow ray that hits nothing counts as LIT** (`RtMissShadowCheck.rmiss`).
  Doom maps are not watertight, so the moon washes sealed rooms.
  `rt_sun_require_sky` makes a ray prove it reached sky, and is **on by default**
  (compiled *and* pinned in the launcher — a pin overrides the compiled default,
  so both must agree). `rt_sun_leak_debug 2` paints it: **RED** reached sky,
  **GREEN** escaped — and it composes with the fix, so all-red is the
  confirmation. The regression it can cause is the opposite one: an unclosed
  courtyard now goes dark. `tools/ab-skyleak.cmd noreq` compares against stock.
- **The shafts are a MEDIUM, and its density hangs off `rt_volume_far`.** What
  you see as a shaft is `rt_volume_scatter` being scattered by the directional
  light, and the shader applies that coefficient **per froxel cell** over a grid
  that is 64 slices at any reach — so raising the reach for smoke (`30 → 60`)
  halved the medium and halved the moon with it. Reported as "shafts weak from
  in front, fine looking up at the moon"; the asymmetry is the phase function's
  ~11× forward bias, and it is the confirmation, not a contradiction.
  `rt_volume_scatter` is now normalised per metre in `rt_main.cpp` (fog is not —
  it is tuned in per-cell units). Doc §5.4, arms `tools/arms/moon-*.cfg`.
- **"The shaft stops short of the floor it lights" is NOT a renderer bug — two
  mechanisms were measured and both came back negative.** Don't re-open it
  without reading §5.5 first. The **depth dither** is a real one-sided bias
  (`-sampleHemisphere()` has positive z, so the volume is never sampled deeper
  than the surface, and it is a prefix sum) worth `0.33 × radius ×
  (rt_volume_far/64)` = 1.56 m at the old settings — and 1.56 m is **invisible**
  here: radius 5 and radius 0 look identical. The **phase function** at
  `rt_volume_lassymetry 0.5` does swing 34× along a raking beam, but zeroing it
  is *dimmer, not flatter* — the forward peak is carrying the shaft, so the
  answer is never lower asymmetry. What is left is path length: a ray crossing
  the beam near the floor spends almost no distance inside it. Look knobs only —
  `rt_volume_lintensity` (brighter shaft, no extra haze) or `rt_volume_scatter`.
- **A knob that "does nothing" is TWO hypotheses — too small to see, or never
  reaching the shader — and one absurd value separates them for one launch.**
  `shaft-probe` (`rt_volume_dither_z 40`, a 12.5 m shortfall) killed the shaft
  outright and retired the plumbing explanation after two subtle arms had failed
  to. Build the absurd arm *before* concluding a mechanism is wrong. Same
  philosophy as `rt_smoke_debug 4`. Depth now has its own knob,
  `rt_volume_dither_z` (1), because a one-sided depth filter and a symmetric
  screen one should never have shared `rt_volume_dither`. Doc §5.5, arms
  `tools/arms/shaft-*.cfg`.
- **There is no single visibility choke point.** The visible shafts are
  *volumetric*, and `RtVolumetric.rgen` does **not** call
  `traceDirectIllumination` — it shadow-tests its own light. A fix in the shared
  path leaves them untouched and looks inert.
- **A LAMP shaft seen through a wall is NOT this bug, and `rt_sun_require_sky`
  has no analogue for it.** The sky probe exists because a *directional* ray runs
  to `MAX_RAY_LENGTH` and a miss scores as lit; a lamp's ray **ends at the bulb**
  and cannot escape the map. The occlusion test is already there and already
  right — `RtVolumetric.rgen:283` traces one shadow ray per light per froxel and
  adds nothing without it, back-face culling is off for volume rays
  (`getAdditionalRayFlags()` returns 0 under `LIGHT_SAMPLE_METHOD_VOLUME`), and
  solid geometry is `INSTANCE_MASK_WORLD_0`, which *is* `rayCullMaskWorld_Shadow`.
  What can still carry light forward: `g_volumetric` is a prefix sum read
  **trilinearly**, so up to one slice (`rt_volume_far / 64` = **0.94 m** at
  shipping) of the lit air *behind* a wall bleeds onto it — which makes the
  leak's thickness linear in `rt_volume_far`, and nothing else in the chain
  scales that way. `docs/plan-light-shafts.md` §4d, arms
  **FIXED AND CLOSED, 2026-08-15 — `rt_volume_depthgate`, on and global.** A small
  residual on one wall was knowingly accepted: tightening the footprint max would
  kill froxels a thin foreground edge can still see past, which is worse.
  Not a visibility
  bug: every shadow ray was already correct, and the leak survived
  `rt_cpu_cullmode 2` (whole map in the acceleration structure), so geometry was
  ruled out too. `g_volumetric` is a **prefix sum stored at froxel centres and
  read trilinearly** at the surface's distance, so a wall collects part of the
  cell *behind* it — where the froxel legitimately sees the next room's lamp —
  and `volume_toSamplePosition_T` **clamps z to [0,1]** while slice 0's centre
  sits ~0.47 m out, so any wall you can touch collects slice 0 **wholesale**.
  Hence "worst with my face against the wall". The fix weights each froxel by how
  much of it lies in front of the geometry visible in its own screen column —
  the ask applied at the **froxel**, not the light, which is the only place it
  can work. Sky columns are never gated, so the moon's shafts are untouched;
  density is not gated, so fog extinction is unchanged. Arms
  `.\tools\ab.cmd leak-gatehard|leak-gateoff|leak-gate 01` (`leak-gatehard`
  first — the absurd arm). Diagnostic ladder that got there:
  `leak-noshaft|leak-noamb|leak-near|leak-nofilter`, and **`leak-nofilter` was
  the load-bearing one** — it sets `rt_volume_dither_z 0`, and that one-sided
  toward-the-camera dither had been *hiding* the leak.
- **Aperture-size gating does not work here** and has been measured, twice. See
  §4 of the doc before proposing it again.
- **A leak that MOVES WHEN YOU TURN is not a sky leak at all** — it is geometry
  culling, and no `rt_sun_*` cvar can touch it. gzdoom feeds the tracer from its
  rasterizer BSP walk, so a wall that is not visible, not adjacent to a visible
  sector, and beyond `rt_cpu_nocullradius` (10 m) is simply absent from the
  acceleration structure, and the next room's lamps shine through where it should
  be. `rt_cpu_cullmode` / `rt_cpu_nocullradius`, doc §5.1, arms
  `.\tools\ab.cmd cull-stock|cull-dark|cull-wide|cull-all`.
- **A wall behind you getting culled is fixed with `rt_cpu_nocullradius`, NOT
  `rt_cpu_cullmode 2`.** Mode 0 already submits every visible sector *and every
  neighbour of one*; on top of that `hw_bsp.cpp:988` marks any sector whose lines
  touch a box of `32 × rt_cpu_nocullradius` map units around the camera, visible
  or not. That shell is the guarantee. **Pinned at 20 m** (10 → 20 measurably
  helped); if one map needs much more, that belongs in an `RT_FOG_PRESETS`-style
  per-map table in `rt_presets.cpp`, not a global everyone pays for. Mode 2
  uploads the whole level every frame to fix the same symptom.
- **`rt_cpu_cullmode` has ALWAYS defaulted to 0 — check before believing
  otherwise.** On 2026-08-15 a hand-set `2`, applied once to one map, was still
  sitting in `gzdoom-rt2.ini` (it is `CVAR_ARCHIVE` and nothing pinned it) and was
  remembered as the shipping configuration. It cost most of a session: it sent a
  diagnostic ladder chasing geometry, and its duplicate-primitive spam (~1500
  console lines, RTGL `Scene.cpp`) was reported as a renderer bug. `git log` on
  `rt_cvars.inc` settles this in one command — it is `0` at the initial import and
  `0` at HEAD. **Both `rt_cpu_*` cvars are now pinned** so an arm or a one-off can
  never silently become the configuration again.

## Something casts no shadow

**Reach for `rt_debug_visibility` before building a single A/B arm.** `1` paints the
shadow-ray visibility term — BLACK where the ray was blocked, no radiance involved; `2`
tints shadowed pixels red over normal shading. The final image cannot separate *"the
occluder never blocked the ray"* from *"it did, and the result was drowned in fill light or
smeared by the denoiser"*, and four A/B ladders failed to tell those apart before this
existed.

**But it only started telling the truth on 2026-08-14.** Mode 1 writes into the unfiltered
*direct* buffer, while the final pixel is direct + indirect + volumetrics + exposure +
screen emissive — so unless the Dev window's "Unfiltered diffuse direct" box was ticked you
were reading a composite, and in an emissive-lit room the visibility term is a small
minority of it. It now sets that flag itself. **Treat every "no shadow" conclusion dated
before 2026-08-14 as unsupported**, and validate the view on a known caster before trusting
it on an unknown one (§34a).

**Do not reach for source SIZE on the MAP01 cage fence — that theory is falsified and cost
two sessions.** `screen/noVisibleShadowFence.png` casts nothing under its lamp ceiling
while a flashlight and a muzzle flash cast crisply, which looks exactly like a penumbra
problem (`rt_ceiling_edge_radius` 0.35 = 11.2 map units vs their 0.02 = 0.64). It is not.
On 2026-08-14 the radius was taken to 0.04, the ~100-light lattice was concentrated into
~16 compact lights carrying 100 % of the pane's flux, and `rt_shadow_samples` raised to 4
— **no shadow at any setting**, and concentrating flux that way is itself a noise source.
All of it reverted. The one arm that ever made the fence cast (`ab-bulb-softness pin`) also
raised `rt_ceiling_edge_intensity` 180 → 720, so what it showed was probably **contrast**,
not size.

**Occlusion is confirmed working — stop looking at the geometry** (`screen/debugMod1.png`,
2026-08-14). With the fixed `rt_debug_visibility 1` the buffer resolves the grating's
diamond lattice *and* a humanoid silhouette cleanly, so alpha-tested fence geometry and
sprite proxies both block shadow rays correctly. Whatever is losing the shadow is
downstream of occlusion: shadowless **fill** (`rt_sector_emis` × `rt_emis_mapboost`,
`rt_ceiling_bulb_emis`, indirect GI) or **summation** over the many lattice lights that are
*not* occluded for a given receiver — ReSTIR shades one light per pixel, so the buffer shows
an umbra for the chosen light while the final image sums over all of them.

Beware one number: the "the glow is ~84 % of the room's light" line in
`rt_ceiling_bulb_noemis` was measured at `rt_ceiling_bulb_gain` **1**, before the gain was
calibrated to 7. At shipping values the same lab reads floor 126.8 at emis 0 and 134.7 at
emis 10 — nearer **11 %**. Do not quote the 84 %. Full write-up:
`docs/rt-lighting-practices.md` §34/§34a, `open-issues` §1.6h.

**A count knob can go inert under you.** Seven ladders thinned lamps with
`rt_ceiling_edge_seglen`; the 2026-08-10 bulb lattice took `SFLATAS`/`SFLATAQ` off that
walk and the knob became `rt_ceiling_bulb_spacing`. Nothing errored — the arms still ran
and still printed counts, about a path the fixtures no longer take. **Date every null**,
and when you move where a feature places things, re-point every tool that tuned the old
placement in the same commit (§34b).

Broken-bulb lamp panes (`SFLATAS`), the art change that made the MAP01 cage's grating
cast, and the traps it cost — **a ceiling flat's world Y is `64 − imageY`**, and RT
materials live in **four** directories of which `developerMode` reads `mat_dev` and
every build re-copies the tracked one over the build tree:

→ **`docs/lamp-panes-broken-bulbs.md`**

## Sprites that emit light

`docs/sprite-illumination.md` is the reference: `emissiveMult` is screen glow and
**cannot light anything**; only `lightIntensity` + `lightColorHEX` cast, and an
`_e.png` mask must never sample the albedo.

**Flames are a special case — read `docs/flame-lighting.md` before touching any
torch, fire or candle sprite.** All 84 of them (`TL*` `TS*` `A030` `A031` `A032`
`GTCH` `?FLM` `CAND`) carry `lightIntensity: 0` on purpose and are lit by
`RT_UploadFlameLights()` in `rt_lights_fx.cpp` instead, because texture meta can express
neither the GLDEFS offset up onto the flame nor a flicker. Consequences that bite:
`rt_flame_light_on 0` means those flames cast **nothing** (use
`rt_flame_light_flicker 0` for a steady light), and `CAND` is intentionally a red
light on amber art, so it fails a naive art-vs-light hue audit.

## Workspace layout

| Path | Role |
|---|---|
| `sourcecode/gzdoom-rt/` | **Primary engine** (patched fork; build required) |
| `gzdoom-rt-1.0.2/` | Stock prebuilt — Doom II RT reference only |
| `Doom64-Retribution/` | Retribution v1.5 (+ `D64RTR_v15.WAD` shell-safe copy) |
| `Doom64-Retribution/Retribution-RT-Materials/` | Authored RT overlays (`rt/mat*`, scene JSON) — **shipped in git** |
| `DoomCE/` | Local Doom 64 CE Full (gitignored) — PBR source only |
| `Doom64-Retribution/Retribution-RT-Materials-CE/` | Converted CE→RT `_n`/`_orm` (gitignored; regenerate) |
| `sourcecode/Duke-RT/` | Material-authoring reference (NRI) |
| `sourcecode/prboom-plus-rt/` | Secondary RTGL1 reference |
| `tools/` | Helper scripts + gallery packs |
| `retribution-asset-inventory.md` | Phase 1 inventory |

## RT renderer source layout — `sourcecode/gzdoom-rt/src/common/rendering/rt/`

**`rt_main.cpp` is no longer the whole renderer.** It was 15,072 lines and every
feature lived in it; as of branch **`fileSplit`** it is 2,967 and the features are
in their own files. Go straight to the one that owns your change — do not add new
feature code to `rt_main.cpp`.

| File | Owns |
|---|---|
| `rt_main.cpp` | Frame loop (`RT_BeginFrame` / `RT_DrawFrame`), `Win32RTVideo`, upscaler + DLSS/FSR cvar mapping, `whatsthat`, `rt_dump_*` |
| `rt_lights_sector.cpp` | Sector lights, gzdoom dynlights (`RT_UploadGzDoomDynamicLights` — pitfalls 22/27/28), lightlevel watch, `rt_sector_emis` threshold |
| `rt_lights_fixtures.cpp` | Lamps inferred from a TEXTURE: ceiling inset, wall strip, ceiling edge, spin panel, solo bulb, hanging tech, hand glow |
| `rt_lights_fx.cpp` | Switches, lava, flames (`RT_UploadFlameLights` — see `docs/flame-lighting.md`) |
| `rt_light_shafts.cpp` | Which fixtures get visible air around them (`rt_volume_shaft_*`). Places no lights of its own: the fixture walks OFFER theirs and this culls/sorts/dedupes/caps the list handed to RTGL1 (`docs/plan-light-shafts.md`) |
| `rt_dust.cpp` | Dust motes (`rt_dust_*`) — the sparkle half of a light shaft. Real traced geometry lit by the scene, on a hashed world lattice with no pool and no state (`docs/plan-light-shafts.md` §4c) |
| `rt_smoke.cpp` | Puff simulation + all six smoke sources: weapons, monster guns (`RT_MONSTER_GUNS`), projectiles (`RT_PROJECTILE_SMOKE`), barrels, flames (`RT_AMBIENT_FLAMES`) + `smoke` CCMD (`docs/rt-smoke.md`) |
| `rt_sparks.cpp` | Impact sparks (`rt_spark_*`): the pool, the 3-tier collision, the batched quads and the per-impact flash + `sparks` CCMD. **The one FX source with a real game hook** — `P_LineAttack` in `p_map.cpp` (`docs/plan-impact-fx.md`) |
| `rt_presets.cpp` | Per-map moon / cloud / tint / fog tables + `moon`, `clouds`, `fog` CCMDs |
| `rt_weather.cpp` | The storm + `thunder` |
| `rt_draw.cpp` | `RTRenderState::InternalDraw` — the funnel every primitive passes through |
| `rt_weapon.cpp` | Flashlight, muzzle flash, gun glow (`rt_mzlflsh*`, `rt_gunglow`) |
| `rt_export.cpp` | Static-scene exportability predicates (public face is `rt_helpers.h`) |
| `rt_titles.cpp` | Title cards, fullscreen images, fluid spawn |
| `rt_renderstate.h` | `RTFrameBuffer` + `RTRenderState` declarations |
| `rt_buffers.h` | Vertex / index / texture buffer classes |
| `rt_internal.h` | Shared internals in `namespace rtx` — `RG_CHECK`, `ONEGAMEUNIT_IN_METERS`, `RT_SectorHue`, colour helpers, the light-ID bases |
| `rt_cvars.inc` | **All 451 cvars.** Add one here and nowhere else |

**Adding a cvar:** one line in `rt_cvars.inc`. It is an X-macro list included
twice — `rt_cvars.h` expands it to externs, `rt_cvars.cpp` to definitions — so a
declaration cannot drift from its definition. Put nothing in that file except an
`RT_CVAR*` invocation or a comment; both faces have to swallow every line.

**Adding a file:** register it in `src/CMakeLists.txt` under `RT_SOURCES`, include
`rt_internal.h`, and say `using namespace rtx;` once at the top.

## Hard rules

- **The renderer never writes the player** — no pitch, position, velocity or flag edits from the RT side, not even for a capture. Camera placement for screenshots is done with playsim commands from the launch line or a console script (`noclip`, `fly`, `warp`, bound `+lookup`). Two `rt_autoshot_*` holds that did this shipped in v0.1.14 and broke play (`map map23` dropped the player from the ceiling, rockets flew 45° up).
- Engine work is in `sourcecode/gzdoom-rt`. Prebuilt release is not mod-safe (Steam gates + `rt/scenes/map##` name collision).
- Retribution loads as `-file` on DOOM2.WAD. Prefer `D64RTR_v15.WAD` in PowerShell (`[v1.5]` is a wildcard).
- Prefer IWAD `D:\Games\GZDoom\doom2.wad` (Steam size 14604584). Avoid `D:\Games\Doom RT\DOOM2.WAD` (different size).
- Keep RT materials in `Retribution-RT-Materials/` (or a pk3 overlay) — never edit Retribution originals in place.
- Runtime mats the engine reads live under `sourcecode/gzdoom-rt/build/RelWithDebInfo/rt/` (gitignored). After regenerating, sync into that tree **and** `Retribution-RT-Materials/` when committing.
- **`rt/data/textures.json` is part of that sync, and for a year it was not.** The authored
  global meta is ~236 KB; the stock gzdoom-rt package ships a 30 KB one. Because the live
  build tree is gitignored, a fresh clone silently got the **stock** file plus 427 missing
  `_e` masks — every world emissive fell back to defaults and ceiling lamps read as
  overbright. Nothing errors; the meta simply has fewer entries. After any generator run,
  check `git status Doom64-Retribution/Retribution-RT-Materials/` is not empty.
- Log engine patches in `compat-patches.md`. Update plan Status when phases move.
- Phase 3 (`material-authoring-spec.md`) gates bulk Phase 4 authoring.

## Launchers (start here)

| Script | Purpose |
|---|---|
| `tools/launch-retribution-rt.cmd` | Play — native RT + DLSS-RR. Optional arg `1`–`32` → `map01`…`map32` (default 1). Loads `d64r-lostsoul-rt.pk3` + the map overlays (`d64r-seqlight-fix.wad`, `d64r-smonf-lights.wad`, …). **3D floors are played as authored** — the old `d64r-3dfloor-rtfix.wad` strip is gone (2026-08-23): the freeze behind it was `P_GetPlaneLight` on an empty lightlist, fixed in `p_3dfloors.cpp`; every map-replacing overlay applies `make_map_3dfloor_rtfix.MODE3D = keep`. Never bring the strip back as a workaround; `--mode strip` exists only as an emergency arm. |
| `tools/launch-enemy-gallery-rt.cmd` | MAP98 dark no-aggro enemy eye review hall. |
| `tools/launch-texture-gallery-rt.cmd` | MAP99 texture PBR gallery (baseline mats). |
| `tools/launch-emis-gallery.cmd` | MAP99 **world-emissives only** (`d64remis.wad` — monitors/EXIT/keys/CRT/lava). |
| `tools/wash-scratch/00-RUN-ORDER.cmd` | **From-scratch wash ladder** (isolated `build/WashScratch`; play build untouched). |
| `tools/launch-texture-gallery-ce-pbr.cmd` | Same MAP99 with DoomCE Substance PBR overlay (A/B). |
| `tools/test_gallery_emis_qa.cmd` | Auto QA: emis hygiene + 8-yaw wash score (pass/fail). |
| `tools/ab-fog.cmd` | Illuminated fog A/B, default MAP26. Profiles `full`/`ramp`/`veil`/`ramp2`/`wall`/`deep`/`even`/`flatramp`/`inverse`/`twotone`; flashlight `flsh`/`flshraw`/`flshwide`; isolation `off`/`nolight`/`flat`/`ambient`/`grey`/`thin`/`dense`/`reach20`/`reach90`/`moon`/`debug`. See `docs/rt-fog.md`. |
| `tools/ab-water.cmd` | Water A/B: `stock`/`styl`/`flat`/`mirror`/`noglow`/`nocaus`/`debug`, default MAP10. Flats are tagged engine-side (`l_waterflag`), no setup needed. See `docs/rt-water.md`. |
| `tools/smoke-lab.cmd` | **Smoke lab — MAP97 dark / MAP96 bright beige** — unattended capture of muzzle smoke in a controlled room (`python tools/build_smoke_lab.py` first). `tools/smoke-sweep.cmd <cvar> <values...>` walks one cvar at a fixed tic; `python tools/smoke_gallery.py` renders named candidate looks into one labelled PNG. Judge smoke here, never in a real level — and colour/visibility questions belong on MAP96. |
| `tools/ab.cmd smoke-<arm>` | Volumetric smoke A/B (arms are cfgs in `tools/arms/`, NOT command-line strings). `smoke-full`/`fat`/`thin`/`still`/`drift`/`walk`/`glued`; monsters `smoke-monster`/`nomonster`; sources `smoke-flames`/`noflames`/`proj`/`barrel`/`crowd`; look `smoke-stylize0`; traps `nearfade`/`blendslow`/`blendraw`; resolution `reach30`/`reach8`; isolation `off`/`nolight`/`debug`; and `fogsafe`/`fogsmoke`, the fog regression. See `docs/rt-smoke.md`. |
| `tools/ab.cmd lampshaft-<arm>` | Light shafts from ordinary lamps. `lampshaft-fat` (**run first** — the absurd arm that separates plumbing from values), `lampshaft-off`/`on`; probes `probe` (uniform arriving), `lit`/`vis` (reach vs occlusion); families `inset`/`lattice`/`solo`; **reach** `noband`/`wide`/`listorder`/`phys`/`flat` — the two "doesn't reach far enough" reports, and neither cause was brightness (§4a/§4b); `nogap`, `nomoon`, `dense`/`bright` (medium vs light — judge separately), `iso`, `near0`. Ships **on**; judge in a dark interior, MAP07's clad corridors. See `docs/plan-light-shafts.md`. |
| `tools/ab.cmd leak-<arm>` | **A lamp shaft read through a wall** (MAP01, 2026-08-15, open). All arms hold the report's conditions: moon off (`rt_sun 0` + `rt_sun_intensity 0` + **`rt_moon_presets 0`**, which is load-bearing — presets restore the sun on every level load) and `rt_volume_shaft_mult 200`. **FIXED** by `rt_volume_depthgate` (ships on): the volume is a prefix sum read trilinearly, so a wall collected the froxel *behind* it. `leak-gatehard` (**run first**, the absurd arm — feather 0.01 + taps 1 should paint the grid and stair-step every silhouette) / `leak-gateoff` (before) / `leak-gate` (after). Diagnostic ladder kept: `leak-base` (reference), `leak-noshaft`, `leak-noamb`, `leak-near`, `leak-fat`, `leak-fine`, `leak-nofilter`. **Not** a visibility bug and **not** geometry — both measured out. See `docs/plan-light-shafts.md` §4d. |
| `tools/ab.cmd dust-<arm>` | Dust motes in the air. `dust-fat` (**run first** — a mote is small enough that "I can't see any" has two causes that look identical), `dust-off`/`on`/`heavy`/`still`/`honest`/`noshaft`. Real traced geometry lit by the scene: **never** emissive (fireflies) and **never** rasterized (fullbright). Ships **on**. See `docs/plan-light-shafts.md` §4c. |
| `tools/ab.cmd spark-<arm>` | Impact spark A/B: `spark-fat` (**run first** — the absurd arm that separates plumbing from values), `spark-on`/`off`, `nolight` (how much is the traced flash), `nogrid` (the before for the pixel look — judge while moving), `nocollide`, `still` (bounce with the fall taken out), `debug`. **LIQUIDS:** `spark-fluidfat` (**run first**), `spark-fluid`/`nofluid`, `spark-fluidtex` (crest colour vs the flat's average -- the colour A/B), `spark-puff` (splash AND the vanilla puff). Ships **on** (the old "ships off" note was stale). Judge sparks in the smoke lab (MAP97 dark, MAP96 bright) and liquids on **MAP34, the fluid sampler** -- lava is the control there, it must still puff and throw nothing. See `docs/rt-impact-fx.md`. |
| `tools/ab.cmd gi-<arm>` | GI bounce depth ladder, in order: `gi-shadow2`/`3`/**`4`** (zero shader involvement — `rt_shadowrays` is which bounce *vertices* may sample lights, and `shadow4` is the control that must equal `shadow3`), `gi-depth1` (plumbing liveness), `gi-fix` (the ~2π energy fix at depth 2 — expect **dimmer, less saturated**), `gi-fix3`/`gi-fix4` vs `gi-fix3-unlit` (real depth, only meaningful with the fix on), `gi-restirm` (the reuse-contract check). Judge on `rt_debug_show 16`/`128`, never the final image. Ships unchanged: depth 2, legacy weight on. See `docs/rt-gi-bounces.md`. |
| `tools/ab-bloodpool.cmd` | Blood POOL A/B (the flats, not the splats): `on`/`off`/`norelief`/`noflow`/`fast`/`slow`/`hard`/`soft`/`coarse`/`fine`/`phase`/`flagcheck`/`flat`/`caustics`, default MAP17. Every arm sets `rt_blood_autogoto 1`, which puts the player ON a pool — a pool is a puddle in a corner and MAP08's nine sit at z −256 in pits. Three layers fail identically: the ART (`d64r-liquid-art.wad`, no cvar), the RELIEF (`rt_blood_relief`) and the FLOW (`rt_blood_flow*`, a flow map -- texture advected along the baked vein direction, not a brightness pulse); `phase` and `flagcheck` are tests, not looks. See `docs/rt-blood-pools.md`. |
| `tools/ab-sludge.cmd` | Sludge / MUD bed A/B: `on`/`off`/`norelief`/`mirror`/`deep`/`flat`/`wet`/`dry`/`flagcheck`/`caustics`, default MAP12. **Only MAP12 (6 sectors) and MAP34 have sludge floors in the whole game**, so every arm sets `rt_sludge_autogoto 1`. Two things make mud out of a water surface and each alone still reads as liquid: the RELIEF (`rt_sludge_relief` — height from the art's full luminance range, NOT the vein mask blood uses, which sludge saturates) and the REFLECTION (`rt_sludge_refl`/`rt_sludge_rough` — a mirror is what sells water). `mirror` and `norelief` isolate the two. Also carries the BISECT arms (`nomaps`/`softnormal`/`normals`/`raw`/`denoised`/`nodlss`/`restir`) that found the "unstable shadows under a moving flashlight" bug: NOT parallax, NOT the upscaler, NOT the bake's frequency content — the CHECKERBOARD SPLIT. The stylized branch shades the lit liquid on odd screen columns and rebuilds the even ones from their neighbours; on a high-contrast authored normal that pattern crawls with the camera and freezes at rest. Fix: `rt_*_refl 0` = no mirror AND no split (full-res surface, glossy specular sheen); sludge ships so. `rt_liquid_checkerboard 0` forces it for all four liquids — console only, kept OUT of the Quality menu because what it trades away is the reflection that sells water. `split` is the before-picture. See `docs/rt-blood-pools.md`. |
| `tools/ab-blood.cmd` | Persistent blood A/B: `off`/`on`/`uncapped`/`tight`/`plain`/`wild`/`roll`; explosion splash `boom`/`noboom`/`bigboom`; per-monster colour `color`/`nocolor` (try MAP03 or MAP14), default MAP01. The lifetime is DECORATE in the WAD, not a renderer setting; explosive kills leave no blood in stock GZDoom because `P_RadiusAttack` never calls `P_SpawnBlood`; and blood colour needs `rt_tex_translations` (pitfall 30). See `docs/blood-persist.md`. |

Important cvars on Retribution launch (do not crank blindly):

- `+rt_upscale_dlss 2 +rt_rayreconstr 0` — DLSS upscaling with the **A-SVGF** denoiser, the
  shipping path. DLSS-RR is **alpha here and does not render well**: it is wired up and
  pinned **off** (`rt_rayreconstr 0`), and `RAYRECONSTRUCTION.md` is an experiment log, not
  a recommendation. Do not turn it on and treat what you see as the intended image.
- `+rt_normalmap_stren 1 +rt_heightmap_stren 1` — **keep near 1**; 10+ makes RR struggle
- `rt_verbose` — **0 by default, and that is the release setting.** RT/RTGL1 diagnostics (boot timings, denoiser path, ReSTIR, `D64RtSkyFix:`, `RT water:`/`RT lava:` tagging) then carry `PRINT_NONOTIFY`: still in the console and `rt-console.log`, just not painted over the game. Set it to 1 to get them back on screen. Do **not** reach for `con_notifylines 0` — that takes pickups and level names with it. Full reference, including where a new `Printf` belongs: **`docs/rt-verbose.md`**.
- Flashlight: `rt_flsh 0` / `1` in console, or the **`rt_flsh_toggle`** CCMD the key is bound to — never `toggle rt_flsh`, which prints `"rt_flsh" = "true"` on screen every press (default **F** via `d64r-rt-flashlight.pk3` KEYCONF). Horror defaults: dim warm beam tipped to ground (`rt_flsh_pitch`), battery cycle (`rt_flsh_battery`) with HUD **left of HEALTH** on ForceScaled 320×240 (`BATTERY` + muted cased 5-cell bar) from `d64r-rt-flashlight.pk3`.
- RR / denoise live A/B: RTGL Dev window → **RR / Denoise live** (RR on/off, temporal prefilter, sensitivity presets). Switch ON emis: LED chroma masks via `gen_world_emissives.py` (missing BMTX brightmaps).
- Dev UI: **UI font scale** + full settings persist (`rt/devmode_settings.json`, `rt/imgui.ini`). **Materials A/B**: strip normals / ORM / height / emissives separately (RR walk-noise diagnosis). Reset button if Override sticks bad.
- ORM metal fog (RR walk noise): `deps\orm-vlm\venv\Scripts\python.exe tools\fix_orm_metallic_ai.py` (MAP01 default; `--all` for full set; `--model` for a larger VLM on 32GB).
- RTGL1 Dev window cursor: open Esc/`~` first so GZDoom releases mouse grab

## Enemy eyes / Lost Soul (Phase 4 — current state)

### Eyes — `tools/gen_enemy_eye_emissives.py`

- **Brightmap-only** masks from `D64RTR_BRIGHTMAPS.PK3` (`bd64/`), validated compact/head.
- **`AUTO_EYES = False`** — auto red-pixel detect painted armor/blood/pinky backs; do not re-enable without QA.
- Clones: `TROO→TRO2`, `SARG→SAR2` for matching frames.
- Skip rear (`*5`) and death/gib (`H+`) frames.
- Meta: `"emissiveMult": 2`, color `(255,10,0)` / `ff0a00`. **No `lightIntensity`** (eyes must not lantern). **No `noShadow`** (that killed enemy shadows).
- Humans (`POSS`/`SPOS`/…) have **no** eye `_e` (no good brightmaps).
- Caco/Baron/Pain/etc. currently **no** eyes (no clean brightmaps) — add carefully later if wanted.
- After regen, engine tree + `Retribution-RT-Materials` are updated; global `rt/data/textures.json` is patched in the **build** tree (gitignored) — re-run generator after a clean build checkout.

Clear all enemy `_e` + strip meta: `python tools/clear_enemy_eye_emissives.py` then regen.

**That script had three defects, all fixed 2026-08-15 — read before trusting it.**
(1) It **could not run at all**: `ROOT = PROJ_ROOT` executed before `PROJ_ROOT` was
defined, so it died on `NameError`. `ast.parse` passes on that, which is why nothing
caught it. (2) It swept **every** `*_e.png` with a `MONSTER_PREFIXES` name, despite being
named for eyes — that deleted all 79 `BOSS*`/`BOS2*_e.png`, which are the Baron's and
Hell Knight's **hand fire** (~2 % coverage across the upper body), while leaving their
`"emissiveMult": 4.0` behind. RTGL falls back to `emission = albedo * emissiveMult` when a
material has no `_e`, so both monsters rendered at **4× their own albedo**
(`screen/baronHellBright.png`). There is now a `NON_EYE_PREFIXES` keep-list
(`BOSS`/`BOS2`/`SKUL`). (3) It stripped meta from the **build tree only**, and it blanked
the eye overlay instead of filtering it.

**A generator that writes only the build copy of `rt/data/textures.json` is undone by the
next build**, because `build-gzdoom-rt.cmd` xcopies `Retribution-RT-Materials/rt` over it —
silently, with the file it wrote still looking correct until then. `patch_global()` now
writes **both** trees; that is the same hard rule as the `textures.json` sync note above,
enforced at the one place that writes it.

### Lost Soul — `tools/pack_lostsoul_rt.py` → `d64r-lostsoul-rt.pk3`

- **Do not replace** the `64LostSoul` actor (stock BRIGHT/SoulTrans stays).
- Pk3 = yellow/orange **SKUL sprite replacements** only. No ZSCRIPT, no MAPINFO, no extra actor.
- **Sprite replacements MUST carry the original `grAb` offset** (`png_set_grab()`). PIL drops ancillary PNG chunks, so a plain `Image.save()` loses it; GZDoom then falls back to a zero offset and the sprite hangs *below* the actor origin. This is what buried every Lost Soul in the floor (fixed 2026-08-08) — it was the yellow-tinting pass, not the light work. The packer warns loudly if any lump has no `grAb`. Same trap applies to **any** pk3 `sprites/` replacement.
- **The light rides on the SKUL fire frames themselves** — `SKUL_LIGHT` (**450**) + `SKUL_EMIS` (0.35) + `lightColorHEX ff9028` + `lightEvenOnDynamic`, frames **A–F only** (`G0`+ is death/gib; a corpse must not light the room), i.e. 30 lit frames of 56. **No `noShadow`.**
- **`pack_lostsoul_rt.py` is the SOLE owner of the SKUL material meta, and that had to be enforced in code.** `gen_enemy_eye_emissives.py` also wrote SKUL entries, from its own `SKUL_EMIS 0.12` / `SKUL_LIGHT 0` — and since `meta_for()` guards the light behind `if SKUL_LIGHT > 0`, a zero did not *dim* the light, it **omitted the field**. Running the eye generator after the packer therefore replaced `0.35` + a 450 light with `0.12` + nothing, and the Lost Souls stopped casting shadows. Measured 2026-08-15: 56 SKUL entries, **0** with `lightIntensity`. The eye generator now writes the SKUL fire **mask** and no meta; its `SKUL_*` constants are marked superseded. Same one-owner rule as the `gen_fx_emissives` PREFIX_RULES warning below.
- `lightIntensity` and `emissiveMult` are **coupled**, not independent: RTGL1 derives the attached light from emissive coverage, so dimming the emissive to hide a glow also kills the cast light. Tune `SKUL_LIGHT` first.
- **`LSGL` carrier blob: removed 2026-08-08, do not reintroduce.** A separate disc actor holding the light cannot be hidden under RT — the play launcher's `rt_translucent_minalpha 0.72` *floors* translucent sprite alpha, so the disc renders near-opaque at any `Alpha` and reads as a solid orange ball on every soul.
- The old "attached light on the same sprite white-blooms the fire" note came from `gen_fx_emissives` PREFIX_RULES applying `lightIntensity 700` **plus `noShadow`** — `noShadow` is the part that blows out.
- Wired into both Retribution and enemy-gallery launchers.
- **Do not** put `SKUL*` back into `gen_fx_emissives.py` PREFIX_RULES (that re-adds `lightIntensity`/`noShadow` and undoes this).

### Monster muzzle flash — `tools/gen_fx_emissives.py`

- Player muzzle = engine `RT_AddMuzzleFlash` from weapon `A_Light1`/`A_Light2` (`rt_mzlflsh*`). Monsters never get that.
- Fire frames: `POSSF*` / `SPOSF*` / `CPOSF*` / `PLAYF*` / `SSWVF*` get attached `lightIntensity` + `ff8c52`.
- Weapon HUD flashes (`PISF`/`SHTF`/…): low `emissiveMult` (~0.22) so PT doesn’t bleach white; **no** same-sprite `lightIntensity` (cast = engine `rt_mzlflsh*` / `RT_AddMuzzleFlash`).
- **No `noShadow`** on monster body fire frames. Aim frames (`…E`) stay dark.
- After regen, also re-run `gen_enemy_eye_emissives.py` if FX was run (keeps SKUL/eyes clean).
- Empty-hall A/B: `tools/launch-empty-gallery-rt.cmd` / `wash-qa/09-empty-hall.cmd`.

### World glow (lava / monitors / keys) — `tools/gen_world_emissives.py`

- Classic brightmaps = **masks only** (not PT lights). Pipeline: BM/luma mask → `*_e.png` → INDIR GI.
- **INDIR** = `_e × emissiveMult × mapboost`; primary = raw `_e` × `rt_emis_maxscrcolor`.
- Authored mults (play + gallery): SMON dense panels ≈1.0; sparse green-text `SMON[ACDE]*` ≈2.8; EXIT ≈0.9, keys ≈1.2, lava ≈1.5 (+ `lightIntensity` 140 floors only), teleporter `SPORT*` ≈2.2 cyan (+ floor `lightIntensity` 110). Pre-clamp “4.2” was effectively GI≈1.
- **No `lightIntensity` on wall screens/EXIT** (floating point lamps). No liquid falls / `*GLOW` / OUTTEX / SWX auto-emis.
- Keys: luma mask + **tint** (raw yellow albedo is brown → looked red in GI). No green keycard in Retribution.
- SMON: BM mask + albedo RGB LEDs only (no teal panel fill); clone `_n`/`_orm`/`_h` across ANIMDEFS frames. Sparse green-text `SMON[ACDE]*`: **tight glyph `_e` only** + `emissiveMult` ≈2.8 (no dilate/halo — that turned text into blocks; `terminalgreenbug.png`).

- MAP01 spawn blink: GZDoom `PointLightFlicker` (9802) beside SMONAA — engine uploads `FDynamicLight` (`rt_dynlight`; play launcher uses intensity **35**).
- Writes **engine** `rt/mat` + `rt/mat_dev` + global/`d64rtr_v15_map01` JSON **and** `Retribution-RT-Materials/`. Play uses the engine tree (`launch-retribution-rt.cmd`); other maps use **global** meta.
- Emis-only QA hall: `tools/launch-emis-gallery.cmd` (`d64remis.wad`).
- RTGL must allow `emissiveMult > 1` (`TextureMeta` + `ASManager` — both had `Saturate`; rebuild `tools/build-rtgl.cmd`).
- Launchers: `+rt_mod_compat 1` + `+rt_emis_mapboost 200` + `+rt_emis_maxscrcolor 3`.
- Discover gaps: `python tools/discover_world_emissives.py`.

### Enemy gallery (debug MAP98)

- Build: `python tools/build_enemy_gallery.py` → `d64renemyg.wad` + mapinfo + tour pk3 (15 booths).
- Capture: `tools/review_enemy_gallery_batch.ps1` (PNG dumps gitignored under `tools/_enemy_gallery/`).
- Scene overlay: `rt/data/scenes/d64renemyg_map98/`.
- Sparse captures rewrite the tour pk3 — rebuild full tour (`COUNT = 15`) before interactive launch if you used `-Indices`.

## Useful local paths

- IWAD: `D:\Games\GZDoom\doom2.wad`
- GPU: NVIDIA GeForce RTX 5090
- Build engine: `tools/build-gzdoom-rt.cmd` → `sourcecode/gzdoom-rt/build/RelWithDebInfo/`
- Build RTGL runtime: `tools/build-rtgl.cmd` (needs `rt/bin/RTGL1.dll` + `nvngx_dlssd.dll`)
- NRD lane deps (only after changing NRD shaders or on a fresh checkout without
  the committed artifacts): `tools/build-nrd-deps.cmd` — ShaderMake, NRD
  `_Shaders` SPIR-V headers (needs the GITHUB dxc in `tools/dxc`, the Windows
  SDK dxc has no SPIR-V codegen), NRI static libs. `build-rtgl.cmd` then links
  it all - but ONLY with `D64RT_WITH_NRD=1` set. `RG_WITH_NRD` defaults
  **OFF**: A-SVGF is the shipping baseline and these deps are not in the
  repo, so defaulting ON broke every clean checkout and the CI release.
- **SDKs / deps policy:** install only under `G:\AI\Doom64-RT\deps\` (or other `G:\AI\…`), never system Program Files.
  - Headers: `deps/RTGL` (`vs-shirokii/RTGL`)
  - Runtime: `deps/RTGL-1.6.3`
- Python for tools: `C:\Users\Winter\AppData\Local\Programs\Python\Python313\python.exe` (system `python` may lack Pillow)
- Git branch: `rayreconstruction` → `https://github.com/jlrouzies-fr/doom64-rt.git`

## Known pitfalls (do not repeat)

1. **`noShadow: true` on monster sprite metas** → enemies stop casting shadows. Never put it on whole SKUL/SARG/TROO frames.
2. **`lightIntensity` on eyes** → zombies/imps become lanterns. Surface `_e` + `emissiveMult` only.
3. **Auto eye detect** → false positives on soldiers and pinky backs.
4. **Lost Soul / HUD flash same-sprite attached light** → fire/muzzle bleaches white; keep cast light separate (`rt_mzlflsh*` / LSGL) or off. Do not re-add `SKUL*` to `gen_fx_emissives` PREFIX_RULES; weapon `PISF`/`SHTF`/… use low `emissiveMult` and **no** `lightIntensity`.
5. **Normal/height strength 10+** → RR/denoiser falls apart; launcher uses `1`.
6. Gallery/tour pk3s locked while gzdoom is running (WinError 32) — kill `gzdoom` before rebuild.
7. Engine `rt/mat/textures.json` is **not** the meta source of truth — use `rt/data/textures.json` (+ scene overlays).
8. **`noShadow` on monster fire frames** → same as eyes: kills enemy shadows. Muzzle meta must omit it.
9. **Intermittent noisy PT + blocky HUD** → RTGL1 Dev `drawInfoOvrd` was uninitialized; random Override forced Linear/Nearest + “Downscale to pixelized”. Fixed in `deps/RTGL` (rebuild via `tools/build-rtgl.cmd`). In Dev window keep **Override unchecked**.
10. **Center-directed / yaw wash from emitters** → was `_e` GI ignoring `emissiveMult` (only global mapboost). Fixed in RTGL HitInfo INDIR. Keep stock mapboost; dial per-tex mult. Also: `mod_compat 1` + allowlist (`gen_world_emissives`).
11. **World `_e` PNG only in `rt/mat/` while `developerMode: true`** → PNGs load from **`rt/mat_dev/`**; `mat/` is KTX2-only. Generators must write both.
12. **EXIT/sign wash white** → `rt_emis_maxscrcolor` 12 clips saturated reds. Play + gallery use **maxscrcolor 3**.
13. **Global meta contamination / silent revert** → stock Doom II emis meta (PLAY @ 4.25 etc.) floods GI via `albedo×mult×mapboost`. Scrub now runs **by default** in `gen_world_emissives.py` (`--no-scrub` debug-only); `check_emis_hygiene.py` gates the **global** JSON (strays + dupes, keep set = overlay JSONs); `restore_pre_wash_gallery_emis.py` is hygiene-gated. Never restore `textures.json` backups without a regen + hygiene PASS.
14. **`OUTTEX*` / `SWX*` full-bright** → skip auto-emis; clear stock meta.
15. **`emissiveMult` > 1 was a no-op** → `TextureMeta` **and** `ASManager` both `Saturate`d to [0,1]. Fixed; rebuild `tools/build-rtgl.cmd`. Without both fixes, doubling meta does nothing.
16. **`lightIntensity` on wall monitors/EXIT** → floating point lamps on the face. Floors (lava) only.
17. **Whole-face tinted `_e`** → primary shows raw `_e` as solid cyan/yellow. Tight BM / luma masks only.
18. **Yellow key GI looks red** → albedo carving is brown; use luma mask + yellow tint.
19. **ANIMDEFS sibling frames flat<->bump** (SMON, CTEL, SPORT, STRAK, GTEL, C307B,
    CFACE, HTEL). RTGL1 resolves `_n`/`_h`/`_orm` **per texture NAME**, and an
    animation is a run of separate names -- so maps on frame 1 only make the
    surface parallax-relieved on that frame and flat on the rest. It reads as
    the texture **moving up and down**, not as a missing map, and sends you
    looking at scrollers, lifts and sector specials. `GTEL1` was relieved 4 tics
    in 32; `HTELB`+`HTELC` are 16 of 24.

    **`tools/sync_anim_relief_maps.py --report` sweeps the whole game for it**
    -- it walks ANIMDEFS itself, so nothing has to be guessed or typed. Then
    `sync_anim_relief_maps.py <base...>` clones frame 1's maps across the run
    into all **four** material dirs.

    **The pixel gate alone is not sufficient, and that is the 2026-08-24
    lesson.** A frame may share relief when it differs on <=5% of the tile OR
    when its colour-REGION LAYOUT is byte-identical -- same geometry under some
    recolour. STRAK differs on **19.0%** and is still the same surface: the
    animation is a brightness PULSE of the stripe, nothing moves. And because
    `STRAKY1_h` is luminance-derived, regenerating `_h` per frame would make the
    stripe rise and fall with the pulse -- it would author in the very artefact.
    **Copy; do not regenerate, and do not raise the gate.** A frame that fails
    both gates has different art and needs its own maps via `gen_ai_pbr.py`
    (settings are recorded per texture in `tools/_gallery/ai_pbr_report.json`)
    plus a **scoped** `bake_material_labels_orm.py` run -- that tool has no name
    filter, so handing it `map01.json` re-bakes all 900 labels.
20. **Liquid falls / `*GLOW`** → not auto-emitters.
21. **Post-clamp wash on MAP01** → authored wall mults (4.2) suddenly fully scaled GI; dial walls ~1.0.
22. **Missing spawn blink lamps** → need `RT_UploadGzDoomDynamicLights` for 9802; also disable stock per-sector lights (`rt_sector_lights 0`).
23. **Lingering fake fill / wash** → `RT_UploadExportableSectorLights` ran every frame at intensity 200 per sector even with autoexport off. Default **off** now.
24. **`FIRE` fx prefix swallowing world textures** → `gen_fx_emissives.py` gave `FIRELAVA`/`FIRELAV3` `lightIntensity` 700 + `noShadow`. Fixed via `WORLD_TEX_RE` guard; world fire/lava textures belong to the world allowlist only.
25. **`rt_rr_temporal` / ComposeNoisy DiffTemporary** → ghost duplicate if writer+reader both live; **black world / muzzle-only** if reader lives after `AccumulateForRR` removed. ComposeNoisy is raw-unfiltered only; do not re-wire temporal-into-RR without a matching every-frame writer.
26. **Spectres now rasterized TRANSLUCENT + minalpha floor** — `IsSpectre()` no longer sets FORCE_WATER/GLASS/MIRROR. Instead uses `RG_MESH_PRIMITIVE_TRANSLUCENT` (rasterized overlay) with `rt_translucent_minalpha 0.72` floor. Gives sprite-shaped see-through look. `rt_spectre` cvar deprecated. Rebuild gzdoom after changes.
27. **`rt_dynlight_flicker 0` silently kills every SMON wall monitor light.**
    `RT_UploadGzDoomDynamicLights` skips `FlickerLight`/`RandomFlickerLight` outright when
    this is off, and 9802 `PointLightFlicker` is exactly how Retribution wires its animated
    wall panels — a light **thing** 4–56u off the face, never texture metadata. Measured:
    SMONAA **88/88** wired that way, SMONDA 25/27, SMONCA 19/21, SMONEA 6/6; **199 of the
    205** 9802s in the game sit beside a SMON panel. With the flag off they all vanish
    before upload and the panels show only their `_e` glow — which casts nothing — so they
    read as *animated but dead*. Now `true` (compiled default **and** launcher pin).
    The diagnostic that found it: on MAP29 exactly **one of three** identical-looking
    SMONDA panels lit the room — lines 922/937 are 9802 (skipped), line 927 is a **9801
    PointLightPulse**, which is not a flicker type and was never skipped. When N identical
    fixtures behave differently, compare their **thing types** before touching art or meta.
    A/B: `.\tools\ab-smon.cmd <off|loud|on|calm|steady|dim|marks> [map]`.
28. **Dynlight blink: the roll-off used to fight the blink, and the cap hides both knobs.**
    Turning 199 monitors on exposed two bugs in `RT_UploadGzDoomDynamicLights`.
    (a) The inverse-square roll-off divided by the **instantaneous** flickering radius while
    the blink term multiplied by it, so a 24/20 light had its **crest** divided by
    `(20/24)²` and its trough untouched — and any blink floor above ~0.36 **inverted** the
    pulse. It now rolls off on the fixture's **nominal** radius (`hi`), which is constant
    per light; steady lights are unaffected since `mapRadius == hi` for them.
    (b) `rt_dynlight_intensity` and the new `rt_dynlight_blink_floor` are **coupled through
    `rt_dynlight_max`**: at scale 40 a 24/20 light's raw crest is 960, so the 500 cap clips
    *both* ends for any floor above ~0.52 and the swing flattens to 1.00× — raising the
    floor silently turns the flicker **off** instead of calming it. The scale must come
    under the cap first.
    (c) **`rt_dynlight_intensity` is GLOBAL to every `FDynamicLight` — never use it to tune
    one fixture family.** Dialling it 40→10 to settle the monitors dimmed the **key-door
    lights** and every other 9800 with it; caught in play immediately and rolled back. Use
    **`rt_dynlight_flicker_scale`**, which applies only to Flicker/RandomFlicker — the same
    class `rt_dynlight_flicker` gates, i.e. 199-of-205 SMON panels. Doors are steady
    `PointLight`s and never reach it. Shipped: `intensity 40` (untouched) +
    `flicker_scale 0.25` + `blink_floor 0.8` → monitors **133..167, swing 1.25×**, every
    steady light back at its original value.

29. **An anonymous namespace is why `rt_main.cpp` grew to 15,072 lines — do not
    start another one.** Nearly everything in that file sat inside `namespace { }`:
    the 4,200-line light block, both renderer classes, every helper. That is
    *internal linkage*, so no second translation unit can see or define any of it,
    and every attempt to move a feature out failed at the link. Shared code now
    lives in `rt_internal.h` under **`namespace rtx`** (a named one, because
    `RG_CHECK` and `ONEGAMEUNIT_IN_METERS` at global scope across the whole gzdoom
    link is asking for a collision), and each RT file says `using namespace rtx;`
    once. If a new helper is needed in more than one RT file, put it in `rt_internal.h`
    as `inline` — not `static` in a .cpp.
    Two live traps from that migration: a file-local `pi()` silently **shadowed**
    gzdoom's `namespace pi`, but an `rtx::` one pulled in by a using-directive is
    merely **ambiguous** with it, so it is `rt_pi()` now; and `RT_CalcPowerupFlags()`
    is deliberately still file-local to `rt_main.cpp` — only the `RT_POWERUP_FLAG_*`
    bits are shared.

30. **An RTGL1 material is identified by NAME, and the first upload of a name
    wins — so anything that changes a texture's *pixels* without changing its
    name is silently discarded.** `MakeTextureName` (`rt_buffers.h`) used to
    derive the name from the `FGameTexture` alone, which meant every palette
    **translation** of a sprite uploaded as the same material. RTGL1's
    `PreferExistingMaterials` (`TextureManager.cpp:500`) then logs "Material
    with the same name already exists, ignoring new data" and drops it. gzdoom
    had done its half correctly the whole time — a separate hardware texture per
    translation (`hw_texcontainer.h:62`) with correctly remapped pixels.
    That is why per-monster `BloodColor` never rendered, including the two
    Retribution itself authored (`64NightmareImp`, `64HellKnight`). It also made
    blood colour **order-dependent**: whichever translation was drawn first
    coloured every monster's blood for the session.
    Fixed by `rt_tex_translations` (default on, pinned): translated textures get
    a `_tr<FRemapTable::Index>` suffix, untranslated names stay byte-identical.
    **Launch-time only** — the name is cached per hardware texture. Prove it is
    live with `rt_tex_translations_debug 1`; no lines means it is not.
    See `docs/blood-persist.md`.

31. **`rt/wad` loads LAST, after every `-file` PWAD — so menu/UI art in a pk3
    cannot win.** `GetCmdLineFiles` (`d_main.cpp:1963`) appends `rt/wad`
    unconditionally after the `-file` list. RT ships its own plain-Doom-font
    `M_LOADG`/`M_SAVEG`/`M_QUITG` and they overrode Retribution's Doom 64
    patches; `M_NGAME`/`M_OPTION`/`M_SKULL1` stayed D64 only because RT ships no
    copy of those. The tracked master for `rt/wad` content is
    **`rt-wad-overlay/`** (both real trees are gitignored), mirrored by
    `tools/sync-rt-wad.py`. Note the menu items are `PatchItem`s: a missing
    patch draws **nothing**, it does not fall back to text.
    Retribution's menu patches are plain `DBIGFONT` renders — `tools/gen_d64_menu_title.py`
    reproduces seven of them at 0 mismatching pixels and can synthesise any new
    word in the same face. See `compat-patches.md` (2026-08-13).

32. **An `emissiveMult` in `textures.json` silently makes a TRANSLUCENT primitive
    ADDITIVE — and additive can never occlude, at any alpha.** RTGL1's
    `TextureMeta.cpp:291` overwrites `prim.emissive` from the material (unless the
    caller sets `RG_MESH_PRIMITIVE_EMISSIVE_OVERRIDE`), and
    `RasterizedDataCollector.cpp:129` then turns any translucent primitive with
    `emissive > 0` into `ADDITIVE` (`SRC_ALPHA` / **`ONE`**). That is why
    `rt_nightmareimp_alpha` and `rt_spectre_alpha` read as completely inert: their
    eye masks carry `emissiveMult 2.0`, so the body blends additively and the alpha
    only scales how much a *dark* sprite ADDS to a lit room. The alpha was never
    wrong — `rt_ghost_debug` measured it arriving intact (0.42 → `packedA` 89/255,
    1.00 → 214/255) while the image did not move. `rt_ghost_emis 0` proves it by
    zeroing emissive (and taking the glowing eyes with it); **`rt_ghost_emis_split`
    is the fix and needs no RTGL1 change** — the body and the emission are on
    different attachments with different blend factors, so the eye mask goes out
    on a second copy of the quad at **alpha 0**, which adds no body (attachment 0
    is `SRC_ALPHA`) and the full glow (attachment 1 is `ONE,ONE`).
    See `docs/spectre-issue-log.md`.
    **The general lesson: when a cvar "does nothing", instrument the value's whole
    path before touching its magnitude — and if the value provably arrives, the
    next suspect is the STATE it is being interpreted in, not the value.**

33. **A traced primitive with no albedo texture takes its colour from
    `RgMeshPrimitiveInfo::color` — the PER-PRIMITIVE one. The per-VERTEX colour is
    stored and never read.** `HitInfo.inl`:

    ```glsl
    // if no albedo textures, use primary color
    dst = mix( unpackUintColor( layerColors[0] ).rgb, dst, float( hasAnyAlbedoTexture ) );
    ```

    `ShVertex` really does carry a `color` field, so the data arrives intact and
    nothing warns — but `layerColors[0]` is per-geometry. The **rasterized** path
    (`RsWorld.inl`) *does* use vertex colour, so the same geometry changes meaning
    when it moves between the two: impact debris was correct while rasterized and
    turned uniformly white the moment it became BLAS geometry, with
    `prim.color` left at `RG_PACKED_COLOR_WHITE`. No albedo or tint value could
    move it, and an arm at albedo **0.02** still rendered white — which is what
    identified it. Per-particle colour therefore needs particles **grouped into
    one primitive per colour** (`rt_sparks.cpp` buckets them), not vertex colours.
    Two neighbours of this, both real: a decal's `emissive` must be 0 or
    `RsDecal.frag` falls back to `ldrEmis = albedo` and the decal glows; and
    packed alpha below `MESH_TRANSLUCENT_ALPHA_THRESHOLD` (0.98) silently demotes
    a primitive to the rasterized overlay, i.e. back to fullbright.
    See `docs/rt-impact-fx.md`.

34. **A decal is one primitive per blob. Batching many fans into one produces
    geometry artefacts that survive every other explanation.** The sprite AO
    (`rt_draw.cpp`) uploads one fan per actor and is correct; impact-debris AO
    batched all its fans into a single `RG_MESH_PRIMITIVE_DECAL` primitive and
    drew lines reaching away from the blobs. The batched version is geometrically
    sound — no triangle spans two blobs — and the documented 5 cm grazing-floor
    limit was ruled out with a distance cull first. **Match the shape of the
    implementation that works rather than reasoning further about why a novel one
    should**; distinct `uniqueObjectID` per blob, since RTGL1 keeps one upload per
    ID and the later one loses.

35. **GIVING A TEXTURE A PBR LABEL SILENTLY DELETES ITS SECTOR SELF-EMISSION.**
    `TextureMeta.cpp` does, unless the caller set `RG_MESH_PRIMITIVE_EMISSIVE_OVERRIDE`:

    ```cpp
    prim.emissive = std::max( 0.0f, meta->emissiveMult );
    ```

    and `JsonParser.h` defaults `emissiveMult` to `0.0f`. So an entry that says
    **nothing whatsoever about emission** — a `metallicDefault`/`roughnessDefault`
    label — still overwrites whatever gzdoom computed with **zero**.
    `rt_sector_emis` was therefore resting on the *absence* of a `textures.json`
    entry. The metal/roughness labelling passes (`e1c8944`, then `8976584` across
    898 textures) removed that absence, and every painted light feature on a
    labelled texture went dark at once — **2091 of 3015 entries carry no
    `emissiveMult`**. MAP02's red corridor panels, the exact case `rt_sector_emis`
    was written for, were among them.

    **It fails silently, and the diagnostics all look healthy.** gzdoom computes
    and sends the right number, so `whatsthat` still prints *"this surface
    SELF-EMITS"* and `rt_tex_probe` still prints `sector_emis=0.350`. Both are
    true. Neither is evidence the emission reached the screen — the value is
    discarded one call later. Treat "the engine says it emits" as a statement
    about the **engine side only**.

    Fixed by **`rt_sector_emis_override`** (default on, pinned): the sector ramp
    claims the same flag the lamp-pane path already claimed for its own value.
    Only the ramp claims it — surfaces with an authored `_e` (`l_isemis`) must
    keep deferring to the material, or an SMON panel's `emissiveMult` 2.8 becomes
    `rt_emis_additive_dflt` 0.15. `+rt_sector_emis_override 0` restores the broken
    behaviour for an A/B.

    **Generalise it: a value computed by the caller and a value owned by the
    material are two owners of one field, and the flag is the only thing that says
    which wins.** Adding metadata of *any* kind to a texture opts it into the
    material's answer for **every** field the material can express, including the
    ones the new metadata is silent about.

36. **A FLAG ON AN ENGINE ZSCRIPT BASE CLASS REACHES THE GAME THROUGH THE MOD'S
    `REPLACES` SUBCLASS -- so a symptom that looks like mod or material data can
    live in `wadsrc/`.** Shooting a monster drew the vanilla `PUFF` sprite *on top of*
    the blood. The mod was clean (`+NOBLOOD` appears once in the whole Retribution
    DECORATE, on `64LostSoul`; no `+PUFFONACTORS` anywhere) and `p_map.cpp`'s
    puff/blood decision was pure upstream. The cause was `+PUFFONACTORS` on gzdoom's
    own `BulletPuff` in `wadsrc/static/zscript/actors/doom/doommisc.zs`, a `HAVE_RT`
    line from the vendor drop -- and `puffDefaults` is resolved through
    `pufftype->GetReplacement()` (`p_map.cpp:4646`), so Retribution's
    `64BulletPuff : BulletPuff REPLACES BulletPuff` **inherits** it. Removed
    2026-08-25; `docs/compat-patches.md` has the full account.

    Two things that made it look like something else. It **adds** rather than
    replaces -- blood still spawns below at `p_map.cpp:5009` -- so "blood is broken"
    was never true. And the report arrived after a materials commit, because
    `gen_fx_emissives.py:254` had given `PUFF` `lightIntensity 250` + `noShadow`,
    pitfall 4 a third time: a flag that had been live since the vendor drop only
    became conspicuous when the sprite it spawns became a light.

    **The enemy-sprite PBR labelling was ruled out by measurement, not argument** --
    0 of 757 monster entries carry `metallicDefault`/`roughnessDefault` in either
    `textures.json` tree. `_orm`/`_e` companions are shading data with no playsim reach.

## Suggested next work

1. **`RAYRECONSTRUCTION.md`** — RR is working and the worm artifact is solved (a stuck cvar, not a renderer bug). Open levers: `rt_spp_direct`/`rt_spp_indirect`, `rt_restir_initial`.
2. **`open-issues-rt-lighting.md`** — ceiling lamp visual confirm; wash residuals.
3. Continue Phase 4 PBR; optional HEAD/BOSS eye masks.
4. Lost Soul: finish or drop LSGL; Phase 5 overlay pk3.
5. **Spectre wall wash** — check if TRANSLUCENT raster overlay causes any emissive/weapon ordering issues (the "punch-through" that originally motivated FORCE_WATER).
