# Developers — the written record

Every feature, fix and dead end in this project is written down. This page is the index of
all of it. If you are about to touch something, the doc for it already exists and it
already lists the traps — start there rather than re-deriving them, because most of these
were written *after* losing a day to the thing they describe.

**Reading order for someone arriving cold:**

1. [`AGENTS.md`](AGENTS.md) — the working handbook. Diagnostic procedures, the RT source
   map, the hard rules, and 31 numbered pitfalls that must not be repeated.
2. [`docs/doom64-retribution-pathtracing-plan.md`](docs/doom64-retribution-pathtracing-plan.md) —
   the living plan: phases, checkboxes, corrections, next steps.
3. [`compat-patches.md`](compat-patches.md) — every engine-side change we made, and why.
4. Then whichever feature page below you actually need.

---

## Start here

| Doc | What it is |
|---|---|
| [`AGENTS.md`](AGENTS.md) | **The handbook.** How to diagnose a wrongly-lit surface, which scanner to run first, the `rt/` source file map, how to add a cvar, and the pitfall list. |
| [`docs/doom64-retribution-pathtracing-plan.md`](docs/doom64-retribution-pathtracing-plan.md) | The living project plan. Update it when phases move; do not start a parallel tracker. |
| [`compat-patches.md`](compat-patches.md) | Engine and RTGL1 patch log — what was hardcoded, what was changed, dated. |
| [`docs/open-issues-rt-lighting.md`](docs/open-issues-rt-lighting.md) | Punch list of what still fails. Deliberately not a cheer sheet — only unresolved items belong in §1. |
| [`CREDITS.md`](CREDITS.md) | Who wrote what we build on. Take attributions from here, never from memory. |

## Features

| Feature | Doc | Notes |
|---|---|---|
| Moon, sun, sky leaks | [`docs/moon-and-sky-leaks.md`](docs/moon-and-sky-leaks.md) | `rt_sun_*`, `rt_moon_*`, per-map aim, the `moon` CCMD, the red/green leak debug — and four answers that were wrong. Read before touching anything sky. |
| Clouds and lightning | [`docs/rt-clouds-and-lightning.md`](docs/rt-clouds-and-lightning.md) | The layered cloud deck (stacked sky-dome shells, not a medium), moonlight attenuated through the stack, and MAP11's storm — authored in three places, of which one still worked. |
| Per-map fog | [`docs/rt-fog.md`](docs/rt-fog.md) | What it is, which maps, how to tune it. |
| …its implementation | [`docs/rt-fog-implementation.md`](docs/rt-fog-implementation.md) | The code path end to end, the two RTGL1 froxel changes, and its four traps. |
| Volumetric smoke | [`docs/rt-smoke.md`](docs/rt-smoke.md) | `rt_smoke_*`, the six sources, the smoke lab, and why the sim is on the CPU. |
| Water | [`docs/rt-water.md`](docs/rt-water.md) | Stylized surface + projected caustics, all cvars, four traps. |
| Persistent blood | [`docs/blood-persist.md`](docs/blood-persist.md) | `rt_gore_*`, per-monster blood colour, and the material-naming bug that hid it. |
| Flames | [`docs/flame-lighting.md`](docs/flame-lighting.md) | All 84 flame sprites are lit engine-side. Read before touching any torch, fire or candle. |
| Act title cards | [`docs/act-title-cards.md`](docs/act-title-cards.md) | The ACT I/II/III cards on MAP01, MAP09, MAP20. |
| HUD mugshot | [`docs/hud-mugshot.md`](docs/hud-mugshot.md) | The Doom guy face Doom 64 never had — generated, plus the HUD rearranged around it. |
| Ray Reconstruction | [`RAYRECONSTRUCTION.md`](RAYRECONSTRUCTION.md) | **Alpha, ships off, not recommended.** Start here always; it points into `docs/rayreconstruction/` when needed. |

## Not built yet — plans

| Doc | What it covers |
|---|---|
| [`docs/rt-feature-ideas.md`](docs/rt-feature-ideas.md) | The shortlist of candidate RT features, with what was **rejected and why** — read this before proposing a new effect. |
| [`docs/plan-light-shafts.md`](docs/plan-light-shafts.md) | Shafts from ordinary lamps, not just the moon. The all-lights froxel estimate already exists for fog; the shaft pass just does not read it. |
| [`docs/plan-heat-haze.md`](docs/plan-heat-haze.md) | Refractive air over lava and fire, via the unused `THIN_MEDIA` primitive flag. |
| [`docs/plan-impact-fx.md`](docs/plan-impact-fx.md) | Impact sparks as real emitters, and scorch decals, riding the existing puff and decal paths. |

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
| [`docs/sprite-illumination.md`](docs/sprite-illumination.md) | How sprite *glow* and sprite *lighting* differ: `emissiveMult` cannot light anything; only `lightIntensity` + `lightColorHEX` cast. |
| [`docs/rt-voxel-models.md`](docs/rt-voxel-models.md) | Everything learned building the D64 replacement models. Read before touching `rt/replace/`. |
| [`docs/rt-weapon-model-coverage.md`](docs/rt-weapon-model-coverage.md) | What RTGL1's glTF replacement system actually is, and what is still missing. |
| [`docs/spectre-issue-log.md`](docs/spectre-issue-log.md) | Spectres: why they render as a translucent overlay rather than forced water/glass. |

## Tooling

| Doc | What it covers |
|---|---|
| [`docs/scripted-screenshots.md`](docs/scripted-screenshots.md) | `tools\shot.ps1` — launch, settle, capture, quit, with no user present. |
| [`tools/wash-scratch/README.md`](tools/wash-scratch/README.md) | The isolated from-scratch ladder, which never touches the play tree. |

## Generated inventories

Regenerate these rather than editing them by hand.

| Doc | What it is |
|---|---|
| [`retribution-asset-inventory.md`](retribution-asset-inventory.md) | The Phase 1 inventory of the Retribution WAD — 3516 lumps. |
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
| [`docs/rayreconstruction/`](docs/rayreconstruction/) | The full RR history — noise investigation, flashlight linger, architecture, session handoff. Large; open one only when `RAYRECONSTRUCTION.md` sends you there. |

---

## If you add a doc

- Put feature reference in `docs/`, engine changes in `compat-patches.md`, status in the
  plan or `open-issues-rt-lighting.md`. **Do not invent a parallel tracker** — that rule
  exists because it happened.
- Write the traps down, not just the result. Every "read this before you touch X" line on
  this page was bought with a lost day.
- Add the row here, and if an agent must read it before acting, add it to `AGENTS.md`
  too — that file is what gets loaded first.
