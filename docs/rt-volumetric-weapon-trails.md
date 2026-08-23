# Sprites vs. the froxel medium

*Three artefacts, one family: the dark trail the super-shotgun reload sweeps
through muzzle-lit smoke; the fog "sticking" to the weapon; and MAP12's
thunder, where every sprite smears huge shadows through the volumetric shafts
as the camera moves. All three are collisions between a billboard-sprite game
and a froxel volumetric, and none of them is the temporal upscaler.*

| | |
|---|---|
| **Status** | Surface-denoiser sibling **fixed 2026-08-23** (`rt_svgf_indir_maxhist`; the "lingering light" was the indirect ghost) -- see its section. Medium: **Fixed structurally** by `rt_volume_taccum 8` (in-grid temporal accumulation, SS3) plus `rt_volume_spriteshadow 0`; `rt_volume_fp` / `rt_volume_reproj` remain as the screen-space fallback's fixes. Verified visually in the MAP94 lab frame-for-frame (the sprite stamp, the casing shadow rectangle, and the fog-on-gun are each gone, and the isolation arms attribute each to its mechanism). MAP12 thunder awaits an in-play pass |
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

## The same class on the surface denoiser: lingering lights (2026-08-22/23)

*Fixed; verified in play (`lingtrail-fix`: no linger, no trail).*

`screen/smearingIssueOverLingeringLight.png`: after a rocket, the launcher
swept a dark silhouette-shaped band across the **wall and floor** beside it --
on surfaces, so `rt_volume_taccum` could not touch it.

### The wrong first diagnosis, and the bisect that corrected it

The first plan read it as §2 above on the DIRECT diffuse path: A-SVGF's history
test (10 % depth + normal, no notion of first-person) rejects every pixel the
gun uncovers, and a rejected pixel restarts from one sample. That mechanism is
real -- the magenta debug showed rejections along the silhouette all the time --
but it was **not where the band was**: the band sat on pixels whose history
was accepted. A fix aimed there (`rt_svgf_fp`) changed nothing visible.

`rt_debug_show` (new: the dev window's layer views as a cvar) settled it in
four runs:

| view | result |
|---|---|
| raw direct (`4`) | no band -- nothing upstream of the denoiser |
| shadow visibility (`rt_debug_visibility 2`) | no red -- not a cast shadow |
| denoised direct only (`32`) | no band **and no lingering light** |
| gradient (`2`) | flat beside the gun -- antilag not firing |

So the "lingering light" was never a light. The real lights (the 2.5 s flash,
the embers) decay correctly in direct. What lingered for seconds was the
**indirect buffer's temporal ghost**: the flash's bounce, accumulated with a
256-frame cap (`clamp(..., 1, 256)`) and blended out at 1/256 per frame after
the light died. And the band was the gun's silhouette **restarting the
indirect history** to the true current value -- a hole in the ghost. Fix the
ghost and the hole has nothing to sit in.

Why upstream kept it that long: indirect is 1 spp and very noisy, so SVGF
averages it over a long window, tuned for static lights. The antilag meant to
break the window drives indirect only from a *direct* luminance drop and then
multiplies by `1 - smoothstep(0, 0.5, indirectBrightness)` -- "if it's bright
enough, don't drop history" -- which protects exactly the brightest stale
bounce. No light in this project decayed over seconds before the impact-FX
work, so it never showed.

### The fix

- **`rt_svgf_indir_maxhist 16`** -- cap the indirect history length
  (`CmSVGFTemporalAccumulation.comp`). 0 = stock 256. Gone in well under a
  second; the cost is noisier indirect in bounce-lit dark areas. The knob.
- **`rt_svgf_indir_antilag 1`** -- drop the brightness suppression on the
  indirect antilag (`RtGradients.rgen`).
- **`rt_svgf_fp 1`** -- kept: on full rejection a non-weapon pixel borrows
  history from its *current-frame* neighbours' reprojections (rings 2..20 px;
  the previous-frame ring was all gun at any real bob speed), capped at 8
  frames. Removes the 1-spp restart noise along any silhouette. `2` = magenta
  borrowed / cyan rejected-no-donor.
- **`rt_svgf_fp_grad 1`** -- kept: the gradient stratum never picks a
  first-person pixel, current or previous.

Uniform plumbing: the first two fields shifted `ShGlobalUniform` by 8 bytes
and the build's layout check refused the dll until padded; those pads then
became the indirect pair. That check is the only thing between a new uniform
and a silent zero.

**Arms**: `.	oolsb.cmd lingtrail-control|fix|ghost|fp|grad|debugfp|nogun`
and the bisect views `lingtrail-view-raw|direct|spec|indir|grad|shadow`.

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

## The screen-space fallback, for `rt_volume_taccum 0`

Everything in this section governs the OLD path and runs only when in-grid
accumulation is off. It is kept because it is the fallback, because each piece
was measured, and because two of the three wrong turns are worth not repeating.

`CmScatterAccum.comp` accumulates the scattering buffer over `rt_volume_history`
frames, reprojecting the previous buffer and validating it. The weapon is real
geometry at ~0.3 m, so every pixel it covers failed validation, and the sample
that replaced the discarded history integrated the volume **to the weapon** —
almost no inscatter. The reload then swept a stripe of emptied fog across the
frame that healed over `rt_volume_history` frames.

**`rt_volume_fp 1`** (0 off, 2 debug) fixes that in two halves:

1. **Under the weapon, integrate to far, at the same screen pixel.** Not a
   freeze — a freeze was tried first and made it *worse*, because it reused the
   reprojected taps and the motion vectors under the weapon are the **weapon's
   own**, so the fog was dragged around with the gun. Sampling to far keeps a
   live estimate of the WORLD's fog flowing under the sprite; a sign bit in the
   `r16f` history buffer marks it so the uncovering frame accepts it.
2. **Composite no fog on first-person pixels** (`CmPrepareFinal`, and its
   postcomp twin). The buffer under the gun deliberately holds a wall's worth of
   veil for continuity; painting that on a quad 30 cm from the eye is the
   "weapon carries fog on it" regression. There is no medium to speak of in
   30 cm, so unfogged is also the physically correct image.

The depth gate skips first-person taps for the same reason — otherwise it culls
the very cells that far integral reads.

**`rt_volume_reproj 1`** replaces the surface validation rules with media rules:
relative path length within 25%, no normal test. The medium is an integral along
the ray; it cares how far the ray goes, not which surface ends it. Rejections
that survive even that borrow validated neighbour history (radius 2, capped at
3 frames) before starting from nothing.

**Reading the debug view.** `rt_volume_fp 2` paints first-person pixels cyan
*into the scattering buffer*, which is then accumulated — so the cyan smears
along the history. That is the accumulator being visualised, not the mask being
wrong.


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

### The wrong turns, kept so they are not retaken

**A freeze that reprojected.** The first attempt froze the medium under
first-person pixels but reused the bilinear *reprojected* taps, merely skipping
their validation. Motion vectors at a first-person pixel are the **weapon's**,
so the carried medium was dragged along with the gun — the smoke stuck to the
sprite and smeared with it, which is exactly what the feature was meant to stop.
Measured worse than its own control. Reading the previous frame at the **same
screen pixel** is what holds the medium still.

**A freeze at all.** Holding a value photographs the fog: lights change and the
flash decays while the frozen pixel does not. Integrating a *far* sample every
frame keeps the same continuity and stays alive.

**Treating the weapon as special.** It never was — only the largest, nearest and
most reproducible instance. The casing does it, monsters do it, geometry edges
do it. Every fix aimed at the weapon alone left the class untouched, which is
what finally forced the question of where the medium is accumulated at all.

**Two instruments that graded the wrong thing.** A plain high-pass counted
per-pixel grain as structure, so the noisiest arm scored worst while visibly
having fewer ghosts; and pairing arms on exact map tics collapsed to one shared
sample in thirteen, because under capture this runs at ~4 fps and `rt_autoshot`
fires on the first frame at or after its tic. Band-pass over a shared tic
*window* is what the tool does now — and even that could not separate the
no-gun floor from the control at 2×se, which is why the verdicts here rest on
matched frames read by eye.

### Still open

- **MAP12's thunder has never been captured in the lab.** The verdict there is
  from play. The lab has no transient world-light arm; adding one would let the
  smear case be measured rather than described.
- **The froxel-scale blockiness** of a small sprite's occlusion — visible in the
  legacy arms as a hole bigger than the casing — points at `volume_sampleDithered`
  rather than at the accumulator, and was never chased. In-grid accumulation and
  the sprite-shadow fix removed the visible instances; the sampling question
  stands.
- **In-grid accumulation's own trade-offs** have not been swept: the fog lags
  `rt_volume_taccum` frames behind a flash *uniformly* (shapeless, unlike the old
  patchwork), fast strafing translates the reprojection slightly, and the 4
  spatial dither samples that replace the temporal averaging have not been tuned
  against dense smoke. Each has a knob; none has been measured.
