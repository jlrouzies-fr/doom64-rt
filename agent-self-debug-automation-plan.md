# Delegation brief — Agent self-debug automation (game runs + data capture)

**Audience:** an agent picking this up cold. **Goal:** let an agent reproduce a rendering symptom, capture evidence, and get a machine-readable verdict **without a human driving the game**.
**One-shot build brief, not a living tracker.** When phases land, update `AGENTS.md` (launchers table) and `open-issues-rt-lighting.md` (tools rows); do not create new tracking docs.

**Read first:** `AGENTS.md` (launchers + pitfalls) → `emis-meta-integrity-fix-plan.md` (the bug class this tooling must catch) → this file.

---

## 1. Why this exists

Post-mortem of the wall-wash saga (see `gallery-emis-wall-wash-diagnostics.md`): the root-cause fix was **applied, then silently reverted by a restore script**, and every automated check passed anyway. Three automation holes caused it:

1. **No run manifests** — captures carried no record of cvars, build hashes, or meta state, so "same issue" reports couldn't be compared across runs.
2. **QA validated the wrong layer** — hygiene checked the scene overlay but not the global `textures.json` where the contamination lived.
3. **Subjective screenshots** — "user still sees wash" with no settle control, no readiness rule, no metric; temporal denoiser (DLSS-RR) made automated captures disagree with human perception.

The required shape of the fix: **every game run must emit (a) structured logs, (b) settled captures, (c) a manifest of cvars/build/meta hashes, (d) a metric verdict — atomically.**

## 2. What already exists (do not rebuild — generalize)

| Asset | Mechanism worth keeping |
|---|---|
| `tools/write_gallery_tour_only.py` + tour ZScript | In-game `EventHandler` teleports the player through poses, calls `level.MakeScreenShot()` (native RT grab — **no focus needed**), prints stdout markers `D64RtGalleryTour: N` / `D64RtGalleryShot: N`. This pose+shot+marker pattern is the core primitive. |
| `tools/review_gallery_batch.ps1` | Full lifecycle: kills gzdoom → builds tour pk3 → launches with `-stdout` log redirect → waits for window → forces client size via Win32 (`AdjustWindowRectEx`/`SetWindowPos`) → waits on log markers → claims `Screenshot_*.png` → per-shot mean-luma sanity (abort if first shot mean < 18, or 3+ dark shots) → writes `manifest.json`. |
| `tools/score_yaw_sweep.py` | Metric scoring: center/lower-frame crop (drops HUD + sky), mean / p95 / bright-frac luma stats, threshold gates, JSON report (`yaw_score.json`), exit code 0/2. |
| `tools/capture-gzdoom.ps1` | `CopyFromScreen` fallback — **fragile** (focus-stealing, grabs overlapping windows). Keep only as last resort; native `MakeScreenShot` is the primary. |
| `tools/wash-qa/*.cmd`, `tools/wash-scratch/` | Scenario ladders (currently manual). To be re-expressed as scenario definitions, not edited per-run. |
| `tools/check_emis_hygiene.py` | Static meta gate (being extended to global JSON under the P0 brief). |

## 3. Gap analysis (each gap → concrete failure it caused)

| Gap | Cost already paid |
|---|---|
| No warmup/settle rule; screenshots on fixed tic counts | "Automations teleport-and-settle often miss it (RR/temporal). Manual free-roam reproduces reliably." |
| Cvars duplicated per script | `review_gallery_batch.ps1` runs `rt_upscale_dlss 0`, flashlight **on**, `rt_emis_additive_dflt 0.15` — play launcher uses DLSS-RR, flashlight off, additive 0. Gallery findings didn't transfer to MAP01. |
| No build/meta provenance | Stale SPV vs patched `HitInfo.inl` ambiguity ("is the live shader fixed?") was unanswerable for days. |
| No structured engine log channel | RT state only observable via Dev window screenshots and human eyes. |
| No stable artifacts layout | PNGs scattered across `tools/_gallery/`, `screen/`, gitignored dirs; regression diffing impossible. |
| No golden registry | Every A/B run from scratch; before/after pairing by directory naming convention. |

## 4. Target design

### 4.1 Run record layout (every harness run, no exceptions)

```
tools/runs/<YYYYMMDD-HHMMSS>-<slug>/
  run.json        # manifest (below)
  stdout.txt      # game log (structured lines)
  shots/*.png
  metrics.json    # scorer output
  verdict.txt     # PASS/FAIL + reasons (exit code mirrors it)
```

`run.json` minimum schema:

```json
{
  "slug": "wash-map01-spawn",
  "utc": "2026-08-04T01:23:45Z",
  "scenario": "scenarios/wash-map01-spawn.json",
  "cvars": {"rt_emis_mapboost": "200", "...": "..."},
  "cmdline": ["-iwad", "..."],
  "dll_sha1": {"rt/bin/RTGL1.dll": "…"},
  "spv_sha1": {"rt/shaders/RtRaygenIndirectInit.rgen.spv": "…"},
  "meta_sha1": {"rt/data/textures.json": "…", "textures_world_emis.json": "…"},
  "git": {"repo_head": "…", "rtgl_dirty": true},
  "emis_hygiene": {"exit": 0, "global_contaminants": 0},
  "pid": 1234, "exit_code": 0, "duration_s": 95
}
```

Rule: **a capture without a manifest is treated as no capture.** Review scripts must refuse to diff shots lacking `run.json`.

### 4.2 One harness: `tools/rt-run.ps1`

Subsumes `review_gallery_batch.ps1` / `run_gallery_*_ab.ps1` / `run_emis_iso_qa.ps1` / `smoke-capture-ret.ps1`. Contract:

```powershell
tools/rt-run.ps1 -Scenario tools/scenarios/wash-map01-spawn.json [-Set rt_emis_mapboost=0] [-Tag before]
```

Scenario JSON = everything that varies (wad list, map, cvars, pose list or tour generator name, settle rule, scorer + thresholds, timeout). `-Set` overrides individual cvars so A/B = two runs of the same scenario with one override. Harness responsibilities (mostly extracted from `review_gallery_batch.ps1`):

1. Pre: kill gzdoom; compute all hashes; run `check_emis_hygiene.py` and store its result in the manifest (run continues but manifest records the state).
2. Launch: `-stdout` redirect, fixed `-width/-height`, window wait + Win32 client-size force (existing code).
3. Readiness gate before any shot: **N seconds wall-clock in final pose AND rendered-frame counter advanced by M** (frame counter via 4.3 logging; interim fallback: M tics from stdout markers). Dwell constants like the tour's `DWELL=105` must come from the scenario, not be hardcoded.
4. Post: claim screenshots, run scorer, write `run.json`/`metrics.json`/`verdict.txt`, exit 0/2.

### 4.3 Engine observability (small, high leverage)

1. **Log file:** verify GZDoom's `+logfile <path>` (or `debug_logging`) works under the RT fork; harness always sets it (mirrors stdout; survives crashes).
2. **RT debug channel:** add a cvar-gated (default off) `Printf` channel in `rt_main.cpp` — e.g. `rt_debuglog` — emitting one-line-per-frame: `RTDBG frame=<n> dynlights=<k> emis_uploads=<k> sector_lights=<0/1>`. This is what makes "are the 9802 flicker lights actually animated in RT?" (open-issues §1.1/§5 step 2) answerable in one run instead of a session. Rebuild via `tools/build-gzdoom-rt.cmd`; log the patch in `compat-patches.md`.
3. **Verbatim meta echo:** engine already warns on duplicate texture names ("first wins") — confirm that warning reaches stdout; if not, make it. Harness treats that warning as a hygiene FAIL.

### 4.4 Scoring that matches the symptom class

Keep `score_yaw_sweep.py` as the reference implementation; generalize into `tools/rt-score.py` with per-scenario metric selection:

- **wash:** current luma stats on center/lower crop, plus **A/B dirty-threshold**: after `rt_emis_mapboost 0` baseline, |mean(200) − mean(0)| must stay < ε per pose (captures "wash dies with boost 0" as a number).
- **blink (9802):** two matched crops across time at the same pose → per-pixel diff ratio in expected light pools; flicker = diff crosses threshold periodically. Needs ≥2 shots at known tic offsets — scenario expresses this as `shots: [{t: "+0"}, {t: "+14"}]`.
- **regression:** SSIM or mean-abs-diff vs golden (Pillow + numpy; add scikit-image only if SSIM is actually needed — deps stay in `G:\AI\Doom64-RT\deps\`).

Every scorer writes `metrics.json` and exits 0/2. Thresholds live in the scenario file, never in scorer defaults.

### 4.5 Golden registry

`tools/golden/registry.json`:

```json
{"scenario": "wash-map01-spawn", "tag": "clean-global-meta", "run": "tools/runs/20260804-012345-wash-map01-spawn",
 "accepted_by": "user", "date": "…", "shots": ["shots/pose0.png"]}
```

Rule: **only the user promotes a run to golden.** Agents propose (diff report + metrics); user accepts. Store goldens under `tools/golden/<scenario>/` (git-tracked if size stays sane, else document external path).

### 4.6 Scenario library (replace per-bug one-off scripts)

Initial set, expressed as scenario JSONs under `tools/scenarios/`:

| Scenario | Replaces | Gate |
|---|---|---|
| `wash-map01-spawn.json` | wash-qa 01/02/07 manual runs | dirty-threshold vs boost-0 baseline |
| `wash-gallery-wallturned.json` | `run_gallery_wallturned_ab.ps1` | score_yaw_sweep thresholds |
| `blink-map01-9802.json` | open-issues §5 step 1–2 (manual) | frame-counter + RTDBG dynlight lines + crop diff |
| `enemy-eyes-gallery.json` | `review_enemy_gallery_batch.ps1` | per-booth mean-luma sanity + golden diff |
| `emis-gallery-heroes.json` | `run_emis_iso_qa.ps1` | per-class luma + bright-frac |
| `smoke-map01-load.json` | `smoke-capture-ret.ps1` | map loads, first-shot mean ≥ 18, no crash |

Then rewrite `tools/wash-qa/*.cmd` as thin wrappers calling `rt-run.ps1` (or delete them and point open-issues at the scenarios). `tools/test_gallery_emis_qa.cmd` becomes: hygiene gate + 2 scenario runs + scorers — still one command, still pass/fail.

## 5. Phasing

| Phase | Deliverables | Acceptance |
|---|---|---|
| **A. Harness + manifest** | `tools/rt-run.ps1`; `tools/runs/` layout; one converted scenario (`wash-gallery-wallturned`) | Two runs (boost 200 / 0) produce complete manifests; scorer exit codes correct; no human input during runs |
| **B. Engine observability** | logfile wired; `rt_debuglog` channel + rebuild; dup-meta warning confirmed | `blink-map01-9802` run shows `RTDBG` lines with per-frame dynlight radius changes (or proves they don't change — either way, §1.3 gets data) |
| **C. Scenario library + gates** | remaining 5 scenarios; `test_gallery_emis_qa.cmd` rewritten; wash-qa wrappers | Full QA command runs unattended end-to-end; verdict files for all scenarios |
| **D. Goldens + regression** | registry; golden diff in scorer; user promotes first goldens | Re-running a scenario against its golden yields PASS on unchanged tree; hand-breaking one meta line yields FAIL with the right suspect |
| **E. Stretch (optional)** | RTGL Dev-mode counters dump to stdout (reservoirs/light count); headless-claim re-test of `MakeScreenShot` on latest build | Only if A–D are stable |

Estimated effort: A ≈ 1 session, B ≈ 1 session (engine rebuild), C ≈ 1 session, D small. A–C are the critical path; D is what makes it a regression system.

## 6. Hard rules for the executing agent

- Windows-only, PowerShell 5.1; game is never headless — do not chase true headless; native `MakeScreenShot` already works without focus.
- Do not weaken QA to make runs pass: no cropping away the symptomatic region, no flashlight-on baselines, no lowered mapboost except as the labeled control arm.
- Never overwrite existing captures: new run = new `tools/runs/<id>/` directory.
- Kill `gzdoom.exe` before/after every run (file locks, WinError 32).
- Cvar source of truth = play launcher (`tools/launch-retribution-rt.cmd`). Scenarios default to matching it (`rt_upscale_dlss 2`, `rt_rayreconstr 1`, `rt_flsh 0` unless the scenario is explicitly about the flashlight); deviations must be named in the scenario file.
- Deps install only under `G:\AI\Doom64-RT\deps\`. Python = `C:\Users\Winter\AppData\Local\Programs\Python\Python313\python.exe`.
- Old per-bug scripts: consolidate or delete — do not leave a third generation of parallel runners.

## 7. Definition of done

- [ ] `tools/rt-run.ps1` + ≥5 scenarios run unattended; every run emits manifest + metrics + verdict.
- [ ] Manifest proves provenance: DLL/SPV/meta hashes + hygiene result present in every `run.json`.
- [ ] `RTDBG` lines answer "dynlights animating?" from a single log.
- [ ] `test_gallery_emis_qa.cmd` = hygiene + scenarios, one command, pass/fail.
- [ ] Golden registry exists; user accepted ≥2 goldens; regression diff demonstrated (break → detect).
- [ ] `AGENTS.md` launchers table + `open-issues-rt-lighting.md` tools rows updated; obsolete scripts removed.
