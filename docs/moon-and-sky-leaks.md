# The moon, and the sky leaks it exposed

MAP13's halls were lit by *painted* light shafts — wedge sectors given a higher
`lightlevel` than the room they sat in, imitating moonlight from a moon that did
not exist. Removing the paint meant giving the light back for real, which meant
adding a moon. The moon then lit a great many rooms that have no opening.

This document is the whole chain: what the moon is, why it leaked, the four
wrong answers, and the two knobs that matter. Companion to
`sequence-light-chains.md` (which covers the painted shafts themselves) and
§1.2b/1.2c/1.2d of `open-issues-rt-lighting.md`.

---

## 1. What the moon actually is

Two separate things that must be aimed alike:

| | what it is | cvars |
|---|---|---|
| **the disc you see** | a moon painted into `MOONSKY`, the sky texture | `tools/gen_moon_sky.py` |
| **the light you feel** | `rt_sun`, RTGL1's analytic directional light | `rt_sun_a` / `rt_sun_b` / `rt_sun_intensity` / `rt_sun_color` |

They are separate because **RT's sky cannot light a room**. Under RT the sky is
`RG_SKY_TYPE_RASTERIZED_GEOMETRY`: gzdoom rasterises the dome into a cubemap that
RTGL samples on ray miss. It is a real environment map — but it is **not**
importance-sampled, so a small bright disc in it is found only by rays that
happen to point at it, which at 1 spp is far too noisy to carry a room. The disc
is scenery. `rt_sun` does the work.

### Why the sky texture is 1024 wide

`hw_skydome.cpp` picks `xscale = texw < 1024 ? floor(1024/texw) : 1`. The WAD's
`SPACE` flat is 256 wide, so the stock night sky wraps **four times** around the
horizon. Painting a moon at 256 would give you four moons. `MOONSKY` is four
copies of `SPACE` side by side — pixel-identical starfield — at 1024, so it wraps
once. Height stays 128 so the `texh <= 128 && tiled` branch of `SetupMatrices`
still applies and the vertical mapping is unchanged.

### Keeping the disc on its own light

**The disc is geometry, not paint.** `RT_DrawMoonQuad` (`hw_skyportal.cpp`) draws
a quad after the dome, along the `rt_sun` direction:

    dir = (sin t · cos b, cos t, sin t · sin b)      t = 90 − rt_sun_a, b = rt_sun_b

The sky renders with the viewpoint at the origin, so placing the quad at
`dir × 9000` puts the moon at the light's own bearing **by construction**. There
is no tracking, no sign to settle, no calibration constant, and the two cannot
drift apart. `MOONDISC` is the texture; `MOONSKY` is now just the starfield.

That replaced a painted moon which needed `rt_moon_track`, `rt_moon_tex_a/b`,
`rt_moon_yawsign`, `rt_moon_pitch_scale` and a sky rotation *and still* could not
be aimed above 60°. All of that is deleted.

Two things the geometry version fixes outright:

- **No altitude ceiling.** A Doom sky dome spans 60° and puts a flat
  averaged-colour cap above it (§8). A painted moon could not be placed there and
  got sliced by the cap boundary when pushed near it. A quad draws over both.
- **No mirror bug.** Vertices here are `(doom_x, doom_z, doom_y)` — see
  `hw_decal.cpp`, `Set(dv.x, dv.z, dv.y)`. The third component is **not** negated.
  Getting that wrong mirrors the moon east–west, which reads exactly like a
  misaligned disc: moon upper-left, light arriving from the right.

**Use the `moon` CCMD** — `moon <az> [alt] [intensity]`, or bare `moon` to report.

    rt_moon_geo       1   draw the disc as geometry (0 = no disc)
    rt_moon_geo_size  12  apparent diameter in degrees

`rt_moon_geo_size` is *not* `rt_sun_angdiam`: that one is the light's angular
size (shadow softness), this is only how big the disc looks.

### Per-map aim

`RT_MOON_PRESETS` in `rt_main.cpp`, applied at `RT_OnLevelLoad`. Each map's
windows face wherever its author pointed them, so one global bearing cannot serve
them all. **MAP13 = azimuth 90**, settled in play.

Maps with no entry fall back to the launcher's `rt_sun_a/b`, snapshotted on the
**first** level load — without that snapshot the fallback would quietly become
"whatever the last map with a preset set".

It is engine-side and not in the sky pk3 for a hard reason: **ZScript cannot set
these cvars.** `_CVar.SetFloat` throws *"Attempt to change CVAR outside of menu
code"* for anything without `CVAR_MOD`, and every `RT_CVAR` is
`CVAR_GLOBALCONFIG|CVAR_ARCHIVE`. A `WorldLoaded` handler is the obvious home for
it and does not work.

To add a map: `rt_moon_presets 0`, aim with `moon <az> [alt]`, then bare `moon`
prints a paste-ready table row. `intensity 0` in a row disables the moon on that
map entirely.

---

## 2. The leak — cause

**A shadow ray that hits nothing is scored as lit.** `RtMissShadowCheck.rmiss`
sets `isShadowed = 0`. That is correct for a sealed world and wrong for a Doom
map, which has no geometry above a ceiling and is full of T-junctions at
wall/ceiling seams. Rays leave the level, hit nothing, and come back "lit" — so
the moon washes rooms with no opening anywhere near them.

Confirmed visually: with `rt_sun_leak_debug 2`, legitimate shafts render **red**
(the ray reached sky) and leaking ones **green** (it escaped the map). The split
lands exactly on that distinction.

### The fix — `rt_sun_require_sky 1` (now the default)

**Status: ON by default**, both compiled (`rt_main.cpp`) and pinned in
`tools/launch-retribution-rt.cmd`. Both were needed — a launcher pin overrides
the compiled default, and that line said `0` for as long as the fix existed, so
changing only one of them changes nothing.

It gates the single **directional** light, so since the storm work it also
covers lightning, and matters more there: a strike is ~24× the moon's intensity,
so a pinhole that never showed under moonlight is glaring under a bolt.


In a Doom map the sky is the only legitimate way out, so a ray that escapes
without hitting sky escaped through a modelling gap. When the ordinary shadow ray
*misses*, fire one more against sky geometry alone (`INSTANCE_MASK_WORLD_2`,
which the normal shadow mask excludes) and require a hit.

| ray outcome | stock | with the fix |
|---|---|---|
| hits solid geometry | shadowed | shadowed |
| hits sky | *(sky is excluded from shadows)* | **lit** |
| hits nothing | **lit** ← the bug | **shadowed** |

Cost is one extra ray, only on points already lit by the moon.
`rt_sun_skyprobe_dist` bounds it.

**The failure mode to watch** is the opposite one: if some courtyard's sky
geometry is not closed, legitimate light there is rejected and it goes dark.
Now that the fix ships on, that is a *regression* rather than a hypothetical —
if a map loses its outdoor lighting, this is the first cvar to flip.
`tools/ab-skyleak.cmd noreq` is the back-to-back against stock behaviour, and
`proof` is the red/green confirmation.

### It must be applied in three places

This is what made the fix look inert for so long. There is no single visibility
choke point:

| path | shader | why it matters |
|---|---|---|
| surface direct | `LIGHT_SAMPLE_METHOD_INITIAL` in `RaygenCommon.h` | lit walls/floors |
| indirect | `LIGHT_SAMPLE_METHOD_INDIR` | bounce |
| **volumetric** | `RtVolumetric.rgen` | **the visible shafts** |

`RtVolumetric.rgen` does **not** call `traceDirectIllumination`. It picks one
light (`TryGetVolumetricLight` → `volumeLightSourceIndex`) and shadow-tests it
itself in `traceDirectIllumination_SpecificLight`. The shafts you see are
volumetric scattering of that light, so a fix in the shared path does not touch
them.

### This fix does not generalise to a LAMP, and it will be proposed again

Since `rt_volume_shaft_*` shipped, ordinary lamps put shafts in the air too
(`docs/plan-light-shafts.md`), and one of those read **through a wall** on MAP01.
The obvious move — "apply `require_sky` to the lamp shafts as well" — is a no-op,
for a reason worth stating here rather than only there.

`require_sky` exists because a **directional** light's shadow ray runs to
`MAX_RAY_LENGTH`, so a miss means the ray left the map. **A lamp's ray terminates
at the bulb.** It cannot escape, and there is no sky for a probe to require. And
`traceShaftLights()` already traces one shadow ray per light per froxel
(`RtVolumetric.rgen:283`) with the same helper this function uses, with back-face
culling off for volume rays and with solid geometry in the shadow mask — so
occlusion is not what is failing. The suspects there are the trilinear read of a
prefix sum (one slice = `rt_volume_far / 64`, i.e. 0.94 m at shipping) and §5.1's
geometry culling. **`docs/plan-light-shafts.md` §4d** carries the ladder;
do not re-open this section for it.

---

## 3. Debugging

    rt_sun_leak_debug 0   off
    rt_sun_leak_debug 1   ISOLATE: only escaping light is drawn
    rt_sun_leak_debug 2   COLOUR: RED reached sky, GREEN escaped

Mode 2 **composes with the fix** — `require_sky` drops the leaks first, then the
colour pass paints the survivors. So `+rt_sun_require_sky 1 +rt_sun_leak_debug 2`
showing **all red and no green is the confirmation the fix worked**. (An earlier
version made them mutually exclusive, which meant the fix could never be
observed, only trusted.)

`rt_sun_leak_debug` is **`RT_CVAR_NOARCH`** on purpose. Every other `RT_CVAR` is
`CVAR_ARCHIVE`, and a debug mode left set suppresses `require_sky` — a stuck `2`
made the fix look like it did nothing for a whole round trip. Same trap
`rt_water_debug` is NOARCH for.

**Which light is which**, when it is not obvious:

    python tools/gen_moon_sky.py --debug && python tools/pack_rt_sky.py

Paints every sky surface magenta with a green grid — ceiling openings,
decorative wall slots, sky-hack bands. In a leaking room, magenta light is the
**dome**, blue-white is the **moon**. Restore with `gen_moon_sky.py` (no flag).

    rt_sky_log 1        then walk into the room
    rt_sky_here         lists sky openings with size, position, FLAT vs WALL

Other bisects: `tools/ab-skyleak.cmd <nosun|nosky|dark|nowalls|full>`,
`tools/ab-moon.cmd` (intensity/bearing), `tools/ab-moonsize.cmd` (angular size).

---

## 4. Four answers that were wrong, and why

Kept because each looks reasonable and someone will propose it again.

**"Gate apertures by size — only let big gaps in."**
`tools/scan_sky_apertures.py` measured both apertures the map format can express:
Doom sky-hack ceiling steps (916 game-wide, only **4** at or under 32 units,
median 128–384) and missing upper textures facing sky (**zero**). MAP01 — the map
with the documented leak — has **none of either**. There are no small gaps to
seal. `rt_sky_wallgap` was never shipped.

**"Make the moon a disc so small holes admit less light."**
`rt_sun_angdiam`, still there and still useful for softness, made **no difference
at 40°** — an 80× wider source. Nothing is being squeezed through anything: the
ray is not passing through a small hole, it is leaving the map.

**"Sky walls occlude, sky flats don't."**
Would have killed MAP13's own windows. 70 game-wide "closed" `F_SKY1` sectors
(floor == ceiling) deliberately produce sky **walls** — MAP13 has 14, including
the west hall windows (`sec 217/218`, 16×224) and the 8×544 slots round the big
hall. Wanted and unwanted openings are the same kind of geometry.

**"`rt_sky_nowalls` will seal it."**
Removing geometry cannot block a directional light — a shadow ray that hits
nothing is *lit*. Only **adding** an occluder, or requiring the ray to reach sky,
can. The cvar remains as a blunt diagnostic for the dome.

---

## 5. The dome is a separate leak

`rt_sun` and `rt_sky` reach a room by different routes. `rt_sun` is a light with
an occlusion test — everything above applies. The **dome** is sampled on ray
*miss* via `getSky()`, so there is no light to occlusion-test and none of
`rt_sun_require_sky` / `leak_debug` / `angdiam` touch it.

If a room still leaks with `rt_sun 0`, it is the dome, and it needs its own
approach. `screen/purpleleakfromtheleft.png` is a dome leak, photographed under
the magenta diagnostic sky — which is why `require_sky` did nothing to it.
**Not yet investigated.**

---

## 5.1 A third leak, and the only one that moves when you turn

*(Numbered 5.1 rather than 6 so the section references in `AGENTS.md` and the
other docs keep pointing where they did.)*

**Symptom: the leak changes as you rotate on the spot — "as if a wall behind me
gets culled".** It does. The wall is in the map and is *missing from the
acceleration structure*, which is a different failure from everything above and
is not fixable by anything in §2.

gzdoom feeds RTGL1 from the same BSP walk it uses to rasterize, so the tracer
only knows about geometry that walk submitted, and the walk is frustum- and
BSP-culled. `hw_bsp.cpp` compensates with a **second, unculled walk** whose
breadth is `rt_cpu_cullmode` — mode 0 runs both walks per frame, which is why
that cvar is marked *"IMPACTS CPU PERFORMANCE HEAVILY"*:

| `rt_cpu_cullmode` | what reaches the acceleration structure |
|---|---|
| **0** (default) | visible sectors + **every neighbour** of a visible sector, plus everything within `rt_cpu_nocullradius` (default **10 m = 320 map units**) |
| 1 | stock GZDoom culling — visible only. The leakiest |
| 2 | the whole map, no culling |

So a wall is absent when it is all three of: not visible, not adjacent to
anything visible, and beyond 320 units. Turning changes the visible set, so it
changes the absent set, so the leak **breathes with the camera**. Nothing in the
sky-leak family can do that — sky geometry is submitted unconditionally
(`rt_sky_always`, which exists for this exact reason: *"always submit sky
geometry (even if it's not visible in primary view)"*).

**`rt_sun_require_sky` is irrelevant here, in both directions.** It gates the
directional light only, and a ray leaving through a missing wall reaches no sky
either, so the moon was already being rejected. What still comes through the hole
is **the next room's own lamps**, the **dome** on ray miss (§5), and indirect
bounce. `tools/ab.cmd cull-dark` kills both sky sources and is what separates
them.

    .\tools\ab.cmd cull-stock 02     the baseline -- turn on the spot
    .\tools\ab.cmd cull-dark  02     rt_sun 0 + rt_sky 0: is it the level's lamps?
    .\tools\ab.cmd cull-wide  02     radius 10 m -> 40 m. The cheap fix
    .\tools\ab.cmd cull-all   02     cullmode 2, whole map. THE DECIDER

**All four arms run with the inferred ceiling and strip lamps off**
(`rt_ceiling_lamps 0` + `rt_ceiling_edge_lamps 0` + `rt_wall_strips 0`). Those
are engine-placed analytic lights inferred from a *texture*
(`rt_lights_fixtures.cpp`), which makes them both the loudest candidate for a
wash coming through a hole and the easiest thing to mistake for one. So
`cull-stock` is deliberately **not** the play configuration — it is the play
configuration minus those two families, which is what the other three need to be
compared against. Add `-- +rt_ceiling_lamps 1 +rt_ceiling_edge_lamps 1
+rt_wall_strips 1` to any arm to put them back for a run.

**Turning those two families off does not darken a Doom 64 room, and that is not
a bug in the arms.** `screen/stilllight.png` is MAP02 with all three at 0 and the
corridor still fully lit. Those cvars govern only lamps the *engine* invents from
a texture (`rt_lights_fixtures.cpp`). What actually lights that corridor,
measured from MAP02's own `TEXTMAP`:

| source | count in MAP02 | cvar |
|---|---|---|
| map light **things** | **83** — 48 × 9800 `PointLight`, 35 × 9802 `PointLightFlicker` | `rt_dynlight` |
| sectors whose painted brightness **self-emits** | **153** at lightlevel ≥ 160, **74** of them ≥ 220 | `rt_sector_emis` (0.35, floor 160) |

The glowing ceiling insets in that shot are largely the second one — Doom 64
paints its lamp recesses bright and `rt_sector_emis` turns painted brightness
into real emission, so there is no "fixture light" to switch off. And the cull
arms hold `rt_dynlight 1` deliberately, which keeps all 83 things burning.

`tools/ab.cmd cull-black` is the arm that ends the ambiguity: **every** source
off, so the correct outcome is a black room. If it is not black, nothing in these
cfgs is reaching the game and no other result in the suite means anything —
verify that before changing another cvar.

**Result, 2026-08-12: `cull-black` is black and shows no leak on MAP02.** So the
cfgs do apply, and with every source off there is nothing to leak — which is the
expected reading and, more usefully, the confirmed floor the bisect stands on.

### The bisect: cull-black plus exactly one source

Each of these is `cull-black` with a single family restored to its play value, so
whichever one brings the wash back owns it:

    .\tools\ab.cmd cull-emis 02      + rt_sector_emis 0.35   (the 153 painted sectors)
    .\tools\ab.cmd cull-dyn  02      + rt_dynlight 1         (the 83 map light things)

Then, on whichever one reproduces it, widen the guaranteed shell **without
editing a file** — `ab.cmd` appends anything after `--` and it wins:

    .\tools\ab.cmd cull-emis 02 -- +rt_cpu_nocullradius 40

Wash stops moving with your heading → geometry culling is the carrier and the
radius is the fix. Wash moves exactly as before → culling is innocent for that
source, and the cause is elsewhere.

The two failures look different, which is itself diagnostic. A **self-emitting
surface** has no position to occlusion-test — it is emission gathered by whatever
ray lands on it, so a ray through a missing wall simply finds the bright sector
behind it, and the result is a general lift. A **map light thing** is analytic
with a real shadow ray, so the leak has a *direction*: it points at the fixture
in the next room.

**Zeroing `rt_ceiling_lamps` alone does nothing visible in a big hall.**
`rt_ceiling_edge_lamps` is a separate path — bulbs around the *perimeter* of a
lamp ceiling, "independent of `rt_ceiling_lamps`" by design, because the centre
sphere is skipped in any sector wider than `rt_ceiling_lamp_maxspan`. Turn off
one and the halls keep their edge bulbs; the arms zero both.

**2026-08-15: still not shippable, and now pinned against.** A hand-set mode 2
survived in the ini for weeks because these cvars are `CVAR_ARCHIVE` and nothing
pinned them, and it was mistaken for the shipping configuration — see `AGENTS.md`.
`tools/d64rt-pins.cfg` now pins `rt_cpu_cullmode 0` and
`rt_cpu_nocullradius 20`; the **radius** is the answer to "a wall behind me is
culled", not the mode.

`cull-all` is decisive rather than shippable: if the leak survives it, geometry
was never the cause and this line of enquiry is closed in one run. It is not a
default because `rt_main.cpp` refuses to pick mode 2 for mod maps on its own —
*"uncull-all (mode 2) on large UDMF mods freezes the main thread for a long time
(looks hung; needs force-close)"* — and Retribution is a large UDMF mod. An
explicit `rt_cpu_cullmode 2` from a cfg is not covered by that guard, so expect a
long stall at load and do not leave it in the pins. Prefer whatever smallest
change also fixes it, normally the radius.

---

## 5.2 The moon competes for each pixel, and usually loses — `rt_sun_split`

Found from `screen/moon_shadow_limit.png`: sprites casting no moon shadow while
the same sprites shadow perfectly from a muzzle flash. It is not a shadow bug
and not a caster bug — the shadows were being cast and thrown away.

**Mechanism.** `RaygenCommon.h` builds two reservoirs — one over the regular
lights, one for the directional light — and merges them **stochastically**:

```glsl
updateCombinedReservoir(combined, dirLightReservoir, rnd);
```

So exactly **one light wins per pixel**. That is proper importance sampling, and
it fails in a specific way for a light that is *huge but weak*: at
`rt_sun_intensity 90`, against a level's own lamps and `rt_sector_emis` surfaces,
the moon wins on a minority of pixels. Its shadows are therefore resolved on a
sparse random subset of the image, and the denoiser flattens what survives. A
muzzle flash escapes this by dominating every pixel it touches, which is exactly
why the same sprite shadows fine when an enemy fires.

**Why more samples only half-worked.** `rt_shadow_samples` averages visibility
for the light **already chosen** (`reservoir.selected`), so it sharpens the moon
only where the moon was picked — measured: 8 samples recovered "a bit".
`rt_spp_direct 4` did restore them, because N independent estimates give the moon
N chances to be drawn, but it pays for that by multiplying rays across **every**
light to repair one.

**The fix.** `rt_sun_split 1` removes the sun from that draw and shades it
deterministically: one shadow ray on every pixel facing it, added to the ReSTIR
estimate over everything else.

- **Unbiased.** The sun is removed from the candidate set rather than counted
  twice, and `calcSunOnlyReservoir()` mirrors how `calcInitialReservoir` built
  `dirLightReservoir` — one candidate, `oneOverSourcePdf` 1, normalised to 1 — so
  sunlit surfaces are the **same brightness** either way. Only the noise changes.
  If brightness moves, the weight has drifted; that is the one way this breaks.
- **DIRECT *and* INITIAL.** Excluding the sun in the direct pass alone would not
  work: the INITIAL pass writes the reservoir image that direct sample 0 loads,
  so the sun would be back in the lottery through the stored reservoir.
- **Indirect and volumetric are untouched** — bounce light and the fog shafts
  keep the stock path and are bit-identical.
- **Cost** is one shadow ray per sun-facing pixel: most of the screen outdoors,
  nearly none indoors.
- The old `validCount == 0` early-out had to move, or a room lit *only* by the
  moon — no regular lights, no valid reservoir — would have returned black for
  exactly the surfaces this exists to light.

**Default is OFF** (`rt_sun_split false`, RTGL1's `sunSplit` defaults to 0), so
play is unchanged until the A/B says otherwise:

    .\tools\ab.cmd title-nosplit menu     stock, run first
    .\tools\ab.cmd title-split   menu     the fix, at stock sample counts
    .\tools\ab.cmd title-split   02       and in a real level, for the frame cost

Both arms hold `rt_shadow_samples 1` and `rt_spp_direct 1` deliberately: the
claim is that one deterministic ray beats eight samples and four spp, so it has
to be shown at stock quality rather than on top of it. To ship it, flip the
compiled default **and** add the pin to `tools/d64rt-pins.cfg` — a pin overrides
the compiled default, so both must agree.

---

## 5.3 Sprites have no thickness — MOVED

`rt_sprite_shadow` (crossed shadow proxies) and `rt_sprite_ao` (contact occlusion
blobs) started here because the first one was reported straight after §5.2 and
turned on the same light-selection mechanism. They outgrew that: they are about
sprites, not about the moon or the sky, and they are now their own document.

**→ `docs/sprite-shadows-and-ao.md`**

What stays relevant to *this* file: §5.2's `rt_sun_split` is why sprite shadows
resolve outdoors at all, and the open "missing shadow on a WALL" issue is the same
per-pixel light-selection problem for a *local* lamp. Both are written up there.

---

## 5.4 The shafts are a MEDIUM, and its density was tied to the volume's reach

Reported after the smoke work: on MAP01 the shafts through the ceiling opening
were much weaker — barely visible standing in front of the opening, but plainly
there standing **under** it and looking up at the moon. That asymmetry reads as
nonsense and is the thing that identifies the cause.

**Nothing about the moon changed.** `rt_sun_intensity` is the 90 it always was
and `rt_sun_require_sky` still passes those rays. What you see as a shaft is the
**global medium** — `rt_volume_scatter` — being scattered by the directional
light, so anything that thins the medium thins the shaft, and no `rt_sun_*` cvar
is involved anywhere in the chain.

The medium was thinned by a **smoke** pin. `RtVolumetric.rgen` applies the
scattering coefficient **per froxel cell**:

```glsl
float scattering = ( fogDens + smoke.a ) * 0.001;
imageStore( g_volumetric, cell, vec4( lighting * scattering, scattering + absorbtion ) );
```

and `CmVolumetricProcess.comp` prefix-sums those cells with **no slice-thickness
weighting**. The grid is 64 slices whatever the reach, so `rt_volume_far` sets
the metres per cell — and `30 → 60`, pinned to double smoke's render distance,
halved how many cells a shaft crosses. Half the cells is half the in-scattered
light. `rt_main.cpp` already stated this coupling for the *shortening* direction
("shortening the reach would silently thicken it, because its density is per
CELL"); nobody applied it to lengthening. **Smoke was immune** because it pays
the slice thickness engine-side before upload, which is exactly why the moon was
the only thing that moved.

**Why looking up still worked.** The phase function is Henyey–Greenstein at
`rt_volume_lassymetry 0.5`. At k = 0.706, `phaseFunction_Schlick` returns 0.462
looking into the beam against 0.040 looking across it — about **11×**. That
ratio was always there; halving the density pushed the across-the-beam view under
the threshold where it reads while the into-the-beam view had 11× of headroom.
So the "impossible" observation is the measurement that confirms the diagnosis.

**The fix is a normalisation, not a value.** `rt_volume_scatter` is scaled per
metre against the 30 m reach it was tuned at, before upload:

    volume_dens = rt_volume_scatter * ( reach / 30 )

so `rt_volume_far` is a **reach and resolution** knob only, and a density value
means the same thing at any reach. Fog is deliberately **not** normalised: it
carries its own tuned pair (`rt_fog_far` / `rt_fog_density`) on nine maps,
`rt-fog.md` §6 documents the per-cell coupling as part of that contract, and
`ab-smoke.cmd fogsafe` asserts those maps did not move.

Two smaller contributors from the same stretch, both worth knowing before tuning
anything here:

- **`rt_volume_dither` is measured in FROXELS**, and the froxels doubled in
  length with the reach. 2 → 5 was therefore ~0.94 m → ~4.7 m of depth smear, a
  five-fold change from one pin plus another pin's side effect.
- **The room under the shaft got brighter.** The lamp-ceiling work
  (`rt-smoke.md` §3.2a) gives SFLATAQ/SFLATAS panes real bulb lights *and* keeps
  their painted glow, so a shaft of fixed brightness reads weaker against MAP01's
  halls than it used to.

A/B, `tools/arms/moon-*.cfg` — view every arm twice, in front of the opening and
under it looking up:

    .\tools\ab.cmd moon-before 01    reproduces the report exactly, on the fixed build
    .\tools\ab.cmd moon-now    01    shipping
    .\tools\ab.cmd moon-far30  01    must MATCH moon-now near the camera -- the acceptance test
    .\tools\ab.cmd moon-dens   01    twice the historical density: shafts and haze together
    .\tools\ab.cmd moon-lint   01    brighter shafts, no extra haze
    .\tools\ab.cmd moon-sharp  01    dither 2 + blur 0: how much is the smoothing pins
    .\tools\ab.cmd moon-dark   01    bulbs off: how much is the brighter room

**Generalise it.** A cvar owned by one feature can set the units another feature
is measured in. Any pin that changes the froxel volume's geometry —
`rt_volume_far`, `rt_fog_far` — silently retunes everything the volume carries,
and the moon lives in there next to the fog and the smoke.

---

## 5.5 The shaft stops before it lands — the depth dither is one-sided

> **STATUS, 2026-08-14: CLOSED, both candidates measured and both NEGATIVE.**
> The screenshot's short shaft is not explained by anything in this section. Two
> arms settled it in one round and the numbers are worth keeping because both
> mechanisms are real — they are just too small, or point the wrong way:
>
> | arm | prediction | **measured** |
> |---|---|---|
> | `shaft-stock` (dither_z 5) vs `shaft-bias` (0) | 1.5 m of beam back | *"kind of identical"* |
> | `shaft-probe` (dither_z 40) | medium collapses | **no shaft at all** — the knob IS live |
> | `shaft-iso` (lassymetry 0) | beam even end to end | **less visible / weaker** |
>
> `shaft-probe` is the load-bearing one. It rules out the silent-plumbing
> explanation outright, so *"identical"* means what it says: the depth bias is
> real arithmetic worth 1.56 m and **1.56 m is simply not visible here**. And
> `shaft-iso` going dimmer rather than flatter says the forward peak is carrying
> the shaft, not truncating it — killing the anisotropy costs brightness and buys
> no reach, so the phase function is not the carrier either.
>
> **What is left is not a bug.** A camera ray crossing the beam near where it
> meets the floor spends almost no *distance* inside it, so the ground contact is
> genuinely faint — path length through the medium, not truncation. The knobs for
> that are `rt_volume_scatter` and `rt_volume_lintensity` (which brightens the lit
> shaft without thickening the haze), and it is a look decision rather than a
> repair.
>
> `rt_volume_dither_z` is **kept** at 1. It is invisible at shipping values, but
> coupling a one-sided depth filter to a symmetric screen one is wrong on its own
> terms, and `shaft-probe` is only possible because the axis has its own knob.

`screen/shaftsStoppingTooEarly.png`, MAP13's west hall. The cone from the window
slots fades out in mid-air and never reaches the floor it is plainly lighting
further along the beam. Reported as *"not reaching enough towards the end"* and
as the shaft being pulled *"too back towards itself"*, with a cut-off that moves
slightly with the camera.

**This is not §5.4 again.** That was a density problem and the per-metre
normalisation fixed it; the medium is the right thickness now. This is the
column being **sampled short**, and the moving cut-off is what says so — a
world-space cause (`rt_sun_require_sky` rejecting far froxels, geometry
occlusion) cannot breathe with the camera.

**The mechanism.** `CmScatterAccum.comp` jitters each pixel's volume lookup along
a **hemisphere** sample, negated:

```glsl
const vec3 offset = sampleHemisphere( rnd.x, rnd.y, oop );
return volume_sampleDithered( position, rnd.z, -offset, ... );
```

`sampleHemisphere` (`Random.h:88`) returns `z = sqrt(1 - u1)`, which is **always
positive**. Negated, the depth component is always ≤ 0: the volume is never
sampled deeper than the surface, only shallower. And `g_volumetric` holds a
**prefix sum from the camera outward** (`CmVolumetricProcess.comp`), so a
consistently shallower sample returns consistently *less* accumulated
in-scattering. It does not blur the far end of a column. It deletes it.

| | value |
|---|---|
| froxel depth at `rt_volume_far 60` | 60 m / 64 slices = **0.94 m** |
| `E[rnd01]` | 0.5 |
| `E[z]` of `sampleHemisphere` = ∫₀¹√(1−u)du | **2/3** |
| **mean shortfall at radius 5** | 0.5 × 5 × ⅔ × 0.94 = **1.56 m** |
| worst case | **4.69 m** |
| stock RTGL1 (radius 2, far 30 → 0.47 m) | 0.31 m |

The shipping pins were **5× the stock bias**, and neither pin looks like it did
that: `rt_volume_dither` went 2 → 5 for smoke's noise, `rt_volume_far` went
30 → 60 for smoke's reach, and the two **multiply**. Same compounding
`moon-sharp.cfg` records for the *smear*, acting here on the *mean*. 1.5–4.7 m
of missing beam is the size of the gap in the screenshot.

**Why it is one-sided, and why symmetrising it is the wrong fix.** Sampling only
toward the camera is what stops the jitter reading a froxel column that belongs
to geometry **behind** the surface — the dark outlines dense smoke draws around
everything seen through it, which `CmScatterAccum.comp`'s own comment records.
That property has to survive.

**The fix: give depth its own radius.** `rt_volume_dither` is now the **screen**
axes only and keeps its 5; `rt_volume_dither_z` is the depth axis and ships at
**1**. Depth only has to break **slice banding**, which is a half-froxel
quantisation artefact, so a sub-froxel radius covers it and the bias falls to
0.31 m — stock's figure, restored at a 60 m reach. The 5 it inherited was sized
against *noise*, and noise is `rt_volume_blur`'s and `rt_volume_history`'s job.

**The screen axes were never at fault.** `x` and `y` are `r·cos φ`, `r·sin φ` —
symmetric about zero, so they blur the shaft's edge without displacing it. The
"misplaced" half of the report is the missing far end, not a lateral shift.

A/B, `tools/arms/shaft-*.cfg` — view each twice, across the shaft and along it,
as §5.4 requires:

    .\tools\ab.cmd shaft-probe 13   dither_z 40: RUN THIS FIRST. Is the knob connected?
    .\tools\ab.cmd shaft-stock 13   dither_z 5: the old coupled behaviour
    .\tools\ab.cmd shaft-now   13   shipping
    .\tools\ab.cmd shaft-bias  13   dither_z 0: the upper bound, not shippable (banding)
    .\tools\ab.cmd shaft-iso   13   the OTHER hypothesis -- lassymetry 0.5 -> 0

**`shaft-probe` is the pattern to reuse, not just an arm.** `shaft-stock` and
`shaft-bias` came back identical, and *"a knob did nothing"* has two completely
different causes — too small to see, or never reaching the shader — which no
amount of staring at the two arms can separate. §7 lists three separate silent
value collapses in this feature alone. So the third arm is a deliberately absurd
value chosen to be **impossible to miss**: 40 froxels is a 12.5 m mean shortfall
out of a 60 m volume. It killed the shaft outright, which retired the plumbing
hypothesis in one run and made the null result trustworthy. Cost: one launch.
Build the absurd arm *before* concluding a mechanism is wrong, not after.

### The other candidate, also negative: the phase function varies ALONG the beam

`rt_volume_lassymetry 0.5` gives k = 0.706, and
`(1-k²)/(4π(1+k·cosθ)²)` runs **0.462 → 0.096 → 0.080 → 0.0137** across
cosθ = −1 → −0.5 → 0 → +1. A 34× range. `tolight` is constant for a directional
light but `toviewer` is not, so froxels at one end of a raking beam are weighted
several times harder than froxels at the other **for no reason the viewer can
see** — and MAP13's moon is at altitude 25, a low raking beam, which is the worst
case because the view direction swings furthest along its length.

That would be a shaft dying along its length with nothing truncating it, and it
is separable from the dither — the phase term varies with view **angle**, the
dither with view **distance**.

**Measured: `shaft-iso` is dimmer, not flatter.** At asymmetry 0 the phase is a
flat 1/4π = 0.0796 against the forward peak's 0.462, so removing the anisotropy
takes ~6× off the view that was working and gives the far end nothing back. The
peak is **carrying** the shaft, not truncating it — which also means the tuning
answer here is never *lower* asymmetry, and §5.4's "invisible from in front, fine
looking up at the moon" is that same peak doing the job it exists for.

**So neither candidate is the cause, and the remaining explanation is not a bug.**
A camera ray crossing the beam near where it meets the floor spends almost no
*distance* inside it, so the ground contact is genuinely faint. That is path
length through the medium, and the honest knobs are `rt_volume_scatter` (thicker
medium, more haze everywhere) and `rt_volume_lintensity` (brighter lit shaft, no
extra haze — `moon-lint` is the arm). Both are look decisions.

**Generalise it — twice.** *A knob that "does nothing" is two hypotheses, and one
absurd value separates them for the price of one launch.* `shaft-probe` retired
the plumbing explanation in a single run after two subtle arms had failed to.
And: *a dither drawn from a hemisphere is a bias, not a dither.* A
filter that is one-sided by design must be sized against the artefact it is
hiding — here, half a froxel of banding — not against whatever noise happens to
be annoying at the time. And it must be sized in the units it is actually
measured in: this radius is in **froxels**, so `rt_volume_far` moves it too.

---

## 6. Files

| file | role |
|---|---|
| `tools/gen_moon_sky.py` | builds `MOONSKY` (+ `--debug` magenta sky) |
| `tools/pack_rt_sky.py` | packs `d64r-rt-sky.pk3` |
| `tools/scan_sky_apertures.py` | measures sky-hack gaps; the negative result above |
| `tools/ab-moon.cmd`, `ab-moonsize.cmd`, `ab-skyleak.cmd` | pre-set A/B arms |
| `tools/arms/cull-*.cfg` | the §5.1 geometry-culling arms (`ab.cmd cull-stock` / `-dark` / `-wide` / `-all`) |
| `tools/arms/moon-*.cfg` | the §5.4 medium-density arms (`moon-before` / `-now` / `-far30` / `-dens` / `-lint` / `-sharp` / `-dark`) |
| `tools/arms/shaft-*.cfg` | the §5.5 depth-dither arms (`shaft-stock` / `-now` / `-bias`) |
| `RTGL/.../CmVolumetricProcess.comp` | the unweighted prefix sum — why CELLS, not metres, are what a shaft is counted in (§5.4), and why sampling it shallow **deletes** the far end of a column rather than blurring it (§5.5) |
| `RTGL/.../CmScatterAccum.comp` | where the volume is sampled per pixel and jittered — the one-sided `-sampleHemisphere` depth bias (§5.5) |
| `RTGL/.../Volumetric.h` | the froxel mapping (`volume_getCenter` / `volume_toSamplePosition_T`) and `volume_sampleDithered`, which owns the split radii (§5.5) |
| `hw_bsp.cpp` | the second, unculled BSP walk — `rt_cullmode`, `rt_nocull`, `rt_segdrawn` (§5.1) |
| `rt_main.cpp` | `rt_sun_*`, `rt_moon_*`, `RT_MOON_PRESETS`, `moon` / `rt_sky_here` CCMDs, `RT_MoonSkyPitchOffset` |
| `r_sky.cpp` | sky yaw tracking in `R_UpdateSky` |
| `hw_skydome.cpp` | sky pitch offset in `SetupMatrices` |
| `hw_sky.cpp` | `rt_sky_nowalls` |
| `RTGL/.../RaygenCommon.h` | `traceSunReachesSky`, surface + indirect probe; `calcSunOnlyReservoir` + the `sunSplit` exclusion (§5.2) |
| `RTGL/.../RtVolumetric.rgen` | the probe on the **shafts** |
| `RTGL/.../VulkanDevice.cpp` | `sunRequireSky` / `sunLeakDebug` uniforms |
| `docs/sprite-shadows-and-ao.md` | **sprite shadows and contact occlusion** — moved out of §5.3, with their own file list |

---

## 7. Troubleshooting

**A change appears to do nothing.** Check it is live before believing the result
— this cost several rounds here. Three separate value collapses each produced the
identical symptom: a `bool` cvar eating mode `2`, an RTGL `> 0.5f ? 1 : 0` eating
it again, and the code being in a shader the effect does not use. Verify the
strings are in `gzdoom.exe`, the `.spv` timestamp is after your edit, and `moon`
reports the mode you asked for.

**Moon disc not where its shaft comes from.** It cannot be, unless the direction
expression in `RT_DrawMoonQuad` is wrong — the disc's position is `dir × R` with
`dir` built from the same `rt_sun_a/rt_sun_b` the light uses. There is no offset
to tune. Check the coordinate order first: vertices are
`(doom_x, doom_z, doom_y)` and the last component is **not** negated; negating it
mirrors the moon east–west, which is how this last failed.

**Shafts vanished entirely.** `require_sky` is over-killing: sky geometry is not
closed there. Turn it off and check with `rt_sky_here`.

**Everything is red in mode 2 but rooms still look wrong.** The moon is
legitimately reaching sky; the problem is *which* opening is in reach. Use
`rt_sky_log 1` + `rt_sky_here`.

**Two builds at once.** RTGL and gzdoom share build state; concurrent builds
produce a storm of `C1041: cannot open program database`. Kill `MSBuild` /
`mspdbsrv`, delete `deps/RTGL/BuildCMake`, rebuild.

---

## 8. The moon can only go 55 degrees up

`hw_skydome.cpp`: `maxSideAngle = 60`. The sky dome spans **60 degrees of
altitude**, and above that Doom draws a flat circular **cap** (`r_skycap_mult`,
`r_skycap_thresh`) because it has no 3D skybox. No texture detail lives up there.

So an altitude above 60 aims the **light** overhead while the **disc** stays
where the texture put it. That reads as a tracking failure and is not one — it is
a request the sky geometry cannot represent. `moon 180 180` (altitude clamps to
90) is how this was found.

Two guards:

- `moon <az> <alt>` **warns** when `|alt| > 60` instead of silently clamping.
- `RT_MoonSkyPitchOffset()` clamps the request to the dome's range and the result
  to ±90 units. Unclamped, altitude 90 against a texture painted at 25 gives
  `(90−25)×3 = 195` units × 57 = **11,115 world units** of translate on a
  10,000-radius dome — the sky comes off its hinges.

**Keep altitude at 55 or below** if you want the disc to sit where its own shafts
come from.

**MAP01 deliberately does not.** It is set to 180/90 — straight overhead — because
the vertical fall of the light is what makes it read like the original game, and
at altitude 90 the direction code clamps theta to 0 so the shafts drop straight
through the roof slots. The disc rides as high as the dome allows and is *not*
where the light originates. That trade was made on purpose, look over realism;
drop it to 55 to reverse it.

## 9. The painted moon art

`tools/_assets/moontexture.png` is composited by `gen_moon_sky.py`. Its
**alpha channel is the disc mask** (opaque to ~r=476 of a 1536×1024 canvas,
feathered out by r=500) and its RGB carries a halo beyond that — so the disc
pastes through alpha and the halo screens on, each doing the job it was drawn
for. The disc radius is detected from the alpha falloff, not hardcoded, so
replacing the art with a differently framed moon still works. `--no-art` falls
back to the procedural disc, and a missing file does the same rather than
failing the build.

**The moon is drawn as an ellipse on purpose.** The sky texture is anisotropic in
angle: 360° across its width, only 60° down its height. At 1024×128 that is
2.84 px/deg horizontally against 2.13 vertically, so a circular moon in texture
space renders as a stretched one in the sky. `gen_moon_sky.py` corrects for it
(12° → 34×26 px); `--aspect` is the residual fudge if it still reads as an
ellipse in game, because `SetupMatrices` rescales `v` again for short tiled
textures.
