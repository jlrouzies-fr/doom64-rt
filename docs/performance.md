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

## Still open

- What the in-play symptom actually is. These are spawn-point measurements with
  nothing happening; a firefight with persistent gore, casings and debris is the
  case `plan-projectile-impact-fx.md:553` flags as never measured.
- `lightgen` at 0.4-0.7 ms is now the largest item in our own per-frame code.
- `rgStartFrame` spikes to 1.2 ms (MAP13) and 3.1 ms (native-res DLAA) - that is
  the N-2 fence, i.e. genuine GPU-bound time, and the honest place to look for
  GPU cost.
- The MAP01/MAP00 `rt/scenes` folders are a byte-identical copy of Doom 2's
  MAP01 scene. They do not bind today (the map name is `d64r-3dfloor-rtfix_map01`,
  not `d64rtr_v15_map01`), but they would if the load order changed.
