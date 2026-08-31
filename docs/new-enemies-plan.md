# The Unseen Evil monsters in Retribution

## Context

Doom 64: Unseen Evil ships four monsters drawn in the Doom 64 style that Retribution
has no art for at all — Chaingunner, Revenant, Arch-Vile, Spider Mastermind — plus a
redrawn Shotgun Guy. Retribution *declares* those four classes, but only as scale
tweaks on the stock Doom 2 monsters:

```
ACTOR 64ChaingunGuy : ChaingunGuy REPLACES ChaingunGuy { Radius 24 Height 96 Scale 1.3 ... }
ACTOR 64Revenant  : Revenant  REPLACES Revenant  { Scale 1.2 }
ACTOR 64Archvile  : Archvile  REPLACES Archvile  { Scale 1.2 }
ACTOR 64SpiderMastermind : SpiderMastermind REPLACES SpiderMastermind { Scale 1.2 }
```

They exist so a Doom 2 wad still loads; they use doom2.wad's sprites and are never
placed in any Doom 64 map. This add-on brings the real D64-style versions in and puts
them into the campaign automatically, gated by progression, with no map file edited.

**Build it:** `tools\.venv-ai\Scripts\python.exe tools/pack_ue_monsters.py` → `Doom64-Retribution/d64r-ue-monsters.pk3`.
The pk3 is **gitignored** — it carries DrPyspy's sprites and sounds and Unseen Evil
ships no licence statement, so only the generator and the authored lumps are committed.
See `CREDITS.md`; ask before redistributing.

## What it does

| | |
| --- | --- |
| `tools/pack_ue_monsters.py` | extracts sprites + sounds from the UE pk3, packs the authored lumps |
| `tools/d64r-ue-monsters/` | the authored lumps: actors, placement handler, sounds, menu |
| `tools/build_uemon_lab.py` + `tools/uemon-lab.cmd` | MAP88/89, each new monster beside the one it replaces |

## Assets — copy bytes, match by lump name

453 sprite frames plus 12 for the Arch-Vile's flame, all copied byte-for-byte from the
UE pk3. Three traps, each silent, each hit during development:

1. **Never re-encode a sprite.** Sprite PNGs carry a `grAb` chunk holding the Doom draw
   offset and Pillow drops ancillary chunks; a sprite that loses it renders sunk into
   the floor. The packer is a zip-to-zip copy with no image library, and `verify()`
   asserts every frame is still byte-identical.
2. **Match by lump name, not extension.** 30 of the Shotgun Guy's 78 frames are stored
   with no `.png` suffix. A `*.png` glob drops the whole firing and death sequence.
3. **Match recursively.** UE files one sprite set across folders — the Shotgun Guy's
   walk cycle is under `shotgunner/walking/`, `TRCR` is under `proj/revenant/`, and
   `AVFR` is not under `proj/` at all but `sprites/fx/archfire/`. A non-recursive match
   shipped 387 frames instead of 465 and left the Arch-Vile with no flame.

`CPOS`/`SKEL`/`VILE`/`SPID`/`AVFR` are free in Retribution — zero lumps, zero RT
material files — so they keep their names. **`SPOS` and `TRCR` are not**: they carry 98
and 34 baked `_orm`/`_n` files keyed on the bare name, so reusing them would hand
Retribution's materials to UE's pixels *and* repaint Retribution's own Shotgun Guy and
Mother Demon ball. They ship as `SPO2` and `TRC2`.

A build-time validator cross-checks every frame letter named by a state table against
the lumps actually packed, and a second guard asserts that every file in the authored
directory is in the packer's list — a lump was once written and then silently not
packed, producing a pk3 that loaded perfectly and did nothing.

## Actors

Re-authored in Retribution's idiom rather than vendored: UE's monsters descend from a
`D64UE_MonsterBase` framework (cvar handler, tag system, obituary system, projectile
mixin) that does not belong here, and its `A_D64_Chase` is `A_Chase` plus a Doom 64
speed multiplier Retribution's monsters already have baked in. Each class inherits the
stock Doom monster — which is what Retribution's own `64*` actors do — and overrides
size, sounds and states. No `replaces` clause: the handler does the placing.

**Sizes are UE's box divided by 0.732**, because UE draws D64 sprites at `YScale 0.732`
in a Doom-sized world and Retribution draws them 1:1. That reproduces Retribution's own
numbers exactly (its zombie is 24/80; UE's is 20/56 → 27/76 → 24/80). Sizing off the
sprite's *pixel height* instead reads plausibly and is wrong — it put the Revenant and
Arch-Vile at 120, taller than any non-boss in the game, and they refused most spots.

| class | radius / height | ednum |
| --- | --- | --- |
| `D64R_FormerSergeant` | 24 / 80 | 30001 |
| `D64R_ChaingunGuy` | 24 / 80 | 30002 |
| `D64R_Revenant` (+ `D64R_RevenantMissile`) | 24 / 80 | 30003 |
| `D64R_Archvile` (+ `D64R_ArchvileFire`) | 24 / 80 | 30004 |
| `D64R_SpiderMastermind` (+ `D64R_SpiderLaser`, `D64R_SpiderBeamPuff`) | **64** / 136 | 30005 |

The Mastermind's radius is measured, not derived. At Doom's and UE's 128 it was offered
all 9 free Arachnotron spots on MAP22 and `TestMobjLocation` refused every one: Doom 64's
arenas are built for Retribution's roster, whose widest footprint is the Mother Demon at
64. Its `+BOSSDEATH`, `+E3M8BOSS` and `+E4M8BOSS` are cleared — it is dropped into
arbitrary maps and must not end one.

Editor numbers live in MAPINFO's `DoomEdNums`, not as a `DoomEdNum` property: that was
DECORATE's syntax and ZScript rejects it.

## Placement — `WorldLoaded`, not `CheckReplacement`

`CheckReplacement` is the obvious hook and the wrong one. It is handed the class and
nothing else, so it cannot see the map thing's TID or ACS special, cannot know where the
thing stands, and cannot test whether the replacement would fit. All four matter.

At `WorldLoaded` the actor list is complete and TID/special/args/position are all set.
Per map load the handler gathers candidates, sorts them by position (ThinkerIterator
order is not contractual), shuffles with an LCG seeded from the map name and levelnum —
never `random()`, so a map lays out identically on every load and every client — and
swaps the selection.

Three things that are load-bearing:

- **Match donors by inheritance** (`mo.GetClass() is cls`), never by exact class. Our
  own `d64r-blood-persist.pk3` declares `RTBloodNightmareImp : 64NightmareImp replaces
  64NightmareImp` (and the same for the Cacodemon, Pain Elemental, Arachnotron and
  Spider Mastermind), so the class a map spawns is not the one you would name. An exact
  test found **zero** nightmare imps on a map with 17, while looking correct.
- **Unsolid the original before fit-testing.** It is still standing on the spot, so a
  naive `TestMobjLocation()` collides with the very monster being replaced and refuses
  every swap.
- **`ClearCounters()` before `Destroy()`.** A plain `Destroy()` does not decrement
  `total_monsters`; `Spawn` already incremented it. Without this, 100% kills becomes
  unreachable.

Anything with a TID or an ACS special is skipped — it is wired into the map's scripts.

## Progression

| unlocks | from | donor | share |
| --- | --- | --- | --- |
| Former Sergeant | MAP01 | ShotgunGuy | 35% |
| Chaingunner | MAP05 | ShotgunGuy | 12%, ramping to 22% by MAP20 |
| Revenant | MAP10 | NightmareImp, then HellKnight | 10% / 8% |
| Arch-Vile | listed maps | Baron of Hell, Hell Knight fallback | 1 per map |
| Spider Mastermind | listed maps | Arachnotron, then Cyberdemon, then Mancubus | 1, fit-tested |

The Sergeant and Chaingunner draw on the same pool, so the shares apply in sequence —
Chaingunners first, Sergeants from the remainder — or a late map turns over more than
half its Shotgun Guys between them.

**Arch-Vile maps** `MAP15, MAP20, MAP23, MAP30` (+ `ABS05, OUT05, RDM05, REC05, RTR05,
RTR10`). Roughly one every five maps, but not the literal 15/20/25/30: MAP25's entire
roster is 8 Nightmare Imps and a Cyberdemon, with no Baron or Hell Knight to take, and
MAP24/26/27 are the same, so it slides back to MAP23 (6 Barons) to keep the spacing
even. MAP30 has no Baron and is why the Hell Knight fallback exists.

**Mastermind maps** `MAP22, OUT10`. Not Cyberdemon-first: **every Cyberdemon in the game
is wired to a TID or special except one on MAP33** — they are all scripted boss fights —
so a Cyberdemon-first order never fires. Only these maps have unwired Arachnotrons at
all: MAP13/14/15/21/22/23/33, ABS02/04/05, OUT07/10, RDM01/07/08.

Settings are `server` cvars (`d64_ue_*`), read at `WorldLoaded`, so a change applies on
the next map. They **archive**, which also means changing a default in CVARINFO does not
reach an install that already wrote the old value to its ini. Do not pin them in
`tools/d64rt-pins.cfg` or the pin overrides the menu.

## Cast light — textures.json, the way the rest of the game does it

`emissiveMult` alone casts nothing; `lightIntensity` + `lightColorHEX` is what emits,
and it works on sprites, which is all of these. **Retribution already lights every
emitter this way** — 473 rows across 71 sprite families — so almost none of this needed
authoring:

| sprite | intensity | colour | |
| --- | --- | --- | --- |
| `CPOSF*` | 520 | `ff8c52` | Chaingunner muzzle — **already there**, we use CPOS directly |
| `LPUF*` | 300 | `ff1408` | the Unmaker beam — **already there**, our beam puffs use LPUF |
| `SPOSF*` | 720 | `ff8c52` | Shotgun Guy muzzle → cloned to `SPO2F*` |
| `TRCR*` | 1200 | `ff8a38` | tracer → cloned to `TRC2*` |
| `SKUL*` | 450 | `ff9028` | the Lost Soul's flame → borrowed for `AVFR*` |

So the only work is the two renames. `SPOS` → `SPO2` and `TRCR` → `TRC2` lost their rows
when they were renamed out of Retribution's namespace, and `AVFR` is new. Everything
else the game already solved. `patch_lights()` in `tools/pack_ue_monsters.py` clones the
values straight out of `textures.json` rather than restating them, so there is nothing
to drift; it reuses `patch_global()` because that carries the write-BOTH-TREES rule (the
build copy is xcopied over from `Retribution-RT-Materials` on every build, so writing
one is erased silently). That import pulls in PIL, so **this step needs the project
venv**: `tools\.venv-ai\Scripts\python.exe tools/pack_ue_monsters.py`.

An earlier version authored a GLDEFS lump with hand-picked pointlights for all five
effects. That was reinventing values the game already had, and worse, its muzzle-flash
binding would have **doubled** the Chaingunner's flash on top of the existing `CPOSF`
rows. GLDEFS is the right tool when a light must be scoped to a class rather than a
texture name — `make_unseenevil_pickup_lights.py` needs it for exactly that reason — but
here every sprite name involved is either ours alone or already carries the right row.

**The Mastermind's beam is Retribution's Unmaker mechanism, not a hitscan.**
`UnmakerLaser` is a speed-200 `FastProjectile` that every tic lays a dense tail of puffs
behind itself at fractional-velocity offsets — `(k*vel)/-35.0`, k stepping by 0.5, i.e. a
puff every ~2.9 units. That density is what makes it read as a continuous beam; an
earlier version drawing puffs 48 units apart along a `LineTrace` read as a dotted line of
separate points. `D64R_SpiderLaser` copies the spacing with a shorter tail (k ≤ 24)
because the Mastermind fires three at once where the Unmaker fires one, and keeps UE's
`random(1,5)*3` damage via `DamageFunction` (Doom's plain `Damage n` is `n*random(1,8)`,
a different distribution).

`D64R_SpiderBeamPuff` restates `UnmakerLaserTrail` rather than subclassing it: that one
is DECORATE, and GZDoom compiles all ZScript before parsing any DECORATE. It keeps the
`LPUF` sprite, which is what gets it the beam light for free.

## The lab

`python tools/build_uemon_lab.py`, then `tools\uemon-lab.cmd [lit|dark|fight]`.

MAP88 (lit 160) reads silhouettes, proportions and walk cycles. MAP89 (dark 48) is the
one for the emissive work — a bright room hides the tracers, the flame and the beam.
`fight` turns `notarget` off. Note `notarget` is a **toggle ccmd**: `d64rt-pins.cfg`
already runs it once, so `+notarget 1` does not mean "on", it means "off again".

The handler is disabled in the lab (`d64_ue_enable 0`) so the reference monsters stay
what the map placed; the new ones are placed by editor number. `d64_ue_debug 2` prints
the map's full monster roster, which is the only way to see what classes are really in
play.

## Verified

Console census (`d64_ue_debug 1`), measured:

| map | result |
| --- | --- |
| MAP15 | revenant 1, arch-vile 1 · refused 0 · monsters 60 → 60 |
| MAP20 | sergeant 6, chaingunner 4, revenant 2, arch-vile 1 · refused 0 · 109 → 109 |
| MAP22 | + mastermind 1 · refused 0 · 45 → 45 |
| MAP88 | all five pairs spawn, no sprite or script warnings |

Monster totals hold, so 100% kills stays reachable. Sprite offsets and frame coverage are
asserted at build time.

## Open

- **No `_n`/`_orm` for the 465 new frames**, so they shade flatter than Retribution's own
  monsters up close. `tools/bake_sprite_normals.py` and `tools/bake_sprite_materials.py`
  read sprites only from `D64RTR_v15.WAD`'s `SS_START..SS_END`, so they need a pk3 source
  before they can be pointed at these.
- The cast light is verified structurally — 34 rows in both `textures.json` trees,
  carrying Retribution's own values — but **not yet visually confirmed in the dark lab**.
