# Delegation brief — Emissive meta integrity fix + wash closure (P0–P2)

**Audience:** an agent picking this up cold. **Effort:** P0 ≈ 1 hour; P1 ≈ half a day (mostly game-run A/B); P2 optional.
**This is a one-shot task brief, not a living tracker.** Record all results/status in the canonical docs: `open-issues-rt-lighting.md`, `AGENTS.md`, `compat-patches.md` (engine only). Do not create new tracking docs.

**Read first (in this order):** `AGENTS.md` → `open-issues-rt-lighting.md` → this file. Skim `gallery-emis-wall-wash-fix-plan.md` §"Root cause" only if you need the wash backstory.

---

## 1. Why this brief exists (evidence, verified 2026-08-03)

The wash root cause was correctly diagnosed (stock Doom II emissive meta contaminating the **global** `rt/data/textures.json`; `albedo × emissiveMult × rt_emis_mapboost(200)` floods indirect GI), and `gallery-emis-wall-wash-fix-plan.md` Step 1 claims the scrub is **"Done"**. **It is not in effect in the live tree.** Verified findings:

| Finding | Where | Claim vs reality |
|---|---|---|
| 42 × `PLAY*` body frames at `emissiveMult: 4.25` | build tree global `textures.json` (e.g. `PLAYA1` line 1274) | fix plan says "gone" — **present** |
| `FIRELAVA` duplicated, first-wins line at 0.7 + `lightIntensity` 700 | lines 41 and 145 | fix plan says "resolve" — **unresolved** |
| ~670 entries total with emis/light fields (90 @ 1.0, 52 @ 0.6, 34 @ 0.7, …) | same file | should be authored keep-set only (~200 entries) |

**Mechanism of the revert (do not blame the scrub itself — it works):**

1. `tools/gen_world_emissives.py` line ~1123: full scrub runs **only with `--scrub`** (opt-in).
2. `tools/restore_pre_wash_gallery_emis.py` restores `textures.json.pre_noemis_ab` — a backup that **contains the stock metas**. After any restore, authored generators (eyes/fx/world) re-add their entries, but nobody re-ran `--scrub`.
3. `tools/check_emis_hygiene.py` **never inspects the global JSON** — only the gallery scene overlay and `rt/mat/*_e.png`. Worse, its `KEEP_E_RE` whitelists `PLAY`, `FIRE`, `BFG` — the contaminant prefixes — so hygiene prints PASS while the wash source is live.

Net effect: the pending retest (`tools/wash-qa/07-fullscrub-boost200.cmd`) was never meaningful, and "wash still open" (open-issues §1.2) has never been tested against a verified-clean global meta.

---

## 2. P0 — Re-apply the scrub and make it stick

### 2.1 Re-scrub the live tree

```powershell
cd G:\AI\Doom64-RT
& "C:\Users\Winter\AppData\Local\Programs\Python\Python313\python.exe" tools\gen_world_emissives.py --scrub
```

Verify immediately:

```powershell
# Expect: no PLAY/FIRELAVA/NUKAGE etc. with emissiveMult; eyes (mult 2), fx, SKUL (0.12), world allowlist remain
Select-String -Path "sourcecode\gzdoom-rt\build\RelWithDebInfo\rt\data\textures.json" -Pattern '"emissiveMult":\s*4\.25'   # expect 0 matches
# Duplicate names (FIRELAVA): report any name occurring >1 with emis fields
Select-String -Path "sourcecode\gzdoom-rt\build\RelWithDebInfo\rt\data\textures.json" -Pattern '"textureName":\s*"([^"]+)"' -AllMatches |
  ForEach-Object { $_.Matches.Groups[1].Value } | Group-Object | Where-Object Count -gt 1
```

Keep-set that **must survive**: enemy eyes (`textures_enemy_eyes.json`, mult ≈ 2), monster/weapon FX fire frames (`PLAYF*`/`POSSF*`/…, `lightIntensity` + `ff8c52`), `SKUL*` (0.12), world allowlist (`textures_world_emis.json`, ≈ 62 entries). Reference counts: `open-issues-rt-lighting.md` §6.

### 2.2 Extend `tools/check_emis_hygiene.py` to gate the global JSON

- Add a check on `sourcecode/gzdoom-rt/build/RelWithDebInfo/rt/data/textures.json`: **fail** if any entry outside the keep set has `emissiveMult` / `lightIntensity` / `lightColorHEX`; **fail** on duplicate `textureName` where either copy has emis fields.
- Compute the keep set from the **actual overlay JSONs** (`textures_world_emis.json`, `textures_enemy_eyes.json` — locate under `Doom64-Retribution/Retribution-RT-Materials/rt/data/`) instead of regexes. Fall back to prefix rules only for FX fire frames (suffix-`F` frames like `POSSF`, `PLAYF1`).
- **Tighten `KEEP_E_RE`**: remove blanket `PLAY`, `FIRE`, `BFG` (these were the contaminants). Fire-frame coverage must be suffix-based, not prefix-based.
- Confirm `tools/test_gallery_emis_qa.cmd` runs the extended hygiene check and now fails when global contamination is reintroduced (test by hand-editing one `PLAYA1 4.25` line back in, expect FAIL, then re-scrub).

### 2.3 Make scrub the default

- `tools/gen_world_emissives.py`: flip the opt-in — scrub runs by default, `--no-scrub` is the escape hatch.
- **Before flipping**, verify `_authored_emis_keep()` covers eyes/FX/SKUL (print keep-set size; spot-check `TROOA1`, `POSSF1`, `SKULA1`, `SMONAA` are in it). If anything authored is missing, fix the keep function first — scrub-by-default with an incomplete keep set will silently strip eyes.

### 2.4 Neutralize the re-contamination vector

- `tools/restore_pre_wash_gallery_emis.py`: make it call `scrub_stock_world_emis()` after restoring the backup and print a loud warning, or delete the script if nothing references it (grep launchers/wash-qa first). It must not be possible to restore stock metas without scrubbing.

### 2.5 Re-run the full regen chain and validate

Order: `gen_world_emissives.py` (now scrubbing) → `gen_enemy_eye_emissives.py` → `gen_fx_emissives.py`. Then:

- Counts match open-issues §6 (≈143 eye metas, ≈62 world allowlist).
- `python tools/check_emis_hygiene.py` → PASS (with the new global check).
- `tools/test_gallery_emis_qa.cmd` → record result.

---

## 3. P1 — Close the wash question (authoritative pass, play launcher only)

Do this **after** P0. All light A/B on `tools/launch-retribution-rt.cmd` (MAP01) and the gallery wall pose — **not** WashScratch (open-issues §1.6 drift risk). `rt_flsh 0` when judging ambient.

1. **Wash A/B on verified-clean meta:** MAP01 spawn + gallery STONE2 `wallturned` pose; boost 200 vs `rt_emis_mapboost 0`. Capture screenshots; log one-line verdicts in `open-issues-rt-lighting.md` §2 ("what was tested") with date.
2. **If wash is gone:** move §1.2 to fixed; mark `gallery-emis-wall-wash-fix-plan.md` and `gallery-emis-wall-wash-diagnostics.md` as **superseded** (one line at top of each pointing at open-issues).
3. **If wash persists:** only then do the shader experiment already specced in `gallery-emis-wall-wash-fix-plan.md` Step 4 (INDIR `emission = vec3(0.0)` in `deps/RTGL/Source/Shaders/HitInfo.inl`, rebuild via `tools/build-rtgl.cmd`). Decide Option A (safety clamp) vs Option B (zero INDIR `_e`) per that plan. Do not start here — the meta state has never been clean in a test before.
4. **Ceiling lamps / 9802 blink (open-issues §1.1, §1.3):** execute open-issues §5 in order: `rt_dynlight 0/1` A/B at spawn → if no flicker, instrument/log uploaded dynlight radius per tic → if flicker but wrong, tune `rt_dynlight_intensity` (currently 50; 24 map units × 50 is untested) → then make the product decision for ceiling blobs: **glow-only (recommend, ship current `_e`)** vs must-cast (co-located light, documented floating-orb risk). Record outcome in §1.1/§1.3.

---

## 4. P2 — Process hardening (only after P0+P1 land)

- Reconcile docs: `AGENTS.md` pitfall list / `doom64-retribution-pathtracing-plan.md` Status must match reality (the scrub was never durably done — say so, then say it now is and how it's enforced).
- `tools/gen_pinky_eye_emissives.py` uses `EMIS = 4.25`, contradicting the documented eye policy (mult ≈ 2). Either fold pinky into `gen_enemy_eye_emissives.py` with the standard policy or document the exception in `material-authoring-spec.md`.
- Optional: generators print an engine-tree vs `Retribution-RT-Materials/` drift check (file-count/hash) so the two trees can't diverge silently.

---

## 5. Hard rules for the executing agent (violations have caused regressions before)

- Never edit Retribution originals; RT content lives in the engine tree + `Retribution-RT-Materials/` only.
- `rt/mat/textures.json` is **not** the meta source of truth — `rt/data/textures.json` + scene overlays are.
- No `lightIntensity` on eyes, wall screens, EXIT signs, or ceiling flats. No `noShadow` on any monster sprite/fire frame.
- Keep launcher cvars as-is: `rt_emis_mapboost 200`, `rt_emis_maxscrcolor 3`, `rt_mod_compat 1`, `rt_sector_lights 0`. Do not lower mapboost to mask wash.
- Do not re-enable `AUTO_EYES` in the eye generator; do not add `SKUL*` to `gen_fx_emissives.py` prefix rules.
- Kill `gzdoom.exe` before rebuilding pk3s/RTGL (WinError 32 file locks).
- Engine/runtime trees are gitignored: after any RTGL source change, rebuild via `tools/build-rtgl.cmd` and **verify SPV + DLL mtimes advanced** before playtesting (stale-shader false negatives already cost a day once).

## 6. Definition of done

- [ ] Global `textures.json` clean; duplicates resolved; hygiene gate covers global JSON and fails on hand-planted contamination.
- [ ] Scrub-by-default live; restore script safe or gone; full regen chain reproduces §6 counts.
- [ ] `test_gallery_emis_qa.cmd` PASS recorded.
- [ ] Wash verdict (gone / persists + next step) recorded in `open-issues-rt-lighting.md` §2; §1.2 moved or updated; superseded notes on the two wash docs if closed.
- [ ] Ceiling-lamp decision recorded in §1.1.
- [ ] `AGENTS.md` / plan Status reconciled. `git status` shows only intended files.
