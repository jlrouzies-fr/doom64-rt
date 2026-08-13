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

## 5.3 A sprite has no thickness — `rt_sprite_shadow`

Reported straight after §5.2 landed, and it is the other half of the same
complaint. A sprite is a **camera-facing quad**, so its shadow is the projection
of a plane:

- **A light lying in that plane projects it to a line.** Look at an actor with
  the light exactly to your left and it casts nothing at all.
- **The quad turns to face you, so the shadow's shape changes as you rotate.**
  Nothing physical does this, and it reads as instability.

Voxelising the actors would fix it properly and is a **documented dead end** here
— `docs/rt-voxel-models.md` §6: silhouette carving from Doom's 8 hand-drawn
rotations cannot represent a concavity, "the ceiling of the method, not a tuning
problem."

**What ships instead: invisible crossed quads.** Each visible actor also submits
`rt_sprite_shadow_planes` (2) quads at **fixed world angles**, flagged
`RG_MESH_PRIMITIVE_SHADOW_ONLY`. At 90° apart no light direction is degenerate —
as one plane goes edge-on the other is face-on — and being world-fixed, the
shadow stops following the camera.

| | |
|---|---|
| **Invisible how** | The proxies land on `INSTANCE_MASK_RESERVED_0`, which is absent from `rayCullMaskWorld` (`WORLD_0\|1\|2`) and therefore from the primary, reflection, refraction and indirect cull masks *by construction*. One line in `VulkanDevice.cpp` adds it to `rayCullMaskWorld_Shadow`, and that is the only ray that can see them. |
| **Why it is cheap** | `CalculateTrueTransformAndItsVerts` already factors a billboard into (rotation, pivot) + un-rotated local verts, so a proxy is **the same vertices under a different transform** — no vertex maths, no second geometry copy, no texture work. |
| **Silhouette, not a rectangle** | The alpha test is carried over in the flags. |
| **Skipped** | Translucent sprites — spectres, the nightmare imp, additive fire. RTGL1 rasterizes those, so they are not in the AS and cast nothing today; giving them a solid shadow would be a change in look, not a fix. |
| **Bounded** | `rt_sprite_shadow_dist` (40 m). The cost is per visible actor per frame. |
| **The caster** | `rt_sprite_shadow_hidecaster` (on) puts `NO_SHADOW` on the visible billboard, or the umbra is the union of all three quads — fatter than the actor and still camera-dependent, i.e. the artefact survives diluted. |

Unique IDs are `actor pointer + 0x4000000000000000 + plane`, deliberately beyond
any Windows x64 user-space pointer: a collision would make RTGL1 drop one of the
two primitives with *"a primitive with the same ID already exists"*, silently,
and the proxy is the one that would lose.

**SHIPPING ON** (2026-08-13) — compiled default `rt_sprite_shadow true` **and**
pinned in `tools/d64rt-pins.cfg`, along with the scope, plane count, width,
hidecaster and distance. Both are needed: a pin overrides the compiled default,
so changing only one changes nothing. A/B:

    .\tools\ab.cmd sprshadow-off 02      stock billboards
    .\tools\ab.cmd sprshadow-on  02      what ships

### What a proxy can and cannot stand in for

A proxy is **an assumption about 3D shape**, and the four artefacts found in play
are all that assumption failing somewhere it does not fit. Worth keeping
together, because each fix narrows *where the feature applies* rather than
improving the proxy:

| symptom | cause | answer |
|---|---|---|
| swinging corner shadows across the flashlight beam | the **player's own** body is a `FirstPersonViewer` sprite that is also an `ExportInstance`, so it got proxies — and clearing the mesh flags dropped `FIRST_PERSON_VIEWER`, making them world occluders standing at the camera | skip viewer sprites. Keeping the flag instead fails: `PV_FIRST_PERSON_VIEWER` is tested before `PV_SHADOW_ONLY`, so the proxy would become *visible* geometry in front of the camera |
| black stripe down the middle of every enemy in the beam | a proxy plane passes through the actor's **own axis**, so it shadows the half of its own billboard behind it — and with the flashlight (a light along the sprite's normal) the perpendicular plane is edge-on and projects to a line down the centre | alpha-tested instances carry `INSTANCE_CUSTOM_INDEX_FLAG_IGNORE_SHADOW_PROXY`; `getShadowCullMask` strips `RESERVED_0` for them, so sprites do not **receive** proxy shadows |
| shadow spilling onto the floor *in front* of a sprite | proxies were as wide as the sprite's **canvas** (a marine: 64 units of art around a radius of 17), so the plane facing the viewer overhung the actor by ~2× | `rt_sprite_shadow_width` scales the horizontal axis to `actor->radius` |
| radiating spokes from corpses, gibs and dropped weapons (`screen/shadowissue.png`) | those are **flat plates on the ground**; four vertical cards through one is simply the wrong shape | emit proxies only for upright things — `!MF_CORPSE && Height >= 24 && Height >= 1.5·radius`. Corpses and pickups keep their stock billboard shadow, exactly as before the feature |
| a **mirrored twin** beside the shadow, on some enemies of a class but not others (`screen/invertedSpriteShadow.png`) | a textured plane's shadow is the **mirror** of its mask when the light is on the plane's far side, so roughly half the world-fixed planes cast a flipped silhouette | flip each proxy's U so its un-mirrored face points at the **camera** — gzdoom already chose the sprite's rotation frame for the camera's angle, so that is the only available definition of correct, and it is the right one for the flashlight |
| that mirroring **surviving the flip**, specifically on side-on enemies | the local verts are not axis-aligned. `hw_sprites.cpp` hands `push_apply_spriterotation` the **actor's own yaw**, so the quad keeps its camera-facing orientation baked in, offset by `camera_yaw − actor_yaw` | canonicalise the quad from its own vertices before using it (below) |

**The one that invalidated three earlier fixes.** Because the local verts carry
that baked offset, a proxy built as "the same verts under a `yaw_k` transform"
actually sat at `yaw_k + (camera_yaw − actor_yaw)`. Consequences, all silent:

- the planes were **not world-fixed** — they rotated with the camera, which is
  the property the whole design rests on;
- **local Y was not the width axis**, so `rt_sprite_shadow_width` narrowed the
  wrong one;
- the mirror test's normal was off by the same angle, worst when the actor is
  **side-on** to the viewer — exactly where the mirrored shadow survived.

The fix derives the quad's frame from its own vertices: take the face normal
(`(p1−p0)×(p2−p0)`), pick the side the camera is on since winding is not
guaranteed, then rotate the verts about local Z until that normal is `+X`. The
quad is then canonical — normal `+X`, width along `Y`, upright along `Z` — and a
rigid rotation cannot mirror it, so the texture's handedness relative to the
normal survives. Only then do the width scaling, the world yaws and the mirror
test mean what they say.

The height test is shape, not taste: gzdoom quarters an actor's `Height` on
death, so a corpse lands near **H/R 0.7** while every standing monster is 1.8+
(demon 30/56) and a barrel is 4.2; pickups are short without ever being corpses
(shotgun 20/16 = 0.8).

**Shipping scope is live monsters only** — `rt_sprite_shadow_scope 1`
(`MF3_ISMONSTER && health > 0`, on top of the shape tests). Scope 0 widens it to
anything upright, which also takes in barrels, torches and tall props.

`health > 0` is not redundant with `MF_CORPSE`: an actor is dead the moment its
health reaches 0 and plays a death animation for several tics **before**
`MF_CORPSE` is set and its height quartered. Without it, a dying enemy keeps
full-height vertical proxies through exactly the frames where it is folding onto
the floor.

**The general lesson.** One proxy shape cannot serve every sprite class. The
useful question is not "is the proxy better" but "does this object match the
assumption" — and where it does not, the honest move is to leave that class on
the stock billboard rather than to keep tuning.

### The plane spread was wrong for 3 and 4 planes

The yaws were a fixed table `{0, π/2, π/6, π/3}`. A plane's orientation is modulo
π — a quad and its 180° twin are the same occluder — so for `planes 4` that table
is **0/30/60/90**: every plane packed into one quadrant, with the 90°–180° half
uncovered. The consequence is that **how wide a shadow an actor casts depends on
the light's compass bearing**, worst case 0.71× the actor's width against 0.97×
at the best. It is derived now, `k·π/n`, so 4 planes are 0/45/90/135 and the
worst case rises to 0.92×. `planes 2` was correct by luck and is unchanged;
**the default is now 4**, which reads better in play.

### Open: a missing shadow on a WALL

Reported 2026-08-13 and **not yet resolved**. Sprite ahead, light to its right,
wall to its left: the shadow lands on the floor but the wall gets nothing. Two
candidates, and they need opposite fixes:

- **Geometry** — the plane facing that bearing is too narrow, or no proxy reached
  that surface. But the spacing arithmetic above predicts a *narrower* shadow,
  not an absent one, so this is the weaker candidate.
- **Light selection** — §5.2 again, for a *local* lamp. `rt_sun_split` took only
  the moon out of ReSTIR's per-pixel draw; every ordinary light still competes,
  so a lamp's shadow resolves only where that lamp wins. Near the sprite it
  dominates the floor and wins; on a wall several lights reach, it wins on a
  fraction of pixels, and a sparse shadow is what the denoiser flattens. That
  predicts "floor yes, wall no" with no geometry involved.

Two arms separate them, both run from the exact viewpoint where it is missing:

    .\tools\ab.cmd sprshadow-probe 02    rt_debug_visibility 1 -- is the ray blocked?
    .\tools\ab.cmd sprshadow-max   02    shadow_samples 8 + spp_direct 4

Actor-shaped **black** on the wall under `probe` means the proxies *are*
occluding and the loss is downstream; the shadow appearing under `max` confirms
selection variance. If selection is the answer, the fix is not more planes — it
is extending the `rt_sun_split` treatment to the dominant local light, which is a
real design job, not a cvar.

Both arms also set `rt_sun_split 1`, since outdoors there is no point testing
sprite shadows the moon was never resolving. **The check that matters most is a
negative one:** nothing new should ever be *visible* — not directly, not in a
mirror or water, not as a brightening from indirect light. A faint cross around
an actor would mean the instance mask is wrong, and that is the single failure
mode this design has.

---

## 5.3.1 The other half — contact occlusion, `rt_sprite_ao`

Requested 2026-08-13, in the same breath as the wall shadow above: *"can we have
a bit of ambient occlusion under enemies / props sprites (e.g. weapons on the
floor) — to compensate that a sprite 2d board doesn't always cast shadows if
light is perpendicular."*

**It is a second mechanism, not a tuning of §5.3, and the reason is the whole
point.** A cast shadow answers *where is the light*, and a board answers that
badly by construction: §5.3's crossed proxies remove the camera dependence and
the fully degenerate direction, but a plane is still a plane, and how much
shadow an actor throws still swings with the light's bearing (0.92× at best,
by the arithmetic in §5.3). Contact occlusion answers a different question —
*is there an object touching this floor* — and that question **has the same
answer from every light direction**. So it survives exactly the frame the cast
shadow loses.

And it reaches the classes §5.3 deliberately refuses. `rt_sprite_shadow_scope 1`
is live monsters only, because a vertical cross through a corpse, a gib or a
dropped shotgun is the wrong shape and threw radiating spokes
(`screen/shadowissue.png`). Those things kept their stock billboard shadow,
which is to say very little. **A blob on the floor is the right shape for a flat
thing lying on a floor** — which is why this is worth building rather than
adding a fifth plane.

### What ships: an RTGL1 decal, not geometry

Each qualifying thing submits a **triangle fan** on the floor beneath it, flagged
`RG_MESH_PRIMITIVE_DECAL`: black, alpha `rt_sprite_ao_strength` at the centre
falling to 0 at the rim. The falloff is **vertex-colour interpolation**, so the
feature ships no art, writes no `textures.json` entry and touches no material —
with no texture bound, RTGL1 samples its 1×1 white (`TextureManager::
CreateEmptyTexture`), which is the identity this needs.

The decal pipeline blends `SRC_ALPHA / ONE_MINUS_SRC_ALPHA` into the G-buffer
albedo, so a black decal leaves the floor at `albedo × (1 − a)` — a pure
**multiplicative darkening**. Three properties fall out of that, and all three
are the reason a decal was chosen over a light or a shadow caster:

| | |
|---|---|
| **It scales with the light already there** | Full strength on a lit floor, invisible in a dark room. An occlusion term must never be able to push a surface below unlit, and an additive black overlay would. |
| **It cannot occlude or be hit** | Rasterized, never in the acceleration structure. No reflection, refraction or bounce ray can see it, and it costs nothing in the AS. |
| **It stops at edges for free** | `RsDecal.frag` discards where the traced surface under the pixel is more than **5 cm** from the quad. So the blob stops at a step instead of smearing down it — and it is hidden behind the sprite's own pixels without a depth test (the pipeline has `depthTestEnable = VK_FALSE`). |

### The footprint's shape — one shape cannot serve every class

Requested after the first working build: *"under a shotgun on the floor it should
not be round, it should be a line the length of the shotgun sprite."* Correct, and
it is §5.3's lesson again in a new place.

- **Standing things keep a circle** at the collision radius. A body's footprint
  really is roughly round, the circle is camera-independent, and the collision
  radius is the honest measure — the sprite's canvas is about twice the body (the
  marine drawn on 64 units around a radius of 17), which is the trap
  `rt_sprite_shadow_width` exists for.
- **Things lying down get an ellipse fitted to the sprite quad.** For a dropped
  shotgun the art is the *only* description of the shape there is, so the
  along-axis is measured from the quad's real horizontal extent in world space.

The along-axis is derived by **2×2 principal axis of the quad's world XY
vertices**, not by "take local Y" — that is precisely the mistake §5.3 spent three
fixes on, because the local verts carry a baked `(camera_yaw − actor_yaw)` offset
and no local axis means what its name says. A covariance carries no such
assumption and is also correct for a pitched quad, where the up axis has a
horizontal component too.

**The across-axis is not measurable and is not pretended to be.** A single
camera-facing billboard carries no information whatsoever about how deep an object
is — the same ceiling `docs/rt-voxel-models.md` §6 documents for silhouette
carving. So it is a declared constant, `rt_sprite_ao_aspect` (0.4), and no work on
this code reaches past that.

**The fitted ellipse turns with the billboard**, and this was accepted when it was
asked for. Note it is the exact opposite of the §5.3 proxies, which are
world-fixed *precisely so the shadow stops following the camera* — and the two are
consistent rather than contradictory: a **cast shadow**'s shape must not follow
the viewer, because nothing physical does that; a **footprint traced from the drawn
object** should track what is actually drawn. `rt_sprite_ao_shape 0` reverts to the
disc as a pin change, and raising `rt_sprite_ao_aspect` toward 1 is the middle
position — it rounds the ellipse out and shrinks the swing without giving up the
fit.

    .\tools\ab.cmd spriteao-disc 02     circle everywhere
    .\tools\ab.cmd spriteao-on   02     fitted -- walk a circle around a dropped gun

### The four things that decide whether it is honest

Each of these is the feature admitting where its assumption stops, in the same
spirit as §5.3's scope tests:

- **Height fade** (`rt_sprite_ao_fade`, 56 map units). The blob asserts the thing
  is *on* the floor. A lost soul crossing a room, a cacodemon, a rocket in flight
  and a jumping player must not carry a disc with them, so it fades linearly from
  contact to nothing. This is the single most important knob for not looking fake.
- **The floor comes from the playsim.** `actor->floorz`, plumbed through
  `m_lastthingfloorz`, not re-derived in the renderer. It is already resolved
  across 3D floors and slopes, and getting it wrong buries the quad in the floor
  where the 5 cm test silently discards it — a failure that looks exactly like
  the feature not being built.
- **Radius is the actor's, not the quad's.** `rt_sprite_ao_radius` multiplies
  `actor->radius`. A sprite quad is the art's canvas and is roughly twice the
  body (a marine: 64 units of art around a radius of 17) — the same trap
  `rt_sprite_shadow_width` exists for. The default is 1.6× on purpose: occlusion
  reaches past a silhouette, and a blob cut exactly at the body reads as a
  sticker.
- **One blob per actor per frame.** A sprite with a fog layer draws **twice**
  (`hw_sprites.cpp` ~390/398), and unlike a mesh primitive a decal has no ID
  collision check to save us — two passes would blend twice and square the
  darkening. Gated on `primitiveIndexInMesh == 0`, which resets per actor, so it
  needs no static state and no frame counter.

The player's own viewer sprite is excluded, for the same reason §5.3 excludes it:
it is drawn at the eye, and a blob under it is a dark ring painted around the
camera.

### Cvars

| cvar | default | note |
|---|---|---|
| `rt_sprite_ao` | `true` | master switch |
| `rt_sprite_ao_strength` | `0.7` | fraction of the floor's albedo removed at the centre. Settled in play — see below |
| `rt_sprite_ao_radius` | `1.6` | multiple of `actor->radius`, for the **circle** |
| `rt_sprite_ao_shape` | `1` | 0 = circle always; 1 = circle upright / ellipse lying down; 2 = ellipse always |
| `rt_sprite_ao_fit` | `1.0` | multiple of the **sprite's** horizontal extent, for the ellipse. 1 = the art's own width |
| `rt_sprite_ao_aspect` | `0.4` | the ellipse's across-axis over its along-axis. A declared assumption, not a measurement |
| `rt_sprite_ao_fade` | `56` | map units of height over which it fades out |
| `rt_sprite_ao_scope` | `0` | 0 = everything with a floor; 1 = only what `rt_sprite_shadow` skips |
| `rt_sprite_ao_segments` | `14` | fan resolution |
| `rt_sprite_ao_dist` | `30` | metres. Tighter than the proxies' 40 — see the limitation below |
| `rt_sprite_ao_debug` | `false` | **`RT_CVAR_NOARCH`** — per-60-draw count of blobs *uploaded*, plus the nearest one's world position. Read the trap below before using it |

Compiled defaults **and** pins in `tools/d64rt-pins.cfg`, both, per the rule in
§5.3: a pin overrides the compiled default, so changing one alone changes
nothing.

    .\tools\ab.cmd spriteao-off  02     control
    .\tools\ab.cmd spriteao-on   02     what ships
    .\tools\ab.cmd spriteao-loud 02     0.9 / 2.5x -- "is it running at all"

`spriteao-loud` exists because the shipping values are deliberately subtle and
*"I see no difference"* is ambiguous between "working and subtle" and "not
running". Run it first when something looks wrong, then judge strength on
`spriteao-on` — judging strength on `loud` is how a feature ships as a sticker.

### The trap: a decal's world position is NOT its transform

**The first version shipped invisible**, and the failure is worth the space
because nothing about it is guessable from the API and nothing at all is logged.

`RsDecal.vert` is three lines long and the middle one is the problem:

```glsl
outTexCoord = texCoord;
outWorldPos = position;                                    // <- LOCAL, untransformed
gl_Position = rasterizerVertInfo.viewProj * vec4( position, 1.0 );
```

The push constant is *already* `model * viewProj` (`RasterizedPushConst`
premultiplies `info.transform`), so **`gl_Position` is transformed and
`outWorldPos` is not.** The fragment shader then tests that untransformed value
against a true world-space `framebufSurfacePosition`.

So the blob was built the way the shadow proxies above legitimately are — verts
around a local origin, location in `mesh.transform` — and the result is a quad
that **rasterizes in exactly the right place on screen and then discards 100 % of
its fragments**, because its "world" position is ~(0,0,0) while the floor is tens
of metres away. Not misplaced. Invisible, silently, with no warning and no
geometry to inspect.

gzdoom's own wall decals never hit this: world geometry takes the `MakeTransform`
branch in `InternalDraw`, where the transform is identity and local already *is*
world. **A sprite is the only caller that arrives at the decal path with a real
transform**, which is why a working decal system could be sitting right there and
still not save the first attempt.

The fix is one line of policy — **world-space vertices, identity transform** —
and `rt_sprite_ao_debug` exists so this class of failure can never again be
confused with the feature being switched off. It counts *uploads*: `emitted > 0`
with a clean screen means a position bug, not a disabled feature. That distinction
is the entire reason the cvar is there.

### Known limitations, stated rather than hidden

- **Not in reflections or water.** It is rasterized into the primary G-buffer, so
  a mirror shows the floor with no blob. This is the cost of the approach and it
  is the thing to look at first if the feature ever needs replacing.
- **Long range.** The decal's 5 cm test compares against the *checkerboard
  neighbour's* traced surface position, and at distance a pixel footprint can
  exceed 5 cm on a grazing floor, which drops fragments. `rt_sprite_ao_dist 30`
  is the bound; the same limit applies to the game's bullet-hole decals.
- **`rt_sprite_ao_scope 0` overlaps `rt_sprite_shadow` on live monsters.** Both
  are present under a standing enemy. That is deliberate — the proxy shadow is
  what vanishes when the light lies in its plane, and the blob is what is left.
  It was the stated reason for a conservative default strength; in play that
  double-darkening turned out not to be the problem the argument predicted.

### Strength: 0.7, and why the a-priori number was too low

Settled in play (2026-08-13). It **shipped at 0.45** on the written argument that
anything past ~0.6 would stop reading as contact and start reading as a painted
black disc. That argument was wrong, and the reason generalises to every knob in
this feature:

**`rt_sprite_ao_strength` is not the darkness you see.** The blob multiplies the
floor's *albedo*, so what reaches the screen is already scaled by the light in the
room, by the rim falloff, and by however much of the blob the sprite itself is
covering. The cvar is the darkness you would get on a fully-lit floor at the exact
geometric centre — a case that essentially never fills a pixel. Reasoning about it
as if it were a screen-space overlay under-shoots, and it under-shot by about a
third.

The same caution applies in the other direction to `rt_sprite_ao_aspect` and
`rt_sprite_ao_fit`: pick them by looking at a dropped weapon in a lit room, not by
argument. The one number that should still be reasoned about rather than eyeballed
is `rt_sprite_ao_fade`, because its failure (a disc following a flying enemy) is
not visible at all from the viewpoint where you would be tuning the others.

**Status: CONFIRMED IN PLAY** (2026-08-13). Invisible on the first build (the
world-position trap above), fixed, then the footprint was fitted to the sprite and
the strength settled at 0.7 from play. The remaining unverified claims are the
*negative* ones — no blob in a mirror or in water, none following a flying enemy,
none surviving into an unlit room — and those are what `spriteao-loud` and a
lift/cacodemon are for.

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

## 6. Files

| file | role |
|---|---|
| `tools/gen_moon_sky.py` | builds `MOONSKY` (+ `--debug` magenta sky) |
| `tools/pack_rt_sky.py` | packs `d64r-rt-sky.pk3` |
| `tools/scan_sky_apertures.py` | measures sky-hack gaps; the negative result above |
| `tools/ab-moon.cmd`, `ab-moonsize.cmd`, `ab-skyleak.cmd` | pre-set A/B arms |
| `tools/arms/cull-*.cfg` | the §5.1 geometry-culling arms (`ab.cmd cull-stock` / `-dark` / `-wide` / `-all`) |
| `tools/arms/moon-*.cfg` | the §5.4 medium-density arms (`moon-before` / `-now` / `-far30` / `-dens` / `-lint` / `-sharp` / `-dark`) |
| `RTGL/.../CmVolumetricProcess.comp` | the unweighted prefix sum — why CELLS, not metres, are what a shaft is counted in (§5.4) |
| `hw_bsp.cpp` | the second, unculled BSP walk — `rt_cullmode`, `rt_nocull`, `rt_segdrawn` (§5.1) |
| `rt_main.cpp` | `rt_sun_*`, `rt_moon_*`, `RT_MOON_PRESETS`, `moon` / `rt_sky_here` CCMDs, `RT_MoonSkyPitchOffset` |
| `r_sky.cpp` | sky yaw tracking in `R_UpdateSky` |
| `hw_skydome.cpp` | sky pitch offset in `SetupMatrices` |
| `hw_sky.cpp` | `rt_sky_nowalls` |
| `RTGL/.../RaygenCommon.h` | `traceSunReachesSky`, surface + indirect probe; `calcSunOnlyReservoir` + the `sunSplit` exclusion (§5.2) |
| `RTGL/.../RtVolumetric.rgen` | the probe on the **shafts** |
| `RTGL/.../VulkanDevice.cpp` | `sunRequireSky` / `sunLeakDebug` uniforms |
| `tools/arms/sprshadow-*.cfg` | the §5.3 sprite-shadow arms (`sprshadow-off` / `-on` / `-probe` / `-max`) |
| `tools/arms/spriteao-*.cfg` | the §5.3.1 contact-occlusion arms (`spriteao-off` / `-on` / `-loud` / `-disc`) |
| `rt_draw.cpp` | both sprite mechanisms: the §5.3 shadow proxies and the §5.3.1 AO decal fan |
| `hw_sprites.cpp` | the per-actor facts they run on — `m_lastthingupright`, `m_lastthinglivemonster`, `m_lastthingfloorz` |
| `RTGL/.../RsDecal.frag` | the 5 cm surface test and the albedo blend the §5.3.1 blob is built on |

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
