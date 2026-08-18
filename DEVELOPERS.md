# Developers — the written record

Every feature, fix and dead end in this project is written down. This page is the index of
all of it. If you are about to touch something, the doc for it already exists and it
already lists the traps — start there rather than re-deriving them, because most of these
were written *after* losing a day to the thing they describe.

**Reading order for someone arriving cold:**

1. [`AGENTS.md`](AGENTS.md) — the working handbook. Diagnostic procedures, the RT source
   map, the hard rules, and 35 numbered pitfalls that must not be repeated.
2. [`docs/doom64-retribution-pathtracing-plan.md`](docs/doom64-retribution-pathtracing-plan.md) —
   the living plan: phases, checkboxes, corrections, next steps.
3. [`docs/compat-patches.md`](docs/compat-patches.md) — every engine-side change we made, and why.
4. Then whichever feature page below you actually need.

---

## Start here

| Doc | What it is |
|---|---|
| [`AGENTS.md`](AGENTS.md) | **The handbook.** How to diagnose a wrongly-lit surface, which scanner to run first, the `rt/` source file map, how to add a cvar, and the pitfall list. |
| [`docs/doom64-retribution-pathtracing-plan.md`](docs/doom64-retribution-pathtracing-plan.md) | The living project plan. Update it when phases move; do not start a parallel tracker. |
| [`docs/compat-patches.md`](docs/compat-patches.md) | Engine and RTGL1 patch log — what was hardcoded, what was changed, dated. |
| [`docs/open-issues-rt-lighting.md`](docs/open-issues-rt-lighting.md) | Punch list of what still fails. Deliberately not a cheer sheet — only unresolved items belong in §1. |
| [`docs/performance.md`](docs/performance.md) | **The first frame-cost numbers this project has ever taken.** What each knob actually costs, measured on the instrument described there — read it before assuming anything about performance. |
| [`CREDITS.md`](CREDITS.md) | Who wrote what we build on. Take attributions from here, never from memory. |

## Features

| Feature | Doc | Notes |
|---|---|---|
| Moon, sun, sky leaks | [`docs/moon-and-sky-leaks.md`](docs/moon-and-sky-leaks.md) | `rt_sun_*`, `rt_moon_*`, per-map aim, the `moon` CCMD, the red/green leak debug — and four answers that were wrong. Read before touching anything sky. |
| Clouds and lightning | [`docs/rt-clouds-and-lightning.md`](docs/rt-clouds-and-lightning.md) | The layered cloud deck (stacked sky-dome shells, not a medium), moonlight attenuated through the stack, and MAP11's storm — authored in three places, of which one still worked. |
| Per-map fog | [`docs/rt-fog.md`](docs/rt-fog.md) | What it is, which maps, how to tune it. |
| …its implementation | [`docs/rt-fog-implementation.md`](docs/rt-fog-implementation.md) | The code path end to end, the two RTGL1 froxel changes, and its four traps. |
| Volumetric smoke | [`docs/rt-smoke.md`](docs/rt-smoke.md) | `rt_smoke_*`, the six sources, the smoke lab, and why the sim is on the CPU. |
| …the outlines behind it | [`docs/rt-volumetric-edge-outlines.md`](docs/rt-volumetric-edge-outlines.md) | **Resolved.** The dark line at every edge seen through a medium is drawn by the **temporal upscaler**, not by the froxel grid — six volumetric knobs ruled out by test on MAP93, including the two this repo previously blamed. `rt_volume_edgesoft` took the silhouettes; in-grid accumulation (below) took the rest. Four approaches built and measured negative are recorded there. |
| …the trails behind sprites | [`docs/rt-volumetric-weapon-trails.md`](docs/rt-volumetric-weapon-trails.md) | Weapon-shaped stamps in smoke, casing trails, and MAP12's thunder smearing every monster and geometry edge through the moon shafts — one class, not three bugs. The medium was accumulated in **screen space**, where history must be validated against surface depth, so every silhouette restarted it. RTGL1 shipped in-grid (world-space) accumulation and left it disabled; `rt_volume_taccum` turns it on. Plus `rt_volume_spriteshadow 0`: billboards and their solid shadow-proxy planes no longer shadow the medium. |
| Impact sparks and debris | [`docs/rt-impact-fx.md`](docs/rt-impact-fx.md) | `rt_spark_*`. The hitscan hook that *is* a real game hook, the PUFF palette the look comes from, per-material debris, and **the texture surface classification** that drives it. Four bugs written up because each looked like the opposite of what it was. |
| Projectile impacts | [`docs/plan-projectile-impact-fx.md`](docs/plan-projectile-impact-fx.md) | **Done and shipping**, despite the filename — plasma/arachnotron/BFG arcs (`rt_arc_*`), the Unmaker wall **burn** (`rt_laser_*`, it shipped as a burn, not the planned melt), and barrels that come apart into flying plates (`rt_barrel_*`, no fire and no acid). The page's own §-by-§ notes say what shipped differently from the plan. |
| Sprite shadows and contact AO | [`docs/sprite-shadows-and-ao.md`](docs/sprite-shadows-and-ao.md) | Two independent problems with camera-facing quads under a path tracer: no side-lit shadow (`rt_sprite_shadow`, invisible crossed quads seen only by shadow rays) and things floating off the floor (`rt_sprite_ao`, a decal multiplied into the floor albedo). Neither replaces the other. |
| The broken lamp pane | [`docs/lamp-panes-broken-bulbs.md`](docs/lamp-panes-broken-bulbs.md) | Why `SFLATAS` ships with three of its four bulbs smashed — the project's **only** art edit, and it is enabled by default. Metre-spaced lights behind a half-metre grating cancel each other's shadows; breaking bulbs fixes it without moving anything. |
| Lamp light shafts | [`docs/plan-light-shafts.md`](docs/plan-light-shafts.md) | **Shipped** — `rt_volume_shafts` and `rt_light_shafts.cpp`. The froxel pass scatters one light (the moon), so beams only ever happened outdoors; this adds an explicit fixture list on top. Covers **three lamp families only** — flames and lava still light surfaces without entering the medium. |
| Water | [`docs/rt-water.md`](docs/rt-water.md) | Stylized surface + projected caustics, all cvars, four traps. |
| Persistent blood | [`docs/blood-persist.md`](docs/blood-persist.md) | `rt_gore_*`, per-monster blood colour, and the material-naming bug that hid it. |
| Flames | [`docs/flame-lighting.md`](docs/flame-lighting.md) | All 84 flame sprites are lit engine-side. Read before touching any torch, fire or candle. |
| Act title cards | [`docs/act-title-cards.md`](docs/act-title-cards.md) | The ACT I/II/III cards on MAP01, MAP09, MAP20. |
| HUD mugshot | [`docs/hud-mugshot.md`](docs/hud-mugshot.md) | The Doom guy face Doom 64 never had — generated, plus the HUD rearranged around it. |
| NRD (ReLAX) denoiser | [`docs/plan-nrd-denoiser.md`](docs/plan-nrd-denoiser.md) | **Active, ships off** behind `rt_nrd 1` (console only, does not persist). An alternative denoiser lane to A-SVGF, same downstream frame shape, a bit noisier at 1 spp — raise samples per pixel to 2 and it closes. Opened because the RR second pass measured null: the correlation is inherent to our sampling. |
| Ray Reconstruction | [`RAYRECONSTRUCTION.md`](RAYRECONSTRUCTION.md) | **Alpha, ships off, not recommended.** Start here always; it points into `docs/rayreconstruction/` when needed. The standing bound is a **renderer** one, not an RR bug: RR is trained on full MIS + area-light transport and this renderer has neither, so it needs brute force (high spp, high light-candidate counts) to look decent — see [`docs/plan-area-lights-mis.md`](docs/plan-area-lights-mis.md). |

## Not built yet — plans

| Doc | What it covers |
|---|---|
| [`docs/rt-feature-ideas.md`](docs/rt-feature-ideas.md) | The shortlist of candidate RT features, with what was **rejected and why** — read this before proposing a new effect. Glass and mirrors are rejected on the *art*, not the plumbing: the game has neither. |
| [`docs/plan-heat-haze.md`](docs/plan-heat-haze.md) | Refractive air over lava and fire, via the unused `THIN_MEDIA` primitive flag. |
| [`docs/plan-impact-fx.md`](docs/plan-impact-fx.md) | **Scorch decals only** — the sparks and debris half of this shipped, and is [`docs/rt-impact-fx.md`](docs/rt-impact-fx.md). |
| [`docs/plan-multi-frame-generation.md`](docs/plan-multi-frame-generation.md) | NVIDIA multi frame generation (2x → 4x). The hard parts — Reflex markers, interposer swapchain, DX12 interop — are already correct; the blockers are the vendored Streamline version and HUD interpolation. |
| [`docs/plan-storm-rain.md`](docs/plan-storm-rain.md) | Rain and wet ground on MAP11, the game's only storm map. The particles are `rt_dust` with gravity; the wetness **cannot** be done in `textures.json`, because the ORM texture wins over `roughnessDefault`. |
| [`docs/plan-area-lights-mis.md`](docs/plan-area-lights-mis.md) | Triangle/area lights and full BRDF–light MIS. **Read the ground-truth section before costing it**: sphere lights are already solid-angle area lights, emissive geometry already emits on the indirect lane, and `TRIANGLE_LIGHTS` is a half-removed upstream feature that breaks the C++ compile. Its value is gated on `rt_refl_thresh` — the roughness floor exists because A-SVGF cannot denoise sharp speculars, and MIS only matters once that floor comes down. |
| [`docs/plan-shadow-contact-hardening.md`](docs/plan-shadow-contact-hardening.md) | Sharp shadows at the contact point, softening with blocker distance — the behaviour RR has and A-SVGF does not. Phase 0 is free (`rt_shadow_samples`, unpinned, never A/B'd) and may show the honest answer is to stop there. Beyond it: recover the blocker distance from the shadow ray, carry a penumbra buffer, then either adapt A-SVGF's à-trous weights or feed NRD **SIGMA**, which is already instantiated and unfed. |

## Lighting — the repair pipeline

The largest body of work in the project: the game paints light where it should emit it.

| Doc | What it covers |
|---|---|
| [`docs/sequence-light-chains.md`](docs/sequence-light-chains.md) | The nine repair families in `tools/make_seqlight_fix.py`, including the ACS calls with computed arguments that signature scanning cannot see at all. |
| [`docs/rt-lighting-practices.md`](docs/rt-lighting-practices.md) | The numbered practice list — how to identify a surface, why fixture proximity is the wrong test, `rt_tex_probe`, `rt_lightlevel_watch`, and the sector-colormap trap. |
| [`docs/solo-bulb-lamps.md`](docs/solo-bulb-lamps.md) | Lighting SFLATDE / SFLATCH, which each show one lit bulb in the art. |
| [`docs/faux-lamp-panels.md`](docs/faux-lamp-panels.md) | SFLATC / SPACECE lit as bulb arrays — a deliberate invention, documented as one. |
| [`docs/lamp-pop-in-investigation.md`](docs/lamp-pop-in-investigation.md) | Why inferred lamps pop in at close range. |

## Materials, sprites and models

| Doc | What it covers |
|---|---|
| [`docs/material-authoring-spec.md`](docs/material-authoring-spec.md) | The authoring contract for `_n` / `_orm` / `_h` / `_e` and the scene JSON. Gates bulk authoring. |
| [`docs/plan-metal-labelling.md`](docs/plan-metal-labelling.md) | **Largely shipped** — metal/roughness labelling for 898 wall and flat textures across seven surface classes. Records why it is *hand*-labelled: a local VLM pass could not tell painted steel from bare metal, and derivation was abandoned. |
| [`docs/plan-sprite-materials.md`](docs/plan-sprite-materials.md) | Sprite emissives and materials. **Its own header still says "planned, not started" and that is stale** — 132 sprite codes (1,087 frames) are classified and baked (`tools/bake_sprite_materials.py`), and `rt_sprite_pbr_mix` ships at **0.35**, not 1, because full PBR breaks flat-normal sprites. The coverage tables and the weapon-material gap are still worth reading. |
| [`docs/sprite-illumination.md`](docs/sprite-illumination.md) | How sprite *glow* and sprite *lighting* differ: `emissiveMult` cannot light anything; only `lightIntensity` + `lightColorHEX` cast. |
| [`docs/rt-voxel-models.md`](docs/rt-voxel-models.md) | Everything learned building the D64 replacement models. Read before touching `rt/replace/`. |
| [`docs/rt-weapon-model-coverage.md`](docs/rt-weapon-model-coverage.md) | What RTGL1's glTF replacement system actually is, and what is still missing. |
| [`docs/spectre-issue-log.md`](docs/spectre-issue-log.md) | Spectres: why they render as a translucent overlay rather than forced water/glass. |

## Tooling

| Doc | What it covers |
|---|---|
| [`docs/scripted-screenshots.md`](docs/scripted-screenshots.md) | `tools\shot.ps1` — launch, settle, capture, quit, with no user present. |
| [`docs/skill-texture-material-labeller.md`](docs/skill-texture-material-labeller.md) | The keyboard-driven gallery a human uses to classify every texture by surface class and roughness — generator, export format, and how the JSON reaches the appliers. |
| [`docs/rt-verbose.md`](docs/rt-verbose.md) | `rt_verbose` — why RT diagnostics are off the notify overlay by default, and why `con_notifylines 0` is the wrong reach. |
| [`tools/wash-scratch/README.md`](tools/wash-scratch/README.md) | The isolated from-scratch ladder, which never touches the play tree. |

## Generated inventories

Regenerate these rather than editing them by hand.

| Doc | What it is |
|---|---|
| [`docs/retribution-asset-inventory.md`](docs/retribution-asset-inventory.md) | The Phase 1 inventory of the Retribution WAD — 3516 lumps. |
| [`docs/texture-status.md`](docs/texture-status.md) | Per-texture RT companion status. |
| [`tools/_emissive_candidates.md`](tools/_emissive_candidates.md) | Scored world-emissive candidates: what is covered, what is missing. |

## Historical — solved, superseded, or one-shot briefs

Kept because they record *why* something is built the way it is. Do not treat them as
current instructions; where they disagree with the pages above, the pages above win.

| Doc | Status |
|---|---|
| [`docs/blood-explosion-burst.md`](docs/blood-explosion-burst.md) | Shipped. The design record behind `blood-persist`. |
| [`docs/blue-room-rt-lighting.md`](docs/blue-room-rt-lighting.md) | Superseded — the specific fix became the general one. |
| [`docs/gallery-emis-wall-wash-diagnostics.md`](docs/gallery-emis-wall-wash-diagnostics.md) | Diagnostic brief for the emissive GI wash. |
| [`docs/gallery-emis-wall-wash-fix-plan.md`](docs/gallery-emis-wall-wash-fix-plan.md) | The matching fix plan / rebuild ladder. |
| [`docs/emis-meta-integrity-fix-plan.md`](docs/emis-meta-integrity-fix-plan.md) | One-shot brief, not a tracker. |
| [`docs/agent-self-debug-automation-plan.md`](docs/agent-self-debug-automation-plan.md) | One-shot brief for unattended reproduction and capture. |
| [`docs/plan-rayreconstruction-secondpass.md`](docs/plan-rayreconstruction-secondpass.md) | **Implemented and measured null.** The second attempt at RR: full input contract verified live, still no better than A-SVGF. That result is what opened the NRD lane. |
| [`docs/rayreconstruction/`](docs/rayreconstruction/) | The full RR history — noise investigation, flashlight linger, architecture, session handoff. Large; open one only when `RAYRECONSTRUCTION.md` sends you there. |

---

## If you add a doc

- Put feature reference in `docs/`, engine changes in `docs/compat-patches.md`, status in the
  plan or `open-issues-rt-lighting.md`. **Do not invent a parallel tracker** — that rule
  exists because it happened.
- Write the traps down, not just the result. Every "read this before you touch X" line on
  this page was bought with a lost day.
- Add the row here, and if an agent must read it before acting, add it to `AGENTS.md`
  too — that file is what gets loaded first.
