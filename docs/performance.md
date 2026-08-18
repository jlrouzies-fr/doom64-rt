# Performance - measured, not assumed

First frame-cost measurements this project has ever taken (2026-08-18, branch
`performance`). Everything here is a number off the instrument described below,
on an RTX 5090 / 9800X3D at a 2534x1369 window.

## The instrument

`stat rt` (`src/common/rendering/rt/rt_stats.cpp`) splits the frame into the four
phases the RT path can spend it in, and prints the gzdoom-side counters beside
them so the RT numbers have a denominator:

```
RT:  start=     rgStartFrame (swapchain acquire, scene import, the N-2 fence wait)
     lightgen=  our ten per-frame light walks, rt_main.cpp's RT_Upload*Lights block
       (upload= the rgUploadLight time inside that bracket, a SUBSET of lightgen)
     primupload= summed rgUploadMeshPrimitive
     drawframe= rgDrawFrame: BLAS/TLAS build, every GPU pass, present
GZD: bsp / wall / flat / sprite / 2d / scene, plus primitive and light counts
```

Two things make it usable without a screen:

- `rt_stat_force 1` keeps the `glcycle_t` counters running when the stat is not
  displayed. Without it every phase reads `0.000`, which looks like "the RT path
  is free" rather than "the timers are off" (`hw_clock.cpp` `checkBenchActive`).
- `rt_stat_every N` prints the same numbers to the console every N tics, so an
  unattended run leaves a log with measurements in it. Implies `rt_stat_force`.

Typical measurement run:

```
tools\launch-retribution-rt.cmd 34 -- +rt_stat_every 70 +rt_autoquit 190 +rt_vsync 0
```

## THE FIRST RESULT: turn vsync off before measuring anything

Every A/B below was flat until this was found, and it is worth stating plainly
because it invalidates any measurement taken with it on.

With `rt_vsync 1` (which is what `gzdoom-rt2.ini` carries - the cvar is archived
and **not pinned**), `drawframe` sits at a fixed ~6.4 ms and responds to nothing:

| arm | drawframe | note |
|---|---|---|
| baseline, `rt_vsync 1` | 6.37 ms | |
| DLSS ultra-perf, 846x456 | 6.34 ms | 1/9 the ray-traced pixels |
| DLAA, 2534x1369 | 6.38 ms | 9x the pixels of the above |
| fixture lights off (1214 -> 115 lights) | 7.12 ms | |
| `rt_cpu_cullmode 1` (638 -> 465 prims) | 6.64 ms | |
| volumetrics off | 6.46 ms | |
| **`rt_vsync 0`** | **0.52 ms** | |

That is a FIFO present block, not work. The resolution changes were confirmed
live in the log (`DLSS2: creating feature 846x456 ->` vs `2534x1369 ->`), so the
flatness is a real null result and not a change that failed to apply.

This does **not** by itself explain the in-play symptom - a frame rate below the
refresh rate with the GPU idle is not what a present block looks like from the
outside. But it does mean **no benchmark run may be taken with vsync on**.

## Baseline, vsync off, standing at the map's spawn

| | MAP13 | MAP20 | MAP34 |
|---|---|---|---|
| sectors / lines / sides | 247 / 2261 / 3280 | 294 / 2755 / 4307 | 706 / 5666 / 9548 |
| rgStartFrame | 1.202 | 0.127 | 0.096 |
| lightgen | 0.417 | 0.428 | 0.675 |
| primupload | 0.286 | 0.603 | 0.280 |
| rgDrawFrame | 0.556 | 0.691 | 0.676 |
| **RT total** | **2.461** | **1.850** | **1.727** |
| **BSP** | **0.195** | **0.418** | **3.778** |
| gzdoom scene total | 0.683 | 1.520 | **4.515** |
| primitives / frame | 734 | 1903 (peak 2253) | 1667 |
| lights / frame | 169 | 174 | 501 |

Corrections this forced on the pre-measurement diagnosis:

- **Primitive counts are hundreds to ~2000, not "thousands".** Per-primitive costs
  (the 28-entry `kLiquids` strcmp table, the hash-map touches) are therefore a
  fraction of a millisecond, not a headline. `primupload` peaks at 0.6 ms.
- **`rgDrawFrame` CPU is 0.55-0.7 ms**, not the dominant cost. One BLAS per
  primitive rebuilt every frame is real, but at this primitive count it is cheap.
- **Light count does not drive `rgDrawFrame`.** 1214 -> 115 lights changed it by
  less than noise. What lights cost is *our* walk to generate them (`lightgen`).
- **The BSP visibility expansion was the largest single CPU item in the game**, and
  only on the big map: 3.778 ms of a 4.5 ms scene on MAP34.

## Fix 1 - the O(sectors x segs) visibility expansion

`hw_bsp.cpp`'s `rt_nocull` pass asked, for every sector near the camera, "does this
sector share a two-sided seg with an already-visible one?" by scanning **every seg
in the level** - inside the loop over every sector. That question is a property of
the seg, not of the candidate, so it is now answered for all sectors in one pass
over the segs before the sector loop.

| | BSP before | BSP after | scene before | scene after |
|---|---|---|---|---|
| MAP34 | 3.778 | **0.243** | 4.515 | **0.966** |
| MAP20 | 0.418 | **0.181** | 1.520 | 1.296 |
| MAP13 | 0.195 | **0.065** | 0.683 | 0.490 |

**3.5 ms/frame saved on MAP34**, 15.5x on the loop itself.

Image-identical, and proven so rather than argued: `rt_cull_verify 1` re-runs the
original predicate alongside the new one and reports disagreements. It printed
`0 sector(s) differ` on every one of 196 sampled frames across MAP02, MAP20 and
MAP34. The cvar stays in the tree as the gate to re-run if this code is touched.

Note this is *not* the same as reducing `rt_cpu_nocullradius`: the radius decides
which geometry reaches the acceleration structure and is load-bearing for light
leaks (`moon-and-sky-leaks.md` S5.1). The shell is unchanged; only the cost of
computing it moved.

## Fix 2 - the instrument had to be split before it could attribute

The first bracket lumped our light walks and our effect systems together as
`lightgen`, and across a 40-second firefight that number went 0.40 -> 1.63 ms.
The obvious reading -- "the light walks get expensive in combat" -- was wrong.
Splitting the bracket into `lightgen` (the ten level light walks) and `fx`
(smoke, projectile impacts, sparks, arcs, dust) put the growth where it belongs.

## The play-time cost, measured at last

`docs/plan-projectile-impact-fx.md:553` asked for exactly this and never got it:
*"the casings' Death states are -1 - they lie there for the rest of the level. A
sustained fight puts a great many sprites on the floor, each a candidate for a
shadow proxy and an AO blob. Measure it with a frame time on screen and a held
trigger before deciding the default."*

Method: MAP13, a crowd summoned in six waves, then `rt_autofire` holds the
chaingun trigger for 1400 tics (40 s). `rt_stat_every 105`, `rt_vsync 0`.

| elapsed | prims | lightgen | fx | primupload | drawframe |
|---|---|---|---|---|---|
| 6 s | 490 | 0.256 | 0.159 | 0.233 | 0.515 |
| 12 s | 688 | 0.261 | 0.242 | 0.271 | 0.555 |
| 24 s | 1010 | 0.259 | 0.350 | 0.351 | 0.602 |
| 36 s | 1580 | 0.268 | 0.924 | 0.414 | 0.633 |
| 48 s | 2009 | 0.271 | **1.226** | 0.430 | 0.614 |

- **`lightgen` is flat.** The level light walks cost 0.26 ms and do not care what
  is on the floor. Baking the fixture-candidate lists would save that 0.26 ms and
  no more - a much smaller prize than it looked before this split existed.
- **`fx` grows 8x** and `prims` 4x, linearly, **with no plateau** in 40 seconds.
  Nothing here is bounded by a cap the way every light system is.
- `drawframe` barely moves, confirming again that per-primitive BLAS work is not
  where this frame goes.

Isolation, same fight, `d64_dropcasings 0 +rt_spark_debris 0 +rt_arc_burn 0`:

| | prims @48s | fx-inclusive walk @48s |
|---|---|---|
| all persistence on | **2009** | **1.505** |
| persistence off | **773** | **0.419** |

and with persistence off the number is **flat for the whole fight**. So the
degradation is caused by the persistent populations, not by combat as such:
casings (`d64_dropcasings 1`, Death states `-1`), spark debris, and the scorch
decals (`rt_arc_burn_life 0` = forever). Roughly 26 primitives per second of
held trigger, each also an AO blob candidate and a TLAS instance.

This is what "it gets heavy the longer you play" is. It is a content-budget
problem, not an engine one - which is why it belongs behind the Quality menu's
Persistence group rather than being silently capped.

## Fix 3 - Options -> Quality, with presets

The knobs that cost frame time are now in one menu, and `rt_quality_preset`
(`rt_quality.cpp`) drives 26 of them as a group. **High is exactly the shipped
values**, verified: preset 2 reproduces the pre-change baseline to the primitive
(2009 prims / 1.227 ms fx at 48 s, against 2009 / 1.226 before the menu existed).

Measured on the same scripted 40 s firefight (MAP13, summoned crowd, held
chaingun trigger, `rt_vsync 0`):

| preset | prims @48 s | fx ms | RT total ms | shape |
|---|---|---|---|---|
| Ultra | - | - | - | raises rt_restir_initial/spp; costs GPU, not CPU |
| **High** (ships) | 2009 | 1.227 | 2.749 | **still climbing at 48 s** |
| Balanced | 1620 | 0.703 | 2.239 | plateaus ~40 s |
| **Performance** | **895** | **0.242** | **1.497** | plateaus ~36 s |

The important column is the last one. Performance and Balanced do not merely
start lower, they **stop growing** - because they bound the persistent
populations rather than the per-frame work. High is unbounded within a level by
design, which is the authored behaviour and stays the default.

Cvars are resolved by name, not through the `rt_cvars.inc` externs, because
`d64_dropcasings`, `rt_gore_max` and `rt_gore_life` are CVARINFO cvars from the
mod pk3s with no C++ symbol. All 26 resolve in the shipped load order
("26 cvar(s) set, 0 not present").

### The pins had to give the cvars up

A pin in `tools/d64rt-pins.cfg` runs at launch and overrides both the compiled
default and anything a preset set - so all 19 preset-owned pins are commented
out in place, next to the notes that explain their values. `tools/check_pins.py`
now parses the preset table out of `rt_quality.cpp` and **fails** if any of them
comes back; that guard was negative-tested by re-adding `rt_dust_max 900` and
confirming a non-zero exit, not just by observing a clean pass.

## Still open

- Whether the measured accumulation is the whole of the in-play symptom. 40 s of
  held trigger costs ~1 ms; a full level of firefights is unbounded but unmeasured.
- `rgStartFrame` spikes to 1.2 ms (MAP13) and 3.1 ms (native-res DLAA) - that is
  the N-2 fence, i.e. genuine GPU-bound time, and the honest place to look for
  GPU cost.
- The MAP01/MAP00 `rt/scenes` folders are a byte-identical copy of Doom 2's
  MAP01 scene. They do not bind today (the map name is `d64r-3dfloor-rtfix_map01`,
  not `d64rtr_v15_map01`), but they would if the load order changed.
