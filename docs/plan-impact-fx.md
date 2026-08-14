# Plan — impact sparks and scorch decals

**Status:** planned, not started.
**Why it is worth doing:** every shot in this game currently ends in a puff of smoke and
nothing else. Under path tracing a spark is a small moving emitter that lights the wall it
bounces off, and a scorch mark is persistent evidence that a fight happened here. Both are
cheap, and both play to what the renderer is already good at.

Related: [`docs/rt-smoke.md`](rt-smoke.md) (the puff spawner these ride on),
[`docs/blood-persist.md`](blood-persist.md) (persistence, lifetimes and the decal path),
[`docs/sprite-illumination.md`](sprite-illumination.md) (what actually casts light).

---

## 1. Sparks

**Where they come from.** `rt_smoke.cpp` already owns six spawn sources — weapons, monster
guns, projectiles, barrels, flames — and already runs a CPU particle sim. A spark source is
another entry in that list, spawned at the same impact point the smoke puff uses, with a
different lifetime, gravity and colour ramp.

**What makes them cast.** Not `emissiveMult`, which is screen glow only and lights nothing.
A sprite casts when it carries `lightIntensity` + `lightColorHEX`; that is the whole
mechanism, and it is why the flames are lit engine-side instead. For sparks the cleanest
route is the flame one: spawn short-lived analytic lights alongside the particles, the way
`RT_UploadFlameLights()` does in `rt_lights_fx.cpp`.

**Budget.** A shotgun blast is 7–20 pellets. Sparks must be capped globally, not per
impact, or a super-shotgun into a wall becomes a light storm. `rt_gore_max` is the
precedent — a global cap with nearest-first culling.

**Scope.** Bullet weapons on metal and stone only. Not on flesh (that is blood, which
already works), not on liquids.

## 2. Scorch decals

**Where they go.** Plasma, rocket and BFG impacts. The decal path is live — blood splats
use it — so this is a new decal texture and a spawn rule, not new plumbing.

**The trap that is already written down:** RTGL1 decals need **world-space vertices**. A
decal built with a transform silently discards every fragment: nothing renders, nothing
errors. See `docs/blood-persist.md`.

**Lifetime.** Blood persistence had to solve exactly this and the answer was not in the
renderer — the one-second lifetime was in the WAD's DECORATE. Check where a scorch's
lifetime is actually decided before adding a renderer cvar for it.

**Fade.** Scorch should fade by *shrinking its alpha*, not by tinting toward the floor
colour: the floor colour is not knowable, and sector colormaps tint albedo rather than
light, so a "matching" tint will be wrong on any coloured map.

## 3. Optional third piece — glowing plasma burns

A scorch from plasma could carry a short emissive tail: bright cyan for ~0.3 s, fading to
plain soot. That gets a genuinely ray-traced moment — a fading pool of light on the floor
after a firefight — for the cost of one extra decal layer with an `_e` mask.

If it is done: the emissive mask must be a **raw** `_e`, never sampled from the albedo.
The ray-traced path uses `_e` directly and only the rasterized path multiplies by
baseColor.

## 4. Cvars

`rt_spark_*` (on, count, life, intensity, cap) and `rt_scorch_*` (on, life, size, cap), one
line each in `rt_cvars.inc`. Off by default until judged in play.

## 5. How to judge it

The smoke lab (`tools/smoke-lab.cmd`, MAP97 dark / MAP96 bright) is the right place — it
exists precisely so muzzle effects are judged in a controlled room rather than in a level.
Sparks are a dark-room effect; scorch marks want the bright beige room where the mark has
to read against a light floor.
