# Plan — rain and wet surfaces on the storm map

**Status:** planned, not started.

Rain falling in MAP11's storm, and the ground going glossy under the lightning that is
already there.

Related: [`rt-clouds-and-lightning.md`](rt-clouds-and-lightning.md) (the storm itself — read
it first, it is the map this whole page depends on), [`rt-fog.md`](rt-fog.md) (the per-map
opt-in precedent), `rt_dust.cpp` (the particle system this borrows wholesale),
[`rt-lighting-practices.md`](rt-lighting-practices.md) (the colormap trap in §4).

---

## 0. Scope, stated up front

**MAP11 "Terror Core" is the only storm level in the game.** It is the only map whose
MAPINFO carries Hexen's `lightning` keyword, which is what spawns `DLightningThinker`
(`a_lightning.cpp`); nothing else in Retribution has it. So this effect ships for **one
map** unless it is given its own per-map opt-in.

That is the honest cost/benefit and it should be decided before any code is written, not
after. Two defensible positions:

- **Storm-gated.** Rain appears where the game already says there is a storm. One map, zero
  authoring, no risk of rain indoors on a tech base.
- **Per-map opt-in**, the way fog is. `rt-fog.md` already established the pattern of a
  per-map table in the renderer, and there are outdoor maps that would plausibly carry rain
  without being authored storms. More reach, but it is an authoring judgement per map and
  invents weather the level designers did not write.

Recommendation: build it storm-gated, expose the gate as a cvar so a second map can be
tried by hand, and only add a table if the effect proves worth it.

---

## 1. The particles — this is `rt_dust` with gravity

**Do not write a new particle system.** `rt_dust.cpp` shipped a camera-fitted field of tiny
quads on a hashed world-cell grid, with everything rain also needs already solved:

| Problem | Where it is already solved |
|---|---|
| Bounded cost | `rt_dust_max` (900) sets the cell spacing, so the cap is structural, not a counter |
| Draw range | `rt_dust_near` / `rt_dust_far` |
| Not drawing inside geometry | `rt_dust_clip` — skip motes not in open air |
| **Outdoor test** | `sec->GetTexture( sector_t::ceiling ) == skyflatnum`, `rt_dust.cpp:415` |
| Sub-pixel specks | the angular-size floor: `max( world size, len * rt_dust_size_ang )` |

That fourth row is the important one. The sky-ceiling test rain needs — "is this point under
open sky" — is already written and already used, for the moon's contribution to the dust
gate. Rain is the same query with the answer used as the primary gate rather than a bonus
term.

**What actually differs from dust:**

- **Motion.** A mote wobbles on a Lissajous around a fixed home (`rt_dust_drift`,
  `rt_dust_speed`); a raindrop falls. The home-cell hashing stays, but the offset within the
  cell becomes `fmod( time * speed )` down the Z axis, so drops recycle through the cell
  without ever being allocated or freed. Wind shear comes free by tilting that axis — and
  the storm already has a wind concept, since the cloud deck moves.
- **Shape.** A drop at speed is a streak, not a speck. The quad wants to be elongated along
  its velocity, which the dust upload does not do — that is the one genuinely new piece of
  geometry code.
- **The gate is inverted.** Dust is gated on *proximity to a shaft* (`rt_dust_shaft_floor`,
  `_radius`) because dust you cannot see lit is not worth drawing. Rain is gated on **open
  sky**, and should be drawn whether or not lightning is currently firing.

## 2. The lightning is the frame that sells it

The storm's flash machinery is built and exposed: `RT_LightningFlashLevel()`,
`RT_LightningAim()`, `RT_LightningWantsSectorFlash()`, `RT_OnLightningFlash()`, and a
`thunder` CCMD to fire one on demand — which is also the test harness for everything on this
page, since waiting for the storm's own 16–31 tic randomness is not a workflow.

Rain lit by a flash is the shot. Two consequences for the design:

- Drops should take the flash's colour and intensity through the same path the sky does, so
  a flash brightens the rain and the clouds together rather than the rain reading as a
  constant overlay.
- **Do not tie drop spawning to the flash.** Rain that only appears when lightning fires is
  a strobe, not weather.

## 3. Wetness — and the trap that will silently eat it

Wet ground is a **roughness** change: the same albedo, far tighter specular. The 898-texture
labelling pass means every surface now has an authored roughness to move *from*, which is
what makes this newly possible.

**The trap: you cannot do this by editing `textures.json`.** The ORM texture wins outright
over `roughnessDefault` (`HitInfo.inl:529`), and nearly everything in this game has an
`_orm`. This is exactly the failure that made the first 82 material labels inert — the
labels were written, the renderer never read them. A wetness that writes
`roughnessDefault` will do nothing at all, and will do nothing *quietly*.

So wetness must be a **shader-side multiplier applied after the ORM sample** — an engine and
RTGL1 change, in the same place `metallicRoughCut` and `metallicMax` already clamp the
sampled values (`HitInfo.inl`). That is the honest cost of this half: it is not data.

Given that, the design is a single scalar — "how wet is the world right now" — uploaded per
frame and applied to surfaces that are **under open sky**. Which needs a per-surface outdoor
test in the shader, not just the per-point one the dust uses on the CPU. Options worth
weighing before building: a flag set at upload time on primitives whose sector has a sky
ceiling (cheap, coarse, and the sector is already in hand at upload), versus anything
requiring a trace (do not).

**Two more traps that apply:**

- **Sector colormaps tint albedo, not light.** A wet sheen judged on a colour-mapped map
  will read wrong for reasons that have nothing to do with the effect. Judge it on a
  neutral sector first.
- **Wetness must ramp, not switch.** Ground that goes glossy the instant the map loads reads
  as a material bug. Ramp it in over several seconds, and — if the storm is ever made to
  start and stop — let it dry out over considerably longer than it wetted.

## 4. Open questions

- Is there an indoor/outdoor boundary problem? MAP11's outdoor sectors abut indoor ones, and
  a hard per-sector wetness edge across a doorway will be visible. The dust clip has the
  same shape of problem and solved it by being subtle; wetness is not subtle.
- Should rain make sound? Out of scope for the renderer, but it is the thing that will make
  the effect feel half-finished if it is missing, and it is a MAPINFO/SNDINFO edit rather
  than a code change.
- Do drops need to *stop* at the floor, or is it acceptable that they pass through and
  recycle? Splash particles are the impact-FX system's business
  ([`plan-projectile-impact-fx.md`](plan-projectile-impact-fx.md)) and should not be
  reinvented here.
