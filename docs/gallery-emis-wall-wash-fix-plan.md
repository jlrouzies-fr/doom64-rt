# Plan: Gallery wall emissive wash — root cause & fixes

**For:** Manual A/B + stepwise rebuild. **Status:** Prefer **WashScratch** ladder below (isolated tree). Older `tools/wash-qa/` still valid for shader-variant swaps on the live tree.

**Reference docs:**
- `tools/wash-scratch/README.md` ← **start here for from-scratch retest**
- `gallery-emis-wall-wash-diagnostics.md` (symptom + experiment log)
- `compat-patches.md` § "Directional white wash mistaken for sky leak"
- `material-authoring-spec.md`

---

## WashScratch (from scratch — recommended)

Isolated runtime: `sourcecode/gzdoom-rt/build/WashScratch/`  
**Never writes** to play `build/RelWithDebInfo/`.

Goal: re-apply finished work **one layer at a time** and mark which step reintroduces STONE2 wall blotches.

| Step | Command | Expect |
|---|---|---|
| 0 | `tools\wash-scratch\00-bootstrap.cmd` | Stock `gzdoom-rt-1.0.2\rt` + our `gzdoom.exe` |
| S01 | `S01-stock-baseline.cmd` | Stock Doom II emis meta @ mapboost 200 — note wash Y/N |
| S02 | `S02-nuclear-scrub.cmd` | All emis fields stripped + `*_e` quarantined — walls **must** be clean |
| S03 | `S03-patched-rtgl.cmd` | Live patched RTGL1 (INDIR×mult, no Saturate) on scrubbed meta — still clean? |
| S04 | `S04-world-emis.cmd` | Authored allowlist only (current dialed mults) |
| S05 | `S05-dynlights.cmd` | + `rt_dynlight` |
| S06 | `S06-map01-play.cmd` | MAP01 on WashScratch |

Checklist: `tools\wash-scratch\00-RUN-ORDER.cmd` · `status.cmd`

**How to report:** for each step, one line: `S0x wash=yes/no  notes=…`. When wash returns, that layer is the culprit — stop and dig there before adding more.

---

## Manual QA on live tree (legacy wash-qa)

All spawn at the **wallturned** pose on MAP99 (STONE2 end-wall on the right). Quit GZDoom between each.

| # | Script | What it tests | Pass look |
|---|---|---|---|
| 0 | `tools/wash-qa/prepare-variants.ps1` | Once: build live / indir_kill / clamp RTGL stashes | 3 variants under `tools/wash-qa/variants/` |
| 1 | `tools/wash-qa/01-scrubbed-boost200.cmd` | Scrubbed meta @ mapboost 200 | Walls hopefully clean; CRT glow OK |
| 2 | `tools/wash-qa/02-scrubbed-boost0.cmd` | Control mapboost 0 | Wash **must** die |
| 3 | `tools/wash-qa/03-scrubbed-sky0.cmd` | Sky off @ boost 200 | Same blotches as 01 ⇒ not sky |
| 4 | `tools/wash-qa/04-indir-kill.cmd` | Shader INDIR emission=0 | Walls clean; CRT still glows on stare |
| 5 | `tools/wash-qa/05-with-clamp.cmd` | Preferred clamp fix | Clean walls + soft GI |
| 6 | `tools/wash-qa/06-restore-live.cmd` | Put live DLL back | — |

Or open `tools/wash-qa/00-RUN-ORDER.cmd` for the checklist.

**Already done (Step 1):** broadened scrub, then **full non-authored scrub** after wash-qa 01–05 failed.

**Wash-qa result (user):** 01, 03, 04, 05 still washed; only **02 mapboost 0** clean.
- HitInfo `_e` INDIR kill (04) did **not** help → wash is not only the `_e` sample path.
- Root cause upgraded: stock **`albedo × emissiveMult`** else-path. Global still had **PLAY\* @ 4.25** (and ~650 other non-authored high mults). Player sprite alone ⇒ `albedo×4.25×200` GI on nearby walls (“glow around character”).
- Fix applied: `scrub_stock_world_emis` now strips **all** emis/light fields except authored keep set (world allowlist + eye/FX/explosion overlays). PLAY body 4.25 gone; only PLAYF muzzle (fx) remains.
- **Retest:** `tools/wash-qa/07-fullscrub-boost200.cmd`

---

## Root cause (confirmed by code inspection)

### Primary: Global `textures.json` is contaminated with stock Doom II high-`emissiveMult` entries

The global JSON at `sourcecode/gzdoom-rt/buuild/RelWithDebInfo/rt/data/textures.json` has **~80 stock entries** with `emissiveMult` ranging from 0.1 to 1.0, and some with `lightIntensity` 700–1800 + `noShadow`. These come from the original Doom II RT authoring and were never cleaned for the Retribution mod.

The existing `scrub_stock_world_emis()` in `tools/gen_world_emissives.py` (line 442) only targets a narrow regex:
```
^(OUTTEX|SWX|BFALL|SFALL|WFALL|LAVA|NUKE|HLAVA|D64LAVA|SMON|SEXIT|CRT|CRTR|CFACE|H36|H49|GATE|DBRAIN|REDWALL)
```

This **misses** all of these active high-mult contaminats:

| Texture | emissiveMult | lightIntensity | Issue |
|---|---|---|---|
| FIRELAVA | **0.7** (line 41, first wins) | 700 | Duplicate at line 145 (0.3) |
| FIRELAV2 | 0.7 | 700 | |
| FIRELAV3 | 0.7 (line 42) | 700 | **Duplicate at line 144** (0.3) |
| FIREBLU1-2 | 0.7 | 700 | |
| FIREMAG1-3 | 0.7 | 700 | |
| FIREWALA/B/ALL | 0.7 | 700 | |
| NUKAGE1-3 | **1.0** | — | |
| BFGFA0/B | 1.0 | 1800 | |
| CHGFA0/B, MISFA0-C | 1.0 | 900 | |
| SHTFA0/B, PLSFA0/B, PISFA0 | 1.0 | 700-1100 | |
| PINSA0, PINVA0 | 0.5 | 200 | |
| BKEYB0, RKEYB0, YKEYB0, etc. | 0.6 | 160 | |
| SOULA0 | 0.6 | 260 | |
| ARM1A0, ARM2A0, BON1D0, etc. | 0.2 | — | |
| LITE3-5, LITEBLU1-4, LITERED, EXITSIGN | 0.03–0.5 | — | |
| W108_2-4 | 0.2 | — | |
| W65B_1-2 | 0.3 | — | |
| SW1S0, SW2S1, SW4S1, SW2_2/4/8 | 0.1 | — | |

**Why this causes wall wash:**

The shader path (see below) computes INDIR emission as `_e * emissiveMult * emissionMapBoost(200)`. If any of these textures have `_e.png` files on disk AND a high `emissiveMult` from global, the result is `_e * 0.7 * 200 = 140×_e` — a flood. Even the `else` path (no `_e`) gives `albedo * 0.7 * 200 = 140×albedo`.

Additionally, the `SKIP_RE` in `gen_world_emissives.py` explicitly skips FIRE* names:
```python
SKIP_RE = re.compile(r"^(SPACE|METAL|STEEL|DOOR|GATE|FRSKY|FIRE[A-Z]|PLAY|POSS|TROO|CLOUD|BFALL|SFALL|WFALL)", re.I)
```
So FIRELAVA/FIRELAV2/etc. are NEVER added to the low-mult overlay, and the stock 0.7 entries persist unchallenged.

### Secondary: `TextureMetaManager::Access` — scene wins, but global is the fallback

`TextureMeta.cpp` line 78-90: scene is checked first, then global. For textures in the scene overlay with correct low mults (SMONAA at 0.0005), this is fine. But textures ONLY in global with high mults and `_e.png` on disk will use the global value.

### Shader path (verified correct — just needs clean inputs)

`deps/RTGL/Source/Shaders/HitInfo.inl` lines 551-568:
```glsl
if (tr.emissiveTexture != MATERIAL_NO_TEXTURE) {
    emission = sample(_e);
    #if defined(HITINFO_INL_INDIR)
        emission *= tr.emissiveMult;   // <-- the fix IS here
    #endif
} else {
    emission = h.albedo * tr.emissiveMult;
}
```

`RtRaygenIndirect.inl` line 184: `emis *= globalUniform.emissionMapBoost;` (default 200).

The SPVs at `sourcecode/gzdoom-rt/buuild/RelWithDebInfo/rt/shaders/` were rebuilt 2026-08-03 10:55 (3 min after HitInfo patch at ~10:52). The build system may not invalidate on `.inl` changes — this needs force-clean verification.

---

## Implementation plan

### Step 1: Comprehensive global textures.json scrub

**File:** `tools/gen_world_emissives.py`, function `scrub_stock_world_emis` (line 442)

**Change:** Broaden the `stock` regex to cover all contaminant prefixes:

```python
stock = re.compile(
    r"^(OUTTEX|SWX|BFALL|SFALL|WFALL|LAVA|NUKE|HLAVA|D64LAVA|SMON|SEXIT|"
    r"CRT|CRTR|CFACE|H36|H49|GATE|DBRAIN|REDWALL|"
        r"FIRELAVA|FIRELAV|FIREBLU|FIREMAG|FIREWAL|FIREWALL|FIRE[A-E]0|"  # <-- ADD
        r"BFGF|CHGF|MISF|SHTF|PLSF|PISF|"                        # <-- ADD: weapons
        r"ARM[12]A|BON[12]D|CELLA|CELPA|PINSA|PINVA|PMAP[A-D]|PVISA|"  # <-- ADD: items
        r"SOULA|BKEY|RKEY|YKEY|BSKU|RSKU|YSKU|"                  # <-- ADD: keys
        r"LITE[0-9]|LITEBLU|LITERED|EXITSIGN|"                   # <-- ADD: lights
        r"SW[0-9]|W108|W65|TSCRN|PUFF|WARN|FLAMP|CEYE)",        # <-- ADD: misc
    re.I,
)
```

Also use `NUKAGE` not `NUKE` in the `LAVA|…|HLAVA` alternation (`NUKE` is not a prefix of `NUKAGE`).

This makes the scrub self-maintaining — future `gen_world_emissives.py` runs will clean these automatically.

**Done:** applied and run against live global JSON.

**Also:** Immediately run the scrub on the current global JSON to fix the live contamination. After scrubbing, verify:

```bash
# Should return ZERO results for high-mult stock world entries
grep -c '"emissiveMult"' sourcecode/gzdoom-rt/buuild/RelWithDebInfo/rt/data/textures.json
```

Only SKUL* (Lost Soul, 0.12 — intentional), world allowlist entries (0.0004–0.001 — intentional), and monster eye entries should remain.

**Also:** Resolve the FIRELAVA and FIRELAV3 duplicates. Both appear twice in the array. After the broader scrub, both lines should be reduced to bare `{ "textureName":"FIRELAVA"   }` with no emis fields. But verify there are no remaining duplicates afterward.

### Step 2: Force-clean rebuild RTGL

The build system uses CMake + `GenerateShadersCache.txt`. Invalidation on `.inl` changes may be unreliable.

**Actions:**

1. Delete the indirect shader SPVs:
   ```bash
   rm sourcecode/gzdoom-rt/buuild/RelWithDebInfo/rt/shaders/RtRaygenIndirectInit.rgen.spv
   rm sourcecode/gzdoom-rt/buuild/RelWithDebInfo/rt/shaders/RtRaygenIndirectFinal.comp.spv
   ```

2. Delete the RTGL shader cache:
   ```bash
   rm deps/RTGL/Source/Shaders/Build/GenerateShadersCache.txt
   ```

3. Rebuild RTGL:
   ```bash
   cmd /c tools/build-rtgl.cmd
   ```

4. Verify the rebuild actually happened:
   ```bash
   # SPVs should have new mtime (not Aug 2 20:52)
   ls -la sourcecode/gzdoom-rt/buuild/RelWithDebInfo/rt/shaders/RtRaygenIndirect*.spv
   # DLL should have new mtime
   ls -la sourcecode/gzdoom-rt/buuild/RelWithDebInfo/rt/bin/RTGL1.dll
   ```

### Step 3: Add shader safety clamp (optional but recommended)

**File:** `deps/RTGL/Source/Shaders/HitInfo.inl`, lines 561-563

**Current:**
```glsl
    #if defined( HITINFO_INL_INDIR )
        emission *= tr.emissiveMult;
    #endif
```

**Change to:**
```glsl
    #if defined( HITINFO_INL_INDIR )
        emission *= tr.emissiveMult;
        emission = min(emission, vec3(0.05));  // hard ceiling: no single mat can flood GI
    #endif
```

This is a belt-and-suspenders safety net. Even if meta JSON goes wrong, no single texture emitter can push more than 0.05× into the indirect buffer. At mapboost 200, ceiling GI ≈ 10 units — should be invisible on dark stone walls.

If you apply this change, redo step 2 (force rebuild).

### Step 4: Instrumented test — confirm the shader is live

This is the definitive experiment from `gallery-emis-wall-wash-diagnostics.md` section 8.2.

**Change `HitInfo.inl` INDIR branch to:**
```glsl
    #if defined( HITINFO_INL_INDIR )
        emission = vec3(0.0);  // kill all surface-emission GI; primary _e still glows
    #endif
```

1. Force-rebuild (step 2)
2. Launch gallery: `tools/launch-texture-gallery-rt.cmd`
3. Walk to the STONE2 shell wall pose, look for blotches

**Expected result:** Walls are clean (no blotches), CRTs/monitors still glow when stared at directly (primary path uses raw `_e`, not INDIR).
- If walls ARE clean → confirms the INDIR emission path is the sole source of the wash; proceed to step 5.
- If walls STILL blotchy → there's a non-HitInfo emission path. Stop and investigate `emissionMapBoost` application in `RtRaygenIndirect.inl` and any other indirect reservoir writes.

### Step 5: Decision — permanent fix

After step 4 confirms the source:

**Option A (preferred): Keep INDIR `_e` with low mults + safety clamp.**
- Revert the `emission = vec3(0.0)` experiment
- Keep the safety clamp from step 3
- Verify walls are clean with the scrubbed global JSON + low world mults
- If still visible wash at mults ~0.0005: the `_e` pixel values themselves are too bright. Check pixel values in `rt/mat/SMONAA_e.png` etc. and reduce the brightmap-to-emissive amplification in `gen_world_emissives.py` `make_e_from_brightmap()`.

**Option B (fallback): Zero INDIR `_e` permanently.**
- Keep `emission = vec3(0.0)` on the INDIR `_e` path
- Primary/reflections still use raw `_e` (CRT glow when looked at)
- Drive world GI from `lightIntensity` + attached lights only (lava at ~140, monitors at 0)
- This matches "emis-off walls clean + CRT still glows" — the nuclear option from diagnostics §7.6

---

## Files to modify (summary)

| File | Change | When |
|---|---|---|
| `tools/gen_world_emissives.py:452-455` | Broaden `stock` regex in `scrub_stock_world_emis` | Step 1 |
| `sourcecode/.../rt/data/textures.json` | Run scrub; verify no high-mult contaminants remain | Step 1 |
| `sourcecode/.../rt/shaders/RtRaygenIndirect*.spv` | Delete for force rebuild | Step 2 |
| `deps/RTGL/Source/Shaders/Build/GenerateShadersCache.txt` | Delete for force rebuild | Step 2 |
| `deps/RTGL/Source/Shaders/HitInfo.inl:561-563` | Add `min(emission, vec3(0.05))` or `vec3(0.0)` | Step 3 / 4 |

## Verification

After completing the scrub + rebuild:
1. Launch gallery: `tools/launch-texture-gallery-rt.cmd`
2. Walk to the STONE2 shell wall area, look for blotchy circular light patches
3. Console A/B: `rt_emis_mapboost 0` should NOT meaningfully change wall appearance (no more 200× high-mult flooding)
4. Reference screenshot: `screen/wallturned.png` — walls should be clean dark stone
5. Auto QA (optional): `tools\test_gallery_emis_qa.cmd` (orbit-inward + center yaw at boost 200)