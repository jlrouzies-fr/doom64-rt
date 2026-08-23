# Volumetric clouds

**Status:** implemented (`rt_vclouds.cpp`, `rt_vclouds_*` pins). Written 2026-08-23 after the shell deck
was pushed as far as compositing tricks can take it (see
[`plan-fire-skies.md`](plan-fire-skies.md) §3d).

**The question this answers:** the cloud deck is eight flat discs with one
colour each. It can be tinted, gradient-tinted, backlit and flashed, and it
still cannot produce cloud with an *interior* — the churning, self-shadowing
mass in `screen/fireskylook.jpg`. What would real volumetric clouds cost here,
and how much of the volumetric machinery this project already has can be reused?

Related: [`rt-clouds-and-lightning.md`](rt-clouds-and-lightning.md) (the deck,
the bake, the traps), [`rt-smoke.md`](rt-smoke.md) (the froxel volume's real
limits), [`rt-fog.md`](rt-fog.md), [`plan-light-shafts.md`](plan-light-shafts.md).

---

## 1. Why the deck cannot get further

Three hard limits, and none of them is a value:

**No shader runs on sky geometry.** RTGL1 rasterises it into a cubemap with
`RsSky.frag`, which is a plain textured fragment shader — `getTextureSample`,
multiply by a push-constant colour, done. It has no world direction, no access
to the global uniform, and no noise. Every effect on the deck therefore has to
be expressed as *draw calls with per-draw colours*, which is why the deck's
lighting is **baked** (`gen_clouds.py`) and why the tint is a multiply.

**A multiply cannot add structure.** `SetObjectColor` gives one colour per
shell over near-achromatic art, so a shell lands at one hue with brightness
following the slice's own luminance. Contrast between dense and thin cloud can
only come from the art, and the art is a single horizontal cut through a
density field — it has no depth of its own.

**The bake is one lighting direction, chosen offline.** Beer-Lambert integrated
top-down through the field. `rt_clouds_litfrom` flips which end of the shell
stack is bright, which is a useful approximation and is not the same thing as
light actually travelling through a volume.

So the deck is a *painting of cloud lit one way*. Everything since has been
compositing around that fact.

---

## 2. Three routes, and the constraint that decides each

### Route A — raymarch inside `RsSky.frag`. **Recommended.**

Make the sky cubemap the volume. Each cubemap texel already corresponds to a
world direction; march that direction through an analytic cloud slab and
integrate density.

**The decisive fact in its favour:** the cubemap is exactly what the path tracer
samples on ray miss (`getSkyAlbedo`, `RaygenCommon.h`, `SKY_TYPE_RASTERIZED_GEOMETRY`
→ `texture(cubemap, direction)`). So clouds raymarched into it **light the level
through GI for free**, with no second representation and nothing to keep in
sync. That is the property the painted deck has too, and it is the reason the
deck was drawn as sky geometry in the first place.

**And it is cheap, because it is not per pixel.** The cubemap is 256²
(`rt_main.cpp:593`, `rasterizedSkyCubemapSize = 256`) × 6 faces = 393k texels —
about 0.4 MP, well under a 1080p frame. A 32-step march is ~12.6M samples per
frame, on a GPU already tracing paths. Resolution is decoupled from screen
resolution, which also means it costs the same at 4K.

**What it needs:**

| piece | where | note |
|---|---|---|
| world direction per fragment | `RsSky.vert` → `RsSky.frag` | the cube face's view matrix already exists in `RenderCubemap` |
| global uniform access | `RsSky.frag` | add `DESC_SET_GLOBAL_UNIFORM`; the descriptor set is already built |
| cloud params | `ShGlobalUniform` | altitude band, coverage, density, wind, tint, light dir/colour, steps |
| noise | 3D texture, or in-shader value noise | see §4 |
| the API to drive it | `RTGL1.h` + `DrawFrameInfo.h` | an `RgDrawFrameVolumetricCloudParams` on the `pNext` chain, as the shaft params do |

**What it gets right that the deck cannot:** self-shadowing (a second short
march toward the light per sample), a real phase function, silhouettes that
change as you turn, and interior structure — the mass in `fireskylook.jpg`.

### Route B — put clouds in the froxel volume. **Rejected, and worth writing down why.**

This is the obvious "reuse the volumetrics" answer: `RtVolumetric.rgen` already
has a lit, occluded, temporally-filtered medium, and adding cloud density above
a height threshold would inherit all of it — the lighting, the shadow rays, the
prefix-sum occlusion, the depth gate.

**It cannot work for a sky, for one reason: the froxel volume is camera-fitted
and reaches `rt_volume_far`, 60 m.** A cloud layer is hundreds of metres across
and needs to reach the horizon. Inside 60 m you would get cloud directly
overhead that *translates with the camera*, no clouds at the horizon at all, and
a hard edge where the volume ends. The grid is also 160×88×64, so slices are
0.94 m at the shipping reach — fine for a muzzle puff, meaningless for a cloud.

`rt-smoke.md` §10 already records both halves of this: *"The volume is
camera-fitted. A puff beyond the far plane is not represented at all"* and
*"Coarse in every shipping configuration"*.

**Where Route B IS right:** ground-level mist, smoke rolling across a courtyard,
a low fog bank the player walks through. That is a different feature and a good
one, and it is genuinely cheap — but it is not a sky.

### Route C — more shells, better art

Where we are. `rt_clouds_shells` up to 8, a bottom-up bake
(`gen_clouds.py --lit-from-below`), the fireback layer. Keep as the fallback
path and the low-spec option: Route A must be a cvar with C still runnable, for
the same reason `rt_clouds` is.

---

## 3. What Route A reuses

The point of this section is that Route A is **not** a from-scratch cloud
renderer. Most of the model already exists in this repo, tuned, with its
failures documented.

- **The density field's shape.** `gen_clouds.py` already builds a 3D FBM field
  with percentile-thresholded coverage, an erosion pass and a base-heavy
  vertical profile — and its docstring records exactly why each of those is what
  it is, including two attempts that failed. Route A wants the *same field*,
  evaluated in the shader instead of sliced. Porting the parameters carries the
  look over; re-deriving them would repeat a sweep that has already been paid
  for.
- **Beer-Lambert.** Same model the slices bake and the same one
  `RT_DrawCloudDeck` walks for moon occlusion. In a march it is just applied per
  step instead of per shell.
- **The phase function.** `RtVolumetric.rgen`'s Schlick/HG, already shared by
  the shafts and the dust gate, with `rt_volume_lassymetry` tuned on the moon
  and nine fogged maps. §5.5 of `moon-and-sky-leaks.md` records why lowering
  asymmetry is *dimmer, not flatter* — that lesson transfers directly.
- **The tint/transmit semantics.** `rt_clouds_tint` and `rt_clouds_transmit`
  mean something specific and hard-won: the tint owns the hue because the art is
  achromatic, and `transmit` is what a *fully covered* patch passes,
  independently of shell count. Route A should keep both names and both
  meanings, so the twelve deck maps' values remain readable.
- **Cloud occlusion of the moon.** `RT_DrawCloudDeck` walks the moon's own ray
  through the shells and scales `rt_sun_intensity` by the product. A march makes
  this *exact* rather than approximate — same ray, real steps — and the
  luminance-floor-not-per-channel-clamp fix (`RT_SetCloudSunTransmittance`) is
  still the right shape.
- **The per-bearing coverage table** (`g_cloudCoverAz`), which now places
  lightning strikes inside cloud. A march can answer that directly.

---

## 4. The decisions to make before writing any of it

**Noise source: 3D texture or in-shader?** A 128³ R8 texture is 2 MB and one
tap; in-shader value noise is zero memory and ~10 ALU per octave × 5 octaves ×
32 steps, which is the whole cost of the march. Uploading a baked 3D texture is
almost certainly right, and it lets `gen_clouds.py` stay the authority on shape.
**But RTGL1 has no 3D texture upload path today** — that is real new API surface
and should be scoped before committing.

**Step count and the horizon.** A slab crossed at 80° from vertical is many
times thicker than one crossed straight up. Fixed step counts either waste steps
overhead or undersample at the horizon. The standard answer is to step in
*altitude* rather than distance, or to scale step count by `1/cos`. Decide
before tuning, because it changes what a "steps" cvar means.

**Self-shadowing is the second march and it doubles the cost.** 6 light steps ×
32 view steps is the usual compromise. It is also what produces the dark
undersides that made the baked deck read as cloud at all, so it is not optional.

**Temporal stability.** The cubemap is redrawn every frame and the clouds move.
At 32 steps with a per-frame jittered offset the march will shimmer, and unlike
the froxel volume there is **no temporal history on the cubemap** to hide it. So
either march without jitter (banding, but stable), or add a small blue-noise
offset with enough steps that the banding is under the noise floor. **Do not
reach for a temporal filter here** — the cubemap feeds GI, and a filtered
environment map would smear the lighting on every surface in the level.

**Where the light comes from.** For a normal map, the moon. For a fire sky the
light is *below* the cloud — the march has to support an under-light term, which
is the honest version of `rt_clouds_litfrom`.

---

## 5. Traps this will hit, all previously paid for

- **The generated uniform header is not a tracked build dependency.** New
  `ShGlobalUniform` fields silently read zero unless `build-rtgl.cmd` clears the
  objects; `tools/check_uniform_layout.py` gates C-vs-std140 agreement. The
  scalar run must stay a multiple of four.
- **`debug::Error` exits the game.** Any new validation in RTGL1 uses `Warning`.
- **Positions crossing into RTGL1 are metres**, and a cloud altitude is a
  distance.
- **RTGL1 is a separate repo** (`deps/RTGL`, branch `doom64-rt`) needing its own
  build, and `deps/` is gitignored by root.
- **A/B cvars must not persist** — `RT_CVAR_NOARCH` for diagnostics, and both
  arms set every value.
- **Keep Route C runnable.** A cvar that switches between the shell deck and the
  march, defaulting to the deck until the march is judged better on every one of
  the twelve maps that currently use a deck — not just on the two fire families.

## 6. Scope, honestly

This is the largest single feature in the sky pipeline: a new shader path, new
API surface, probably a 3D texture upload path RTGL1 does not have, and a
re-tune of twelve shipping maps. It is not a day's work, and it should not start
until the deck-based fire sky has been judged — because if the backlit deck gets
close enough, the right call may be to spend that effort on the *ground* volume
(Route B's mist) instead, where the froxel machinery already does most of it.
