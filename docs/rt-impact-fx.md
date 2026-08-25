# Impact FX — sparks, wall debris, and the surface classification

What happens when a hitscan hits the world. A shot used to end in a puff of smoke and
nothing else; it now throws **sparks** off metal and **debris** off everything positively
labelled as something softer, with the material class coming from the same hand-labelling
pass that authors the PBR metallic/roughness values.

Cvars: `rt_spark_*` (85 of them). **Ships ON** — `rt_spark` is `true` both compiled and
pinned. (This page said "ships off" for months after that stopped being true, and so did
`tools/d64rt-pins.cfg`. Corrected 2026-08-25.)

Still planned, not built: scorch decals — [`plan-impact-fx.md`](plan-impact-fx.md).

Related: [`rt-smoke.md`](rt-smoke.md) (the puff this fires alongside, and why sparks are
*not* on the froxel volume), [`blood-persist.md`](blood-persist.md) (the decal path),
[`sprite-illumination.md`](sprite-illumination.md) (what actually casts light),
[`plan-metal-labelling.md`](plan-metal-labelling.md) (where the classification comes from).

---

## 1. The hook — `P_LineAttack`, and two bugs on the way in

`rt_smoke.cpp` has six spawn sources and **none of them is a game hook**: each infers its
trigger from a sprite frame, a pointer disappearing, or the rising edge of `extralight`.
That rule exists because those actor classes belong to the **Retribution WAD**, so nothing
may require a DECORATE edit. An impact is not in that category — `P_LineAttack` is engine
C++ this project already patches, and it is the only place in the game where a hitscan's
surface is known.

**It must be `P_LineAttack`, not `P_SpawnPuff`.** `P_SpawnPuff` is one level too late: it
receives a yaw and an `updown` int, which is why `RT_SpawnBlood_Thing` sitting beside it has
to reconstruct a fake normal and says so —

> `p_mobj.cpp`: *approximate, as trace doesn't give a normal…*

In `P_LineAttack` the whole `FTraceResults` is in scope, so sparks get a **true** surface
normal from `trace.Line` + `trace.Side` and are reflected about it. That reflection is the
entire read of the effect: it is what makes particles come *off* a surface rather than
merely appear at it.

Gates, all free at that site:

| case | behaviour |
|---|---|
| `PF_HITTHING` — flesh actor | nothing; blood owns it |
| `PF_HITSKY` / `TRACE_HasHitSky` | nothing |
| water / poison / sludge / blood | a coloured **splash**, and no vanilla PUFF — §2.4 |
| any other liquid terrain — **lava**, and `F_SKY1` | nothing, and the puff stays |
| beyond `rt_spark_far` | nothing (a **spawn** cull, §5) |
| everything else | sparks or debris by class |

Monster hitscans go through the same function and **do** fire, for the reason `rt-smoke.md`
gives about monster gun smoke: an effect that only happens to the player's shots reads as
belonging to the HUD rather than to the world.

### 1.1 `trace.HitTexture` is not filled in for walls

**This cost a round trip and is the single most important trap on the page.** Core `Trace()`
sets `HitTexture` for **floors and ceilings only**. The wall case is patched in by
`DLineTracer::TraceCallback` (`p_trace.cpp`), which belongs to the ZScript `LineTracer`
class and **never runs for `P_LineAttack`**.

So every wall hit arrived with an invalid `FTextureID`, resolved to an empty name, and
reported `'?' -> other [UNLISTED]` for the entire game. Reported from play as *"the
categories are not good, they all show sparks even uncategorised"* — which looked like a
labelling gap and was a plumbing bug.

The hook now derives it itself, mirroring that callback's tier logic:

```cpp
trace.Line->sidedef[trace.Side]->textures[txpart].texture   // 0 top, 1 mid, 2 bottom
```

**What made it findable in one pass** is that the probe prints the texture *name*, not just
the verdict. A probe that had printed only "unlisted" would have looked like missing data.

### 1.2 Determinism

The hook is in playsim, so it reads `trace` and nothing else. **No gameplay RNG is consumed
and no playsim state is written** — the renderer keeps a private xorshift. Tier 2 of the
collision calls `Trace()` and must never pass `TRACE_Impact` or `TRACE_PCross`: those fire
`SPAC_IMPACT` / `SPAC_PCROSS` line specials, and renderer particles triggering map specials
would be a gameplay change and a netgame desync in a system the player cannot see.

---

## 2. The surface classification

### 2.1 It rides the PBR labelling pass

**The `surface` field was already being authored and nothing consumed it.** The material
labeller (`tools/gen_material_labeller.py` → the page → `tools/apply_material_labels.py`,
see [`plan-metal-labelling.md`](plan-metal-labelling.md)) exports
`tools/_material_labels/<map>.json`:

```json
"SFLATDF": { "metallicDefault": 1, "roughnessDefault": 0.95, "surface": "metal"    },
"SFLATD":  { "metallicDefault": 0, "roughnessDefault": 0.8,  "surface": "concrete" },
"SMONAA":  { "metallicDefault": 0, "roughnessDefault": 0.8,  "surface": "other"    }
```

`apply_material_labels.py` merges only `metallicDefault` and `roughnessDefault` into
`textures.json` and **ignores `surface` entirely**. So the classification impact FX needs is
a by-product of work happening for another reason: this feature costs no labelling effort of
its own and improves every time that pass advances.

**Doom 64 texture names carry no meaning** — `C1`, `C102B`, `C307B1`, `SPACEAO1`. There is
no prefix rule separating metal from stone, so this can never be a predicate the way
`l_waterflag` is. It has to be an explicit per-texture list.

### 2.2 `tools/build_spark_surfaces.py` — read-only, both trees

The labelling pipeline is owned elsewhere. This script **never** writes a label file, edits
`textures.json`, or touches `apply_material_labels.py`. It reads `surface` and emits the
table the renderer loads:

    Doom64-Retribution/Retribution-RT-Materials/rt/data/spark_surfaces.txt

Written to **both** trees — the gitignored engine build dir *and* `Retribution-RT-Materials`
— for the reason `apply_material_labels.py` documents: writing only one means the change
either dies at the next build or never reaches the game.

A generation step is unavoidable regardless: `tools/` is not in the engine's lump search
path, so the game cannot read the label files directly. Given that, the shipped format is
two columns (`NAME class`) rather than JSON — no parser needed in the renderer, diffable,
and hand-editable for a one-off override while testing. A trailing `*` makes a prefix; a
bare `NAME` with no class means metal, for compatibility with the first version.

Reload in-game with **`spark_surfaces`** — no restart, no rebuild.

### 2.3 The classes

| `surface` | effect |
|---|---|
| `metal` | hot **sparks** + impact flash |
| `other` | sparks — the fallback |
| `concrete` | grey chips |
| `wood` | long thin splinters, light and tumbling |
| `dirt` | small crumbs that do not bounce |
| `flesh` | blood droplets that splat |
| `fluid` | a wide fast splash in the liquid's own colour — §2.4 |
| unknown class | parsed as `other` → sparks |
| unlisted | sparks, probe says `[UNLISTED]` |

**Sparks are the default and only a positive label opts out.** This is a reversal of the
first rule ("metal sparks, everything else is debris"), which was wrong for the state of the
data: with 83 textures labelled of 2331 at the time, *everything else* meant almost the whole game, and
one unlabelled map would have turned every surface in it to chips. Opt-in means an unlabelled
texture can only ever look un-upgraded, never wrong — and that is what makes
`rt_spark_debris` safe to ship **on**.

### 2.4 Liquids — the splash, and why there was not one (2026-08-25)

Reported from play: *"when shooting enemies the PUFF sprite appears"* and, separately,
*"I thought there were specific effects for fluid textures but I don't see them in game."*
Both were true, and the second had nothing to do with the `fluid` class being wrong.

**The class was never reached.** `P_LineAttack`'s gate refused the impact hook on any
surface the TERRAIN lump calls liquid:

```cpp
if (Terrains[trace.Sector->GetTerrain(plane)].IsLiquid) { sparkOK = false; }
```

`D64RTR_v15.WAD` ships a `TERRAIN` lump marking every liquid flat `liquid`, so
`RT_SpawnImpactSparks` was never called on a pool — **not even the surface probe**, which
lives inside the spawn function, so `rt_spark_surface_debug` printed nothing either and the
feature looked identically dead from every diagnostic. The gate also short-circuits on
`TRACE_HitWall`, which is why the three **fall** sheets (`WFALL01` / `SFALL01` / `BFALL01`,
all labelled `fluid`) were the only place the class had ever run.

**And gzdoom's own splash is dead for a separate reason.** Every `splash "…"` line in that
same lump is **commented out**, so `Terrains[n].Splash == -1` and `P_HitWater` returns at
`p_mobj.cpp:6452` having spawned nothing. Retribution also defines none of the splash actors
those lines name. So the TERRAIN route needs new actors *and* new sprite art; the debris
path needs neither, which is why it was taken.

#### The classifier

`RT_LiquidSplashId()` (`rt_spark_surfaces.cpp`) answers **0 water / 1 nukage / 2 sludge /
3 blood**, or −1. It is called from playsim, and **the same call answers both halves** — the
puff suppression and the gate — because two tests that could disagree is how a surface ends
up losing its puff and getting nothing back.

The name→family table was a **static local inside `l_waterflag`** (`rt_draw.cpp`), i.e. the
only answer to "what liquid is this" lived inside the function that sets a *primitive flag*
and nothing else could ask. It is now `RT_LiquidIdOfName()` in `rt_internal.h`. **Only the
lookup moved.** `l_waterflag` keeps its `rt_water_style` / `rt_water_liquids` gates and keeps
excluding the falls — tagging a fall `RG_MESH_PRIMITIVE_WATER` makes it refractive, and
`ASManager` then drops every `INSTANCE_MASK_WORLD_*` bit so the wall stops blocking shadow
rays. A splash sets no primitive flag, so the splash path is free to use the falls and does.

Three things that are load-bearing:

- **PREFIX, not exact.** `D64B2_01` is frame 1 of 64. Verified live: the first tagging line
  off MAP34 is `D64S2_64`, not `_01`.
- **The class is FORCED, not looked up.** `spark_surfaces.txt` labels only frame `_01` of
  each sequence, and any liquid the labeller has not reached — every Unseen Evil pool —
  would fall through to `Other` and throw **sparks off water**.
- **Lava is deliberately excluded**, by decision, not by omission. It matches neither table,
  so the terrain gate still stops it and it keeps the puff it shipped with.

#### The colour is the CREST, not the flat

| id | family | `rt_*_crest_*` | reads as |
|---|---|---|---|
| 0 | water | 140, 204, 255 | pale blue |
| 1 | nukage | 50, 150, 50 | green |
| 2 | sludge | 120, 78, 38 | brown |
| 3 | blood | 255, 115, 102 | red |

**The flat's own average would be the wrong colour**, and not by a little. The stylized
liquid shader repaints the surface from `rt_*_tint_*` to `rt_*_crest_*`, so the source art
is not what the player is looking at — a droplet sampled from it would not match the pool it
just came out of. Taking the crest makes the two agree **by construction** and follows any
retune of the liquid look for free. Same reasoning as §3.1: the spark ramp is PUFF's own
palette rather than a hand-picked orange. `rt_spark_fluid_color 0` (arm `spark-fluidtex`) is
the before-picture.

**A literal colour must escape the debris colour path**, and this is the subtle half.
`rt_spark_debris_sat` (3.0) expands chroma and then the luminance is pinned to
`rt_spark_debris_albedo × profile.albedo` — both correct for a *whole-texture mean*, which is
dull and sits at an arbitrary brightness, and both **wrong** for an exact colour. Water's
pale 140,204,255 would be pushed to raw cyan and then dragged down to a mid grey-blue. So
`Spark::litRgb` skips both and takes one honest scale, `rt_spark_fluid_albedo`; the age curve
still applies, so a droplet fades like everything else. **The flag is cleared in
`AllocSpark`**, not by each caller — a pool slot is reused, and a barrel shard or a fire-sky
ember inheriting a droplet's `true` would silently skip both corrections.

#### Tuning a splash without moving everything else

Every axis of a debris particle is `rt_spark_debris_* x the class row`, and **both halves
are shared**: the cvar moves concrete, wood, dirt, flesh and fluid together, and the row can
only be changed by editing `RT_DEBRIS_PROFILES` and rebuilding. Liquids are the one class
still being iterated on, so they get a third multiplier of their own:

| cvar | default | on top of |
|---|---|---|
| `rt_spark_fluid_count` | 1.0 | `rt_spark_debris_count` x 2.4 = ~14 droplets |
| `rt_spark_fluid_size` | **0.5** | `rt_spark_debris_size` x 0.5 -> **0.0125 m** |
| `rt_spark_fluid_life` | **0.1** | `rt_spark_debris_life` x 0.3 -> **0.6 s** |
| `rt_spark_fluid_speed` | 1.0 | `rt_spark_debris_speed` x 1.35 = 4.6 m/s |
| `rt_spark_fluid_gravity` | 1.0 | `rt_spark_debris_gravity` x 1.0 |
| `rt_spark_fluid_bounce` | 1.0 | `rt_spark_debris_bounce` x 0.08 |
| `rt_spark_fluid_spread` | 1.0 | `rt_spark_spread` — **no class row behind it**, see below |

Five ship at 1.0. **Size and life do not**, and that is the first thing these knobs bought:
judged in play the same day they were added, a droplet at 1.0 was chip-sized and lay around
for six seconds, which reads as *debris that happens to be blue*. At 0.0125 m and 0.6 s it
reads as spray. Nothing else moved -- and nothing else *could* move, which is the point: the
same retune through `rt_spark_debris_size` would have taken every concrete chip in the game
with it.

Note life also sets the cost. Live count is spawn rate x lifetime, so 0.1 makes the splash
ten times cheaper as well as ten times briefer.

Three things they are:

- **Applied at the point of use, not by doctoring the profile.** Two of the seven — gravity
  and bounce — are read in the SIMULATION every tic from `ProfileFor(sp.surf)`, not at
  spawn, so returning an adjusted profile would have meant a mutable static standing in for
  a `constexpr` table, and a printed row that no longer matched what the sim used. The row
  stays the honest statement of what the class *is*; the cvar states what you changed.
- **Keyed on `SurfKind::Fluid`, not on "was this a liquid hit."** So the three wall falls and
  anything else labelled `fluid` move with them. The knob's name is the class.
- **`_spread` is the odd one and the reason it is in the list.** `rt_spark_spread` is read
  raw at `rt_sparks.cpp:596` and shared by sparks and every debris class alike — there is no
  profile field for it. So the fluid row's own comment, *"thrown wide"*, described something
  **nothing implemented**. This is what makes it true.

`rt_spark_max` is worth a thought alongside `_life`: live count is spawn rate x lifetime, so
a large rise in one wants the pool raised with it (§5).

#### The puff

`rt_liquid_nopuff` (on, pinned) skips `P_SpawnPuff` for the world-hit branch when the surface
is one of the four. `nointeract` is excluded — that path *guarantees* a puff and returns it to
the caller; it is an aiming probe, not a visible impact. Leaving `puff` null is already safe
downstream: `puff->radius` is inside the skipped block, and the `P_HitWater` and decal
branches null-check.

Note this cvar lives in **`rt_cvars.inc`**, not beside `rt_blood_repl` in `p_map.cpp`, and is
reached with a local `EXTERN_CVAR` the way `p_mobj.cpp` reaches `rt_fluid`. `check_pins.py`
only knows the cvars in that file, and it reports a pin naming anything else as
**"PINNED BUT NO SUCH CVAR (silently does nothing)"** — which is exactly the class of silent
failure the pins file exists to prevent.

#### Two diagnostics that were lying about fluid

Both fixed in the same pass, because either one would have cost a round trip here:

- The probe computed `pDebris` as `pSurf == SurfKind::Concrete`, while the real decision has
  always used `SurfThrowsDebris()`. So it printed **"sparks"** for wood, dirt, flesh and
  fluid — every other class that does in fact throw debris.
- Fluid fell into `s_dbgOther` in the per-second tally, so a splash appeared in **no count
  anywhere**. It now has its own column.

#### Ruled out: the RTGL1 fluid sim

`RT_SpawnFluid` takes **no colour** — the fluid colour is frame-global
(`RgStartFrameFluidParams::color`), so every particle in flight would recolour at once — and
`rt_fluid` is pinned **false**. `blood-persist.md` already says do not re-investigate.

### 2.5 Two lessons from the seeding

The first table was seeded from `metallicDefault >= 0.5` and produced 56 "metal" textures.
The authored labels disagree **in both directions** — `SFLATAC` and `SFLATAF` carry a high
`metallicDefault` and are labelled **concrete**. `metallicDefault` was authored for
*reflectivity*; `surface` for *what the thing is made of*, and only the second is the
question being asked.

**Liquids must be excluded from any metallic-derived seed.** `FWATER*`, `BLOOD*` and
`SLIME*` all carry `metallicDefault 1.0` — for reflectivity, not because they are metal. The
liquid gate in `P_LineAttack` excludes them anyway, but a table *claiming* water is metal
would be a trap for the next reader.

Note [`rt-feature-ideas.md`](rt-feature-ideas.md) #4: a full metal/non-metal PBR pass was
**attempted and rejected** as infeasible. This is a materially easier question — a class per
texture, no roughness accuracy required, only for surfaces the player shoots — which is why
it is worth doing. But the rejection is why the *unlisted* default has to stay good rather
than assuming the list is ever complete.

---

## 3. What a particle is

### 3.1 Sparks — additive, rasterized, self-luminous

One flat, single-coloured, camera-facing quad. No texture, no gradient, no art assets.

**Colour is `PUFF`'s own palette**, lifted from the `PLTE` of `PUFFA0`–`PUFFF0` in
`D64RTR_v15.WAD`: `f8f8b0 → b8a868 → 786040 → 604820 → 482818 → 301808 → 180800`. A spark
therefore cools through exactly the colours of the sprite it fires alongside — the two match
by construction rather than by eye. That sprite is why the work started here at all: 16 px
wide, 4-bit indexed, ≤ 4 real colours a frame, and Retribution overrides it to
`RenderStyle Normal` so it is fully opaque.

**The additive blend is the feature, not the bug.** `RasterizedDataCollector::ToPipelineState`
turns any TRANSLUCENT primitive with a non-zero `emissive` into ADDITIVE (`SRC_ALPHA`,
`ONE`). For a translucent *sprite* that is the bug behind `rt_spectre_alpha` reading as inert
(pitfall 32); for a hot spark it is exactly right, and it is why this needs no art and no
alpha tuning.

The honest cost: a translucent primitive is a **rasterized overlay kept out of the
acceleration structure**, so sparks appear in no reflection and cast no GI. §4 is the traced
half.

### 3.2 Debris — opaque, ray-traced, lit by the room

Reported from play: *"debris do not apply environment light — debris in a dark room are
still bright."* Correct, and structural. `RsWorld.inl` shades the whole raster path as:

```glsl
outColor.rgb *= max( vec3( 1 ), tonemapping.avgLuminance );
```

No light sampling of any kind — a primitive is its vertex colour multiplied by *at least* 1.
`localLightsIntensity` and `classicLight` do not help; they belong to other paths.

**The first fix was wrong, and how it was wrong is the useful part.** It multiplied the
sector light level into the vertex colour by hand (the `rt_ghost_lightscale` approach). That
reads the *painted* lightlevel rather than the traced result — a known approximation — but it
also could not escape the other half of that line: **`avgLuminance` is eye adaptation**. It
decays over seconds, so chips visibly took time to darken on entering an unlit room even
though the sector term was instant. Reported back as *"debris take time to get dark as the
room"*.

> **No engine-side multiply can fix a term the engine cannot see.** The exposure average is
> not exposed through the API and can only ever brighten. The answer was to stop being
> rasterized.

`VulkanDevice::IsRasterized` puts a primitive in the acceleration structure when it has **no
`TRANSLUCENT` flag** and a primitive alpha ≥ `MESH_TRANSLUCENT_ALPHA_THRESHOLD` (0.98).
Debris satisfies both, so the path tracer lights it properly — instantly, with shadows, and
visible in reflections. The three workaround cvars were deleted; dead knobs are worse than
none.

Two consequences that are not optional:

- **Debris fades by SHRINKING, never by alpha.** Dropping alpha below 0.98 silently demotes
  the whole batch back to the rasterized overlay — back to fullbright — for the last part of
  every chip's life. The final quarter of the life shrinks the quad instead; alpha stays 1.
- **A chip's shading normal is the surface it came off**, stored at spawn. The quad stays
  camera-facing so a chip is never edge-on and invisible, but a camera-facing *normal* on
  traced geometry swings the lighting as the player turns and reads as flicker.

**A spark glows; a chip is lit.** That is the clean line between the two, and the reason they
are separate batches: the blend mode is chosen by `emissive`, and additive can only ever
*add*, whereas a chip must be able to be darker than the wall behind it.

#### The traced albedo is PER-PRIMITIVE, not per-vertex

Moving debris into the acceleration structure fixed the lighting and broke the colour, and
the second half was silent. `HitInfo.inl`:

```glsl
// if no albedo textures, use primary color
dst = mix( unpackUintColor( layerColors[ 0 ] ).rgb, dst, float( hasAnyAlbedoTexture ) );
```

`layerColors[0]` is `RgMeshPrimitiveInfo::color`, per **geometry**. `ShVertex` really does
carry a `color` field, so the per-vertex data arrives intact and nothing warns — the traced
albedo path simply never reads it. The **rasterized** path (`RsWorld.inl`) *does* use vertex
colour, so the same geometry changes meaning as it moves between the two. Debris was correct
while rasterized and went uniformly white the instant it became BLAS geometry, with
`prim.color` still at `RG_PACKED_COLOR_WHITE`.

**Chips were white by construction**, which is why the saturation fix, the tint and
`rt_spark_debris_albedo` all failed to move them — and why the arm that settled it set albedo
to **0.02** and they *stayed white*. A surface reflecting 2 % of what hits it cannot read as
white under any light, so one run eliminated every brightness hypothesis at once.

**So debris is batched by COLOUR.** A primitive carries exactly one albedo, and per-particle
colour needs either one primitive per particle (thousands of uploads and BLAS entries) or
particles grouped by colour. Grouping is far cheaper and the quantisation is invisible: chip
colour comes from a handful of wall textures and a slow age ramp, so a room uses a few of the
32 buckets. The key carries the class as well as the colour, so a class that later names a
sprite still gets its own material.

Two constraints on the bucket colour, both load-bearing:

- **Packed alpha stays 1.0.** Below `MESH_TRANSLUCENT_ALPHA_THRESHOLD` (0.98) RTGL1 demotes
  the primitive back to the rasterized overlay — i.e. straight back to fullbright, the thing
  this whole path exists to escape.
- **At the bucket cap a chip folds into bucket 0** rather than being dropped. A slightly
  wrong colour is a far smaller artefact than debris vanishing.

#### PBR is not the whiteout lever, and the header says so

Asked in play, after the chips still blew out: *"should we give them light absorption
property? like PBR?"* Right instinct, wrong lever. `RgMeshPrimitivePBREXT` exists and
`ASManager.cpp:885` consumes it for exactly this geometry — but it documents its defaults as
**roughness 1.0, metallic 0.0** when no roughness-metallic texture is present, which debris
has none of. The chips were *already* the roughest, least-shiny dielectric available, and a
rough diffuse surface returns `albedo × E / π` whatever its roughness. Lowering roughness
makes them **shinier, not darker**.

It is set explicitly anyway (`rt_spark_debris_rough` / `_metal`), because "no material at
all" leaves the `ASManager` fallback unstated, and an unstated default is exactly the class
of thing that costs days here. But it was never the fix — the albedo plumbing above was.

#### Scattered normals

Every chip used to carry the **surface** normal it came off. The flashlight is at the camera
and chips fly toward the camera, so `N·L ≈ 1` for every chip at once — maximum irradiance,
identically, on all of them. Reported as debris going white under the flashlight, and it is
a genuinely separate cause from the albedo bug above; both were live at the same time.

Normals are now scattered per particle, still biased **35 %** toward the surface normal: a
chip did just come off that wall, and a uniform sphere of normals faces half of them into it.
Real rubble has normals pointing everywhere, so only some fragments catch a light.

### 3.3 Chips take the colour of the wall

Averaged with gzdoom's own `averageColor()` over the texture bitmap — the same call
`FGameTexture::GetGlowColor` uses, with one deliberate difference: `GetGlowColor` passes
`maxout = 153`, which **normalizes** so the peak channel hits that value, brightening a dull
texture into a saturated glow hue. That is wrong for an albedo, so this passes **0** for the
honest mean.

Only possible because of the §1.1 fix — without a valid `FTextureID` there was nothing to
sample.

- **Cached per texture.** `GetBgraBitmap` decodes the whole image; far too expensive per
  impact, let alone per particle. Computed once on first hit and kept.
- **The ramp stays as the age curve.** The texture supplies the *hue*, the ramp supplies how
  it darkens over life. Replacing the ramp outright gives one flat colour for 20 s; using
  only the ramp gives grey rubble off a rust-red wall.
- **Normalized to a target luminance** (`rt_spark_debris_albedo`, 0.30). Doom wall art
  averages wherever it happens to sit and some textures are near-white; using the mean raw
  would put an albedo of 0.8 on a lump of concrete — which is precisely what made the first
  ramps read as *"too bright colors"*. **These ramps are albedos, not pixel colours**, and
  that changed meaning silently when debris moved to traced geometry.
- **Chroma is expanded** (`rt_spark_debris_sat`, 3.0) — see below.

**A whole-texture mean is a chroma killer, and that is the fourth bug.** Reported from play:
chips are grey off a wall that is *"definitely beige / orange"*. The pipeline was working;
the data was too dull to use. Measured, with the probe printing the sampled value:

| texture | mean | chip at sat 1 | at sat 3 | at sat 5 |
|---|---|---|---|---|
| `SPACEAL` | `#574D4B` | `#544B49` | `#644741` | `#734339` |
| `SPACECH1` | `#504848` | `#534B4B` | `#604747` | `#6D4444` |

Both means *are* warm — R > G > B — but by about **14 %**, because beige highlights average
against shadow and black gaps and collapse toward neutral. Normalizing luminance scales all
three channels equally and faithfully preserves that 14 %, so the chip came out grey.

**gzdoom hits the identical wall and solves it the other way:** `GetGlowColor` passes
`maxout = 153` to `averageColor` precisely because a plain mean is too dull to be a glow
colour. That normalizes the **peak channel**, which also blows brightness out — right for a
glow, wrong for an albedo. So this expands chroma about the pixel's own luminance instead,
leaving brightness to `rt_spark_debris_albedo`, and the two corrections stay independent.

**The general lesson:** two of the four bugs on this page were an input that looked
reasonable — a mean that *is* warm, a `FTextureID` that *is* a valid type — feeding maths
that was correct. Instrumenting the value's whole path found both in one run each;
adjusting magnitudes would have found neither.

### 3.3a Contact occlusion under settled debris

Straight from [`sprite-shadows-and-ao.md`](sprite-shadows-and-ao.md) §2: with no contact term
a chip reads as hovering, and a cast shadow cannot supply one because a flat fragment lit at
a shallow angle throws almost nothing. A blob answers *is something touching this floor*,
which has the same answer from every light direction.

An RTGL1 decal multiplied into the floor's albedo, so it scales with the light already there
and is invisible in an unlit room, and it can never occlude or be hit. All three of that
document's hard-won rules apply unchanged: **world-space verts with identity transform** (the
`RsDecal.vert` trap), **a single fan** with no high-alpha ring, and **`emissive = 0`** or the
decal shader falls back to `ldrEmis = albedo` and the blob glows.

**Only SETTLED chips get one.** The claim a blob makes is that the thing is touching this
floor, and a bouncing chip is not — the same honesty `rt_sprite_ao_fade` buys for a flying
enemy.

**One primitive per blob, and that was a bug fix.** The first version batched every fan into
a single decal primitive and drew *lines reaching away from the blobs*. That version is
geometrically sound — no triangle spans two blobs, each fan interpolates only its own
vertices — and the documented 5 cm grazing-floor limit was ruled out first with a distance
cull (`rt_spark_debris_ao_dist`, kept: it is a real limit). What actually fixed it was
matching the shape of the implementation that works: the sprite AO uploads one fan per actor.
Distinct `uniqueObjectID` per blob, since RTGL1 keeps one upload per ID and the **later** one
loses. Bounded by `rt_spark_debris_ao_max` (64), because a decal upload is not free and a
20 s debris life settles far more chips than are worth one each.

**The generalisable part:** when a novel structure misbehaves and the obvious explanations
have been ruled out by test, adopt the shape of the known-good implementation rather than
reasoning further about why the novel one *should* work.

### 3.4 Two style modes

`rt_spark_style`: **0 pixelated**, **1 realistic** (default).

| | pixelated | realistic |
|---|---|---|
| position / size | snapped to `rt_spark_grid` | continuous |
| colour | hard step through 7 palette entries | the same 7, interpolated |
| spark shape | square | stretched along its own velocity |
| debris shape | square | tumbling, irregular aspect |

**Realistic is deliberately restrained**: same ramp, same sizes, no bloom of its own, no
motion blur, and the streak is **capped** by `rt_spark_streak` (2.5×) rather than being
proportional to speed. Uncapped, a fast spark becomes a long thin line that reads as tracer
fire — `spark-realloud` is that failure, kept so the shipping value is visibly a choice. The
ramp is not swapped for a "realistic" one: this is the Doom 64 palette drawn smoothly, not a
different palette.

**Grid snapping is world-space, never screen-space.** Screen blocks crawl as soon as the
camera turns and the eye reads that as noise rather than style — the same reasoning as
`rt_smoke_stylize_grid`.

No filtering work was needed: `rt_smoothtextures` defaults false so the game is already
`RG_SAMPLER_FILTER_NEAREST`, and with no texture bound there is nothing to filter.
`rt_ef_vintage` is **not** the tool — it is whole-screen pixelization.

### 3.5 The per-class profile table

`RT_DEBRIS_PROFILES` in **`rt_spark_surfaces.cpp`** (it moved out of `rt_sparks.cpp` when
that file passed 4000 lines; this page said `rt_sparks.cpp` until 2026-08-25), indexed by
class. Same shape and the same reason as
`RT_SMOKE_PROFILES`: rows are **multipliers** on the `rt_spark_debris_*` cvars, so tuning a
cvar still moves every class together and a row states only how that class differs. Concrete
is the reference row of all 1s.

| class | reads as |
|---|---|
| concrete | blocky chips, heavy, barely bouncy |
| wood | splinters — aspect **0.12–0.35**, 0.62× gravity so it floats down further, 2.2× spin. Note these are genuinely line-shaped (~8:1); a "line" attached to a chip is this, not the AO |
| dirt | crumbs — 1.8× count, small, **0.12× bounce** so it hits and stops, high friction |
| flesh | blood droplets — fat, slow, **0.05× bounce**, short-lived |
| fluid | splash — 2.4× count, small and fast, thrown wide, **full texture colour** |

**Aspect is absolute, not a multiplier.** A splinter is 0.12–0.35 and a crumb is 0.7–1.4, and
no scaling of one produces the other. **Fluid's tint is 1.18**, deliberately over 1 so it
clamps at full texture colour — "coloured like the liquid" means the neutral ramp must not
show through at all.

**Concrete, wood and dirt share one lifetime** (the full `rt_spark_debris_life`). Dirt was
briefly 0.55× on the reasoning that loose earth does not lie around; in play that just made
dirt vanish while the chips beside it stayed, which reads as the effect failing rather than
as a material difference. The three solid classes now differ only in how they *move*.

**Each class has its own batch**, so a class can carry its own material. All profiles have
`texture = nullptr` for now, including flesh: an RTGL1 material only exists once gzdoom has
actually drawn that texture, so naming a sprite the level has not shown yet gets the 1×1
white fallback, and white blood is worse than red untextured. Wire `BLUD` only after
confirming it resolves.

---

## 4. Lights — the traced half

`emissiveMult` is screen glow and lights nothing; a sprite casts only via `lightIntensity` +
`lightColorHEX`, and neither applies to an engine-generated quad. So the cast light is
analytic, following `RT_UploadFlameLights()`: candidate collection, `std::partial_sort`
nearest-first, truncate, then `RgLightSphericalEXT` + `RgLightInfo` → `rgUploadLight`.
**Positions in metres** (`ONEGAMEUNIT_IN_METERS`), or the light lands 32× out.

**Two sources.** One short flash per *impact* (`rt_spark_light`), and a capped set riding the
flying sparks themselves (`rt_spark_glow`).

### 4.1 The glow, and why it was missing

Reported from play: *"the sparks themselves don't seem to emit any light, only the impact
location."* Accurate, and structural:

> **Screen brightness and cast light are different channels and nothing crosses between
> them.** The particles are an additive *rasterized* overlay, kept out of the acceleration
> structure. However bright a spark is on screen it is not a light source, and no value of
> `rt_spark_bright` can make it one.

`rt_spark_glow_max` (8) caps how many flying sparks carry a light, ranked by distance
**biased by age** — without the age term the cap fills with settled embers while the shower
you just made stays dark. A handful glowing among many reads as all of them glowing.

**Never one per spark.** A super-shotgun is 20 impacts × 8 sparks = 160 moving lights in a
frame, which is `rt-lighting-practices` §20 exactly.

### 4.2 Two ID rules, both load-bearing

- `SparkGlowId_Base` is **keyed on the spark**, not the candidate slot. A slot is reassigned
  as sparks die, so a slot-keyed light would teleport across the room between frames — worse
  for ReSTIR than dying, because RTGL1 carries the old reservoir to a new place. Each spark
  has a monotonic `sid` for this.
- **`.pNext` must point at the `RgLightSphericalEXT`.** Omitting it makes RTGL1 warn
  `"Couldn't find RgLightDirectionalEXT, RgLightSphericalEXT, … (uniqueID=N)"` and **drop the
  light**. Every other field is valid so nothing else complains. This shipped broken exactly
  once and the symptom was §4.1: the impact flash set `pNext` and the glows did not.

**Debris never glows and never flashes.** A chip of stone is not hot; if debris lights the
room, the classification is wrong.

### 4.3 Brightness has exactly one lever

The emission line is `outColor.rgb += ldrEmis * ldrColor.a * emissionMaxScreenColor`, and two
of the three are dead ends:

- **`prim.emissive` is a no-op above 1** — `Utils::Saturate`d, and the batch already ships at
  1.0. Same trap as pitfall 15.
- **`emissionMaxScreenColor` is `rt_emis_maxscrcolor`** — global to every world emissive,
  pinned at 3, and raising it clips saturated colours (pitfall 12).
- **`ldrEmis` is the palette colour**, already `f8f8b0` at the hot end; scaling clips to white
  and loses the PUFF match.

That leaves **vertex alpha**, which `rt_spark_bright` scales. It is not a linear gain: alpha
is 8-bit, so a multiplier above 1 cannot raise the peak, it **widens** it —
`a = clamp(bright · (1 − t²), 0, 1)`. At 2.0 a spark holds full brightness for the first ~70 %
of its life instead of dimming from birth. Integrated that is ~1.3×, not 2×; the perceived
change is larger because the spark stops visibly decaying.

`rt_spark_light_intensity` is the half that really doubles — an analytic light has no ceiling.

---

## 5. Simulation, collision and the pool

**Collision shipped in v1 rather than as polish**: a particle that sinks through the floor is
not a spark, it is a fading dot. Three tiers, cheapest first.

**Tier 1 — floor and ceiling, every step.** `PointInSector` + `floorplane`/`ceilingplane
.ZatPoint`, smoke's idiom. Where a smoke puff *clamps* and loses vertical velocity, a
particle **reflects** (per-class restitution), with friction bled off the tangent.

**Tier 2 — walls, only when the step leaves its sector.** The sector pointer is already
fetched for tier 1, so "did it change?" is free and false for most steps. Only then is the
movement segment traced with `Trace()` and reflected off `res.Line`. `ActorMask` empty so
particles pass through monsters; `TRACE_NoSky` so one that reaches sky dies. **This is the
only unbounded cost in the feature**, hence `rt_spark_trace_max`; profile a super-shotgun
into a *corner*, not a quiet corridor.

**Tier 3 — settle.** Below `rt_spark_rest` and on the floor, velocity is zeroed and the
particle lies where it fell. Its tumble angle is baked into `phase` and `spin` cleared, so it
does not snap back to its birth orientation on landing — at a 20 s life that would be the most
visible thing debris does.

**Spawn must offset along the normal** (2 cm), or tier 2's first trace reports an immediate
self-hit and the particle sticks to the wall it should be leaving. `RT_SpawnBlood_Thing`
offsets for the same reason.

### 5.1 Eviction is oldest **of its own kind**

Sparks live ~5 s and debris ~20 s in one shared pool. A plain oldest-out rule evicts **debris
almost every time** — it is reliably the older population — so chips would be culled within a
second or two and their 20 s life would be a number that never happened. Evicting within the
kind bounds each population by its own spawn rate. Same shape as the ambient-first rule in
`RT_SpawnSmokePuffs`.

**The pool follows the lifetimes.** Live count is spawn rate × lifetime, so the 1.1 → 5 s and
1.4 → 20 s changes took `RT_SPARK_HARDMAX` to 4096 and `rt_spark_max` to 2000. This is the
same coupling `rt_smoke_life` documents: on this kind of effect "more" is more parcels *and*
the budget to hold them, never lifetime alone.

**The distance cull is at SPAWN, not render.** Eviction is oldest-out while the interesting
particles are the ones in front of your face, so a firefight across the map would otherwise
push your own impact out of the pool.

---

## 6. Console output

Three levels, because "is the table loaded", "what am I shooting" and "which texture exactly"
are different questions and only the last wants a line per bullet.

**1. Once at load**, via `RT_DiagPrintLevel()` — console and `rt-console.log` always, the
notify overlay only under `rt_verbose 1`:

```
rt_spark surfaces: 843 entries from rt/data/spark_surfaces.txt  (metal 431 -> sparks, concrete 332 + other 23 -> debris)
rt_spark surfaces: 'rt/data/spark_surfaces.txt' NOT FOUND -- every surface will classify as 'other'. Run: python tools/build_spark_surfaces.py
```

**That failure line is why this section exists.** The first version used gzdoom's **lump**
filesystem for a path that lives **on disk** — `rt/data/` is RTGL1's directory, and the lump
system holds only the IWAD, the `-file` PWADs and `rt/wad`. So the lookup always returned −1.
Worse, it treated "not found" as a silent normal state on the reasoning that an empty table is
harmless. It is harmless *and* indistinguishable from a feature that does not work. **A load
that can fail must say so.** Every other RT reference to that tree reads it as a plain
relative path (`std::filesystem::exists("rt/bin_remix/…")`); the launcher does `cd /d
"%ENGINE%"`, so relative resolves.

**2. Per second under `rt_spark_debug 1`** — the A/B/C ladder plus a class breakdown:

```
rt_spark 1s: A/hit 22 impacts (0 rejected: far)  B/spawn 130 sparks, 412 live of 2000  C/sent 412 quads, 9 lights of 12  (4 wall traces)
  types: metal 12 (sparks)  concrete 31  other 8  UNLISTED 44   [rt_spark_debris 0 -- all of these spark]
```

The trailing note appears whenever `rt_spark_debris` is off — the other way this reads as
broken, where the classification is correct and everything sparks by configuration.

**3. Per impact under `rt_spark_surface_debug 1`** — `'SDFLTAB' -> concrete (debris)`.
**Pinned 0**, and turned on by the arms that want it (this page claimed it was pinned on;
it is not). It runs **even with `rt_spark`
off**: it is a surface *identification* tool in the same family as `whatsthat` and
`rt_tex_probe`, and gating it on an effect that ships off would have made the pin print
nothing, ever.

**`sparks` and `spark_surfaces` print the worklist** — the distinct texture names you have
actually hit that are not in the table. Gathered by *playing* rather than by auditing 2331
textures, ordered by what the player shoots at.

The ladder exists because **"nothing spawned" and "spawned but not drawn" are identical on
screen**, and this project has lost sessions to not being able to tell them apart.

---

## 7. How to judge it

`.\tools\ab.cmd spark-<arm> [map]` — arms are cfgs in `tools/arms/`, each self-contained
(every `rt_spark_*` value stated, so no arm inherits another's ini leftovers).

| arm | isolates |
|---|---|
| `spark-fat` | **run first.** 10× count, 4× size, no gravity. If this shows nothing the problem is plumbing, not values |
| `spark-on` / `spark-off` | the shipping numbers, and the before |
| `spark-pixel` / `spark-real` | the two style modes. Judge **while moving** |
| `spark-realloud` | `rt_spark_streak 6` — realistic overdone, the thing not to ship |
| `spark-nolight` / `spark-noglow` | both light sources off / impact flash only |
| `spark-glowmax` | 32 glows at 2× — the **cost** probe, not a candidate |
| `spark-nogrid` | unsnapped motion, hard palette: isolates snapping from colour |
| `spark-nocollide` | all three tiers off — what "not worth shipping" looks like |
| `spark-still` | no gravity, long life, high restitution — the arm for reading collision |
| `spark-debris` / `spark-nodebris` | classification on with the probe, and off |
| `spark-debrisheavy` | more/bigger/longer chips, to confirm they darken **instantly** |
| `spark-debrisdark` | albedo 0.02 — the **absurd arm** that proved the traced albedo was per-primitive |
| `spark-fluidfat` | **run first for liquids.** 10x droplets, 4x size, no gravity |
| `spark-fluid` / `spark-nofluid` | the liquid splash, and the before |
| `spark-fluidtex` | droplets take the flat's average instead of its crest — the colour A/B |
| `spark-puff` | splash AND the vanilla puff, to see what `rt_liquid_nopuff` removes |
| `spark-debug` | the staged ladder |

**Where:** the smoke lab, not a real level first — `python tools/build_smoke_lab.py`, then
`tools/smoke-lab.cmd`. **MAP97 dark** for the glow and whether the arc reads as a bounce;
**MAP96 bright beige** for whether an additive spark is visible against a *lit* wall. That
second case is the one smoke went several rounds without reproducing: a bright particle on a
dark wall is the easy one.

For LIQUIDS: **MAP34, the fluid sampler** — the one map with all four. `rt_blood_goto`,
`rt_sludge_goto` and the matching `*_autogoto` cvars put the player on a pool without
hunting for one. Water splashes pale blue, poison green, sludge brown, blood red, and
**lava is the control**: it must still show a puff and throw nothing.

Then in play: a wall, a floor, a ceiling; a monster (**no** particles — blood owns flesh
actors); the sky (none); a shotgun blast to watch the cap hold. For collision — a wall above a
staircase (particles should come down the steps), a ledge edge (they should go over), a closed
door (none through).

**Before any launch:** `python tools/check_pins.py rt_spark_` — every pin restates its
compiled default, so either half moving alone is an error. A pin overrides the compiled
default, and the two disagreeing is how the rocket-smoke numbers were "lowered" for a week
without taking effect.

---

## 8. Known limits

- **Sparks appear in no reflection and cast no GI** — inherent to the additive raster overlay.
  Only the analytic lights are traced. Debris does not pay this; it is opaque and traced.
- **3D floors are not handled.** Tier 1 reads only the sector's own planes, so a particle
  falls through a 3D floor. Real since 2026-08-23: the 3D floors (209 of them, mostly
  bridges) are back in the game now that the engine freeze behind the old strip is fixed.
- **Debris colour is the texture's flat average**, not a sample at the impact point. A wall
  that is half rust and half steel gives one blended chip colour.
- **Scope is hitscans.** Projectile and explosion impacts produce nothing;
  [`plan-impact-fx.md`](plan-impact-fx.md) is that territory.
- **`flesh` and `dirt` are untested** — zero entries in the labelling as of writing.
- **Liquid splashes are hitscan only**, like everything else on this page. A rocket into a
  pool still does nothing; that is `plan-projectile-impact-fx.md`.
- **A splash does not disturb the surface.** No ripple, no ring, no displacement — the
  droplets come off a flat that goes on animating exactly as it was.
- **Lava throws nothing and keeps its puff**, by decision (2026-08-25), not by oversight.
- **The classification is far from complete** (843 of 2331 textures), and the `[UNLISTED]`
  worklist is the way to advance it.
