# Flame lighting — torches, fires and the candle (`rt_flame_light_*`)

Every open flame in Doom 64 Retribution — 89 sprites across 18 families — is lit by an
**engine light**, not by RTGL1's sprite-attached light. This file is the whole story:
what changed, why texture meta could not do it, and the invariants that will break it.

Written 2026-08-10. Companion to `docs/sprite-illumination.md` (Case 7 there is the
summary; this is the detail). Sibling reading: `docs/rt-lighting-practices.md` for the
general RT lighting rules, `docs/sequence-light-chains.md` for map-side light animation.

---

## TL;DR for an agent picking this up

- Flames are lit by `RT_UploadFlameLights()` in `rt_main.cpp`, table `RT_FLAME_KINDS`,
  master cvar `rt_flame_light_on` (default **on**).
- The matching sprites carry **`lightIntensity: 0`** in `textures.json` on purpose.
  `rt_flame_light_on 0` therefore means flames cast **nothing**. It is not a fallback to
  the old behaviour, and it is not the knob for "too flickery" — that is
  `rt_flame_light_flicker 0`, which keeps the corrected light *position*.
- Three places encode the same decision and must be changed together. See
  [The three-way invariant](#the-three-way-invariant).
- `sourcecode/` is **gitignored**. The engine change is not in git history and never will
  be; `git log` will show you the data and tool halves only.

---

## Inventory — what is covered

| Family | Sprites | Actor class | Frames |
| --- | --- | --- | --- |
| `TLBL` `TLGR` `TLRD` `TLYL` | 20 | `64TorchLong{Blue,Green,Red,Yellow}` | A–E |
| `TSBL` `TSGR` `TSRD` `TSYL` | 20 | `64TorchShort{…}` | A–E |
| `A030` `A031` `A032` `GTCH` | 20 | `64WallTorch{Yellow,Blue,Red,Green}` | A–E |
| `BFLM` `GFLM` `RFLM` `YFLM` | 20 | `64SingleFire{Blue,Green,Red,Yellow}` | A–E |
| `FIRE` | 5 | `64BigFire`, `64MotherFire`, `64MotherFireTrail` | A–E |
| `CAND` | 4 | `64Candle` | A–D |

`FIRE` carries **8** `textures.json` entries, not 5: `FIREA0`–`FIREH0`. Only `A0`–`E0`
exist as lumps in the WAD; `F0`–`H0` are phantom rows the generator emitted. Harmless, but
the 84→92 entry count across a strip run is not a miscount.

**Not covered, deliberately:** the barrels `BAR1`/`BEXP`, `TFOG`/`IFOG` teleport fog, and
every projectile. Those are sprite-attached lights and Case 5 of `sprite-illumination.md`
owns their colours.

### `FIRE` was wrongly excluded — the 2026-08-10 correction

The original pass left `FIRE` out with the note *"not a GLDEFS flame prop — keeps its
attached light."* **That premise is false.** The WAD's GLDEFS has:

```
flickerlight BIGFIRE { color 1.0 0.9 0.0  size 32  secondarySize 38  chance 0.5  offset 0 32 0 }
object 64BigFire         { frame FIRE { light BIGFIRE } }
object 64MotherFire      { frame FIRE { light BIGFIRE } }
object 64MotherFireTrail { frame FIRE { light BIGFIRE } }
```

It is a GLDEFS flame prop, with an offset like every other one, and it was the single
biggest hole in this work — by placement count it is the fire in this game. Census of
all 71 UDMF maps in `D64RTR_v15.WAD`, by thing type:

| doomednum | actor | sprite | placements | maps |
| --- | --- | --- | --- | --- |
| 2051 | `64BigFire` | `FIRE` | **117** | 11, 12, 13, 18 (64 of them), 20, 21, 22, 24, 34 |
| 1033 / 1034 / 1035 / 899 | `64SingleFire{Blue,Red,Yellow,Green}` | `BFLM` `RFLM` `YFLM` `GFLM` | **1 each** | **MAP34 only** |

**The second row is the thing to know before you go looking for a `?FLM` fire.** All four
sit clustered around `(600…664, −552…−616)` in MAP34 and nowhere else in the game. A
report that "the loose fires do not light" is far more likely to mean "I was not standing
in MAP34" than a defect — check the torches first, they share the identical code path.

---

## Why this could not stay in texture meta

Two independent defects, and neither has an expression in RTGL1's texture metadata.

### 1. Position

RTGL1 anchors a sprite light to the **centre of the billboard quad** (`VulkanDevice.cpp`,
`center = average of the 4 quad verts`). A `TL*` standing torch is 27×100, so its light sat
at ~50 units — mid-pole. The mod's own GLDEFS asks for `offset 0 80 0`. The torch was
lighting the room from its own midriff, roughly 30 units below the flame you can see.

Texture meta has **no offset field**. This is the same wall the `BOS2` Hell Knight fists
hit, and it was logged as unfixable in Case 6 before this work.

### 2. Flicker

Texture meta is static per sprite frame. The only data-only way to vary a flame's light is
a per-frame intensity ramp across the `A`–`E` animation.

**That does not work, and the reason is worth remembering:** every one of these props is
spawned at map load, so their state counters are in lockstep. A per-frame ramp would make
every torch in the level pulse in perfect unison. That reads as an electrical fault, not
as fire — it is not merely a weaker version of the right answer, it is actively wrong.

So the lights moved into the engine, following the pattern `RT_UploadHandGlowLights()`
already established for the Baron-family fists.

---

## The table is the mod's own GLDEFS

`up` and the relative intensities are read out of the WAD's `GLDEFS` lump `flickerlight`
blocks. Nothing here is invented:

| GLDEFS block | sprites | `size` | `offset` | RT intensity |
| --- | --- | --- | --- | --- |
| `TORCHLONG*` | `TLBL` `TLGR` `TLRD` `TLYL` | 40 | 80 | 900 |
| `TORCHSHORT*` | `TSBL` `TSGR` `TSRD` `TSYL` | 40 | 64 | 900 |
| `*TORCH` (wall) | `A030` `A031` `A032` `GTCH` | 28 | 24 | 700 |
| `*FIRE` (loose) | `BFLM` `GFLM` `RFLM` `YFLM` | 32 | 8 | 650 |
| `BIGFIRE` | `FIRE` | 32 | 32 | 650 |
| `CANDLE` | `CAND` | 16 | 16 | 260 |

`BIGFIRE` is the one row whose offset lands **above** the sprite's own midpoint: `FIREA0`
is 32×50, so RTGL1's billboard-centre anchor put the old attached light at ~25u against
GLDEFS' 32. That error alone was small — the reason the row matters is that the light also
could not flicker, and 117 static bonfires lighting a room like fluorescent tubes is
exactly the failure this whole file exists to describe.

To re-read them yourself, the GLDEFS lump is inside `D64RTR_v15.WAD` (standard WAD
directory at offset 4, `<II8s` entries) — there is no loose copy on disk.

### Colours

Colours do **not** come from GLDEFS, which asks for fully-primary hues (`0.0 1.0 0.0`
green, `1.0 0.1 0.1` red). Under path tracing those bleach toward white at these
intensities — the failure documented in Case 5. The table uses the shared flame palette
instead, the same four hexes the `_e.png` mask generators tint with:

```
FLAME_BLUE   4488ff      FLAME_RED     ff4020
FLAME_GREEN  44ff66      FLAME_YELLOW  ffcc33
```

`FIRE` takes a fifth, `RT_FLAME_BIGFIRE` `ff8020`, which lives only in the engine and in
`gen_fx_emissives.py`'s forced hex for the `FIRE` rule. GLDEFS asks for `1.0 0.9 0.0`;
this is orange instead because `ff8020` is what the `_e` mask is already tinted with, and
the mask is what the player sees. Same rule as everywhere else here: cast light follows
the mask.

Keeping cast light and on-screen glow on one palette is the point. They drifted apart once
already (the `LPUF` regression) and a literal in the engine would let it happen again.
These constants exist in three files — `RT_FLAME_KINDS` in `rt_main.cpp`, and
`FLAME_*` in both `gen_fx_emissives.py` and `gen_torch_emissives.py`.

### The candle is a deliberate exception

`CAND` takes `RT_FLAME_CANDLE` `ff4a14` — a warm **red** — not `FLAME_YELLOW`, and 260
intensity against a wall torch's 700.

Its previous attached light was `ffaa55` @ 280: straight amber, the same hue family as a
pitch torch four times its size. A candle is a single wick and should read as a dim ember
at the edge of a dark room.

**Note the art disagrees, and that is fine.** `CAND?0` is 8×31 with a brightest texel of
`(232,168,0)` — amber. On a sprite that small the amber is the wax body catching its own
light as much as the flame itself, so the measured average is not the authority here that
it was for the projectiles in Case 5. This colour came from the user's judgement of how a
candle should read, over the pixel data. If you re-audit sprite light colours with a
hue-delta sweep, **`CAND` will flag as wrong. It is not.**

---

## The flicker

Per actor, three incommensurate sines summed at weights `0.55 / 0.30 / 0.15` at
frequencies `1× / 2.37× / 4.11×`, normalised so `rt_flame_light_flicker` is a true
fraction of base intensity. The sum has no short period, so a torch the player stands next
to for a minute never visibly loops.

**Phase comes from the actor's own pointer** (`>> 4`, low 16 bits, mapped to 0..2π). That
is the part that solves the lockstep problem described above — without it, every torch
would still flicker in unison, just smoothly.

The same phase drives a second set of sines at `0.83× / 1.19× / 1.61×` that **moves** the
light up to `rt_flame_light_wobble` map units on each axis — half that vertically, since a
flame licks upward far more than it slides. Pulsing alone reads as an electrical fault;
pulsing *plus* wander reads as combustion. Both halves matter.

Timebase is `primaryLevel->maptime`, not wall clock, so a paused game or an open console
freezes the fire with everything else.

### Why not GLDEFS' actual flicker

GLDEFS `flickerlight` is a hard two-state switch — `size` ↔ `secondarySize`, re-rolled
each tic at `chance 0.5`. Under a path tracer every flicker also swings the indirect
bounce, so a binary switch strobes. The same depth is delivered smoothly instead. 35 Hz
stepping from `maptime` is not a compromise: it is already finer than what GLDEFS asks
for.

### Tuning history

Shipped first at `flicker 0.28` / `speed 0.42`, which the user reported as too strong and
too frequent. Halved to `0.15` / `0.25`.

The misjudgement is worth recording: **a torch is not a prop with a light on it, it is the
ambient light of the room it stands in.** Depth that looks right on an isolated campfire
swings the entire room's indirect bounce with it, which roughly doubles the perceived
effect. If it still reads busy, drop `speed` before `flicker` — the 4.11× harmonic is what
sets the perceived rate.

---

## The three-way invariant

The same decision is encoded in three places. **Change one, change all three**, or a flame
gets lit twice from two different heights — worse than the bug this replaced.

| Place | What it holds |
| --- | --- |
| `RT_FLAME_KINDS` in `rt_main.cpp` | sprite → colour, up-offset, intensity. **The light.** |
| `PREFIX_RULES` in `tools/gen_fx_emissives.py` | `A030`/`A031`/`A032`, `?FLM`, `FIRE`, `GTCH`, `CAND` — all at intensity `0` |
| `INTENSITY` in `tools/gen_torch_emissives.py` | the 40 `TL*`/`TS*` — set to `0` |

`tools/strip_flame_sprite_lights.py` applies the data half to every `textures.json` and is
idempotent. Its `FIRE` rule is the one that is **not** a blanket four-character prefix: it
matches `FIRE[A-Z]0` exactly, because Doom II's world fire/lava *wall* textures
(`FIRELAVA`, `FIRELAV2/3`, `FIREWALL`, `FIREWALA/B`, `FIREMAG1-3`, `FIREBLU1/2`) share the
same four characters and are not flames. `gen_fx_emissives.py` carries a `WORLD_TEX_RE`
guard for exactly this; the guard postdates some of the scene files, which is why
`scenes/d64rtr_v15_map01/textures.json` still has those eleven wall textures sitting on
`lightIntensity: 700` + `noShadow`. Inert as a light (meta lights are sprite-only) but
`noShadow` on a wall is not, and it is a separate thing to clean up. It exists so the state can be re-asserted after someone re-runs a generator;
it is **not** the source of truth — the generators are.

`emissiveMult` is untouched everywhere. The flame must still glow on screen; only the cast
light moved. `lightIntensity: 0` follows the muzzle-flash convention already in these
files — a 0 casts nothing.

---

## Cvars

All live at runtime. Only the table itself needs a rebuild.

| Cvar | Default | Notes |
| --- | --- | --- |
| `rt_flame_light_on` | `true` | master switch. Off = flames cast **nothing** |
| `rt_flame_light_scale` | `1.0` | multiplies the whole table; retune the family here, not one row |
| `rt_flame_light_radius` | `0.09` | metres. Wider softens the shadows a torch throws down a corridor |
| `rt_flame_light_flicker` | `0.15` | depth, 0..1 of base intensity. `0` = steady, position still correct |
| `rt_flame_light_speed` | `0.25` | radians/tic of the base sine (~1.4 Hz) |
| `rt_flame_light_wobble` | `2.0` | map units of drift per axis. Past ~4 the light detaches from its sprite |
| `rt_flame_light_maxdist` | `3072` | wider than the fist cull: torches are room lighting, and popping one in is visible |
| `rt_flame_light_max` | `64` | nearest-first budget |
| `rt_flame_light_debug` | `false` | **`RT_CVAR_NOARCH`** — cyan markers at 350 intensity + a per-60-frame count |

`tools/ab-flame.cmd <on|debug|steady|calm|off> [1-34]` sets all nine explicitly per arm.
`ab-flame.cmd debug 18` is the one to run first — 64 bonfires and cyan markers, so it
answers both "is the system running" and "does the budget hold" at once.
`ab-flame.cmd debug 34` is the only way to see the four `?FLM` fires.

All nine are **pinned in `tools/launch-retribution-rt.cmd`**. Every `RT_CVAR` is
`CVAR_ARCHIVE`, so changing a compiled default alone does nothing once the ini holds a
value — this is a mistake the project has already paid for more than once.

---

## Files

Engine (**gitignored — not in git history**):

```
sourcecode/gzdoom-rt/src/common/rendering/rt/rt_main.cpp
  cvar block            rt_flame_light_*
  FlameLightId_Base     1ull << 43
  RtFlameKind / RT_FLAME_KINDS / RT_FlameKindOf()
  RT_UploadFlameLights()      called from RT_BeginFrame, after RT_UploadHandGlowLights()
```

Tracked:

```
tools/strip_flame_sprite_lights.py     NEW — zeroes the attached lights, idempotent
tools/gen_fx_emissives.py              PREFIX_RULES intensities -> 0 for the flame rows
tools/gen_torch_emissives.py           INTENSITY -> 0
tools/launch-retribution-rt.cmd        pins + a rationale comment block
docs/sprite-illumination.md            Case 7, STATUS rows, Tuning entry
```

Data (5 `textures.json` targets, 84 entries each pass):

```
sourcecode/gzdoom-rt/build/RelWithDebInfo/rt/data/textures.json            <- the live file
sourcecode/gzdoom-rt/build/RelWithDebInfo/rt/data/scenes/d64rtr_v15_map01/textures.json
sourcecode/gzdoom-rt/build/WashScratch/rt/data/scenes/d64rtr_v15_map01/textures.json
Doom64-Retribution/Retribution-RT-Materials/rt/data/textures_fx.json       <- overlay, inert
Doom64-Retribution/Retribution-RT-Materials/rt/data/scenes/d64rtr_v15_map01/textures.json
```

Committed as `f190969 flames: drop the sprite-attached light, the engine lights them now`.

---

## What was verified

- Builds clean (`EXITCODE=0`); all nine cvar strings confirmed present in `gzdoom.exe`.
- 84 entries zeroed across all target files; every file re-parses as valid JSON.
- `gen_torch_emissives.py` re-run produces **byte-identical** md5s against the
  hand-stripped files — proof the generator and the data agree.
- The four `FLAME_*` hexes agree across both generators and the engine table.

### 2026-08-10, the `FIRE` pass

- User confirms the torches (`TL*`/`TS*`/`A03x`/`GTCH`) **do** cast light in-game. That is
  the first in-engine confirmation this system has ever had, and it is what made moving
  `FIRE` onto the same path safe rather than a gamble against trap 1.
- Builds clean (`EXITCODE=0`); the new `rt_flame_light_on` help text is present in
  `gzdoom.exe`, so the rebuilt binary really does carry the new table row.
- 8 `FIRE?0` entries zeroed in each of five files (`WashScratch/rt/data/textures.json` had
  no `lightIntensity` key on them to begin with); all six re-parse as valid JSON; the
  eleven `FIRE*` **wall** textures were left untouched in every file — the regex guard
  holds.
- **`FIRE` itself is not verified in-engine.** Same standing instruction as below.

**The original pass was never verified in-engine.** There is no screenshot, no
`rt_flame_light: uploaded=N` log line. Verify with `rt_flame_light_debug 1` — cyan markers
should sit **on the flames**, not at pole height, and the count should match the torches in
the room.

---

## Known limitations / not done

- **No per-family flicker character.** A candle and a 100-unit pitch torch flicker with the
  same waveform at the same rate. A candle should arguably be slower and shallower. There
  is no per-kind flicker field in `RtFlameKind`; adding one is a small change.
- **Wobble is unconstrained.** The light can drift into a wall on a torch mounted flush
  against one. Nothing clips it. Not observed as a problem at `2.0`, but it is a real
  hazard if anyone raises it.
- **`GTCH` shares the wall-torch offset (24)** though its sprite is 16×43–47, slightly
  taller than the `A03x` sconces. GLDEFS gives them all `offset 0 24 0`, so this follows
  the mod; it has not been eyeballed.
- **The budget is global, not per-room.** 64 nearest lights. A map with a large torch-lined
  hall has not been checked against that cap.

## Traps

1. **`rt_flame_light_on 0` is not "the old behaviour".** The meta is zeroed. It is total
   darkness for every flame. Reach for `rt_flame_light_flicker 0` instead.
2. **Re-running a `gen_*` tool cannot re-attach the lights** — both were set to `0` — but
   *editing* one back without deleting the matching `RT_FLAME_KINDS` row double-lights the
   flame from two heights.
3. **`CAND` will fail an art-vs-light hue audit.** By design. See the candle section.
4. **The engine half is gitignored.** If `RT_FLAME_KINDS` disappears from a fresh checkout
   of `sourcecode/`, it was never in git — it is not a revert, and the data half will be
   sitting there at intensity 0 with nothing lighting it.
5. **Colours live in three files.** Change the palette in one and the cast light drifts
   away from the on-screen glow.
6. **`FIRE` is three actors, not one.** The row lights `64BigFire`, and also the Mother
   Demon's `64MotherFire` fireball and its `64MotherFireTrail` — GLDEFS binds all three to
   `BIGFIRE`. So the projectile now flickers and wobbles like a prop fire. At `wobble 2.0`
   that is 2 map units on a thing moving at speed 15; not visible, but it is the first
   time this table has touched something that moves, and raising `rt_flame_light_wobble`
   affects it too.
7. **Do not give the strip tool or a generator a bare `FIRE` prefix.** It swallows eleven
   world wall textures. See the note under the three-way invariant.
8. **Four of the sprites in the inventory exist once each, in MAP34.** Do not conclude the
   system is broken from `?FLM` alone. See the placement census.
