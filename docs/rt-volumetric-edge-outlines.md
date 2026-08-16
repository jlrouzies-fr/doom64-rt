# Edge outlines behind volumetrics

*Geometry and sprites seen through smoke or fog are traced by a thin dark line.
This is the README's first known issue. It is now reproducible on demand,
measured, and — for the first time — attributed.*

**The finding, up front: the outlines are drawn by the temporal upscaler, not by
the froxel grid.** Telling that upscaler where the medium's silhouettes are
(`rt_volume_ubias`, §7.1) is built and measured, and is **not** the fix: it
removes part of the outline by discarding temporal history exactly where the
smoke needs it, so the smoke goes noisy in motion. It ships off. Every volumetric knob that was supposed to carry them —
the depth gate, the sample dither, the spatial blur, the depth bias, the
scattering history, the froxel slice thickness — changes the artefact by 0.3
luminance levels or less and none of them removes it. Turning the upscaler off
removes it completely, on the same frame, with the same smoke.

| | |
|---|---|
| **Status** | **RESOLVED.** `rt_volume_edgesoft 2` (§7.3) removed the sprite and geometry silhouettes; the remaining tracing on flat-surface texture seams (§7.4) went with **in-grid temporal accumulation** (`rt_volume_taccum`, §10) — confirmed in play: "zero edge". The upscaler still rings, but a medium that is temporally smooth in world space no longer hands it the step it was ringing on |
| **Lab** | `MAP93`, `tools/build_edge_lab.py`, `tools/edge-lab.cmd` |
| **Open lead** | The DLSS **render preset** was hard-coded to `E` — deprecated on the DLSS 4 runtime this build ships — so every arm below is the same reconstruction. `rt_dlss_preset` + `tools/edge-preset-ladder.ps1` make it an arm (§7.6). Built, not yet measured |
| **Measurement** | `tools/measure_edge_outlines.py`, and `tools/measure_edge_ringing.py` for the reconstruction's own signature in a frame with no medium in it |
| **Corrects** | [`rt-smoke.md`](rt-smoke.md) §9, the `rt_volume_dither` cvar help, and the README's Known-issues paragraph — all three name the froxel grid |

---

## 1. The symptom

Inside a smoke curtain, every edge behind it is drawn as a contour: pillar
corners, floor tile seams, and the monsters as hollow pencil outlines. Outside
the curtain, in the same frame, nothing.

| | |
|---|---|
| `tools/_edgelab/arm-dense8.png` | the artefact, at the shipping upscaler |
| `tools/_edgelab/arm-native.png` | **the same smoke with no upscaler** — a smooth cloud, no outlines anywhere |
| `tools/_edgelab/repro-control-smokeoff.png` | the room with `rt_smoke 0`, for reference |

The two smoked frames differ by one cvar. Put them side by side before reading
any further — the whole of §5 is that pair, counted.

## 2. The lab — MAP93

`python tools/build_edge_lab.py` writes `d64redgelab.wad` + its mapinfo pk3.
A lit 32 m hall, built so that the two things being judged — **medium in front,
edges behind** — are the only variables:

- **Six void pillars** at 7, 13, 20 and 29 m, so an artefact that depends on
  froxel slice thickness (0.94 m at `rt_volume_far 60`) shows which slices it
  lives in instead of being one anecdote at one distance. One is **1 m across**,
  dead centre: the depth gate's footprint MAX is documented to under-cull
  exactly there.
- **Seven monsters, spawned `dormant`.** Both kinds of edge are in frame,
  because they are not the same thing to the renderer: a pillar is opaque
  geometry with a hard depth, a monster is an alpha-tested sprite whose
  silhouette is a cutout inside one quad. Dormant matters for a different
  reason — a monster that wakes walks, and a moving silhouette gives the
  denoiser nothing to reproject, so every capture would be a different frame
  with its own smear. `Deactivate()` on a monster with no `Inactive` state sets
  `tics = -1`: it stands in its spawn frame, visible and solid, for as long as
  the capture takes.
- **A bright hall** (lightlevel 180 plus a lamp grid). Smoke is a *luminous
  veil*, so what decides whether the edges behind it still read is contrast, not
  opacity. At the first version's lightlevel 120 the room was darker than the
  smoke and every density from 2 to 8 gave the same flat grey frame.

### Three settings that have to be forced, and why

Each one produced a confident false negative first:

| | |
|---|---|
| `rt_smoke_perweapon 0` | `rt_smoke_autospawn` takes the **ready weapon's** profile, and the player spawns holding a pistol, whose row multiplies the radius by **0.07**. Puffs came out at 6 cm — under a froxel — and read as nothing at all, while `rt_smoke_debug 1` cheerfully logged 128 live puffs. The identity profile makes `rt_smoke_*` mean what it says. |
| `rt_smoke_density 3`–`8`, not the shipping 14 | the curtain has to be **seen through**. At shipping density a wide spread is an opaque wall, and there are no edges behind it to outline. |
| `rt_flsh 0` | the flashlight is a lamp **at the eye**. A lamp inside the curtain blows the frame to white — as did the map's own first warm lamp, which is why that one now sits 10 m out to the sides. |

## 3. How it is measured

Twice in one session this artefact was misread by eye — once as absent when it
was there, once as present when the frame merely showed the scene correctly
attenuated. It is not an eyeball problem.

**`tools/measure_edge_outlines.py <smoked.png> <control.png>`.**

The method, and each part of it exists because a simpler one failed:

1. **A control frame says where the edges are.** Same room, same lights, same
   spawn, `rt_smoke 0`. Detecting edges in the *smoked* frame is circular — the
   artefact **is** an edge, so a detector run on it reports the artefact as the
   geometry.
2. **A local linear fit is the model.** If the medium is behaving, then for
   every pixel `smoked = transmittance × control + inscatter`, and both
   coefficients are froxel-resolved — smooth over the ~16 px a froxel column
   covers. So fitting a locally-constant `a·control + b` over an 8 px window
   must explain the frame, silhouettes included. What the fit cannot explain is
   the candidate artefact, in luminance levels.
3. **The profile is flipped by the control's gradient sign** before averaging.
   Without that, left- and right-facing edges cancel and the mean profile is
   flat zero whatever is happening — which is exactly what the first version of
   this script printed.
4. **The smoke mask comes from the pair**, not from a guess. The curtain covers
   a fraction of the frame and the bare side walls outvote it; the first
   statistics averaged over the whole play area and reported no artefact at all.

**A caveat that matters.** The fit residual at an edge is *not by itself* proof
of a bug: at a silhouette the transmittance genuinely does step, and a
locally-constant `a` cannot fit both sides of a genuine step either. What makes
it evidence is the **comparison between arms on the same frame** — the
no-upscaler arm has the identical genuine step and returns +0.1. The number is a
relative instrument, and it agrees with the visual A/B in §1.

## 4. The pipeline, in order

Naming the passes is most of what makes the candidate list legible.

| pass | what it does |
|---|---|
| `RtVolumetric.rgen` | lights each froxel of a **160 × 88 × 64** camera-fitted grid, one sample per cell; `volume_depthGate` (`:331`) weights each cell by how much of it is in front of the geometry visible in its own screen column |
| `CmVolumetricProcess.comp` | prefix-sums the grid along z, camera outward |
| `CmScatterAccum.comp` | per pixel: reconstructs world position from depth, reads the prefix sum **trilinearly** at that distance (`volume_sampleDithered`, with a screen-space dither and a 5-tap blur), then temporally accumulates over `rt_volume_history` frames |
| `CmPrepareFinal.comp:54-58` | composites: `hdr = hdr × volumetric.a + volumetric.rgb` — **at render resolution** |
| DLSS / FSR2 | runs **after** `imageComposition->Finalize` (`VulkanDevice.cpp:1293-1325`) |

The last row is the one that turned out to matter, and it is the only one none
of the previous rounds looked at.

## 5. The ladder

All arms on the same frame: MAP93, 150-tic settle, `rt_smoke_density 8`,
identity smoke profile. **Spike** is the mean fit residual at offset 0 — the
pixel *on* the edge — inside the smoke; negative is a dark line. **Flat** is the
noise floor in the smoke away from any edge, for scale.

| arm | what it tests | spike @0 | flat | verdict |
|---|---|---:|---:|---|
| `dense8` (baseline) | shipping, DLSS balanced | **−0.9** | 5.33 | the artefact |
| `dense8b` | the same arm, re-run | −0.9 | 6.14 | run-to-run ≈ ±0.05 |
| `gateoff` | `rt_volume_depthgate 0` | −1.0 | 6.18 | **not the depth gate** |
| `nofilter` | `rt_volume_dither 0` + `rt_volume_blur 0` + `rt_volume_dither_z 0` | −0.7 | 4.16 | **not the sample-time filters** |
| `hist1` | `rt_volume_history 1` | −0.8 | 4.62 | **not the scattering history** |
| `far30` | `rt_volume_far 30` — halves the slice to 0.47 m | −0.6 | 4.65 | **not the slice thickness** |
| `dlssq` | DLSS quality (higher render res) | −1.0 | 5.82 | present |
| `dlaa` | **DLAA — render res = output res**, DLSS still running | **−1.3** | 9.47 | present, and *worst* |
| `fsr2` | FSR2 native | −0.7 | 4.67 | present — not vendor-specific |
| `native` | `rt_upscale_dlss 0 rt_upscale_fsr2 0` | **+0.1** | 3.13 | **gone** |
| `nativeb` | the same arm, re-run | +0.1 | 3.18 | gone |
| `simplefog` | `rt_volume_type 2`, smooth analytic fog, DLSS on | −0.2 | 0.42 | 4× weaker |

Two more numbers worth keeping:

- **The outline is one pixel wide.** Offsets ±2 and beyond sit at ∓0.1 — there
  is no halo, no ramp, no 12-pixel froxel-sized band. Anything carried by the
  160 × 88 grid would be ~16 render pixels across.
- **The medium adds no edge energy overall.** Across the whole smoked region,
  edge detail arrives at **0.42** of the control's — which is just the
  transmittance. A whole-frame statistic cannot see this artefact at all; that
  is why it needed a one-pixel profile.

Verified live before any null was trusted: each arm's log carries its own
`RT upscale/RR decision` and `Setup(): params.upscaleTechnique=` line —
`native` reads `nvDlss=0`, `upscaleTechnique=1` (`LINEAR`), `DLSS upscaler=off`.

## 6. What this means

**Proven.** The artefact is produced by the temporal upscaling pass. It is
absent with no upscaler, present in every DLSS mode and in FSR2, strongest at
DLAA, and it is one pixel wide and dark, only where the medium is.

**Strongly indicated, not proven.** The upscaler is the *carrier*; the medium's
own structure is the *payload*. Two observations point that way: the artefact is
worst at DLAA — where the reconstructed geometric edge is sharpest — and it is
4× weaker with a smooth analytic fog (`simplefog`) than with the froxel-resolved
smoke at a comparable veil. The composite `hdr × a + rgb` happens **before** the
upscaler, so what the upscaler receives at a silhouette is a colour in which two
very different media states have already been baked in on either side of the
edge, and its history rectification has no way to know that the discontinuity
belongs to the medium rather than to the surface. This last sentence is the
mechanism this doc believes; it is inference from a black box, and it should be
written as such until something inside DLSS confirms it.

**Ruled out, by test rather than by argument** — the froxel grid, in all the
forms this repo has previously blamed:

- the depth gate and its footprint MAX (`plan-light-shafts.md` §4d listed its
  residual as showing "at corners and silhouettes" — that residual is real, but
  it is not this),
- the lateral dither across silhouettes (the mechanism named in
  `rt_volume_dither`'s own help and in `CmScatterAccum.comp:72-75`),
- the 5-tap spatial blur,
- the one-sided depth bias,
- the scattering history,
- the froxel slice thickness.

## 7. If it is to be fixed

Diagnosis only — nothing here is implemented, and each option costs something
real.

### 7.1 Tell the upscaler the medium is there — SHIPPED, and it buys 40 %

Both upscalers have an input for exactly this case — *content composited after
the main pass, whose colour change the motion vectors do not describe* — and
**RTGL1 passed neither**:

| | | |
|---|---|---|
| DLSS 2 | `pInBiasCurrentColorMask` | `nvsdk_ngx_helpers_vk.h:78`, in the very `NVSDK_NGX_VK_DLSS_Eval_Params` struct `DLSS2.cpp` fills in — was null |
| FSR2 | `transparencyAndComposition` | `ffx_fsr2.h:180`, "alpha value of special objects in the scene" — was `{}` |

Both mean "favour the current frame over history here". `CmPrepareFinal` now
builds that mask and writes it into `FB_IMAGE_INDEX_REACTIVITY` — which already
existed, was already bound as FSR2's `reactive`, and was otherwise unwritten in
this project (only `RsRasterizerLensFlare.frag` writes it, and the engine never
calls `rgUploadLensFlare`). Four cvars drive it:

| cvar | default | |
|---|---|---|
| `rt_volume_ubias` | `0` | master strength, 0..1. At 0 the mask is not even **bound**, so the control arm is the old path exactly |
| `rt_volume_ubias_edge` | `0.15` | the relative depth step that counts as a full-strength silhouette |
| `rt_volume_ubias_floor` | `0` | constant bias over the whole veil; 0 = silhouettes only |
| `rt_volume_ubias_debug` | `0` | draw the mask instead of the image |

**Measured, MAP93, same frame, `rt_smoke_density 8`:**

| arm | mask | spike @0 | flat (still) |
|---|---|---:|---:|
| `rt_volume_ubias 0` | — | −0.8 | 4.64 |
| `rt_volume_ubias 0.5` | broad | −0.7 | 4.44 |
| `rt_volume_ubias 1` | broad | −0.5 | 4.70 |
| `ubias 1`, `edge 0.05` / `0.01` / `floor 0.3` | broader still | −0.5…−0.6 | 4.41–4.71 |
| **`rt_volume_ubias 1`, deadbanded mask** | **tight** | **−0.7** | 4.40 |

### The verdict: this is a bad trade, and it ships OFF

The broad mask removes ~40 % of the outline. **In play it makes the smoke
visibly noisy — "as if the dither is not applied any more" — and the edges are
still there.** That verdict came from playing it, and it is correct; the table
above could not have produced it, for a reason worth writing down:

> **A settled still frame cannot measure temporal noise.** Every capture here is
> taken after a four-second hold, by which point the temporal history has
> converged and discarding it costs almost nothing. The `flat` column is
> therefore measuring the one case that hides this feature's entire cost. The
> number was not wrong, it was answering a different question — and it was
> quoted as "no noise cost", which was.

Tightening the mask (a deadband, so a surface that is merely quantised
contributes nothing) does cut the noise — but it takes the benefit with it:
−0.5 becomes −0.7 against a −0.8 baseline, i.e. roughly 12 % instead of 40 %.
**That is the shape of the whole approach.** The benefit scales with how much of
the veil gets biased, and biasing the veil is exactly what makes the smoke
noisy, because the volume is lit at one sample per cell with one shadow ray and
its temporal history is the only thing averaging that out. There is no setting
where the mask removes the outline and leaves the smoke alone.

So it stays, at `0`, as a measured negative result and a switch someone can flip
— not as the fix. The fix is §7.2.

Two wrong signals on the way, each caught in one launch, and one dead end:

- **The transmittance gradient was the wrong signal.** A puff's own falloff is
  smooth over most of its area, so that version marked the whole cloud and its
  froxel banding with it: `rt_volume_ubias_debug 1` showed a white blob with
  rings in it rather than outlines.
- **A first-difference depth test was also wrong**, and looked plausible. It
  fires on any *receding* surface — a floor seen at a grazing angle changes
  distance fast from pixel to pixel — so it marked every floor and wall inside
  the smoke. What works is the **second difference**, `|d₊ + d₋ − 2d|`, which is
  zero for any planar surface at any angle and large only where the surface is
  not continuous. The debug view then shows exactly what it should: one-pixel
  contours on the monsters, the pillars and the wall junctions, black elsewhere.

And the dead end, recorded because it looked like the answer twice:
**depth's non-linearity is *not* what was leaking.** A second difference of raw
depth genuinely is non-zero on a receding plane (screen space interpolates
`1/depth`, not depth), so switching the test to the reciprocal should have
cleaned up the veil — and it changed the mask by **0.01 %**, pixel for pixel.
What looked like a veil-wide floor in the debug view was **bloom**: the debug
value is written into `framebufFinal` in `CmPrepareFinal`, which is upstream of
the upscaler, sharpening and bloom, so bright contours get a soft halo painted
around them before the screenshot. Measuring "how much of the mask is faintly
non-zero" off that image measures the bloom kernel. Widening the taps to ±2 to
chase the same ghost made both the mask and the outline worse.

Both signals were caught in one launch each **because the debug view exists** —
a mask goes into a black box, and without a way to look at it "the fix did
nothing" and "the mask is the wrong shape" are the same screenshot. The bloom
trap is the other half of that lesson: the debug view is a *rendered frame*, not
a buffer dump, and anything downstream of the write is in it too.

> **`rt_volume_ubias_debug` must be `RT_CVAR_NOARCH`, and it shipped archived
> for one session.** It saved into the ini on the run that used it, so every
> later launch — *including the control* — came back rendering the mask instead
> of the game, and four captures were measured before the black control frame
> gave it away. Making it NOARCH stops it being saved but does not remove the
> line an earlier build already wrote, so it is also pinned off in
> `tools/d64rt-pins.cfg` along with the other three.

### 7.2 Composite the medium after the upscaler — BUILT, and it does NOT work

`rt_volume_postcomp 1`. `CmPrepareFinal` stops compositing; the upscaler
reconstructs an ordinary surface image; `CmVolumeCompose.comp` applies the veil
at output resolution afterwards. The arithmetic is preserved term for term
(`out = (surf·T + S)·exp + emis·T` becomes `Final = surf·exp + emis` then
`out = Final·T + S·exp`), and the implementation is confirmed correct: with the
medium held constant, postcomp on vs off differs by **0.54 mean levels against a
2.85 run-to-run floor**, i.e. the same image.

**And the outline is unchanged.**

| arm | spike @0 |
|---|---:|
| DLSS balanced, postcomp 0 | −1.0 |
| DLSS balanced, postcomp 1 | −0.9 |
| DLAA, postcomp 0 | −1.3 |
| DLAA, postcomp 1 | **−1.8** |

DLAA is the decisive row: render resolution equals output resolution there, so
the medium is not resampled at all — and postcomp is *worse*. That kills the
"upscaler mis-reconstructs surface-plus-medium added together" story this doc
told, and the "bilinear upsample of a stepping transmittance" story that would
have replaced it. **Whatever the upscaler is doing, it does not depend on the
medium being in its input.**

Kept as a cvar because it is correct, cheap, and the question will be asked
again. Gated off automatically under DLSS Ray Reconstruction (which denoises
from the composed radiance) and under frame generation (which interpolates
frames past this point, so generated frames would have no fog and the image
would strobe).

### 7.3 Feather the medium across the silhouette — WORKS, and it is what to use

`rt_volume_edgesoft <px>`. Where — and only where — there is a genuine
silhouette, average `framebufScattering` over a small cross before compositing.
The silhouette test is the **second difference of 1/depth**: second difference
because a first difference fires on any receding surface and marks every floor;
of the reciprocal because screen space interpolates `1/depth`, so a plane at any
angle gives exactly zero.

| arm | spike @0 | temporal noise (fog burst) |
|---|---:|---:|
| off | −1.0 | 0.606 / 0.613 (floor, two runs) |
| **`rt_volume_edgesoft 2`** | **−0.4** | **0.598 — inside the floor** |
| `rt_volume_edgesoft 5` | −0.5 | — |

**60 % of the artefact, at no temporal cost**, and this time the "no cost" is
believable rather than an artefact of the instrument: it is measured on a burst
under the deterministic fog medium, and the mechanism *cannot* cost noise —
unlike `rt_volume_ubias` it never touches temporal history, it only averages a
low-frequency field over a few pixels. Visually the monster contours are gone
from `arm-v9-soft2.png`; faint floor-seam traces remain.

2 px beats 5 px, so this is not "more blur is better" — it is a step being
removed, and once it is removed a wider average only softens the haze boundary.

Why it works when 7.1 and 7.2 did not: every surviving theory of this artefact
has the medium's **step** at a silhouette at its centre, and the two failed
attempts both tried to fix what happens to that step downstream. This removes
the step.

### 7.4 What the remaining 40 % actually is

Not the same artefact. Look at `arm-vC-s2e05.png`: the monster and pillar
contours — *the reported symptom, "lines around sprites and 3d element edges"* —
are gone. What is left is faint tracing on **floor tile seams**, and a floor is
a continuous flat surface: there is no silhouette there, no depth break, and
nothing for the medium to step across. The detector correctly finds nothing,
which is why the feather plateaus at −0.4 no matter how it is tuned:

| variant | spike |
|---|---:|
| off | −1.0 |
| 5-tap cross, threshold 0.15 | −0.4 |
| full 3×3, threshold 0.15 | −0.5 |
| full 3×3, threshold 0.05 | −0.4 |
| 3×3 at radius 3, threshold 0.02 | −0.4 |

A 7× sweep of the threshold and a fuller kernel move nothing, because the
remaining lines are on **albedo** edges rather than depth edges. Whatever draws
them is reacting to image contrast, not to the medium — the veil only makes it
visible by flattening everything around it. That is a different investigation,
and quite possibly not a volumetric one at all.

### 7.5 Also ruled out, by measurement

| theory | arm | result |
|---|---|---|
| **The sharpen pass.** `rt_sharpen 0` is *auto*, and auto means AMD CAS whenever DLSS or FSR2 is on — so the "native is clean" arm was missing the sharpen as well as the upscaler, and a contrast-adaptive sharpen drawing a dark rim on the dark side of every edge fits the symptom perfectly | `+rt_sharpen 3` with DLSS on | **worse**: −1.3 at balanced (against −1.0), −1.7 at DLAA (against −1.3). Sharpening was slightly *masking* it |
| **Jitter misalignment under postcomp.** The upscaled image is unjittered while the scattering buffer is indexed by jittered render pixels, so the medium's step could sit half a pixel from the surface's | both signs of the correction, at DLAA where it is the only misalignment | neither rescues it. Subtracting (the derivation) gives −0.6 balanced / −2.1 DLAA; adding gives −0.9 / −1.5. All worse than not running the pass |

Four theories have now been built and measured: the upscaler bias mask, the
post-upscale composite, the jitter correction, and the sharpen pass. One
mitigation works. The pattern is worth stating plainly for whoever picks this
up: **everything that treats the medium helps only the silhouette half, and
everything that treats the image pipeline has come back negative.**

**What is *not* on this list: winding `rt_volume_dither` back down.** §9 of
`rt-smoke.md` and the cvar help both used to recommend it for this symptom. It
buys 0.2 of the 1.0 — and it costs far more than that, because **the shipping 5
is load-bearing and has to stay as strong as it is**. The froxel volume is lit
at one sample per cell with one shadow ray and is the only buffer in the frame
with no spatial denoiser of its own (`rt_volume_blur` is already at its maximum
of 1); the jitter is most of what stands between the shipping look and extremely
noisy smoke, which is why it was raised 2 → 5 from play in the first place. The
`nofilter` arm in §5 is a **measurement, not a setting** — it exists to answer
"is the dither the carrier", the answer is no, and nothing about that result
argues for lowering it.

### 7.6 The variable this whole document held constant — the DLSS preset

**BUILT, NOT YET MEASURED.** Every arm above — `dense8`, `dlssq`, `dlaa`,
`fsr2`'s DLSS neighbours, and all four attempted fixes — ran on the same
reconstruction, because `DLSS2.cpp` hard-coded it:

```cpp
NVSDK_NGX_DLSS_Hint_Render_Preset preset = ... : NVSDK_NGX_DLSS_Hint_Render_Preset_E;
```

for **all six** quality modes. So "present in every DLSS mode" (§5) is a weaker
statement than it reads: the quality mode changes the render resolution, not the
reconstruction. Every DLSS row in this document is preset E.

And `rt\bin\nvngx_dlss.dll` is **310.7 — a DLSS 4 runtime**. On that runtime the
bundled SDK header says, in its own comments:

| preset | what `nvsdk_ngx_defs.h` says |
|---|---|
| A–D | "removed, use preset J or K" |
| **E** | **"Deprecated"** — the legacy CNN model |
| J | transformer; "slightly less ghosting at the cost of extra flickering" |
| **K** | **"Default preset for DLAA/Balanced/Quality that is transformer based. Best image quality preset"** |

The build has been shipping a DLSS 4 runtime and then explicitly forcing it back
onto the deprecated CNN model. Ringing and over-sharpening at high-contrast
edges is exactly the class of artefact the transformer model was built to fix,
and a dark one-pixel line beside every edge is a ringing signature.

`rt_dlss_preset` now carries the raw NGX enum (`0` Default, `5` E, `10` J, `11`
K); it is `RT_CVAR_NOARCH` and pinned at `5`, so today's behaviour is unchanged
and the control arm is the old path exactly. Changing it re-creates the DLSS
feature, because the preset is baked in at create time and would otherwise
appear to do nothing until the window resized — a very convincing false
negative. RTGL1 logs `DLSS2: creating feature WxH -> WxH, render preset N` on
every create, so an arm that failed to apply is distinguishable from an arm that
changed nothing.

**Why this is a candidate for §7.4's residue specifically.** The remaining
tracing sits on albedo seams, where there is no depth break and nothing for the
medium to step across — it reacts to image contrast. That is a reconstruction
filter's behaviour, not a volumetric's, and the reconstruction filter is the one
thing here that has never been varied.

**The honest caveat, stated before any capture.** FSR2 shows the artefact too
(−0.7), and no DLSS preset can explain FSR2. So the most this can be is *the
DLSS half* of a mechanism the two upscalers share — negative-lobe temporal
reconstruction — and a good result on K would not close the FSR2 row.

To take it: `.\tools\edge-preset-ladder.ps1` (four presets, each with its own
control), then `measure_edge_outlines.py` per pair.

## 8. Re-taking any of this

```powershell
python tools\build_edge_lab.py                   # build MAP93

.\tools\edge-lab.cmd                             # the repro
.\tools\edge-lab.cmd off                         # the control
.\tools\edge-lab.cmd -- +rt_upscale_dlss 0 +rt_upscale_fsr2 0    # the arm that removes it

python tools\measure_edge_outlines.py tools\_edgelab\arm-dense8.png `
                                      tools\_edgelab\repro-control-smokeoff.png
```

**Every arm needs its own control at the same upscaler setting** — the fit
compares a smoked frame against a smoke-free one, and a control rendered through
a different upscaler is a different image. That is why half the captures in
`tools/_edgelab/` are `ctrl-*` frames with no smoke in them.

## 9. Corrections this doc makes

- **`docs/rt-smoke.md` §9, "The dark outlines are older than the denoising"** —
  its two exclusions (dither, spatial filter) are confirmed here. Its conclusion,
  "a silhouette compositing artifact — adjacent pixels either side of an edge
  integrate genuinely different amounts of medium", is half right: the different
  amounts are real and correct, and the *line* comes from what happens to that
  step afterwards.
- **`rt_volume_dither`'s cvar help** states the dither is "what draws dark
  outlines around things seen through smoke". Measured: it is worth 0.2 of 1.0,
  and zeroing it leaves the outline in place.
- **README, Known issues** — the paragraph attributes the artefact to froxel
  cells straddling a silhouette, and offers `rt_volume_depthgate` as the
  mitigation. The depth gate does not touch it (`gateoff`: −1.0 against a −0.9
  baseline). The paragraph should keep the symptom and point here for the cause.


---

## 10. How it actually ended — the medium stopped being a screen-space quantity

Everything above investigates what happens to the medium's **step at a
silhouette** on its way through the image pipeline. Four approaches were built
against that step and three came back negative. The step itself turned out to be
avoidable.

That came from a different investigation —
[`rt-volumetric-weapon-trails.md`](rt-volumetric-weapon-trails.md), chasing dark
trails behind the super shotgun's reload — which found that the froxel medium was
being **temporally accumulated in screen space** (`CmScatterAccum.comp`), where
history must be validated against surface depth. Every silhouette therefore
rejected it and restarted from a single sample of a volume lit at one shadow ray
per cell. That is the same population of pixels this document measures: the ones
at edges. A restarted pixel next to a converged one is a step in the medium over
and above the genuine transmittance step — sharper, noisier, and re-created every
frame.

RTGL1 shipped the alternative and left it disabled (`const float
g_temporalWeight = 0.0;` in `CmVolumetricProcess.comp`, with the world-space
reprojection helper and prev-frame grid bindings all wired and never called).
`rt_volume_taccum 8` turns it on: each froxel cell blends against its own world
position in the previous frame's grid, no surfaces involved, and the ray integral
is recomputed fresh every frame from the smooth field. The medium arriving at
`CmPrepareFinal` is then continuous across silhouettes in a way it never was
here, and the upscaler's ringing has almost nothing to bite on.

**What this does and does not overturn:**

- §5's ladder stands. The artefact *was* carried by the upscaler; `native` still
  removes it, DLAA is still the worst arm. Nothing here says otherwise.
- §6's "strongly indicated, not proven" mechanism — the medium's own structure is
  the payload, the upscaler is the carrier — is now better supported: removing
  most of the medium's high-frequency structure removed the artefact without
  touching the upscaler at all.
- §7.1, §7.2 and §7.5 remain measured negatives, and §7.6's DLSS preset question
  is still open and still worth taking; it is simply no longer urgent.
- §7.3 (`rt_volume_edgesoft 2`) stays on. It is cheap, it is measured, and it
  addresses the genuine transmittance step, which in-grid accumulation does not
  remove — only the restart noise on top of it.

**Not re-measured on the MAP93 ladder.** The verdict here is from play, and the
lab arms exist to take it properly: capture `arm-*`/`ctrl-*` pairs at
`+rt_volume_taccum 0` and `+rt_volume_taccum 8` per §8 and run
`measure_edge_outlines.py`. Recorded as user-confirmed, not as a number.
