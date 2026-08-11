# Localised volumetric smoke

`docs/rt-fog.md` built a participating medium in RTGL1's froxel volume: real
lights scatter through it, so fog around a torch glows and fog in a dark corridor
stays dark. Its §8 lists the limit this document is about —

> **The fog is global to the level.** [...] Per-sector fog would need the medium
> bound to geometry, which the froxel volume has no notion of.

One density for the whole map. No way to say *there is smoke here*.

This is that: a small list of world-space spheres whose density is **added** to
the same medium, per froxel. Fire the gun, and a puff of real medium appears at
the barrel and is lit from inside by the muzzle flash that made it.

---

## 1. What this is, and what it deliberately is not

**Not a sprite.** A billboard of smoke art is what the game already does and it
does not interact with light at all — it is a texture, drawn at an alpha, and a
muzzle flash going off inside it changes nothing. `docs/rt-lava.md`'s haze layer
was removed for exactly this reason.

**Not a second volume.** The puffs live in the froxel grid the fog already
fills. That is what buys the whole feature for one loop in one shader:

- lighting is the froxel pass's existing NEE/ReSTIR estimate, so every lamp,
  lava pool and muzzle flash in the level lights the smoke;
- occlusion is free. `CmVolumetricProcess.comp` is a straight front-to-back
  prefix sum over whatever `RtVolumetric.rgen` wrote, so a puff darkens what is
  behind it and is darkened by fog in front of it with no extra work at all.

**The test that tells smoke from a grey blob**: fire at a wall in a *dark* room
and watch the first two or three frames. The puff should be visibly brighter
while its own muzzle flash is still lit than it is a moment later.
`tools/ab-smoke.cmd nolight` is the same puff with that taken out.

---

## 2. Why the simulation is on the CPU

The obvious reference is Duke-RT, which has a full GPU smoke system —
~14.5k lines of `nri_smoke*.{h,cpp}` with particle simulation, a dedicated
world-space grid, its own lighting and temporal passes, and emitters driven from
map rules, actors and weapon-fire events. None of it ports (NVIDIA NRI and HLSL,
not RTGL1 and GLSL), but the data model was worth copying and was: a puff here is
their `NRISmokeParticleGpu` minus the fields a CPU sim does not need.

Three reasons the sim is nonetheless on this side, and none of them is "it was
easier":

**The froxel grid caps the detail, not the particle count.** 160×88×64 cells.
Ten thousand GPU particles still land in ~0.22 m cells and read as blobs. Detail
has to come from the *shader* — per-froxel noise modulating the puff density —
which is cheap and completely independent of how many particles exist. That is
the upgrade this design leaves open (§7).

**Only the CPU can see the level.** Environment reaction means the ceiling, the
floor, the sector you are standing in. That is `PointInSector`, `floorplane`,
`ceilingplane` — game state, on this side. A puff flattening against a low
ceiling and spreading instead of climbing through it is CPU work; a GPU sim gets
depth-buffer collision at best, which is screen-space guesswork.
`ab-smoke.cmd drift` is that behaviour on its own.

**The counts are tens.** Muzzle smoke is three puffs a shot against a 24 budget.
Duke-RT's machinery exists because they want continuous rocket trails and
per-map ambient sources at scale — which is a real reason, and the reason §7
lists a buffer upgrade rather than pretending 32 is enough forever.

---

## 3. The knobs

    rt_smoke               master
    rt_smoke_density       optical depth per METRE at the core
    rt_smoke_color         scattering albedo (hex)
    rt_smoke_count         puffs per shot
    rt_smoke_budget        live puffs uploaded, max 32
    rt_smoke_life          seconds
    rt_smoke_radius        metres at spawn
    rt_smoke_growth        metres/second of expansion
    rt_smoke_speed         initial speed along the barrel, m/s
    rt_smoke_spread        random lateral velocity, m/s
    rt_smoke_rise          buoyancy, m/s^2
    rt_smoke_drag          velocity damping per second
    rt_smoke_inherit       fraction of the PLAYER's velocity, 0..1
    rt_smoke_offset        metres ahead of the muzzle
    rt_smoke_repeat        min TICS between spawns while the trigger is held
    rt_smoke_far           the volume's reach when smoke has it to itself
    rt_smoke_ambient       unlit floor, smoke-only frames
    rt_smoke_illum         light from ALL lights
    rt_smoke_light_near    the near-light fade INSIDE a puff
    rt_smoke_illum_blend   temporal blend INSIDE a puff
    rt_smoke_debug         NOARCH; what was actually sent

All `RT_CVAR` (`CVAR_ARCHIVE`) except `rt_smoke_debug`, and **all pinned in
`tools/launch-retribution-rt.cmd`** — a launcher pin overrides the compiled
default, so a value left in the ini by an `ab-smoke.cmd` arm would otherwise
follow you into normal play.

### Four of them are not obvious

**`rt_smoke_repeat` exists because the rising edge is not enough.** A shot is
detected as the rising edge of `player->extralight`, which a weapon's `Flash`
state raises with `A_Light1`/`A_Light2` and clears with `A_Light0`. That is
correct for the pistol and the shotgun. It is wrong for the chaingun and the
plasma rifle, which **re-enter their flash state before `A_Light0` runs**, so
extralight never returns to 0 and the edge fires once for an entire burst. The
5-tic repeat is the fallback, and it is a little under the chaingun's 4-tic cycle
so a held trigger produces roughly one burst per shot without emptying
`rt_smoke_budget` into the first half second. `ab-smoke.cmd edgeonly` is the
failure, kept because it is invisible on the two weapons you would test with.

**`rt_smoke_density` is per METRE, and the fog's is not.** `RtVolumetric.rgen`
applies its coefficient per *cell*, which is why `rt-fog.md` §6 has to warn that
shortening `rt_fog_far` makes the same fog density read thicker. Smoke pays the
slice thickness engine-side instead, so a puff looks the same whatever the
volume's reach is — including on a fogged map, where the reach is not ours to
choose. The conversion is one multiply in the packing loop and it is worth the
line.

**`rt_smoke_far` is a resolution knob, not a reach.** The volume's 64 slices
spread over it: 14 m gives 0.22 m cells, which resolve a 0.18 m puff; the 30 m
of `rt_volume_far` gives 0.47 m and the puff collapses into a single slab.
`ab-smoke.cmd reach30` is that failure. Short costs nothing here because the base
density is 0 when smoke has the volume to itself, so the far slice — which
everything beyond the plane is shaded with — is empty rather than a wall of haze.
**A fogged map always wins this**, so smoke on MAP26 is coarse (45/64 = 0.70 m).

**`rt_smoke_inherit` picks which wrong answer you get.** A puff is born in the
world, but the gun that made it is moving. At 0 the smoke visibly lags a strafing
player and reads as stuck to the world; at 1 it is glued to the camera. 0.85 is
where the lag stops being the thing you notice. `ab-smoke.cmd walk` and `glued`
are the two ends.

---

## 4. The two traps, and why both fixes are per froxel

Both of these change values the **fog** depends on. The obvious implementation
of each is per *frame*, and that is the version that quietly retunes MAP26 every
time the player pulls the trigger. Because the smoke density at a froxel is
known before the lighting block runs, both are chosen per cell instead — a cell
with no smoke in it takes the fog's value bit for bit.

### The near-light fade would erase the effect

`rt-fog.md` §4: a light standing in the medium lights the froxels around it by
inverse square, so a light at ~0 m whites out the screen, and
`rt_fog_light_near` (2 m) fades in-scattering out within that distance **of a
light**. That paragraph ends "muzzle flashes get the same treatment for free,
which they needed for the same reason".

They needed it for fog filling the whole screen. Muzzle *smoke* lit from inside
by the flash is the entire look, and a muzzle flash is at ~0 m from its own
smoke — so at 2 m the puff is fully faded and there is nothing to see.

`rt_smoke_light_near` is therefore **0**, deliberately the opposite of the fog's
2. `ab-smoke.cmd nearfade` applies the fog's value inside the puff and is worth
looking at once: it is the whole feature disappearing while every cvar still
says it is on.

### The 0.05 temporal blend is far too slow for a muzzle flash

`RtVolumetric.rgen` blends the all-lights estimate against last frame's at 0.05.
That is right for fog, which changes no faster than the player walks. A muzzle
flash lasts 2–3 frames: at 0.05 the volume needs ~0.7 s to respond and as long
again to let go, so the smoke would light up **after** the flash and then linger.

`rt_smoke_illum_blend` is 0.4 inside a puff and the literal 0.05 everywhere
else. Higher is more responsive and noisier, and the volumetric is not denoised,
so this is a tuning arm rather than a constant to settle once —
`ab-smoke.cmd blendslow` (the stock 0.05) against `blendraw` (0.9).

**The seam this leaves.** A froxel at the edge of a puff switches blend rate
between frames as the puff drifts across it. The density falloff is smooth and
reaches zero at the rim, so the switch happens where the puff contributes almost
nothing — but that is an argument, not a measurement. If it ever shows, the fix
is to lerp the blend by `smoothstep( 0, eps, smoke.a )` rather than branch on it.

---

## 5. Smoke must not touch the fog, and that is checked

The fog is shipped, and its transmittance ladder in `rt-fog.md` §6 is arithmetic
rather than taste. Four rules keep smoke out of it:

1. **Separate code.** Own cvar block, own `RgDrawFrameSmokeParams` (a new `pNext`
   struct, *not* more fields on `RgDrawFrameVolumetricParams` — a struct that
   does not change size cannot break a caller that knows nothing about smoke),
   own uniform group appended after the whole volume block, own GLSL header, own
   doc, own A/B tool. `RT_ResolveFog`, `ResolvedFog` and `RT_FOG_PRESETS` are
   untouched.
2. **The shared block collapses, bit for bit.** With `smokeCount` 0 the loop does
   not execute and the medium arithmetic returns the fog's two lines exactly.
   *Algebraically* equal was not good enough and the difference is the reason
   `smoke_blendTint` has an early return: the general expression reduces to
   `( d · tint ) / d`, which is `tint` on paper but can land an ulp away in
   floating point — and `fogsafe` asserts a pixel-identical frame, not a close
   one. The reasoning is written out in `Smoke.h` beside the code.
3. **Both trap fixes are per froxel**, never per frame (§4).
4. **Smoke never writes a fog value.** Every edit inside the volumetric params is
   `fog.on ? <the value that shipped> : ...`, so a fogged map takes the branch it
   has always taken. The smoke-only branch is unreachable when fog is on.

**The check that makes this real** is `ab-smoke.cmd fogsafe`: MAP26's shipping
fog with `rt_smoke 1`, standing still. It must be **pixel-identical** to
`ab-fog.cmd ramp` — both send zero puffs, and with zero puffs the shader is the
fog's. If they differ, something that should have been per froxel became per
frame. Run it before tuning anything about smoke.

`ab-fog.cmd flsh` is the other one to re-check specifically, since it exercises
the near-light fade that §4 modifies.

---

## 6. Testing

`tools/ab-smoke.cmd <arm> [map]`, default MAP01 — an unfogged map, where smoke
has the volume to itself and `rt_smoke_far` decides the resolution. Fire at a
wall in a dark room.

| arm | what it isolates |
|---|---|
| `full` | the shipping numbers |
| `fat` | 4× density, 2× radius, 4 puffs. **Run this first** — if it shows nothing, the problem is plumbing, not values |
| `thin` | a third of the density: where the puff stops occluding |
| `still` | no rise, drag, or growth, 6 s life. Shape and froxel resolution with the motion taken out |
| `drift` | 4 s at double the rise: watch a puff climb, flatten against the ceiling and spread. The CPU sim reading the sector |
| `walk` / `glued` | `rt_smoke_inherit` 0 and 1 — the two wrong answers |
| `nearfade` | trap 1: the fog's 2 m fade inside the puff. The effect vanishing |
| `blendslow` / `blendraw` | trap 2: the stock 0.05 against 0.9 |
| `reach30` / `reach8` | `rt_smoke_far` as slice thickness |
| `off` | `rt_smoke 0` — the before |
| `nolight` | `rt_smoke_illum 0`. Ambient plus one light, i.e. usually nothing: flat grey soup |
| `debug` | `rt_smoke_debug 1` |
| `fogsafe` | **the fog regression** (§5). MAP26, must match `ab-fog.cmd ramp` |
| `fogsmoke` | MAP26, firing. Both media in one volume, and the puff coarser because the fog owns the reach |

`rt_smoke_debug` prints once a second: live puff count, how many were sent, the
nearest puff's position, radius and density in metres, the volume's reach and its
slice thickness. That is what separates *no smoke visible* from *no puffs
spawned* — the failure this project has lost sessions to.

**`rt_mzlflsh 0` disables smoke too.** The puff is born at the muzzle flash's
resolved position — already traced back out of any wall the raw offset would have
put it inside — so the light and the smoke it lights are one point rather than
two similar calculations that can drift apart. `rt_mzlflsh` is `CVAR_ARCHIVE` and
was **not** pinned before this work; it is now, because an ini value could
otherwise have turned the smoke off with no `rt_smoke_*` cvar saying so.

---

## 7. Known limits

- **Puffs are spheres.** Real smoke is not, and at these radii the eye can tell.
  The fix is not more spheres, it is per-froxel noise modulating the density —
  cheap, independent of particle count, and the natural next step.
- **32 puffs, hard.** They ride in the global uniform (1 KB) rather than a
  storage buffer, which is the right trade at this count and the wrong one for
  rocket trails or per-map ambient sources. That upgrade is a `LightManager`
  clone plus a descriptor set, and it should wait until something actually needs
  the capacity.
- **The volume is camera-fitted.** A puff beyond the far plane is not
  represented at all. For muzzle smoke, which is by definition in front of your
  face, this has not mattered.
- **Coarse on a fogged map** (§3): the fog owns `volumetricFar`, so the slices
  are 0.70 m instead of 0.22 m and a puff reads much softer. Judge
  `rt_smoke_density` on MAP26 as well as on an unfogged map.
- **Extinction is monochrome**, inherited from the fog (`rt-fog.md` §2): a puff
  fades what is behind it *toward* its colour rather than filtering by it. For
  grey powder smoke this is invisible; for a strongly coloured puff it would not
  be.
- **Ambient is global to the volume.** On a fogged map a puff inherits
  `rt_fog_ambient`, which at the shipping 1 is more than twelve times
  `rt_smoke_ambient`. That is why the fog and the unfogged case need judging
  separately.
- **Player weapons only.** Monsters' guns, rockets and explosions are each an
  emitter against the same pipeline, and none of them exists yet.

---

## See also

- `docs/rt-fog.md` — the medium this extends, and §4's near-light fade
- `docs/rt-fog-implementation.md` — the froxel chain end to end, and its traps
- `compat-patches.md` — the RTGL1 patch log entry
- `tools/ab-smoke.cmd` — the arms above
