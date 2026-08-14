# Plan — projectile impact FX: plasma arcs, Unmaker melt, rocket embers

**Status:** planned, not started.

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

**Projectiles never reach the impact hook.** `RT_SpawnImpactSparks` is called from exactly
one place — `p_map.cpp:4900`, inside `P_LineAttack` — which is **hitscan only**. Plasma,
rockets, the BFG and the Unmaker are `MF_MISSILE` actors and never touch it. So today a
plasma bolt hitting a wall produces no sparks, no debris and no surface reaction of any
kind. §3, §4 and §5 are all blocked on the same hook, which is why §2 is the keystone item
and should be built first even though §1 is cheaper.

---

## 1. Plasma light instability — no new lights, no new geometry

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

**Reuse the existing walk.** `rt_smoke.cpp` already iterates the thinker list every tic and
already keeps `RocketMark` records with `lastPos`, `dir` and the matched row. Add a
`RT_NoteProjectileImpact( AActor* )` call inside that walk rather than opening a second
iteration — but **check the gating first**: if the walk is skipped when `rt_smoke` is off,
impact FX would silently inherit the smoke cvar, which is exactly the kind of hidden
coupling that costs a session. If it is gated, hoist the walk, do not duplicate it.

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

With §2 in place this is a spawn rule, not a system: call the existing spark spawner with an
electric colour ramp (the ramps are `constexpr` tables at the top of `rt_sparks.cpp`), a
short life, and high initial speed so the particles crawl along the surface before dying.

Two things worth taking from the shipped system rather than reinventing:

- **The surface classification already applies.** `rt/data/spark_surfaces.txt` says what was
  hit. An arc should behave differently on `metal` (spread, bright) than on `flesh`, and
  `fluid` should probably get nothing at all.
- **`rt_spark_style`** already exists with two looks (0 = pixelated, 1 = realistic). An
  electric impact should honour it rather than adding a third global style.

The one genuinely new element is colour: everything in the spark system so far is a heat
ramp (white → amber → red). Electric wants cyan-white → blue → dark, which is a new ramp
table but nothing more.

---

## 4. Unmaker melt

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

## Suggested order

1. **§1** — self-contained, no new plumbing, immediately changes how the weapon feels.
2. **§2** — the keystone. Nothing else moves until the hook exists, and it also unlocks the
   scorch decals in [`plan-impact-fx.md`](plan-impact-fx.md) for free.
3. **§3** — small once §2 lands.
4. **§4** — build with the scorch decal, not separately.
5. **§5** — last; it is the one with the density and double-smoke problems to solve.

## Open questions

- Does the `rt_smoke` thinker walk run when `rt_smoke` is off? Decides whether §2 hooks into
  it or hoists it.
- Should the BFG get §3's treatment? It is the same projectile category and the same hook,
  but its own light is enormous and may swamp any arc.
- Is there an Unmaker *beam* to consider as well as the projectile, or is every shot a
  `UnmakerLaser` actor? The DECORATE lists `UnmakerLaser`, `UnmakerLaserTrail` and
  `OriginalUnmakerLaserTrail`; only the first should be an impact.
