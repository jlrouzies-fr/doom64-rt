# Plan — projectile impact FX: plasma arcs, Unmaker burn, rocket embers, barrels

**Status: DONE.** Everything on this page is built, judged in play and shipping on, with
one deliberate exception: **§7, bullet holes with relief, is set aside** — impact depth is
not being pursued for now.

Two items were delivered differently from how they were written, and the difference is
worth reading before trusting the section text below:

- **§4 was "Unmaker melt" and shipped as an Unmaker BURN** — a small red crackle with a
  churn and one smoke thread, reusing the plasma filigree rather than the melt/drip idea
  the section describes. See the note on §4.
- **§6's barrels shipped without the fire and without the acid.** The scorch, the plate
  and the smoking coals are all in; the short-lived flame emitter (§6.2) and the acid
  (§6.3, which was always a design decision before it was code) were not built and are
  not currently wanted.

Impacts that leave a mark today: the player's rocket and plasma, the BFG, and — added after
a play note that they were missing — the cyberdemon's rocket, the revenant's tracer (`TRCR`),
the Mother Demon's ball (`RBAL`) and the mancubus's `MANF`, all at rocket scale. Still
unmarked: imp fireballs (`64DoomImpBall`, `64NightmareImpBall`) and `64MotherFire`. Those are
a judgement call about how marked-up a normal firefight should get, not a technical gap — one
table row each.

Scope decided in play review:

| § | | |
|---|---|---|
| 2 | projectile impact hook | **built** — `RT_UpdateProjectileImpacts`, its own walk |
| 3 | plasma / BFG / arachnotron arcs | **built** — `rt_arc*`, ships **on** |
| 1 | plasma light instability | **built** — the light-density fix landed here instead: `rt_arc_glow_max` 10 → 100, and one light per Unmaker mark instead of 26 |
| 4 | Unmaker impact | **built** — `rt_laser*`; a red crackle, small churn, one smoke thread, cold in 10 s. Not the melt this section describes |
| — | the scorch decal | **built** as part of §3/§5 (`rt_arc_burn*`), which also delivers `plan-impact-fx.md` |
| 5 | rocket embers + smoke | **built** — `rt_ember*`; embers live ON the mark, not as particles |
| 6 | barrel scorch, plate, smoking coals | **built** — `rt_barrel*`, hand-cut art in `rt/mat/d64rt/barrel/`. Fire (§6.2) and acid (§6.3) NOT built |
| 7 | bullet holes with relief | **set aside** — impact depth is not being pursued |
| 8 | ejected shell casings | **built** — the WAD's own system, `d64_dropcasings` pinned ON |

### What shipped, in one place

Every impact in the game now leaves something, and each has its own knobs so tuning one
cannot move another — a rule this system had to learn three times:

| source | mark | cvars |
|---|---|---|
| plasma / arachnotron / BFG | electric filigree + scorch | `rt_arc*` |
| rocket, cyberdemon rocket, `TRCR`, `RBAL`, `MANF` | scorch + glowing coals + smoke | `rt_ember*` |
| Unmaker laser | small red crackle + churn + one smoke thread, 10 s | `rt_laser*` |
| exploding barrel | floor scorch, ~50 coals, 60 pieces of hand-cut plate, permanent | `rt_barrel*` |
| hitscan | sparks and material debris | `rt_spark*`, now shipping **on** |

Still unmarked by choice: imp fireballs (`64DoomImpBall`, `64NightmareImpBall`) and
`64MotherFire` — a judgement about how marked-up a normal firefight should get, one table
row each if that changes.

**The lesson worth carrying out of this plan** is not in any section. The Unmaker mark was
tuned for an afternoon in the impact lab and produced *nothing at all* in game, because
`arc_here` plants a mark directly and therefore validates the RENDERER while never once
exercising the TRIGGER. `UnmakerLaser` is a `FastProjectile` at Speed 200 that explodes
inside the tic it was fired, so the disappearance rule every other projectile uses could
never see it. A lab that only draws the effect will happily certify a feature nothing asks
for. `tools/impact-lab.ps1 -Weapon <class>` now fires the real weapon, and every impact
here is worth one run through it.

Two scope calls that override what the sections below propose:

- **No smoke on plasma.** ~~and none on the Unmaker~~ — the Unmaker DOES get one thread,
  decided when §4 was built: a laser burn that glows and does not breathe reads as a
  decal. Plasma still gets none.
- **The BFG reuses the arc**, in green, rather than getting an effect of its own. That
  answered the open question below, and it cost one ramp table.

Three effects that all sit on **one missing piece of plumbing**, plus one that does not.
The shipped impact system is [`rt-impact-fx.md`](rt-impact-fx.md) and this extends it rather
than starting a parallel one — same particle system, same surface classification, same
budgets.

Related: [`rt-impact-fx.md`](rt-impact-fx.md) (the sparks/debris that shipped),
[`plan-impact-fx.md`](plan-impact-fx.md) (scorch decals — the melt in §4 is the same decal
path and should land with it), [`rt-smoke.md`](rt-smoke.md) (the puff system §5 feeds),
[`rt-lighting-practices.md`](rt-lighting-practices.md) (§20, the light-density rule that
bounds §5).

---

## 0. Where the gap actually is

Two facts to establish before designing anything, because both contradict the obvious
assumption:

**The plasma ball already casts light.** Retribution ships its own GLDEFS inside
`D64RTR[v1.5].WAD` (24 pointlights, including keys, armour and every sphere), and the
projectile is defined there:

```
pointlight PLASMABALL { color 0.0 0.1 1.0  size 64 }
```

`RT_UploadGzDoomDynamicLights` (`rt_lights_sector.cpp:163`) forwards those into RTGL1, so a
bolt in flight is already a real moving blue light in the path tracer. What it is not is
*electric*: it is a perfectly steady lamp travelling in a straight line. **The gap is
instability, not illumination.**

**Plasma already leaves a scorch decal, and it may already be in the path tracer.**
`64PlasmaBall` and `64ArachnotronPlasma` both declare `Decal "PlasmaScorchLower"` in the
WAD's DECORATE (`tools/_decorate_extract.txt:1105`, `:3618`), and `PlasmaScorchLower` is
defined in `D64RTR[v1.5].WAD`'s DECALDEF. That is GZDoom's own decal system, and RT does
**not** ignore it: `rt_draw.cpp:282` maps `RtPrim::Decal` to `RG_MESH_PRIMITIVE_DECAL` and
`:466` exempts decals from the export path, so an engine decal becomes an RTGL1 decal.

**Verify this in play before building anything decal-shaped.** If plasma scorches already
appear, then §4's melt is a *cooling ramp and a light on top of an existing decal*, not a
new decal system — and the scorch decals in [`plan-impact-fx.md`](plan-impact-fx.md) may be
substantially built already for the projectile weapons. Shooting the plasma rifle at a wall
and looking answers it in ten seconds; assuming either way costs a day.

**Projectiles never reach the impact hook.** `RT_SpawnImpactSparks` is called from exactly
one place — `p_map.cpp:4900`, inside `P_LineAttack` — which is **hitscan only**. Plasma,
rockets, the BFG and the Unmaker are `MF_MISSILE` actors and never touch it. So today a
plasma bolt hitting a wall produces no sparks, no debris and no surface reaction of any
kind. §3, §4 and §5 are all blocked on the same hook, which is why §2 is the keystone item
and should be built first even though §1 is cheaper.

---

## 1. Plasma light instability — no new lights, no new geometry

> **BUILT, though not the way this section proposes.** The pulse-the-intensity idea below
> was never needed: what actually turned out to be wrong with impact lighting was DENSITY,
> not stability. One mark was emitting 26 light candidates (1 ember + `rt_arc_branches` +
> `rt_arc_creep`) against a global cap of 10, so a dozen marks contested ten slots
> nearest-first and only whichever one you stood on was lit. Fixed by raising
> `rt_arc_glow_max` to 100 and cutting an Unmaker mark to a single light. The trap this
> section documents — drive intensity, never radius, because above `rt_dynlight_rsoft` a
> bigger radius is *dimmer* — still stands and is still worth reading.

The cheapest item on this page and the only one that needs no new plumbing. Modulate the
dynamic light the bolt already carries: intensity noise (crackle), and a small positional
jitter (the light straying off the sprite centre, the way an arc does).

The rig to copy is the flame one, which solved this exact problem for torches:
`rt_flame_light_flicker` (depth), `rt_flame_light_speed` (rate), `rt_flame_light_wobble`
(how far the light strays from the sprite). Proposed twins: `rt_plasma_flicker`,
`rt_plasma_flicker_speed`, `rt_plasma_wobble`, under a `rt_plasma_arc` master that ships
**on** — unlike the sparks, this one cannot spawn anything, so it has no budget risk.

**The trap that will bite: radius is not brightness.** Above `rt_dynlight_rsoft` (40 map
units) a *larger* radius is *dimmer*, and a pulse driven through the radius therefore comes
out inverted. `PLASMABALL` is `size 64` — already past that threshold. The flicker must
drive **intensity**, never `m_currentRadius`, or the effect will read as backwards at
exactly the moment it is brightest. This is the same trap written up in
`rt-lighting-practices.md`.

**A second one, from the DLSS-RR diff.** The upload records `curDynIds` membership *before*
the brightness cutoffs (`rt_lights_sector.cpp:277`) precisely so a light that dips dark for
a few tics does not read as disappear-then-reappear and flush RR temporal history every
frame. A flicker added downstream of that is safe; one that skips the upload entirely on
dark frames is not. Do not "optimise" the dark end by continuing out of the loop.

**Which classes.** `64PlasmaBall`, `64ClassicPlasmaBall`, `64ClassicPlasmaBallNormal`, and
`64ArachnotronPlasma` — the arachnotron's shot is the same visual and should not be the one
steady bolt in the game. Match by class substring; `PlasmaBall` alone also catches the
classic variants, but `64PlasmaTrail` (a `RocketSmokeTrail` subclass) must not be caught.

---

## 2. The projectile impact hook — the keystone

**Everything below needs the same three answers:** where did the projectile die, what did it
hit, and which way was the surface facing.

**The death event is `MF_MISSILE` clearing, not the actor disappearing.** This is already
solved and written down in `rt_smoke.cpp:453`: `P_ExplodeMissile` clears the flag while the
actor *lives on*, same class, through its entire death animation. Matching on class name
alone kept seeing a rocket that had already hit the wall and kept feeding it trail parcels —
the cluster of puffs that sat against a wall and never faded was not a failure to expire, it
was continuous replacement. Losing the flag is the explosion, so the event fires on the
right frame and needs no DECORATE edit, no ZScript, and no game-code hook. That matters
because these classes are the WAD's, not ours.

**The existing walk cannot be reused as it stands — checked, and it is gated three deep.**
The plan's own caution was the right one to act on. `RT_UpdateSmokePuffs` returns at
`rt_smoke.cpp:1097` when `rt_smoke` is off, before the iterator is ever constructed; the
walk body at `:1186` runs only if one of five `rt_smoke_*` sub-cvars is on; and inside it,
`RT_ProjectileSmokeFor` (`:467`) answers `nullptr` for anything not in
`RT_PROJECTILE_SMOKE` — a five-row table of **rocket, TRCR, RBAL, MANF, FIRE**. Plasma, the
BFG and `UnmakerLaser` are in none of them, so they are not tracked, have no `RocketMark`,
and have no `lastPos` or `dir` to trace from.

So there are three couplings, not one, and the middle one is the trap: hooking the walk
would make plasma impacts vanish when someone turns *rocket trails* off. **Hoist the
iteration** — one walk, its own gate, feeding both systems — or give the impact hook its own
`MF_MISSILE` walk. Do not extend `RT_PROJECTILE_SMOKE` with zero-smoke rows to get the
tracking, which looks like the cheap option and buries an impact-FX dependency inside a
smoke table.

What *is* worth reusing verbatim is the mark structure and the `MF_MISSILE`-cleared edge
(`:453`), which is the part that was expensive to get right.

**Finding the surface.** The mark's last position is a tic of flight short of the wall, in
mid-air, with no normal and no texture. Recover all three with a `Trace()` from `lastPos`
along `dir`, copying `SparkHitWall` (`rt_sparks.cpp:1138`) — which already documents the
rule that matters:

> The trace flags MUST NOT include `TRACE_Impact` or `TRACE_PCross`: those trigger
> `SPAC_IMPACT` and `SPAC_PCROSS` line specials, and renderer particles firing map specials
> would be a gameplay change and a netgame desync in a system the player cannot see.

Empty `ActorMask` so the probe passes through monsters, `TRACE_NoSky` so a bolt that reaches
sky simply produces nothing.

**The trace length must come from the projectile's speed.** `UnmakerLaser` is a
`FastProjectile` — it moves in substeps and can cover a great deal of ground between the tic
the mark was written and the tic the flag cleared. A fixed probe distance will find nothing
for the Unmaker and will overshoot into the next room for a mancubus fireball. Derive it
from `Speed`, with a hard ceiling.

**`HitTexture` is not filled in for walls.** Core `Trace()` sets it for floors and ceilings
only; the wall case is patched in by `DLineTracer::TraceCallback`, which belongs to the
ZScript `LineTracer` class and never runs here. `p_map.cpp:4870` already mirrors that tier
logic (`TIER_Upper` → `textures[0]`, `TIER_Lower` → `[2]`, 3D-floor case reading
`ffloor->master`) for exactly this reason — the hitscan path arrived with an invalid
`FTextureID` and the whole classification silently reported "unlisted" for the entire game.
**Factor that block out and share it**, rather than writing it a second time; a second copy
that drifts from the first is a bug that reads as "the labelling is wrong".

**No hit is a legitimate outcome.** A bolt that detonates on a monster or in mid-air gets no
surface, and §4 and §5 must simply not fire. §3 still can — an arc in open air is fine.

---

## 3. Plasma impacts that arc

**This section was wrong, and the correction is the useful part of it.** It proposed a spawn
rule rather than a system: call the existing spark spawner with an electric ramp, a short
life, and high speed so the particles crawl along the surface. That was built, and it failed
in play — *"just spawn many particles, square / rectangle over the place… not at all the
improved scorched."*

The mistake was assuming the **direction** of the particles was what separated an arc from a
shower. It is not. What the eye reads as "sparks" is that the fragments are *discrete,
separate and moving*, and a ring of quads is a spark shower however you aim it. An electric
remain is none of those things: it is a **connected filigree that stays put and crackles**.

So the arcs are **not particles and not in the spark pool**. The primitive is a polyline
lying in the surface plane: one `ArcMark` per impact, `rt_arc_branches` random walks out of
it, each segment a thin in-plane quad, plus a small core where the ball died. The geometry is
regenerated from the mark's seed every frame — which is what lets branches drop out and
return, and that flicker is more of what sells it than any brightness value.

The general lesson, and it is the same one the debris whiteout taught: **when an effect reads
as the wrong thing, check the construction before the values.** No setting of speed, spread,
life or colour on a particle system would have produced this, because the problem was that it
was a particle system.

Two things worth taking from the shipped system rather than reinventing:

- **The surface classification already applies.** `rt/data/spark_surfaces.txt` says what was
  hit. An arc should behave differently on `metal` (spread, bright) than on `flesh`, and
  `fluid` should probably get nothing at all.
- **`rt_spark_style`** already exists with two looks (0 = pixelated, 1 = realistic). An
  electric impact should honour it rather than adding a third global style.

The one genuinely new element is colour: everything in the spark system so far is a heat
ramp (white → amber → red). Electric wants cyan-white → blue → dark, which is a new ramp
table but nothing more.

**Take the ramp from `PLSE`, the way the sparks took theirs from `PUFF`.** The plasma ball
already has an impact animation — `Death: PLSE ABC 3, PLSE DEF 2 BRIGHT`, six frames,
16 tics ≈ 0.23 s — that plays at exactly the point and moment the arc would spawn. Lifting
the ramp from those lumps' own `PLTE` makes the two agree by construction rather than by
eye, which is the single thing that made the spark colours stop needing tuning. It also
sets the arc's life: much past ~0.25 s and the particles outlive the flash they came from,
and the effect reads as two events rather than one.

---

## 4. Unmaker melt

> **SUPERSEDED — the Unmaker impact shipped as a BURN, not a melt.** Everything below
> describes a dripping/melting decal that was never built. What ships is `rt_laser*`: the
> plasma filigree at `rt_laser_arc_scale 0.18` in the LPUF sprite's own reds, a small churn
> (`rt_laser_burn_scale 0.55`), one glowing point and one smoke thread, cold in ten
> seconds. Reusing a rig built for another weapon cost a table row and a per-flavour ramp.
>
> Two things it needed that no other impact did, both recorded in the cvar help: its own
> detection door (it is a `FastProjectile` and is found already dead, by its `LPUF` death
> sprite, then probes six ways for the surface), and size and lifetime prised apart —
> every other flavour multiplies one style scale into both, which is right for a BFG and
> fatal for something deliberately tiny.

`UnmakerLaser` (a `FastProjectile`, per the WAD's DECORATE) hitting a wall should leave a
spot that is briefly **molten** — glowing white-hot, cooling through orange to a dark
scorch — rather than a puff of sparks.

**This is the scorch decal from [`plan-impact-fx.md`](plan-impact-fx.md) with a cooling
ramp on top**, and the two should be built together: same decal, same lifetime question,
same geometry. Every trap on that page applies here. The three that will actually cost a day
each:

- **RTGL1 decals need world-space vertices and an identity transform.** `RsDecal.vert`
  writes `outWorldPos = position` untransformed, so a decal built with a transform
  rasterizes in the right place on screen and then discards every fragment — nothing
  renders, nothing errors.
- **The decal shader falls back to `ldrEmis = albedo` when no emissive texture is bound.**
  A non-zero `emissive` on an untextured decal makes the whole thing glow. For a melt that
  is nearly what is wanted, which makes it *more* dangerous, not less: it will look
  plausible while being uncontrollable. Bind a real raw `_e`, and remember the raw/multiplied
  split — the ray-traced path uses `_e` directly, only the rasterized path multiplies by
  baseColor.
- **A triangle fan, centre opaque, rim at zero** — as the sprite AO blob does. A ring or
  plateau topology puts a visible crease in every segment.

**The glow will not light the room.** `emissiveMult` is screen emission and cannot
illuminate anything. A melt that is meant to cast a fading pool of light onto the floor
needs its own short-lived analytic light, positioned in **metres**
(`ONEGAMEUNIT_IN_METERS`), decaying with the same curve as the decal's emissive so the two
cool together. This is the whole payoff of the effect — a genuinely ray-traced afterglow —
so it is not optional, but it is also one light per Unmaker impact and the Unmaker is a
rapid-fire weapon. **Cap it hard and cull by distance**, per `rt-lighting-practices.md` §20.

**Classification gates it.** A melt on `fluid` is wrong. On `flesh` it should be a burn.
`concrete` and `metal` are the cases the effect is actually for.

---

## 5. Rocket embers that feed the existing smoke

A rocket already produces a smoke burst on death (`RT_PROJECTILE_SMOKE`, the row matched by
class so `64Rocket` and `64CyberRocket` share it). The proposal is what is left **after**
the burst clears: a handful of embers scattered on the floor at the blast point, glowing
down through orange to black over several seconds, each one releasing a thin thread of smoke
while it is still hot.

This is mostly assembly of shipped parts:

- The **debris** particles already have long life, gravity, bounce, settling and contact-AO
  blobs (`rt_spark_debris_life` is already 20 s, `_gravity`, `_bounce`, `_ao*`). An ember is
  a debris chip with an emissive ramp instead of a texture-tinted albedo.
- The **smoke** is `RT_SpawnSmokePuffs( eye, at, dir, vel, profile )`, already used for
  world-anchored ambient sources at `rt_smoke.cpp:982` — a settled ember is exactly that
  case, so it needs no new emitter type, just a countdown per ember like `AmbientMark`.

**Two failure modes to design against, not tune away later:**

- **Double smoke.** The death burst and the embers fire at the same place at the same
  moment. If both run at full strength the result is one opaque ball, and the embers — the
  point of the effect — are invisible inside it. The embers' smoke should start *after* the
  burst has begun to thin, i.e. the countdown starts at a delay, not at zero.
- **Light density.** An ember that glows should probably not be an analytic light; N embers
  per rocket, several rockets in a fight, is precisely the arithmetic that nearly put 105
  flickering monitors on MAP07. Either give the *group* one light at the blast centre that
  decays, or accept screen-emission-only embers and let §4's melt be the effect that
  actually casts. Decide this in the design; do not leave it to a tuning pass.

**Cooling and the AO blob.** Settled debris already draws a soft contact darkening
(`rt_spark_debris_ao`). A *glowing* ember with a dark AO blob under it is contradictory —
the blob should fade in as the ember cools, not be present from the first frame.

---

## 6. Barrel destruction — fire, a scorched floor, smoking debris, spilled acid

> **BUILT, minus the fire and the acid.** `rt_barrel*` ships the floor scorch, ~50 glowing
> coals with smoke threads, and 60 pieces of barrel plate that lie where they land
> (`rt_barrel_life 0` = until the pool evicts them, about thirty barrels).
>
> The plate is **hand-cut art**, not generated geometry: four cut-outs in
> `rt/mat/d64rt/barrel/`, drawn as world-oriented alpha-tested traced quads, mixed with a
> share of small procedural grit (`rt_barrel_small_frac`). The generated version came
> first and was rejected on sight — no procedural tear generator arrives at charred metal
> with hot orange along the break, because what makes those read is that someone drew
> them. Adding a fifth piece is dropping a fifth PNG into **both** `rt/mat` and
> `rt/mat_dev`; one tree alone resolves to a transparent placeholder and the piece
> silently vanishes.
>
> §6.2's flame emitter and §6.3's acid were NOT built and are not currently wanted. The
> acid was always a design decision before it was code — see that section, the constraint
> is real and has not changed.

An exploding barrel currently produces a smoke burst and nothing else. It should leave a
scene: a small fire burning down over a few seconds, a scorch churned into the floor under
it, chunks of barrel lying around still smoking, and a spill of the green stuff it was full
of.

**The trigger is already solved and must not be rebuilt.** `RT_BarrelSmoke`
(`rt_smoke.cpp:1003`) fires on the barrel entering sprite frame **BEXP E**, which is where
`A_Explode` sits in `64ExplosiveBarrel`'s Death state. The comment there records why nothing
else works: the barrel **lingers for a full 1050-tic respawn timer** after exploding, so the
disappearance rule the projectiles use would put the effect roughly twenty seconds late, and
the health test the monster-gunner path uses is meaningless because a barrel in its death
state has no health. Hang everything below off that same edge.

Note the gating, though — the same three-deep problem as §2. `RT_BarrelSmoke` is reached only
when `rt_smoke` **and** `rt_smoke_barrel` are on. Barrel fire and debris must not inherit a
smoke cvar; either hoist the edge detection or give this its own walk, as §2 did.

### 6.1 What is already built and can simply be pointed at this

| Piece | Reuse |
|---|---|
| the explosion edge | `RT_BarrelSmoke`'s BEXP-frame test |
| smoke burst | `RT_SpawnSmokePuffs` + the existing `barrel` profile |
| chunks that fly, bounce and settle | the **debris** half of `rt_sparks.cpp` — gravity, bounce, friction, settling, contact-AO blobs, all shipped |
| the scorched floor | the **arc burn decal** (`rt_arc_burn`) is already a black albedo-darkening fan; a barrel scorch is the same primitive, wider, on a floor rather than a wall |
| smoke off settled chunks | identical to §5's embers — **build the two together**, it is one mechanism |

So most of this is assembly. The genuinely new part is the fire, and the acid is the part
with a hard constraint on it.

### 6.2 The fire

A lingering flame needs three things that do not currently co-exist anywhere: a light that
decays over a few seconds, an emissive thing to look at, and smoke rising off it. The light
and the smoke are solved — `RT_UploadFlameLights` and the ambient-smoke emitters in
`rt_smoke.cpp` already pair exactly this way for torches, and `RT_FlameSpriteOffset` exists
so the two come from one resolved point rather than two.

What a torch does **not** have is a lifetime; it burns forever. So the new work is a
short-lived flame emitter — a position, a decaying intensity, and a countdown — rather than
a new lighting technique. Use the flame flicker rig (`rt_flame_light_flicker` / `_speed` /
`_wobble`) rather than inventing another, and remember the trap §1 states: **drive intensity,
never radius.** Above `rt_dynlight_rsoft` (40 map units) a larger radius is *dimmer*, so a
flame pulsed through its radius comes out inverted.

### 6.3 The acid — read this before designing it

Two facts, both of which contradict the obvious plan:

**RTGL1's fluid is switched OFF in this project.** `rt_fluid`'s compiled default is `true`,
but `tools/d64rt-pins.cfg:16` pins it **false**, and a pin overrides the compiled default.
`RT_SpawnFluid` (`rt_titles.cpp:16`) returns immediately on `!rt_fluid`, so anything built on
it today is inert and will look exactly like a plumbing bug. Find out *why* it is pinned off
— cost, stability, or an artefact — before assuming it can simply be turned on.

**The fluid has ONE global colour.** `rt_blood_color_r/g/b` is a single colour for the whole
simulation, not a per-spawn parameter: `RgSpawnFluidInfo` carries position, velocity,
dispersion and count, and no colour at all. So green acid and red blood **cannot coexist** —
spawning green acid makes every wound in the level bleed green.

That is a hard blocker on doing the acid as fluid, and it should decide the approach rather
than be discovered halfway in. Three options, in the order they are worth trying:

1. **Not fluid at all.** The `fluid` surface class in the debris system already exists and
   already produces splash particles tinted from the texture. Green acid is that, with a
   fixed green ramp instead of a sampled one — no new system, no global-colour problem, and
   it works with `rt_fluid` off.
2. **A spreading decal**, as §6.1's scorch but green and growing, for the puddle it leaves.
   Pairs naturally with option 1 for the spray.
3. **Real fluid**, only if `rt_fluid` is going to be turned on for other reasons anyway and
   the global colour is acceptable — i.e. only if the project is willing to have green blood.

### 6.4 Order

The scorch and the debris are nearly free (both are shipped systems pointed at a new
trigger). The fire is a small new emitter type. The acid is a design decision first and code
second. Do them in that order, and do the smoking-debris part **with §5**, not separately.

## 7. Bullet holes with relief

> **SET ASIDE.** Impact depth is not being pursued for now. The section stands as written;
> nothing below it was built.

Impacts currently leave flat marks. A hitscan hole should read as a **hole** — a punched
cavity in concrete, a shallow dent in metal — and the difference costs one texture set plus a
row in a table, because it rides the surface classification (`rt/data/spark_surfaces.txt`)
that is already shipped and already labelled.

Small, but it is on screen constantly: every shot fired in the game makes one.

**One correction to the premise, and it changes what to build.** The decal path supports
**normal maps, not height maps** — there is no parallax anywhere in it. `RsDecal.frag`'s push
constants are `packedColor`, `textureIndex`, `emissiveTextureIndex`, `emissiveMult` and
`normalTextureIndex`; the only `height` in the whole decal path is the framebuffer's. So the
relief is lighting-derived, not geometric: a hole will look convincingly recessed as the
light moves across it, and will **not** break the wall's silhouette or shift with parallax as
you strafe.

Under a path tracer that is a better deal than it sounds — the normal is what the bounce
lighting actually reads — but it should be understood going in, because "add depth to the
decal" and "make the decal light like it has depth" are different jobs with different
results, and only the second is available.

**How the normal composes, which is the good news.** The shader perturbs the *underlying*
surface normal rather than replacing it:

```glsl
mat3 basis = getONB( underlyingNormal );
out_normal = encodeNormal( safeNormalize2(
    basis[0] * nmap.x + basis[1] * nmap.y + basis[2], underlyingNormal ) );
```

So one hole texture works on every wall at any orientation, and it inherits whatever the
wall's own relief is doing. No per-surface authoring beyond the per-class variants.

**What it needs:**

- One albedo + `_n` pair per class. Two to start: a punched **hole** for `concrete` and a
  shallow **dent** for `metal`. `wood` (splintered) and `flesh` are obvious later additions;
  `fluid` should get nothing.
- The class is already answered — `SurfaceKindOf()` in `rt_sparks.cpp` returns it at every
  impact, which is how debris already picks its profile.
- The geometry is the shipped decal shape: world-space verts, identity transform, one
  primitive per hole. Every trap is already solved in `UploadAoBlob`.

**The trap on this specific path**, and it is stated plainly in the shader above: when no
emissive texture is bound, `ldrEmis = out_albedo.rgb` — the decal's own albedo becomes its
screen emission, scaled by `emissiveMult`. **A bullet hole with a non-zero `emissiveMult`
therefore glows.** Pin it at 0. This is the same fallback that makes it *dangerous* for §4's
melt, where a faint glow looks plausible and is actually uncontrollable.

Also: RTGL1 resolves materials through `rt/data/textures.json` only — the split
`textures_*.json` overlays are inert, and the live build-directory copy has to be edited too.
Budget for that, it has cost this project a session before.

## 8. Ejected shell casings — already built, now pinned ON

**Do not build this.** Retribution ships the entire feature and it is switched off by a
cvar. The work here is turning it on and then making it look right under path tracing; there
is no gameplay code, no DECORATE and no art to author.

What is already in `D64RTR_v15.WAD`:

| | |
|---|---|
| actors | `BulletCasing` and `ShellCasing`, both from `CasingBase` |
| physics | `BounceFactor 0.5`, `WallBounceFactor 0.4`, `BounceCount 5`, `BounceType Doom`, `+MOVEWITHSECTOR`, `+FLOORCLIP`, `+CLIENTSIDEONLY` |
| sprites | 13 × `BCAS` — 8 tumble frames plus **5 different rest poses** chosen at random on landing — 8 × `SCAS`, 6 × `SHDY` |
| sound | 28 lumps: random bounce sets per casing type, impact sets, and a separate liquid-hit set |
| liquid | a casing landing in blood or slime vanishes with its own sound |
| per-weapon ejection | pistol and chaingun throw `BulletCasing` from `(12, 0, 35)`; shotgun throws `ShellCasing` from `(30, 0, 35)`; **the SSG throws two**, at `Random(0,1)` and `Random(-2,-3)` lateral |

The switch is `d64_dropcasings`, declared `server int d64_dropcasings = 0;` and read by an ACS
script that every weapon's Fire state jumps on (`A_JumpIf(CallACS("DropCasings") == 1,
"CasingsFire")`). A menu entry is authored for it too: `Option "Eject Casings",
"d64_dropcasings", "DropCasingsToggler"`.

So step one was **one line in `tools/d64rt-pins.cfg`** — `d64_dropcasings 1`, now pinned
alongside the other `d64_*` pins. Nothing else in the repo referenced the cvar, so before
that line the whole feature was inert. What remains is looking at it.

### What the RT side would actually owe

- **Contact occlusion.** A casing is a sprite: a camera-facing quad with no thickness, so a
  settled one reads as HOVERING and a cast shadow cannot fix it — a flat fragment lit at a
  shallow angle throws almost nothing. This is exactly what `docs/sprite-shadows-and-ao.md`
  exists for and what `rt_spark_debris_ao` already does for chips. Shipped machinery, pointed
  at a new population.
- **Brass is metal**, and these will render as flat dielectrics until they have a PBR entry.
  That is the `tools/_material_labels` pipeline, which belongs to the other agent — flag it
  there rather than editing `textures.json` by hand.
- **Population, and this is the one to check before pinning it on.** The chaingun fires
  ~8.5/s and the casings' Death states are `-1` — they lie there for the rest of the level.
  A sustained fight puts a great many sprites on the floor, each a candidate for a shadow
  proxy and an AO blob. Measure it with a frame time on screen and a held trigger before
  deciding the default, the same way `spark-glowmax` and `arc-glowmax` exist as cost probes.
- **If the sprites are ever regenerated, PIL drops the `grAb` chunk** and they will sink into
  the floor. They should not need regenerating — but a PBR pass that round-trips them would.

## Suggested order

> **HISTORICAL — the order below was followed and the work is done.** Kept because the
> reasoning about what unlocks what is the useful part, and because two of its predictions
> were wrong in instructive ways: §1 was not the cheap self-contained item it looked
> (the real problem was light DENSITY, found only when the Unmaker made it visible), and
> §6's barrels were not "nearly free" — the plate needed hand-cut art and four separate
> renderer fixes before it read as anything.

1. **§1** — self-contained, no new plumbing, immediately changes how the weapon feels.
2. **§2** — the keystone. Nothing else moves until the hook exists, and it also unlocks the
   scorch decals in [`plan-impact-fx.md`](plan-impact-fx.md) for free.
3. **§3** — small once §2 lands.
4. **§4** — build with the scorch decal, not separately.
5. **§5** — the one with the density and double-smoke problems to solve.
6. **§6** — barrels. Its scorch and debris are nearly free once §5 exists, because the
   smoking-settled-ember mechanism is shared; build that part **once**, for both. The acid
   is a design decision (§6.3) before it is any code at all.

**§7 sits outside this order and can be done at any point** — it depends on nothing above,
needs no new plumbing, and is the only item on this page that shows up on every single shot
rather than on one weapon. If the list stalls, do that one.

**§8 is not really on this list at all** — it was one pin plus a look, since the WAD already
ships the whole feature. **The pin is in.** The only real question it raises is the population
cost, and that is answered by looking rather than by planning.

## Open questions

**Answered — the walk.** It does not run when `rt_smoke` is off, and there are two further
gates below that. See §2; the conclusion is hoist, not hook.

**Answered — the Unmaker beam.** There is no beam. Every shot is one `UnmakerLaser`
(`_decorate_extract.txt:1409`), and the actor is **invisible**: its Spawn state is `TNT1 A 1`
and the visible bolt is a chain of ~30 `UnmakerLaserTrail` sprites (`LPUF C`, `RenderStyle
Add`, `Scale 0.65`, `Speed 0`) that it drops behind itself each tic. Only `UnmakerLaser`
should be an impact — the trails are stationary decoration and would each fire one.

Two consequences for §4 that follow from the same DECORATE:

- **`Speed 200`** against the plasma ball's `Speed 40`. This is the case §2's speed-derived
  trace length exists for, and it is a factor of five, not a rounding margin.
- Because the laser itself draws nothing, the melt is the *only* thing that marks where an
  Unmaker shot landed. That raises its value and it also means there is no existing flash
  whose colour it must agree with — unlike §3, this ramp is a free choice.

**Answered by building it — the `Speed 200` above was worse than a trace-length problem.**
It is not that the probe is too short; it is that a `FastProjectile` covers its whole
velocity inside one `Tick()`, so the laser is spawned, crosses the room and explodes
*before the renderer's walk has run once*. `P_ExplodeMissile` clears `MF_MISSILE`, so it is
never observed as a projectile at all and the disappearance rule cannot fire. It is caught
by its `LPUF` death sprite instead — the technique `RT_BarrelSmoke` uses on `BEXP` — and
then probes six ways for the surface, having no heading left to trace along. This cost a
whole tuning session before it was noticed, because the lab plants marks directly and never
fires the weapon.

**Still open — nothing blocking; these are taste calls left deliberately unmade.**

- ~~Should the BFG get §3's treatment?~~ **Yes, decided and built** — green, from `BFE2`'s
  own palette. Whether its own light swamps the arc is now a thing to *look at* rather than
  reason about; `arc-nolight` is the arm that isolates it.
- Does `Decal "PlasmaScorchLower"` actually appear in the path tracer today? See §0 — the
  answer decides whether §4 and the scorch decals are new work or a ramp on existing work,
  and it is a ten-second check in play.
