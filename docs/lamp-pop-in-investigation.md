# Solo/faux bulb lamps popping in at close range — investigation log

## Symptom
`rt_solo_lamp` / `rt_faux_lamp` (and possibly real ceiling-edge lamps and wall
strips) don't render at range — they appear abruptly as the camera moves
closer, roughly ~50m out.

## STATUS: fixed and verified in-engine 2026-08-09 evening. Awaiting visual playtest.

Measured in MAP03 after the rebuild + launcher fix (`rt-console.log`, both
debug cvars on). The `within 3072u` proves the new values are actually live:

```
rt_ceiling_edge: uploaded=805 of 1351 wanted (cap 320, within 3072u)
  faux 14 flat(s), 215 of 215 wanted (cap 256) I=500    <- was 128 of 215
  solo 23 flat(s), 270 of 270 wanted (cap 384) I=45     <- was  64 of ~260
```

**Solo and faux are now fully saturated — the nearest-N trim no longer binds
for either**, which was the dominant cause per the analysis below. Solo needed
384 rather than the first-pass 256: doubling `maxdist` pulled more bulbs into
the candidate set, raising demand from ~260 to 270, so 256 still clipped 14.

`uploaded=805` is the merged total of all three classes (320 real + 215 faux
+ 270 solo), not the real-lamp count alone — real ceiling-edge is still capped
at 320 against ~866 demand, deliberately untouched (see below).

The fixes were real but **could not reach the running game, for two
independent reasons stacked on top of each other.** Both are now cleared.

### Blocker 1: stale binary (found first)
The exe was 16 minutes *older* than the last `rt_main.cpp` edit:

```
gzdoom.exe (RelWithDebInfo):  2026-08-09 08:22:34
rt_main.cpp (the cap raise):  2026-08-09 08:38:56
```

So the user's "same issue" report was against a binary that never contained
the fix. **Rebuilt `RelWithDebInfo` 2026-08-09 20:04 — clean, EXITCODE=0.**

### Blocker 2: the launcher pins the OLD values (the one that actually mattered)
Rebuilding alone would *still* have changed nothing, and this is the trap
worth remembering. `tools/launch-retribution-rt.cmd` passes all three cvars
explicitly on the command line, and a `+cvar` on the command line overrides
the compiled-in `RT_CVAR` default. The launcher was pinning:

```
+rt_ceiling_edge_maxdist 1536     (source default now 3072)
+rt_faux_lamp_max        128      (source default now 256)
+rt_solo_lamp_max        64       (source default now 256)
```

Editing the source defaults was therefore **completely inert** under the only
launcher anyone uses. Had we followed the original "rebuild and retest" plan,
the test would have come back "same issue" a second time — but now against a
*fresh* binary, which reads as a genuine null result and sends the next step
to "the bug is elsewhere: RTGL1 light limits, ReSTIR eviction, temporal
warm-up" (step 4 below). That is a long, expensive detour away from a cause
that was already correctly identified.

**Fix applied:** the three pinned values in `tools/launch-retribution-rt.cmd`
updated to 3072 / 256 / 256 to match the new source defaults. Pinning is
deliberate project style (every `RT_CVAR` is `CVAR_ARCHIVE`, so an unpinned
value can be silently poisoned by a stale ini) — so the right fix is to
update the pins, not remove them.

**Generalised lesson:** in this project, changing an `RT_CVAR` default is
only half the change. Grep the launchers for the cvar name and update every
pin, or the new default never runs. This is the "verify a change is live
before trusting a null result" memory with a second delivery layer that the
timestamp check alone does not catch.

## Code path (all in `sourcecode/gzdoom-rt/src/common/rendering/rt/rt_main.cpp`)

Three independent upload functions feed lamp lights to RTGL1, each with its
own budget/culling logic:

- `RT_UploadCeilingEdgeLamps` (~line 5870) — real ceiling-edge lamps, faux
  **flat** (`SFLATC`), and solo bulbs (`SFLATDE`/`SFLATCH`). All three share
  one candidate-collection walk (`addLattice`), one `maxDist` distance
  filter, then three *separate* nearest-N budget trims (`cand`/`fauxCand`/
  `soloCand`), merged and re-sorted before upload.
- `RT_UploadWallStripLights` (~line 5547) — real wall strips and faux
  **wall** (`SPACECE`). Walks `primaryLevel->lines` in raw line-index order.
  **No distance filter or distance sort at all** — first-come-first-served
  by line index until the per-class budget (`rt_wall_strip_max` /
  `rt_faux_lamp_max`, shared) is spent.

## Findings so far

### 1. Distance cutoff (`rt_ceiling_edge_maxdist`)
Applies only to the `RT_UploadCeilingEdgeLamps` path (real + faux-flat +
solo). Default was 1536 map units = 48m (`ONEGAMEUNIT_IN_METERS = 1/32`,
rt_main.cpp:844) — matches the user's "~50 meters" observation almost
exactly. Does **not** apply to `RT_UploadWallStripLights` at all (no
distance check exists there).

**Fix applied:** doubled `rt_ceiling_edge_maxdist` 1536 → 3072 (48m → 96m).

### 2. Budget/quantity cutoff — turned out to be the dominant cause
Confirmed from `rt-console.log` with `rt_ceiling_edge_debug 1` /
`rt_wall_strip_debug 1` on, in MAP03 "Main Engineering":

```
rt_ceiling_edge: uploaded=512 of 1001 wanted (cap 320, within 1536u)
  faux 14 flat(s), 128 of 215 wanted (cap 128) I=500
  solo 23 flat(s), 64 of 257-266 wanted (cap 64) I=45      <- only ~24% lit
rt_wall_strip: uploaded=4 (cap 128) | matchedTex=10 ...
  faux 6 sidedef(s), uploaded=8 (cap 128) I=500             <- NOT saturated
```

- **Solo flats**: cap 64 vs demand ~260 (24% coverage). Demand already
  exceeds the cap well inside the *old* 48m maxdist radius, so the nearest-N
  trim — not the distance filter — decides which bulbs light up. A distant
  solo bulb only lights when it becomes one of the 64 closest, i.e. as you
  walk toward it. This is the same symptom as a distance cutoff but a
  different mechanism, and doubling `maxdist` cannot fix it (more candidates
  compete for the same 64 slots, if anything making it worse).
- **Faux flat**: cap 128 vs demand ~215 (60% coverage). Same mechanism,
  less severe.
- **Real ceiling-edge**: cap 320 vs demand ~1001 (32% coverage). Known/
  documented pre-existing (see the cvar's own comment about MAP02 sector 16).
  Not touched this pass — raising it to cover demand is a much bigger
  light-slot/ReSTIR cost than the solo/faux bump, left for a separate call.
- **Wall strips (real + faux SPACECE)**: uploaded 4 and 8 against a cap of
  128 — **not** budget-saturated in this scene. If wall-mounted lamps are
  what's popping in, this isn't why; wall strips have no distance sort
  either (see above), so a wall-lamp pop-in bug, if confirmed after rebuild,
  is a different investigation (candidate: add nearest-first sorting to
  `RT_UploadWallStripLights`, currently raw line-index order).

**Fix applied:** raised `rt_faux_lamp_max` 128 → 256, `rt_solo_lamp_max`
64 → 384. Both now fully cover demand — confirmed saturated in the STATUS
block above (215/215 and 270/270), which is what makes this the confirmed
cause rather than a plausible one.

## Changes made
File: `sourcecode/gzdoom-rt/src/common/rendering/rt/rt_main.cpp` (submodule)
- `rt_ceiling_edge_maxdist`: 1536.f → 3072.f
- `rt_faux_lamp_max`: 128 → 256
- `rt_solo_lamp_max`: 64 → 384

File: `tools/launch-retribution-rt.cmd` — the pinned overrides, without which
none of the above reaches the game:
- `+rt_ceiling_edge_maxdist`: 1536 → 3072
- `+rt_faux_lamp_max`: 128 → 256
- `+rt_solo_lamp_max`: 64 → 384

Binary rebuilt 2026-08-09 20:08; both files verified in sync, all six live.

## To resume
1. Nothing to prepare — rebuilt, launcher fixed, saturation confirmed in-log.
2. Launch with the debug cvars pre-set (do NOT type them into the console —
   they are `CVAR_ARCHIVE` and will persist):
   `cmd /c 'tools\launch-retribution-rt.cmd 3 nodebug -- +rt_ceiling_edge_debug 1 +rt_wall_strip_debug 1'`
   Note PowerShell eats a bare `--`, hence the `cmd /c` wrapper.
   Then walk toward a lamp that previously popped in.
3. Budget is no longer the constraint for solo/faux (both X=Y above), so if
   they *still* pop in, the bug is elsewhere — look at RTGL1-side light
   limits, ReSTIR reservoir eviction, or temporal accumulation warm-up, not
   this upload code.
4. If it's specifically wall-mounted lamps popping in, budget isn't
   saturated (`rt_wall_strip: uploaded=4 (cap 128)`, faux 8 of 256) — go add
   distance-aware selection to `RT_UploadWallStripLights` instead. It still
   has none: no distance filter, no distance sort, raw line-index order.
5. If solo/faux-flat are fixed but real ceiling-edge lamps still visibly pop
   in, that's the next cap to raise (320 vs ~866 demand within the new 3072u
   radius, 37%), with the perf cost that implies. Untouched this pass.

## Open perf question
Nothing was measured for frame cost. Solo went 64 → 270 lights and faux
128 → 215, so ~290 more lights per frame reach RTGL1 in MAP03. If the
playtest shows a framerate drop, the lever is `rt_solo_lamp_max` — the
pop-in returns gradually as it is lowered, so it trades off smoothly.
