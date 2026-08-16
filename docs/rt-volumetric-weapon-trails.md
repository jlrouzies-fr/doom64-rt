# Sprites vs. the froxel medium

*Three artefacts, one family: the dark trail the super-shotgun reload sweeps
through muzzle-lit smoke; the fog "sticking" to the weapon; and MAP12's
thunder, where every sprite smears huge shadows through the volumetric shafts
as the camera moves. All three are collisions between a billboard-sprite game
and a froxel volumetric, and none of them is the temporal upscaler.*

| | |
|---|---|
| **Status** | **Fixed structurally** by `rt_volume_taccum 8` (in-grid temporal accumulation, SS3) plus `rt_volume_spriteshadow 0`; `rt_volume_fp` / `rt_volume_reproj` remain as the screen-space fallback's fixes. Verified visually in the MAP94 lab frame-for-frame (the sprite stamp, the casing shadow rectangle, and the fog-on-gun are each gone, and the isolation arms attribute each to its mechanism). MAP12 thunder awaits an in-play pass |
| **Lab** | `MAP94`, `tools/build_trail_lab.py`, `tools/trail-lab.ps1` (`-All` runs the five-arm ladder) |
| **Measurement** | `tools/measure_weapon_trails.py` — honest caveat: at ~12 usable frames per arm its window statistic could not separate even the no-gun floor from the control at 2×se; the verdicts here rest on matched frames read by eye, where the artefacts are unmistakable |
| **Not** | the temporal upscaler ([`rt-volumetric-edge-outlines.md`](rt-volumetric-edge-outlines.md)), not the depth gate alone, and not the weapon specifically — any sprite |

## The ending: the fix upstream shipped and never turned on

The screen-space fixes above each removed the instance they were aimed at, and
the user kept finding the next instance: the ejected casing sweeps the same
trail the weapon did; on MAP12, thunder plus camera motion trails on every
monster silhouette AND every geometry edge (`screen/trailAfterTHunderAndMove.png`
-- the purple splotches are monster-shaped stamps in the flash-lit fog, the dark
band hugs the rock silhouette). That is the tell of a CLASS, not a list: any
screen-space history validated against surface depth restarts at every
silhouette, and no rule tweak changes that.

Then the class-level fix turned out to already exist. `CmVolumetricProcess.comp`
shipped from upstream with

```glsl
const float g_temporalWeight = 0.0;
...
if( g_temporalWeight > 0.0 ) { vec4 prev = volume_sample_Prev( cell ); ... }
```

-- in-grid temporal accumulation, fully wired (prev-frame grid bindings, the
world-space reprojection helper `volume_sample_Prev`, the ping-ponged volume
images), hard-disabled by a constant, with zero callers of the helper. The
screen-space accumulator in CmScatterAccum is the workaround that replaced it,
and it is the wrong place for a medium.

**`rt_volume_taccum 8`** (default) turns the real mechanism on:

- Each froxel cell EMA-blends against its own WORLD position reprojected into
  the previous frame's grid. No surfaces are involved anywhere -- nothing to
  reject, nothing to restart, for any sprite, casing, or edge, ever.
- CmScatterAccum then stops accumulating in screen space entirely: the ray
  integral is recomputed fresh every frame from a temporally smooth field. The
  lost temporal averaging of the sample dither is replaced by 4 spatial dither
  samples per pixel (four trilinear taps of a smooth 3D field).
- Reprojection of the camera-to-cell integral is exact under camera rotation;
  under translation the error is the fog inside one frame of movement against
  paths of many metres, corrected continuously by the EMA. Cells that leave the
  previous frustum take the fresh value -- the grid's honest disocclusion, at
  screen edges rather than silhouettes.

**Verified in the lab**: `trail-gridonly` (grid accumulation alone, every
screen-space fix off) has no stamp at all -- the architecture was the whole
accumulator story -- while its casing shadow rectangle survives, isolating the
sprite-shadow mechanism as separate. `trail-fix` (ship config) has neither.

With taccum on, `rt_volume_history`, `rt_volume_reproj` and the accumulator
half of `rt_volume_fp` are inert -- they govern a code path that no longer
runs. They remain for `rt_volume_taccum 0`.

## The three mechanisms, each confirmed by its own experiment

**1. Sprites shadowed the froxel medium** (`rt_volume_spriteshadow`, now 0).
`RtVolumetric.rgen` shadow-tested its lights with `traceShadowRay(0, …)` — mask
`WORLD_0 | RESERVED_0`. That is every alpha-tested billboard *and* every sprite
shadow-proxy plane, because index 0 never triggers the proxy strip that sprites
get for their own surface shadows. Proxies are solid planes: the ejected shell
casing stamped a **rectangle** of shadow into the smoke, bigger than the casing
because a shadow volume grows with distance from the light. Billboards rotate
with the camera, so their sheets sweep the fog as the view turns — MAP12's
"any sprite smears the shafts when thunder happens as I move the camera".
*Fix:* media shadow rays strip `RESERVED_0` from the mask and route through a
media SBT hit-group pair whose any-hit (`RtAlphaTestMedia.rahit`) discards
`GEOM_INST_FLAG_SPRITE` — so grates and fences, which are alpha-tested WALLS,
still cut their shafts. Confirmed: the `trail-ssonly` arm (this fix alone)
removes the rectangle and keeps the stamp.

**2. The accumulator treated the medium like a surface** (`rt_volume_fp`,
`rt_volume_reproj`). Two halves:

- *The weapon.* Real geometry at ~0.3 m: history under it failed the
  reprojection tests and was refilled with the medium integrated **to the
  weapon** — nothing — so the reload swept a stripe of emptied fog that healed
  over `rt_volume_history` frames: the dark trail, reproduced in the lab as a
  hard sprite-shaped stamp floating in the smoke. A **freeze** was tried first
  and made it worse twice over: it dragged the fog with the gun (motion vectors
  under the weapon are the weapon's own) and painted the carried *world* fog
  over the viewmodel — "the weapon carries fog on it". The fix keeps the
  buffer's world-fog estimate alive under the sprite instead: fresh samples are
  taken **to far** at the same screen pixel (the depth gate now skips weapon
  depth so those cells exist), the store is sign-marked, and the uncovering
  frame accepts it seamlessly. The composite then paints **no fog on
  first-person pixels** — which is also the physically right image of a gun
  30 cm from the eye. Confirmed: `trail-fix` vs `trail-legacy` at the same
  animation tic — stamp gone, smoke smooth, gun crisp; `trail-nogun` is the
  floor it lands on.
- *Every other sprite.* The stock validation demanded depth within 10% AND
  normal agreement — surface-denoiser rules. The medium is an integral along
  the ray: fog-to-a-monster at 20 m vs fog-to-the-wall at 24 m differ by a few
  percent of veil, yet every billboard silhouette rejected history under
  camera motion, and each rejected band restarted from one noisy sample.
  Against a *transient* light (flash, thunder) a restarted band disagrees with
  its lagging neighbours by most of the flash — the smear. Media rules accept
  history within 25% relative path length, drop the normal test entirely, and
  full rejections borrow validated neighbour history (radius-2, capped at 3
  frames) before starting from nothing.

**3. What remains inherent.** An 8-frame accumulator genuinely lags a two-frame
lightning flash; that is the Cyberpunk-class trade-off of one-sample-per-cell
volumetrics and it is uniform — a soft afterglow, not a shape. Everything that
turned it into *shapes* is items 1 and 2.

## The mechanism

`CmScatterAccum.comp` accumulates the scattering buffer over `rt_volume_history`
frames (pinned at **8**). Each frame it reprojects the previous buffer and
validates it with two tests:

```glsl
testReprojectedDepth ( depth, depthPrev, motionZ ) &&
testReprojectedNormal( normal, normalPrev )
```

**The first-person weapon is real geometry at about 0.3 m.** It is submitted with
`RG_MESH_FIRST_PERSON` (`rt_draw.cpp:245`) and traced by the primary rays like
anything else, so it writes `framebufDepthWorld` and the normal buffer. Every
pixel the sprite covers therefore fails both tests against whatever the world put
there last frame — the history is discarded and `historyLen` resets to 1.

That alone would only cost noise. What makes it *dark* is what replaces the
discarded history:

> `fializeScattering()` reconstructs the pixel's world position from
> `framebufDepthNdc` and integrates the prefix-summed froxel volume out to it.
> At a weapon pixel that depth is **the weapon**, so the integral runs over ~0.3 m
> of medium and returns almost no inscatter.

So the accumulator throws the fog away and refills with nothing. When the sprite
moves on, the pixel it vacates carries that emptied value, and re-converges over
`rt_volume_history` frames — while its neighbours, never covered, still hold the
muzzle flash in *their* history. The difference is the trail, and its length in
frames is `rt_volume_history`.

This is why it reads as "the sprite resets the temporal information". It does,
literally, and the reset is legitimate for a surface denoiser — the surface
behind the weapon genuinely is unknown — but it is wrong for the medium, which
is a *volume in front of* the geometry and does not change because a sprite
moved through the picture of it.

## The fix — `rt_volume_fp`

`0` off (the old path), `1` freeze under the weapon, **`2` freeze + history
dilation (the default, and the one that works)**, `3` debug.

Mode 1 is described below because it is the mechanism the investigation
started from. It measured -9.7 %, inside the noise. **SS4 is what actually
happened when it was put in front of the lab**, and mode 2 is the result.

Three parts, all in `CmScatterAccum.comp`:

1. **Detect first-person per pixel.** `RaygenPrimary` packs `h.instCustomIndex`
   into `framebufSurfacePosition.w`, and that carries
   `INSTANCE_CUSTOM_INDEX_FLAG_FIRST_PERSON`. No new buffer, no new pass.
2. **Skip the depth and normal tests at the weapon's edge — in both
   directions.** On the frame the sprite *covers* a pixel, and on the frame it
   *uncovers* it. Only doing the first would discard the carried value one frame
   before it was going to be used, which is the entire point of carrying it.
   "Was this pixel first-person last frame" is stored in the **sign of
   `historyLen`**: `framebufScatteringHistory` is `r16f`, one signed channel with
   no room for a flag, and the length is always ≥ 1 when it means anything, so
   the sign is free.
3. **Freeze rather than integrate.** Under the weapon, hold the carried value and
   do **not** grow `historyLen`. Not growing it matters on its own: `historyLen`
   is the mix weight, so a frozen pixel that kept counting would emerge
   over-converged and re-adapt more slowly than its neighbours — a *bright* trail
   instead of a dark one.

It costs nothing visually while the weapon is over the pixel, because the weapon
is opaque and covers it.

## How to read the arms

**Run `rt_volume_fp 3` first.** It paints the frozen pixels cyan. A per-pixel
flag that reaches the shader and one that does not produce the same screenshot
otherwise, and §7.1 of the edge-outlines doc is the record of what that costs.
If the weapon is not cyan, nothing else here means anything.

**`fpfreeze-hist1` is the discriminator, not a candidate fix.** It is the *old*
path with `rt_volume_history 1`. If the trail is the volumetric's temporal
accumulation, it disappears there — at the price of visibly noisy fog, which is
why it is not a fix. If the trail *survives* `hist1`, then it is not this pass at
all and the change above is aimed at the wrong thing. Run it before believing the
diagnosis.

## What this does not explain

The muzzle flash's own lag. The flash is a transient light and the medium
integrates it over 8 frames, so the fog keeps glowing for ~8 frames after the
flash is gone, everywhere — not just behind the weapon. `fpfreeze` makes the
weapon's path agree with the rest of the frame; it does not make the rest of the
frame agree with the flash. If the glow's decay reads as wrong after this, that
is a separate question about `rt_volume_history` and transient lights.


---

## The lab, and what it overturned

Everything above was written before a single frame was captured. Then it was
measured, and the diagnosis survived while the *fix* did not.

**The lab.** `MAP94`: a 512×384 box, lightlevel 0, no lamps, one flat wall 4 m
ahead. The only light in the room is the muzzle flash, and the only thing it can
light is the weapon's own smoke. `tools/trail-lab.ps1` holds the trigger on the
super shotgun and takes a burst across the fire-and-reload cycle.

**The metric.** Band-pass RMS (σ 2 to σ 12) in a box covering the upper middle of
the frame — above the weapon, below the message feed, smoke against a flat wall.
Two earlier versions were wrong and both are worth recording:

- *A plain high-pass* counts per-pixel grain as structure, so `rt_volume_history 1`
  — the noisiest arm by construction — scored worst while visibly having fewer
  ghosts. The instrument was grading noise, not ghosts.
- *Pairing arms on the exact map tic* collapsed to one shared sample out of
  thirteen. Under capture this runs at ~4 fps and `rt_autoshot` fires on the
  first frame at or after its tic, so two arms almost never sample the same one.
  The comparison is over a shared tic **window** instead: ~12 samples per arm
  across the same two fire cycles, with the frame-to-frame spread as the noise
  scale.

**The ladder**, shared window 95–192 tics, lower is better:

| arm | what it tests | score | verdict |
|---|---|---:|---|
| `fpfreeze-off` | the shipping path | 3.06 ± 1.39 | the artefact |
| `fpfreeze-on` | freeze under the weapon only (mode 1) | 2.76 ± 1.14 | −9.7 %, **inside the noise** |
| **`fpfreeze-dilate`** | **freeze + history dilation (mode 2)** | **1.85 ± 0.94** | **−40 %, the only arm clearing 2×se** |
| `fpfreeze-nogun` | `r_drawplayersprites 0` — no weapon drawn | 1.95 ± 1.49 | the floor: what the frame looks like with no gun |
| `fpfreeze-hist1` | `rt_volume_history 1` | 2.26 ± 1.65 | inconclusive |
| `fpfreeze-gateoff` | `rt_volume_depthgate 0` | 2.54 ± 1.38 | inconclusive — **not the depth gate** |

Mode 2 lands **at the no-weapon floor**: with the dilation on, the frame is as
clean as if the gun were not being drawn.

### What was proven, and how

**The sprite causes it — by removing the sprite.** `fpfreeze-nogun` keeps the
smoke and turns off `r_drawplayersprites`. The hard-edged, sprite-shaped stamp
floating in the middle of the smoke disappears completely and the cloud goes
smooth. That is the causal test, and it is worth more than the whole table.

**It is not the depth gate.** `rt_volume_depthgate 0` gives a frame
indistinguishable from the control, stamp included — the same answer the edge
outlines investigation got for its own artefact.

**It is not about the weapon.** A small dark blocky hole survives `nogun`: the
ejected shell casing, a *world* sprite, punching its own hole in the medium. Any
sprite does this. The user's independent report is the general case — on MAP12,
thunder plus moon shafts, "when thunder happens any sprite causes huge smear all
over the place as I move the camera". That is the same mechanism at scale: a
transient light in the medium's history, plus camera motion, plus sprites
rejecting that history all over the frame.

### Why mode 1 was the wrong shape, and mode 2 is right

Mode 1 freezes the medium under first-person pixels. It treats the weapon as
special, and the weapon is not special — it is only the largest, nearest and most
reproducible instance.

Worse, the **first** implementation of it made things measurably worse, and for a
reason worth keeping: it reused the bilinear *reprojected* taps and merely
skipped their validation. The motion vectors at a first-person pixel describe the
**weapon's** motion, so the carried medium was dragged along with the gun — the
smoke stuck to the sprite and smeared with it, which is precisely what the
feature was meant to stop. Reading the previous frame at the **same screen
pixel** holds the medium still instead, which is correct whenever the camera is
not turning, and when it is, the pixel is under an opaque sprite anyway.

Mode 2 stops treating the weapon as a case at all:

> When the reprojection tests reject everything, do not start this pixel's medium
> from nothing. Look one step further out — a 3×3 at radius 2 around the
> reprojected position, **fully validated** — and use a neighbour's history if
> one survives.

The medium is resolved on a 160×88 grid, so one render pixel's scattering is an
excellent estimate of its neighbour's. The old fallback — `historyLen` 1 and a
single sample of a volume lit at one sample per cell with one shadow ray — is a
terrible estimate by comparison, and against a *transient* light it is not merely
noisy but wrong: the neighbours are still holding the flash and the rejected
pixel is not. A borrowed history is capped at 3 frames so it blends back toward
the pixel's own samples rather than sticking, which is what keeps this from
trading a hole for a smear.

Nothing here is a relaxation of the validation. The dilated taps pass the same
depth and normal tests; the search is only widened. What it repairs is the case
where the 2×2 footprint happened to land on the sprite that just moved.

### Still open

The dark blocky hole from a *world* sprite (the shell casing) is softened by mode
2 but not gone. It is bigger than the casing and blocky at froxel scale, which
points at the sampling in `volume_sampleDithered` rather than at the accumulator,
and it has not been chased. MAP12's thunder case has not been captured in the
lab — the report is the user's, from play, and the lab has no transient
world-light arm yet.
