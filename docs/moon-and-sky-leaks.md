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

## 6. Files

| file | role |
|---|---|
| `tools/gen_moon_sky.py` | builds `MOONSKY` (+ `--debug` magenta sky) |
| `tools/pack_rt_sky.py` | packs `d64r-rt-sky.pk3` |
| `tools/scan_sky_apertures.py` | measures sky-hack gaps; the negative result above |
| `tools/ab-moon.cmd`, `ab-moonsize.cmd`, `ab-skyleak.cmd` | pre-set A/B arms |
| `rt_main.cpp` | `rt_sun_*`, `rt_moon_*`, `RT_MOON_PRESETS`, `moon` / `rt_sky_here` CCMDs, `RT_MoonSkyPitchOffset` |
| `r_sky.cpp` | sky yaw tracking in `R_UpdateSky` |
| `hw_skydome.cpp` | sky pitch offset in `SetupMatrices` |
| `hw_sky.cpp` | `rt_sky_nowalls` |
| `RTGL/.../RaygenCommon.h` | `traceSunReachesSky`, surface + indirect probe |
| `RTGL/.../RtVolumetric.rgen` | the probe on the **shafts** |
| `RTGL/.../VulkanDevice.cpp` | `sunRequireSky` / `sunLeakDebug` uniforms |

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

`moontexture.png` at the repo root is composited by `gen_moon_sky.py`. Its
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
