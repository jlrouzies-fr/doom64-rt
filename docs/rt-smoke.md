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
    rt_smoke_offset        FRACTION along the traced eye->muzzle segment
    rt_smoke_repeat        min TICS between spawns while the trigger is held
    rt_smoke_trail         scale on the per-weapon trail (0 = single burst)
    rt_smoke_curl          lateral turbulence, m/s^2 at one second of age
    rt_smoke_perweapon     apply RT_SMOKE_PROFILES
    rt_smoke_far           the volume's reach when smoke has it to itself
    rt_smoke_ambient       unlit floor, smoke-only frames
    rt_smoke_illum         light from ALL lights
    rt_smoke_light_near    the near-light fade INSIDE a puff
    rt_smoke_light_far     metres beyond which a light stops lighting smoke
    rt_smoke_illum_blend   temporal blend INSIDE a puff
    rt_smoke_spp           direct-lighting samples per froxel INSIDE a puff
    rt_smoke_maxlight      ceiling on in-scattered light INSIDE a puff
    rt_smoke_autospawn     NOARCH; spawn with no weapon, for unattended capture
    rt_smoke_debug         NOARCH; 1 logs the chain, 2..8 are shader probes

Four more belong to the VOLUME rather than to smoke, and therefore change fog
too. They were added chasing smoke's noise and each fixes something that was
wrong for fog as well:

    rt_volume_blur          0..1, a 5-tap spatial filter, taken at SAMPLE time
    rt_volume_dither        per-pixel sample jitter in froxels (stock 2)
    rt_volume_occlude_emis  attenuate screen emission by the medium
    rt_volume_type          0 none / 1 froxel / 2 depth-based
    rt_volume_far           the volume's reach, and therefore its Z resolution
    rt_volume_scatter       the global medium's density
    rt_volume_ambient       its unlit floor
    rt_volume_lintensity    multiplier on scattered light
    rt_volume_lassymetry    Henyey-Greenstein g
    rt_volume_history       frames of per-pixel temporal accumulation

`rt_volume_far` is worth knowing about even if you only care about smoke: it
sets the froxel slice thickness (`far / 64`), which is the resolution limit
everything in §8 runs into.

### Per weapon

`RT_SMOKE_PROFILES` in `rt_main.cpp` bends those defaults per ready weapon,
matched by class-name substring the way `MuzzleFlashTintFor` picks the flash
colour. The rows are **multipliers**, so tuning a cvar still moves every weapon
together and a row only states how that weapon differs.

| weapon | reads as |
|---|---|
| Pistol | a 2.5 cm thread off the barrel, 14-parcel trail, slow growth |
| Chaingun | the same thread, shorter and faster — a machine gun is a pistol here |
| Shotgun / SSG | a SCATTER of small parcels, widely spread. Not one ball |
| Rocket launcher | **nothing at the muzzle**. The rocket carries it (below) |
| Plasma / BFG / Unmaker | **nothing**. Not combustion; the muzzle flash is the effect |

`rt_smoke_perweapon 0` gives every gun the same profile, which is the A/B.

**Why the shotgun is sparse rather than fat.** A wide bore does make a cloud, and
the first version rendered one as a single 0.4 m parcel per shot. It sat in the
middle of the screen and blocked the view, because the froxel grid cannot give a
single parcel any internal structure -- it reads as a grey wall, not as smoke.
Several small parcels thrown wide read as a burst and leave gaps to see through,
which is both better looking and better to play.

**Why a count multiplier of 0 means zero.** `want` rounds UP so a 0.34 multiplier
still yields one parcel; an exact 0 short-circuits instead, and arms no trail. A
weapon with no smoke costs nothing at all.

### The rocket carries its own

A backblast hanging in front of you while the rocket leaves is the wrong read,
and it obscures the shot you just took. So the launcher's muzzle makes none, and
the projectile does the work:

    rt_smoke_rocket          master
    rt_smoke_rocket_every    TICS between trail parcels in flight
    rt_smoke_rocket_radius   metres, small -- a line of big parcels is a wall
    rt_smoke_boom            parcels in the burst when it dies
    rt_smoke_boom_radius     metres

**The death event is DISAPPEARANCE, and that is the part worth remembering.**
Rockets are tracked by pointer while they live, dropping a parcel every couple
of tics. When a tracked one is no longer in the thinker list it has exploded, so
the burst spawns at the last position seen. That needs no hook, no DECORATE edit
and no ZScript -- which matters, because the projectile class is the WAD's
(`64Rocket`), not ours. The class match excludes `Launcher` and `Smoke`, since
`64RocketLauncher` and `64RocketSmokeTrail` both contain "Rocket".

The explosion is the one place a fat cloud is right: it is meant to obscure.

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

**`rt_smoke_far` only applies when smoke OWNS the volume**, which means no fog
*and* `rt_volume_type 0`. It is a resolution knob rather than a reach — the
volume's 64 slices spread over it, so 14 m gives 0.22 m cells — and short costs
nothing there because the base density is 0, so the far slice everything beyond
is shaded with is empty rather than a wall of haze.

**In shipping configuration it therefore does not apply at all.**
`rt_volume_type` is 1, so the volume already holds the global `rt_volume_*`
medium, and taking it over would mean deleting that medium — which is exactly
the bug §4's third trap describes. Smoke gets `rt_volume_far`'s 0.47 m slices
instead, and on a fogged map `rt_fog_far`'s 0.70 m. **That is what sets the
radius floor below**, and it is the real resolution limit of the feature today.

**`rt_smoke_radius`'s floor is the froxel slice, and the slice is bigger than it
looks.** At 0.47 m cells, a 0.18 m puff is 0.77 of a cell across its whole
*diameter*: it lands inside a single froxel and reads as a flicker. The shipping
0.35 spans about 1.3 cells at birth and roughly 3 by the end of its life. This
is the number to raise first if smoke looks like a blink rather than a cloud.

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

### The all-lights switch would delete every light shaft in the level

`volumeAllLights` (`rt_fog_illum`) switches the volume off
`traceDirectIllumination_SpecificLight` and onto the full estimate. That function
is not just "the single-light path": it is the **only** place the sun's
sky-probe test lives (`sunRequireSky`, `sunLeakDebug`, the `traceSunReachesSky`
call). The visible moon shafts *are* that function's output.

So setting the flag per frame because a puff exists turns every shaft in the map
off for as long as the player holds the trigger. `RgDrawFrameSmokeParams` carries
its own `allLights` instead, read **per froxel**: a cell with no smoke keeps the
single-light path and its shafts, a cell inside a puff gets the full estimate and
its own muzzle flash. The store to `g_illuminationVolume` follows the same
predicate, because a cell that computes the estimate and does not store it would
read a stale image forever and never converge.

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
4. **Smoke never writes another medium's value** — the fog's *or* the global
   `rt_volume_*` one. It may only take the volume's settings over when nothing
   else is in it: `!fog.on && rt_volume_type == 0`. The first version tested only
   `!fog.on`, and the result is worth stating plainly because it is the failure
   mode to watch for: on any unfogged map, firing set the global density to 0 and
   the reach from 30 m to 14, and the moon's light shafts — which *are* that
   medium being scattered — vanished until the trigger was released.
   **Smoke adds; it does not replace.** That is what the density-weighted blend
   in `Smoke.h` is for, and the engine has to honour it too.

**The check that makes this real** is `ab-smoke.cmd fogsafe`: MAP26's shipping
fog with `rt_smoke 1`, standing still. It must be **pixel-identical** to
`ab-fog.cmd ramp` — both send zero puffs, and with zero puffs the shader is the
fog's. If they differ, something that should have been per froxel became per
frame. Run it before tuning anything about smoke.

`ab-fog.cmd flsh` is the other one to re-check specifically, since it exercises
the near-light fade that §4 modifies.

---

## 6. Testing

`.	oolsb.cmd <arm> [map] [-- +cvar value ...]`. Arms are config files in
`tools/arms/*.cfg`, exec'd after the base pins so they win; `ab.cmd list` shows
them. Fire at a wall in a dark room.

**Do not add an arm as a command-line string.** That is what
`launch-retribution-rt.cmd` used to do with its ~325 pins, and the assembled line
hit cmd.exe's 8191-character limit — the passthrough sits at the end, so arms were
silently dropped and ran on defaults while the tool printed the values it
believed it had set. Three debugging runs were lost to a probe that never
activated. Pins now live in `tools/d64rt-pins.cfg`.

For an unattended capture, which is how all of this was verified:

```
gzdoom.exe -iwad <doom2.wad> -file <D64RTR_v15.WAD> +logfile <path> +map map03            +rt_smoke_autospawn 30 +i_pauseinbackground 0            +rt_autoshot 110 +rt_autoquit 160
```

`rt_smoke_autospawn` spawns parcels with no weapon and no trigger, so the render
path can be exercised without input; `i_pauseinbackground 0` matters because an
unfocused window throttles to about one tic a second.

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

Shape and emission:

| arm | what it isolates |
|---|---|
| `noTrail` | `rt_smoke_trail 0` — a single burst. The BALL, and the proof that a filament is a shape in time (§8) |
| `edgeonly` | `rt_smoke_repeat 0`. Hold the chaingun: extralight never re-arms, so a whole burst makes one puff |
| `novol` | everything the tool changes EXCEPT the smoke, for isolating an arm-side difference |

Noise, and the whiteout:

| arm | what it isolates |
|---|---|
| `noblur` | `rt_volume_blur 0` — the unfiltered volume. Judge it while MOVING |
| `spp1` | one sample per froxel instead of four. The estimate itself, not the filtering |
| `lowblend` | `rt_smoke_illum_blend 0.08` — ~12 frames of averaging instead of ~5, which is only honest now that the history is reprojected |
| `noclamp` | `rt_smoke_maxlight 0` and `rt_smoke_light_near 0` — the state that produced the plasma whiteout |
| `farlight` | `rt_smoke_light_far 0` — every emissive in the room lights the puff again |

Shader probes, kept because this class of bug recurs (§7):

| arm | what it paints |
|---|---|
| `probeuni` | BLUE everywhere, reading only the debug field. Bottom of the ladder |
| `probeall` | GREEN everywhere while puffs exist — tests the count |
| `probe` | MAGENTA in the froxels a puff covers — tests the positions |

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

## 7. Two bugs that cost a session, and how they were actually found

Neither was in the smoke code, and both are written up in `compat-patches.md`.
They are here because the *method* is the reusable part.

**A stale object file made every read above 1984 bytes return zero.**
`GlobalUniform.cpp` allocates the uniform buffer with `sizeof(ShGlobalUniform)`,
and its object was not rebuilt when the generated header grew for smoke — so the
buffer was 1040 bytes short. Fields below the old size worked; fields above it
silently read zero, with no validation error and nothing in any log.

What broke the deadlock was refusing to keep reasoning. A **probe ladder** in the
shader — paint on a flag read, then on the count, then on the arrays — localised
the failure to the array reads. Then a **swap experiment**: exchanging the two
arrays' positions in the struct. The failure followed the *offset*, not the field
name, which turns "the shader ignores my data" into "the address is wrong", and
that is a different search. Object timestamps finished it.

`tools/build-rtgl.cmd` now deletes the object directory whenever the generated
header changes. `rt_smoke_debug 2..8` are the probes, kept because they cost
nothing and this class of bug recurs.

**The A/B launcher silently drops its own arguments.** The command line assembled
by `tools/launch-retribution-rt.cmd` is 8192 characters and cmd.exe truncates at
8191, so the `-- +cvar` passthrough — which is at the end — never arrives. Three
diagnostic runs were wasted on probes that never ran, each reporting the default
of the cvar the arm claimed to set. Until that is fixed, **verify smoke by
invoking `gzdoom.exe` directly with a short argument list**, and check the
`DEBUGMODE=` field in the log to confirm which mode actually ran.

`rt_smoke_autospawn <tics>` spawns a puff ahead of the camera with no weapon and
no trigger, which is what makes an unattended capture possible at all — pair it
with `rt_autoshot` and `rt_autoquit`.

---

## 8. A filament, and why a sphere could never be one

Asked for a 2 cm wisp off a pistol barrel, the first four attempts all came back
as a ball. Each failure was a different cause and only the last one is about art.

**A single burst is a ball at any radius.** A filament is a shape in TIME: the
thin column exists because the barrel keeps breathing while the earlier parcels
rise away. So a shot arms an emitter (`rt_smoke_trail`) that keeps releasing ONE
parcel every few tics, world-anchored at the muzzle point. One at a time --
releasing pairs collapses it back into a clump.

**A sphere cannot be thin in this grid.** The froxel volume's two axes differ by
a factor of forty: at 1.5 m a cell is 1.7 cm across the screen and 47 cm deep. A
sphere has one radius, so to be resolvable in depth it needs half a slice, and
that same 23 cm is then its width on screen — the depth requirement was setting
the visible size. A puff is now an **ellipsoid stretched along the view**: what
the profile asked for across the screen, half a slice along the view. The stretch
is invisible because it points down the axis you are looking along, and the
density is divided by the same factor so the optical depth is unchanged.

**Real smoke leaves laminar and breaks up later.** `rt_smoke_curl` scales the
lateral push by the SQUARE of a parcel's age, so the thread is straight for the
first fraction of a second and only wanders once it has risen. Each parcel
carries its own phase, or the whole trail waves in unison and reads as a ribbon.

**The emitter follows the barrel; the parcels do not.** World-anchoring the
emitter -- the first version -- left the thread hanging where the shot happened
while the gun walked away from it. The release point is now rebuilt from the
CURRENT viewpoint each time, so smoke keeps coming off the barrel as you turn
and walk, while parcels already released stay where they were born. That split
is the whole trick: the emitter tracks, the smoke trails.

**Expansion must DILUTE.** A parcel that grows 37x and keeps its density is 37x
more smoke than was fired, and that -- not the radius -- was what "too much
smoke" actually was. Density now scales as `radius0 / radius`. Exponent ONE, not
two: what a ray collects is optical depth, density x path length, so `1/r` holds
the depth through the core constant as the parcel spreads. At `1/r^2` it falls as
`1/r` on top of the `(1-t)^2` age fade, the two compound, and a wisp that grows
8x over its life vanishes completely -- which is exactly what the first attempt
did.

The pistol therefore ships at a 2.5 cm across-view radius, a 14-parcel trail at
3-tic spacing, almost no lateral spread at birth, and slow growth.

---

## 9. The noise, and what actually moved it

Smoke is estimated at ONE direct-lighting sample per froxel and one shadow ray.
The surface path has A-SVGF or DLSS-RR behind it; **the volume has nothing** but
a temporal blend. So its variance reaches the screen raw, and a bright light
close to a dense puff is the worst case in the game.

Four things were done, in this order, and the honest scoreboard is:

| change | measured |
|---|---|
| `rt_volume_blur` — 5-tap spatial filter at sample time | **−37%** high-frequency energy |
| reprojected volume history (below) | no measurable change on a STATIC camera, which is expected |
| `rt_smoke_spp 4` — more samples inside puffs | **−15%** |
| `rt_smoke_maxlight` — whiteout clamp | saturated pixels **5.3% → 1.4%** |

**The filter had to move.** The obvious home is `CmVolumetricProcess`, and it
does not work there: that pass writes the image it reads, and is only safe
because each thread reads exactly the one (x,y) column it writes. Reading a
neighbour returns whatever another thread already stored — the finished prefix
sum instead of raw scattering — and the volume collapses. It is taken at SAMPLE
time instead, in `volume_sampleDithered`, where the texture is read-only. XY
only: Z is the integration axis and carries the puff's depth extent.

**The history had to be double-buffered before it could be reprojected.** The
temporal blend read `imageLoad( g_illuminationVolume, cell )` — the same cell
INDEX as last frame. The grid is camera-attached, so that history is wrong the
instant you turn. Reprojecting means sampling a neighbour, which is the same
write-while-reading hazard, so `illumination` is now double-buffered like
`scattering` already was: storage bound to this frame, sampler to the previous.
Cells with no history take the new estimate whole rather than blending toward
black, which would draw a halo at every disocclusion.

**Reprojection fixes camera motion and nothing else.** A moving light — a flying
plasma bolt — genuinely changes the radiance at a fixed world point, so no
temporal method can average it. That is why rocket smoke lit by a plasma bolt
stays the hardest case, and why `rt_smoke_spp` matters: it is the only knob that
improves the estimate rather than filtering it.

**The whiteout was not noise at all.** A light carried at ~0 m lights the froxels
around it by inverse square, so the plasma rifle's glow inside a dense cloud
saturated the screen — the same physics as the flashlight in fog (`rt-fog.md`
§4), which smoke had deliberately disabled its fade for. `rt_smoke_maxlight`
bounds the result rather than the cause, keeping the muzzle flash.

### Emissive surfaces were never occluded by the medium

Reported as "the panel lights leak through the smoke", and it is a one-line
ordering bug in `CmPrepareFinal`: screen emission is added AFTER the volumetric
composite and OUTSIDE its guard, so an emissive panel shines through fog and
smoke at full strength. `rt_volume_occlude_emis` multiplies it by the
transmittance.

**This was a fog bug too**, for as long as fog has existed — every fogged map had
unoccluded emissives. Turning it on therefore changes those nine maps, and MAP26
is worth a look.

### The dark outlines are older than the denoising

Geometry seen through smoke is traced by thin dark outlines. They are NOT new:
the same rectangles are visible around the wall panels in the very first working
smoke capture, buried in the noise. Denoising revealed them rather than causing
them.

Ruled out by test, not by argument: the spatial filter (present at
`rt_volume_blur 0`) and the sample dither (present at `rt_volume_dither 0.4`).
The emissive fix above removes the bright-edge half. What remains is a silhouette
compositing artifact — adjacent pixels either side of an edge integrate
genuinely different amounts of medium — and it is **open**.

---

## 10. Known limits

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
- **Coarse in every shipping configuration** (§3). Whoever else is using the
  volume owns its reach, so the slices are 0.47 m (global medium) or 0.70 m
  (fogged map) rather than `rt_smoke_far`'s 0.22 m. A puff is a couple of cells
  across, and that — not the puff count — is the ceiling on how smoke looks.
  Fixing it properly means a smoke grid decoupled from `volumetricFar`, which is
  the same upgrade the buffer limit below points at.
- **Extinction is monochrome**, inherited from the fog (`rt-fog.md` §2): a puff
  fades what is behind it *toward* its colour rather than filtering by it. For
  grey powder smoke this is invisible; for a strongly coloured puff it would not
  be.
- **Ambient is global to the volume.** On a fogged map a puff inherits
  `rt_fog_ambient`, which at the shipping 1 is more than twelve times
  `rt_smoke_ambient`. That is why the fog and the unfogged case need judging
  separately.
- **Player weapons only.** Monsters' guns do not smoke. The player's rocket does
  (§3), by tracking the projectile.
- **Dark outlines on geometry seen through smoke** (§9), still open.
- **One sample per froxel is the floor.** `rt_smoke_spp` raises it only inside
  puffs, which is what makes it affordable; the surrounding volume is still 1 spp
  with no spatial filter of its own beyond the sample-time taps.

---

## See also

- `docs/rt-fog.md` — the medium this extends, and §4's near-light fade
- `docs/rt-fog-implementation.md` — the froxel chain end to end, and its traps
- `compat-patches.md` — the RTGL1 patch log entry
- `tools/ab-smoke.cmd` — the arms above
