# Plan — heat haze over lava and fire

**Status:** planned, not started.
**Why it is worth doing:** the lava is a real emitter now — it lights the room, it drifts,
it breathes — but the air above it is perfectly clear. A hell floor that glows and yet
leaves the wall behind it razor sharp reads as a lit texture rather than as heat.

Related: [`docs/rt-smoke.md`](rt-smoke.md) (the froxel volume and the CPU puff sim),
[`docs/flame-lighting.md`](flame-lighting.md) (all 84 flame sprites and where they are lit).

---

## 1. The capability that is already there and unused

RTGL1 exposes a primitive flag this project has never set:

```
RG_MESH_PRIMITIVE_THIN_MEDIA
```

Nothing in `sourcecode/gzdoom-rt/src` references it. `GLASS`, `MIRROR`, `LAVA`, `WATER`,
`DECAL` and `EMISSIVE_OVERRIDE` are all wired; `THIN_MEDIA` and `ACID` are the two that
are not.

The tagging pattern to copy is `l_waterflag` in `rt_draw.cpp:869` — a lambda that returns
primitive flags per surface, combined at `rt_draw.cpp:1142`. Water, lava and no-caustics
are all selected there by the same mechanism, so a `l_thinmediaflag` sits naturally beside
them.

## 2. Two possible sources for the haze

1. **A quad above lava flats.** Spawn a thin horizontal primitive a fixed height over every
   surface that already matches the lava predicate (`l_lavaflag`), flagged `THIN_MEDIA`.
   Cheap, and it follows the existing lava-light grid machinery in `rt_lights_fx.cpp`,
   which already walks those flats and knows their extents.
2. **Reuse the smoke volume.** `rt_smoke.cpp` already simulates puffs on the CPU and feeds
   the froxel medium, and `RT_AMBIENT_FLAMES` already spawns from flames. A "hot air"
   source with near-zero albedo and a strong refractive component would ride existing
   plumbing, and would automatically be localised near the player like the rest of smoke.

Route 2 is more in keeping with what exists; route 1 is easier to judge because it is
static and always in the same place. Try 1 to answer "does refraction over lava look
right", then move it onto the smoke system if it does.

## 3. Scope

Lava first, since it is the strongest case and the surfaces are already identified. Then,
if it holds up: the big fires (`64BigFire`), and the `FIRELAVA`/`FIRELAV3` wall textures.
Candles and small torches almost certainly should **not** get it — 84 flame sprites each
carrying a medium is exactly the density mistake §20 warns about.

## 4. Traps

- **The lava predicate already exists — use it.** `l_lavaflag` decides what is lava for the
  emissive path. If the haze uses a second, hand-written list of texture names, the two
  will drift and some lava will glow without shimmering.
- **`rt_lava_debug 1` paints every surface the shader thinks is lava magenta.** Run it
  first; the answer to "which flats are lava" is already instrumented.
- **Refraction interacts with the smoke and fog media.** All three live in the same froxel
  volume, and `rt_volume_far` changes the density of everything in it at once. A haze
  tuned on MAP22 will be a different strength on a map with different fog reach.
- **Do not let it read as fog.** The distinguishing feature of heat is *distortion of what
  is behind it*, not opacity. If the effect ends up looking like grey haze, it is the wrong
  effect and should be turned down rather than tinted.

## 5. Cvars to expose

Follow the `rt_lava_*` naming already in `rt_cvars.inc`: `rt_lava_haze` (on/off),
`rt_lava_haze_strength`, `rt_lava_haze_height`, `rt_lava_haze_speed`. All in one block,
one line each, in `rt_cvars.inc` and nowhere else.

## 6. How to judge it

The lava maps: MAP22 and MAP28, plus `tools/ab-lava.cmd` which already exists for lava A/B
work. Look at a wall *through* the air above a lava lake, and at a distant doorway — the
tell is whether the geometry behind the heat wobbles, not whether the air is visible.
