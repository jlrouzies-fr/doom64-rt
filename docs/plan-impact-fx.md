# Impact sparks and scorch decals

**Status:** sparks **implemented** (`rt_spark_*`, shipping OFF pending play judgement).
Scorch decals still planned, not started.

**Why it was worth doing:** every shot in this game used to end in a puff of smoke and
nothing else. Under path tracing a spark is a small moving emitter that lights the wall it
bounces off, and a scorch mark is persistent evidence that a fight happened here.

Related: [`docs/rt-smoke.md`](rt-smoke.md) (the froxel medium, and why sparks are *not* on
it), [`docs/blood-persist.md`](blood-persist.md) (persistence, lifetimes and the decal
path), [`docs/sprite-illumination.md`](sprite-illumination.md) (what actually casts light).

---

## 1. Sparks — shipped

### 1.1 The hook, and why this plan was stuck on it

The original version of this document said sparks would be "another entry in that list" of
`rt_smoke.cpp`'s six spawn sources. That was the wrong frame, and it is what kept the
feature from starting.

`rt-smoke.md` §3 states that **none of those six is a game hook** — each infers its trigger
from a sprite frame, a pointer disappearing, or the rising edge of `extralight`. That rule
exists for one reason: the actor classes (`64Rocket`, `64ZombieMan`, `64ExplosiveBarrel`)
belong to the **Retribution WAD**, so nothing may require a DECORATE edit or a ZScript.

**An impact is not in that category.** `P_LineAttack` is engine C++ this project already
patches, and it is the only place in the game where a hitscan's surface is known. So the
spark hook is a real one, in `p_map.cpp`, in the non-actor branch beside the existing
`P_SpawnPuff` call.

**And it must be `P_LineAttack`, not `P_SpawnPuff`.** `P_SpawnPuff` is one level too late:
it receives a yaw and an `updown` int, which is why `RT_SpawnBlood_Thing` sitting beside it
has to reconstruct a fake normal and says so in a comment —

> `p_mobj.cpp`: *approximate, as trace doesn't give a normal…*

In `P_LineAttack` the whole `FTraceResults` is still in scope: `trace.HitPos`,
`trace.HitVector`, `trace.HitType`, and `trace.Line` + `trace.Side`, which give a **true
wall normal** (the perpendicular of the linedef delta, flipped by the side). Sparks are
reflected about that normal, and **the reflection is the entire read of the effect** — it
is what makes them come *off* the surface rather than merely appear at it.

Gates, all free at that site:

| case | behaviour |
|---|---|
| `PF_HITTHING` — flesh | no sparks; blood owns it |
| `PF_HITSKY` / `TRACE_HasHitSky` | no sparks |
| liquid flat (`Terrains[...].IsLiquid`) | no sparks — a bullet into nukage is a splash |
| beyond `rt_spark_far` | no sparks (a **spawn** cull, see below) |
| everything else | sparks |

Monster hitscans go through the same function and **do** spark, for the reason `rt-smoke.md`
§3 gives about monster gun smoke: an effect that only happens to the player's shots reads as
belonging to the HUD rather than to the world.

**The hook is in playsim, so it reads `trace` and nothing else.** No gameplay RNG is
consumed and no playsim state is written; the renderer keeps a private xorshift. Doing
either would desync demos and netgames invisibly.

### 1.2 What a spark is

One flat, single-coloured, camera-facing **square** in world space. No texture, no gradient,
no falloff, no art assets: the quad *is* the pixel. All live sparks go up as **one batched
primitive per frame**.

Four rules give it the stylized look:

1. **One square, one colour.** A gradient would make it a glow, not a pixel.
2. **Size snaps to a world grid** (`rt_spark_grid`, default 1/32 m = 1 map unit).
3. **Position snaps to the same grid**, so a spark steps like an animated sprite instead of
   sliding. **World space, never screen space** — screen-space blocks crawl as soon as the
   camera turns and the eye reads that as noise rather than style, the same reasoning as
   `rt_smoke_stylize_grid`.
4. **Colour is quantized to `PUFF`'s own palette**, indexed by age and deliberately **not
   interpolated**: `f8f8b0 → b8a868 → 786040 → 604820 → 482818 → 301808 → 180800`, lifted
   from the `PLTE` of `PUFFA0`–`PUFFF0` in `D64RTR_v15.WAD`. A spark therefore cools through
   exactly the colours of the sprite it fires alongside — the two match by construction
   rather than by eye. Blending between two entries would put colours on screen that are not
   in the sprite's palette, which is the smooth look this is avoiding.

**No filtering work was needed.** `rt_smoothtextures` defaults false, so the whole game is
already `RG_SAMPLER_FILTER_NEAREST` — and with no texture bound there is nothing to filter.
`rt_ef_vintage` is **not** the tool here: it is whole-screen pixelization and cannot be
applied to one effect.

### 1.3 The additive blend is the feature, not the bug

The batch is `RG_MESH_PRIMITIVE_TRANSLUCENT` with `emissive = 1`, and RTGL1's
`RasterizedDataCollector::ToPipelineState` turns any translucent primitive with a non-zero
emissive **ADDITIVE** (`SRC_ALPHA`, `ONE`). For a translucent *sprite* that is the bug behind
`rt_spectre_alpha` reading as inert (pitfall 32). For a hot spark it is precisely the blend
wanted, which is why this feature needs no art and no alpha tuning — alpha simply scales how
much the spark *adds*.

**The cost is honest and worth stating:** an additive translucent primitive is a rasterized
overlay, kept out of the acceleration structure, so sparks appear in **no reflection, no
water, and cast no GI**. `rt_spark_light` is the traced half.

Two constraints copied from the sprite-AO decal in `rt_draw.cpp`: `pMeshName = nullptr`, or
RTGL1 hunts for an `rt/replace/*.gltf` substitute; and a `uniqueObjectID` in a high-bit range
(bit 60 here, below the shadow and AO proxies at 62 and 61), because RTGL1 drops a duplicate
ID silently and it is the *new* primitive that loses.

`rt_translucent_minalpha` does **not** apply — that floor lives in `l_spriteAlpha` and only
fires for `RtPrim::ExportInstance`. A direct `rgUploadMeshPrimitive` never enters it.

### 1.4 Collision, in three tiers

A spark that sinks through the floor is not a spark, it is a fading dot. This is why
collision shipped in v1 rather than as a later polish pass.

**Tier 1 — floor and ceiling, every step.** `PointInSector` + `floorplane`/`ceilingplane
.ZatPoint`, the same idiom smoke uses and `rt_lights_fixtures.cpp` uses throughout. One
difference: where a smoke puff *clamps* and loses its vertical velocity so it spreads, a
spark **reflects** (`rt_spark_bounce`), with `rt_spark_friction` bled off the tangent. A
spark is a point, so smoke's radius term and its crawlspace guard both drop out.

**Tier 2 — walls, only when the step leaves its sector.** Each spark caches its `sector_t*`.
`PointInSector` was already fetched for tier 1, so "did it change?" is free — and false for
the large majority of steps. Only then is the movement segment traced with `Trace()`, the
same function `P_LineAttack` uses, and reflected off `res.Line`. `ActorMask` is empty so
sparks pass through monsters; `TRACE_NoSky` so a spark that reaches sky dies rather than
bouncing off the sky plane.

> **The trace flags must never include `TRACE_Impact` or `TRACE_PCross`.** Those fire
> `SPAC_IMPACT` and `SPAC_PCROSS` line specials — renderer particles triggering map specials
> would be a gameplay change and a netgame desync, in a system the player cannot see. With
> them unset and no callback, `Trace()` is a pure query.

**Tier 3 — settle.** Below `rt_spark_rest` and on the floor, velocity is zeroed and the spark
lies where it fell, glowing down the palette ramp until its life runs out. That is what turns
a burst into embers rather than a puff of dots — and skipping the integration for a settled
spark is also what stops the sub-step jitter a nearly-stopped bouncer would otherwise show.

Two details that would each have cost a round trip:

- **A spark is born offset along the normal** (2 cm). Spawned exactly on the face it came
  from, tier 2's first trace reports an immediate self-hit and the spark sticks to the wall
  it should be leaving. `RT_SpawnBlood_Thing` offsets for the same reason.
- **`rt_spark_trace_max` caps traces per tic.** Tier 2 is the only unbounded cost in the
  feature, and a bounded budget is easier to reason about than a promise that sector changes
  stay rare. Profile a super-shotgun into a **corner**, not a quiet corridor.

### 1.4a Two style modes

`rt_spark_style`: **0 pixelated** (default), **1 realistic**. Same particles, same
palette, same sizes — only the quantization and the shape change.

| | pixelated | realistic |
|---|---|---|
| position | snapped to `rt_spark_grid` | continuous |
| size | snapped, floor of one grid cell | continuous |
| colour | hard step through the 7 PUFF entries | the same 7, interpolated |
| shape | square | stretched along its own velocity |

**Realistic is deliberately restrained**, and that is a constraint rather than a preference:
same ramp, same sizes, no bloom of its own, no motion blur, and the streak is **capped** by
`rt_spark_streak` (2.5×) rather than being proportional to speed. Uncapped, a fast spark
becomes a long thin line that reads as tracer fire instead of as a fragment —
`tools/arms/spark-realloud.cfg` is that failure, kept so the shipping value can be seen to
be a choice. The ramp is *not* swapped for a "realistic" one: this is the Doom 64 palette
drawn smoothly, not a different palette (`don't over-apply retro styling` cuts both ways).

### 1.5 The lights — impact flash, and the sparks themselves

`emissiveMult` is screen glow and lights nothing; a sprite casts only via `lightIntensity` +
`lightColorHEX`. Neither applies to an engine-generated quad, so the cast light is an
analytic one, following `RT_UploadFlameLights()` end to end: candidate collection,
`std::partial_sort` nearest-first, truncate to `rt_spark_light_max`, then
`RgLightSphericalEXT` + `RgLightInfo` → `rgUploadLight`. Positions are **metres**
(`ONEGAMEUNIT_IN_METERS`), or the light lands 32× out and reads as absent.

**One per impact.** A super-shotgun is 20 pellets and 20 impacts; at 8 sparks each, one light
per spark would be 160 moving lights in a frame, which is `rt-lighting-practices` §20
exactly. The global cap plus nearest-first is the `rt_gore_max` precedent this document
originally asked for.

**And the flying sparks needed lights of their own.** Reported from play: *"the sparks
themselves don't seem to emit any light, only the impact location."* That was accurate, and
it was structural rather than a tuning miss —

> **Screen brightness and cast light are different channels, and nothing crosses between
> them.** The particles are an additive *rasterized* overlay, and RTGL1 keeps translucent
> primitives out of the acceleration structure entirely. However bright a spark is on
> screen, it is not a light source, and no value of `rt_spark_bright` can make it one. Only
> an analytic light casts.

So `rt_spark_glow` adds some — **not one per spark**, which is the same 160-light trap
above. `rt_spark_glow_max` (8) caps how many flying sparks carry a light at once, ranked by
distance **biased by age**: without the age term the cap fills with settled embers while the
shower you just made stays dark. A handful glowing among many reads as all of them glowing,
because the eye cannot audit which dot is lighting the wall.

Two details that matter:

- **The glow's `uniqueID` is keyed on the SPARK, not on the candidate slot**
  (`SparkGlowId_Base + spark.sid`, a monotonic spawn counter). A slot is reassigned to a
  different spark as sparks die, so a slot-keyed light would *teleport across the room*
  between frames — worse for ReSTIR than dying, because RTGL1 would carry the old reservoir
  to a new place. The pool index cannot serve either: removal is swap-with-back.
- **The light takes the spark's current ramp colour**, so a spark that has cooled to brown is
  not still throwing pale yellow on the wall.

`spark-noglow` is the reported before; `spark-glowmax` is the cost probe (32 lights at 2×
intensity) — run it on a super-shotgun into a corner with a frame time on screen before
arguing for a higher cap.

**Debris never glows, and never flashes**: a chip of stone is not hot. If debris lights the
room, the surface classification is wrong, and that is where you would see it.

`SparkFlashId_Base` is `1ull << 48` — verified clear of `LavaLightId_Base` (`1<<47` plus
`secIndex * 65536 + cell`, which cannot reach `1<<48` at any Doom map size) and below
`GunGlowLightId` at `1<<50`. **The low bits are the pool SLOT, never the age or the tick**:
an id that moves makes RTGL1 see the whole set die and respawn each frame and throw away its
temporal reservoirs, and a flash lives ~0.18 s, so it would be reborn for its entire life.

The flash is driven from the **impact point**, which does not move — a light chasing a
grid-snapped spark reads as the two coming apart.

### 1.6 Brightness has exactly one lever, and it is not the obvious one

Asked from play for sparks twice as bright, the three candidate multipliers turn out to be
two dead ends and one real knob. Worth writing down, because the two dead ends are both
traps this project has already paid for once.

The emission line in `RsWorld.inl` is:

```glsl
outColor.rgb += ldrEmis * ldrColor.a * globalUniform.emissionMaxScreenColor;
```

- **`prim.emissive` is a no-op above 1.** `RasterizedDataCollector.cpp` stores
  `.emissive = Utils::Saturate( info.emissive )`, and this batch already ships at `1.0`.
  Raising it changes nothing and logs nothing — **pitfall 15 exactly**, the same `Saturate`
  that made `emissiveMult > 1` silently inert for a year.
- **`emissionMaxScreenColor` is `rt_emis_maxscrcolor`, and it is GLOBAL.** It is pinned at 3
  and shared with every monitor, EXIT sign, key and lava pool in the game. Moving it for
  sparks re-tunes all of them, and raising it clips saturated colours (**pitfall 12**).
- **`ldrEmis` is the palette colour**, and the hot end is already `f8f8b0`. Scaling it clips
  the ramp to white and throws away the match to the PUFF sprite that the whole look is
  built on — `keep the art, add shading on top`, not the reverse.

That leaves **vertex alpha**, which is what `rt_spark_bright` scales.

**It is not a linear gain, and the clamp is the mechanism rather than a safety net.** Alpha
is packed to 8 bits, so a multiplier above 1 cannot raise the peak — it **widens** it:

    a = clamp( rt_spark_bright * (1 - t²), 0, 1 )

At the shipping 2.0 a spark holds **full** brightness for the first ~70 % of its life
instead of dimming from the frame it was born, then falls off. That hold is what reads as
brighter. Integrated over the life it is ~1.3×, not 2× — the honest number — and the
perceived change is larger than that because the spark stops visibly decaying the instant
it appears.

**The flash is the half that really is 2×.** `rt_spark_light_intensity` went 90 → 180 and
has no ceiling at all: it is an analytic light, not an 8-bit packed vertex colour.

### 1.7 Life, and the pool that follows it

`rt_spark_life` went 0.55 → **1.1** from play. Two consequences, one of them wanted and one
of them a coupling that must move with it:

- **The ramp stretches.** Colour is indexed by `age / life`, so doubling the life makes a
  spark sit on each PUFF palette entry twice as long — it stays *hot* for longer, not merely
  *present* for longer. Combined with tier 3's settling, embers linger about twice as long
  on the floor.
- **The pool followed: `rt_spark_max` 320 → 640.** Twice the life is twice the live sparks
  for the same rate of fire. Left at 320, a shotgun blast (20 impacts × 8 sparks = 160) would
  start evicting its own sparks within two shots, and eviction is oldest-out — so what
  disappears is the lingering tail that the longer life was asked for in the first place.
  **This is the same trap `rt_smoke_life` documents**: on this kind of effect, "more" is more
  parcels *and* the budget to hold them, never lifetime alone.

Nothing else needed compensating. Unlike smoke — where `rise` integrates over time and
`curl` scales with age *squared*, so a longer life silently changed the plume's shape —
a spark's only time-integrated term is gravity, and a longer arc is exactly what a
longer-lived spark should have.

### 1.7a Wall debris — scaffolding in, classification open

`rt_spark_debris`: on a **non-metal** surface, throw dull chips of the wall instead of hot
sparks. The whole path works end to end; what is missing is the data.

**Ships OFF**, and that is not caution — with it on, most of the game currently reads as
non-metal and throws debris, because the list has 56 entries out of 2331 textures. Turn it
on to work *on* the list, not to play.

**Debris differs from a spark in five ways**, and they were chosen so a chip is
distinguishable before its colour is even read: a separate **alpha-blended** batch (not
additive), its own cool grey ramp, heavier gravity, lower restitution, and **no light of any
kind** — no flash, no glow.

> **The two batches cannot be merged, and the reason is a one-line rule in RTGL1.**
> `RasterizedDataCollector::ToPipelineState` picks the blend mode from the primitive's
> `emissive`: `> 0` becomes ADDITIVE (`SRC_ALPHA, ONE`), `== 0` stays a normal alpha blend.
> Additive can only ever *add*, and a chip of stone must be able to be **darker** than the
> wall behind it. So sparks and debris are two uploads with two mesh IDs.
>
> For the same reason **debris does not take `rt_spark_bright`**: in an alpha-blended batch,
> alpha is *opacity*, so multiplying it would make chips more solid rather than brighter —
> the same number meaning two different things, which is how a shared knob quietly breaks
> one of its users.

#### The classification rides the PBR labelling pass — it is not a second effort

**The `surface` field was already being authored and nothing consumed it.** The PBR
material-labelling pipeline (`tools/gen_material_labeller.py` → the labelling page →
`tools/apply_material_labels.py`, see `docs/plan-metal-labelling.md`) exports
`tools/_material_labels/<map>.json`:

```json
"SFLATDF": { "metallicDefault": 1, "roughnessDefault": 0.95, "surface": "metal"   },
"SFLATD":  { "metallicDefault": 0, "roughnessDefault": 0.8,  "surface": "concrete" },
"SMONAA":  { "metallicDefault": 0, "roughnessDefault": 0.8,  "surface": "other"    }
```

`apply_material_labels.py` merges only `metallicDefault` and `roughnessDefault` into
`textures.json` and **ignores `surface` entirely**. So the exact classification impact FX
needs was being produced as a by-product of work happening for another reason — this
feature costs no labelling effort of its own, and improves every time that pass advances.

**`tools/build_spark_surfaces.py` consumes it, strictly read-only.** It never writes a label
file, never edits `textures.json`, and never touches `apply_material_labels.py` — that
pipeline is owned elsewhere. It reads the `surface` values and emits the table the renderer
loads, into **both trees** (the gitignored engine build dir *and* `Retribution-RT-Materials`)
for the reason `apply_material_labels.py` documents: writing only one means the change either
dies at the next build or never reaches the game.

A generation step is unavoidable regardless — `tools/` is not in the engine's lump search
path, so the game cannot read the label files directly. Given that, the shipped format is two
columns rather than JSON: no parser needed in the renderer, diffable, and hand-editable for a
one-off override while testing.

**The labels correct the old guess, which is the proof they were worth having.** The first
version of this table was seeded from `metallicDefault >= 0.5` and produced 56 "metal"
textures. Against the authored labels that was wrong in both directions: `SFLATAC` and
`SFLATAF` carry a high `metallicDefault` but are labelled **concrete**, and the real count is
**28 metal, 17 concrete, 38 other** out of 83 labelled. `metallicDefault` was authored for
*reflectivity*; `surface` is authored for *what the thing is made of*, and only the second
question is the one being asked here.

| `surface` | effect |
|---|---|
| `concrete` | **debris**, pale dusty ramp |
| `metal` | sparks + the impact flash |
| `other` | sparks |
| anything else | sparks — an unknown class degrades rather than erroring |
| unlisted | sparks, and the probe says `[UNLISTED]` |

**Sparks are the default and only `concrete` opts out, which is a reversal.** The first rule
was "metal sparks, everything else is debris", and it was wrong for the state the data is
actually in: with 83 textures labelled of 2331, *everything else* meant almost the whole
game, and one unlabelled map would have turned every surface in it to chips. The rule is now
**opt-in** — a texture has to be positively labelled `concrete` to behave differently — so
metal, `other`, and everything the labeller has not reached all keep the shipped spark, and
the effect can only improve as the labelling advances. That is also what makes
`rt_spark_debris` safe to ship **on**.

**`[UNLISTED]` is reported separately from `other`** even though they behave identically:
they are the same effect but a very different thing to know when the question is how far the
labelling has got.

#### Classifying the surfaces by hand

**Doom 64 texture names carry no meaning.** `C1`, `C102B`, `C307B1`, `SPACEAO1`. There is no
prefix rule that separates metal from stone, so this cannot be a predicate the way
`l_waterflag` is — it has to be an explicit list. And an explicit list of a thousand entries
has to be editable without a rebuild, or it never gets finished. Hence a **data file**:

    Doom64-Retribution/Retribution-RT-Materials/rt/data/spark_surfaces.txt

Tracked in git, staged into the build tree by `build-gzdoom-rt.cmd` (it must **not** live
only in the gitignored build `rt/`, which the next restage wipes). One name per line,
case-insensitive, `#` comments, trailing `*` for a prefix. **Anything not listed is
non-metal.** Reload in-game with the **`spark_surfaces`** CCMD — no restart, no recompile.

#### What the classification says on the console

Three levels of output, because "is the table loaded", "what am I shooting" and "which
texture exactly" are different questions and only the last one wants a line per bullet.

**1. Once, at load** — `Printf( RT_DiagPrintLevel(), … )`, so it reaches the console and
`rt-console.log` always and the on-screen notify area only under `rt_verbose 1`:

```
rt_spark surfaces: 83 entries from rt/data/spark_surfaces.txt  (metal 28 -> sparks, concrete 17 + other 38 -> debris)
```

or, when it cannot be read:

```
rt_spark surfaces: 'rt/data/spark_surfaces.txt' NOT FOUND -- every surface will classify as 'other'. Run: python tools/build_spark_surfaces.py
```

**That failure line is the whole reason this section exists.** The first version used
gzdoom's *lump* filesystem for a path that lives on disk, so it never found the table — and
it treated "not found" as a silent normal state, on the reasoning that an empty table is
harmless. It is harmless *and* indistinguishable from a feature that does not work, which is
how it shipped broken and was reported from play as "everything is a spark". A load that can
fail must say so.

> **`trace.HitTexture` IS NOT FILLED IN FOR WALLS, and that was the second cause of the same
> symptom.** Core `Trace()` sets `HitTexture` for floors and ceilings only; the wall case is
> patched in by `DLineTracer::TraceCallback` (`p_trace.cpp`), which belongs to the ZScript
> `LineTracer` class and never runs for `P_LineAttack`. So every wall hit arrived with an
> invalid `FTextureID`, resolved to an empty name, and reported `'?' -> other [UNLISTED]`
> for the entire game — visible in `rt-console.log` as a wall of identical `'?'` lines,
> which is what identified it. The hook now derives the texture itself from
> `trace.Line->sidedef[trace.Side]->textures[tier]`, mirroring that callback's tier logic.
>
> The lesson is the project's own: **the log named the failure in one line once the probe
> printed the texture NAME rather than only the verdict.** A probe that had printed just
> "unlisted" would have looked like a labelling gap rather than a plumbing bug.

**2. Per second, with `rt_spark_debug 1`** — a second line under the A/B/C ladder, so the
distribution is readable while playing without a print per bullet:

```
  types: metal 12 (sparks)  concrete 31  other 8  UNLISTED 44   [rt_spark_debris 0 -- all of these spark]
```

The trailing note appears whenever `rt_spark_debris` is off, because that is the other way
this reads as broken: the classification can be perfectly correct and every impact still
sparks, by configuration.

**3. Per impact, with `rt_spark_surface_debug 1`** — the identification tool below.

**And `sparks` / `spark_surfaces` print the worklist**: the distinct texture names you have
actually hit that are *not* in the table.

```
  unlisted textures hit (7): C102B C307B1 SDFLTAM ...
  ^ these are the ones the material labeller has not reached; they all fall through to debris.
```

That list is gathered by *playing* rather than by auditing 2331 textures, which makes it the
most useful output the feature produces while the labelling is in progress — it is a
worklist for the labeller, ordered by what the player actually shoots at.

**`rt_spark_surface_debug 1` is the tool that makes the job possible**, and it is not
optional:

    rt_spark surface: 'SPACEAK' -> METAL      (sparks)
    rt_spark surface: 'C102B'   -> other      (debris)

Shoot a wall, read the name, decide, add the line, `spark_surfaces`. There is no other way:
a screenshot carries no texture name, and identifying a surface by matching the art has
pointed the wrong way before (`whatsthat` exists for exactly this reason). The print happens
*before* the distance cull so a surface can be identified from wherever you are standing.
The name comes from `trace.HitTexture`, which `Trace()` sets per wall tier and per flat — so
it is the exact surface the shot landed on, with no second lookup and no chance of naming a
neighbour.

#### The 56 seeded entries, and one prior worth knowing

The list is **seeded, not authored**: it is every texture already carrying
`metallicDefault >= 0.5` in `rt/data/textures.json`, minus the liquids. That is not a guess
— it is data that already existed, and it lands on exactly the metal families (`SWX*` and
`CMPSW*` switches, `SDOOR*`, `SFLAT*`/`SPACE*`/`STRAC*` tech panels).

**The liquids had to come out.** `FWATER*`, `BLOOD*` and `SLIME*` all carry
`metallicDefault 1.0` — authored for **reflectivity**, not because they are metal. They must
never spark; the liquid gate in `P_LineAttack` excludes them anyway, but a metal list that
claimed water was metal would be a trap for the next reader.

**Note `docs/rt-feature-ideas.md` #4**: a full metal/non-metal PBR authoring pass was
**attempted and rejected** — *"no AI parsing of the textures was able to reliably tell metal
from non-metal, and doing 1000+ textures by hand is not worth it."* This is a materially
easier question than that one was: a **binary** per texture, no roughness or ORM accuracy
required, and only for surfaces the player actually shoots — walls at eye level, not every
ceiling and flat. So it is worth trying. But the rejection is the reason the *unlisted*
default has to stay good rather than assuming the list will ever be complete, and it is why
`rt_spark_debris` is a switch rather than the only behaviour.

#### Debris is RAY-TRACED, and that took two attempts

Reported from play: *"debris do not apply environment light — debris in a dark room are
still bright / visible."* Correct, and the cause is one line of `RsWorld.inl`:

```glsl
outColor.rgb *= max( vec3( 1 ), tonemapping.avgLuminance );
```

**That is the entire shading of the rasterized path.** No light sampling of any kind — a
primitive is its vertex colour, multiplied by *at least* 1. So a chip of stone rendered its
authored colour whatever the room was doing, and `localLightsIntensity` / `classicLight` do
not help: they belong to the ray-traced and classic paths and are never read here.

**The first fix was wrong, and the way it was wrong is the useful part.** It multiplied the
sector's light level into the vertex colour by hand — the approach `rt_ghost_lightscale`
uses for ghosts. That reads the *painted* lightlevel rather than the traced result, which is
a known approximation. But it also could not escape the other half of that line:
**`avgLuminance` is eye adaptation.** It decays over seconds, so chips visibly took time to
darken on walking into an unlit room even though the sector term was instant — reported back
as *"debris take time to get dark as the room"*. That was the workaround failing, not a
tuning miss.

> **No engine-side multiply can fix a term the engine cannot see.** The exposure average is
> not exposed through the API, and it can only ever *brighten* (`max(vec3(1), …)`). The
> answer was to stop being rasterized at all.

**Debris is now opaque ray-traced geometry.** `VulkanDevice::IsRasterized` puts a primitive
in the acceleration structure when it has **no `TRANSLUCENT` flag** and a primitive alpha at
or above `MESH_TRANSLUCENT_ALPHA_THRESHOLD` (0.98). The debris batch now satisfies both, so
the path tracer lights it for real — instantly, correctly, with shadows, and visible in
reflections. The three workaround cvars (`rt_spark_debris_light` / `_minlight` / `_tint`) are
**gone**; the renderer does the job properly and dead knobs are worse than none.

Two consequences that are not optional:

- **Debris fades by SHRINKING, never by alpha.** Dropping alpha below 0.98 silently demotes
  the whole batch back to the rasterized overlay — i.e. back to fullbright — for the last
  part of every chip's life. The final quarter of the life shrinks the quad to nothing
  instead, and alpha stays pinned at 1.
- **A chip's shading normal is the surface it came off**, stored at spawn. The quad is still
  camera-facing so a chip is never edge-on and invisible, but a camera-facing *normal* on
  traced geometry swings the lighting as the player turns, which reads as flickering.

**Sparks stay rasterized and additive, deliberately.** They are self-luminous; being
independent of the room is correct for them, and dimming a spark by the room it is lighting
would be backwards. That asymmetry is now the clean line between the two: **a spark glows, a
chip is lit.**

**Not done, and deliberately so:** a chip's colour is a neutral grey ramp, not the surface it
came off. `trace.HitTexture` makes the real thing reachable (average albedo of the hit
texture) and that is the obvious upgrade — but a *wrong* per-surface colour is worse than a
neutral one, so it waits until the classification makes debris worth looking at.

### 1.8 Cvars

35 of them, one line each in `rt_cvars.inc` and nowhere else, all pinned in
`tools/d64rt-pins.cfg`. Every pin restates its compiled default, so
`python tools/check_pins.py rt_spark_` is an error if either half moves without the other —
maintained the way `rt_smoke_*` is, and for the same reason.

**`rt_spark` ships at 0**, compiled *and* pinned, until judged in play.

### 1.9 How to judge it

`.\tools\ab.cmd spark-<arm> [map]`:

| arm | isolates |
|---|---|
| `spark-fat` | **run this first.** 10× count, 4× size, 3 s life, no gravity. If this shows nothing the problem is plumbing, not values |
| `spark-on` / `spark-off` | the shipping numbers, and the before |
| `spark-pixel` / `spark-real` | the two style modes. Judge **while moving** — the snapping is a motion difference before it is a shape one |
| `spark-realloud` | `rt_spark_streak 6` — realistic *overdone*, kept as the thing not to ship |
| `spark-nolight` | both light sources off. How much of the effect is traced at all |
| `spark-noglow` | impact flash only. The reported "sparks don't emit light" state |
| `spark-glowmax` | 32 glows at 2× intensity — the **cost** probe, not a candidate |
| `spark-nogrid` | unsnapped motion but still hard palette steps: isolates snapping from colour |
| `spark-nocollide` | all three tiers off. What "not worth shipping" looks like |
| `spark-still` | no gravity, 6 s life, high restitution. The arm for reading collision |
| `spark-debris` | debris on + the surface probe. For **building the list**, not judging the look |
| `spark-debrisheavy` | more/bigger/longer chips, to judge the debris look and confirm it darkens **instantly** |
| `spark-debug` | the staged ladder |

`rt_spark_debug 1` prints once a second, and the `sparks` CCMD prints the same line on
demand:

```
A/hit    impacts seen, and how many were rejected
B/spawn  sparks created, live of max
C/sent   quads uploaded, lights of cap, wall traces
```

That ladder exists because **"nothing spawned" and "spawned but not drawn" are identical on
screen**, and this project has lost sessions to not being able to tell them apart.

**Where:** the smoke lab, not a real level first — `python tools/build_smoke_lab.py`, then
`tools/smoke-lab.cmd`. **MAP97 dark** for the glow, the flash and whether the arc reads as a
bounce; **MAP96 bright beige** for whether an *additive* spark is visible against a lit wall.
That second one is the case smoke went several rounds without reproducing, for the same
reason: a bright particle on a dark wall is the easy one.

Then in play: a wall, a floor, a ceiling; a monster (must produce **no** sparks); the sky
(none); a shotgun blast at a wall to watch the cap hold. For collision specifically — a wall
above a staircase (sparks should come down the steps), a ledge edge (they should go over it),
and a closed door (none should pass through).

### 1.10 Known limits

- **No reflections, no GI** for the particles — inherent to the additive raster overlay.
  Only the flash is traced.
- **3D floors are not handled.** Tier 1 reads only the sector's own planes, so a spark falls
  through a 3D floor. Narrow in practice, because `d64r-3dfloor-rtfix.wad` already strips
  them on the play launcher — but real.
- **Tier 2 is the only unbounded cost**, bounded by `rt_spark_trace_max` rather than by
  argument.
- **Scope is hitscans.** Projectile and explosion impacts make no sparks; those are §2's
  territory.

---

## 2. Scorch decals — still planned

**Where they go.** Plasma, rocket and BFG impacts. The decal path is live — the sprite-AO
blob uses it — so this is a new decal texture and a spawn rule, not new plumbing.

**The trap that is already written down:** RTGL1 decals need **world-space vertices** and an
identity transform. `RsDecal.vert` writes `outWorldPos = position` untransformed, so a decal
built with a transform rasterizes in the right place on screen and then discards every
fragment: nothing renders, nothing errors. See `rt_draw.cpp` and `docs/blood-persist.md`.

**A second trap, from the AO blob:** the decal shader falls back to `ldrEmis = albedo` when
no emissive texture is bound, so a non-zero `emissive` on an untextured decal makes it glow
and write screen emission where there should be none. That directly constrains §3.

**Lifetime.** Blood persistence had to solve exactly this and the answer was not in the
renderer — the one-second lifetime was in the WAD's DECORATE, and `rt_gore_max` is a ZScript
FIFO in `d64r-blood-persist.pk3`, not a renderer cap. Check where a scorch's lifetime is
actually decided before adding a cvar for it.

**Fade.** Scorch should fade by *shrinking its alpha*, not by tinting toward the floor
colour: the floor colour is not knowable, and sector colormaps tint albedo rather than light,
so a "matching" tint will be wrong on any coloured map.

**Geometry.** Use a single triangle **fan**, centre opaque and rim at zero, exactly as the AO
blob does. A ring/plateau topology puts a visible crease in every segment — the reasoning is
written out at length in `rt_draw.cpp` and should not be rediscovered.

## 3. Optional third piece — glowing plasma burns

A scorch from plasma could carry a short emissive tail: bright cyan for ~0.3 s, fading to
plain soot. That gets a genuinely ray-traced moment — a fading pool of light on the floor
after a firefight — for the cost of one extra decal layer with an `_e` mask.

If it is done: the emissive mask must be a **raw** `_e`, never sampled from the albedo. The
ray-traced path uses `_e` directly and only the rasterized path multiplies by baseColor. And
note the decal emissive fallback in §2 — an emissive decal needs a real `_e` bound, not just
a non-zero `emissive` float.
