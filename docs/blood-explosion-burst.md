# Blood on explosive kills — plan

Reuse the BLUD splat for rockets and barrels. Companion to
`docs/blood-persist.md`; the change lands in the same pk3.

## The asymmetry, and where it comes from

Shooting an enemy with the pistol or shotgun leaves BLUD splats, and since
`d64r-blood-persist.pk3` those splats stay on the floor. Blowing the same enemy
up with a rocket or a barrel leaves **nothing**. That is not a renderer setting
and not a Retribution authoring choice — it is stock GZDoom, confirmed in the
engine source:

- Blood actors are spawned **only by attack code**, never by damage code.
  `P_DamageMobj` (`src/playsim/p_interaction.cpp`) contains no blood at all.
- Hitscan reaches blood through the actor virtual `SpawnLineAttackBlood`
  (`wadsrc/static/zscript/actors/attacks.zs:742`), called from `P_LineAttack`
  at `src/playsim/p_map.cpp:4875`.
- `P_RadiusAttack` (`src/playsim/p_map.cpp:6117`, damage loop 6203–6290) calls
  `P_DamageMobj(..., DMG_EXPLOSION)` and then **only `P_TraceBleed`**. There is
  no `P_SpawnBlood` anywhere in that function. `P_TraceBleed`
  (`p_map.cpp:5098`) spawns no actor — it makes a wall **decal**, plus the RT
  fluid particles under `HAVE_RT`. Crushing is the same.
- A rocket's direct impact (`p_map.cpp:1337`) only splatters if the missile has
  `+BLOODSPLATTER`; `64Rocket` does not. But the rocket explodes on contact, so
  the victim takes the radius hit at distance 0 — **`DMG_EXPLOSION` alone covers
  both rockets and barrels.**

Goal: an explosion throws a splash of the *same* BLUD splats outward from the
victim, which arc down and settle on the floor exactly like the hitscan ones —
and therefore persist and get capped by the machinery that already exists.

## Where the change goes

**Entirely inside `d64r-blood-persist.pk3`. No engine rebuild.** Everything is
edited in the generator `tools/gen_blood_persist.py`, which holds all four
lumps as string constants and writes the pk3 with `--apply`.

`WorldThingDamaged` is the hook: it carries `DamageFlags` (`DMG_EXPLOSION =
2048`, `wadsrc/static/zscript/constants.zs:962`), `Damage`, `Inflictor` and
`DamageAngle`. It fires from both `p_interaction.cpp:1494` (the fatal path,
before `CallDie`) and `:1515`, so an enemy killed outright by the blast still
gets its burst.

### Why the splats are spawned directly and not only via `SpawnBlood()`

The look is *thrown outward, then falls*, which needs a per-splat `Vel` — and
`Actor.SpawnBlood()` returns nothing. Setting the velocity from
`WorldThingSpawned` instead does **not** work: that event fires from
`AActor::CallPostBeginPlay` (`p_mobj.cpp:4923`), which the thinker list runs on
a later pass (`dthinker.cpp:608`), not synchronously inside `Spawn()`. Any
"burst is active" latch would already be stale by the time the event arrived.

So the burst does both:

1. **one** `t.SpawnBlood(...)` call — the engine path, and the only thing that
   emits the RT fluid particles (`RT_SpawnBlood_Thing`, `p_mobj.cpp:6140`),
   which has no ZScript export and cannot be reproduced by hand;
2. **N** splats spawned directly so their `Vel` can be set:
   `Actor.Spawn(t.GetBloodType(0), pos, NO_REPLACE)` — `GetBloodType`
   (`actor.zs:559`) already applies the replacement chain
   `Blood → 64Blood → RTBloodPersist`, hence `NO_REPLACE`, matching what
   `P_SpawnBlood` does. Copy `t.BloodTranslation` onto each unless
   `bDontTranslate`.

Both kinds land in the existing `WorldThingSpawned`, so scale jitter, `bXFLIP`,
optional roll, the FIFO and `rt_gore_max` apply with **no change to that
method**. The `RTBloodPersist` DECORATE Spawn state still throws its 1–3
satellites, which trail slightly behind a moving parent — free extra scatter.

### `ZSCRIPT` — new `WorldThingDamaged` in `RTBloodPersistHandler`

Guards, in order (the first three mirror `SpawnLineAttackBlood`'s own test at
`attacks.zs:744`):

- `rt_gore_burst` off → return.
- `(e.DamageFlags & DMG_EXPLOSION) == 0` → return.
- `t.bNoBlood || t.bDormant || t.bInvulnerable` → return. In the whole
  Retribution DECORATE `+NOBLOOD` appears exactly once, on `64LostSoul`
  (line 3264) — that is the flag which keeps souls bloodless.
- `t.GetBloodType(0) == null` → return. This is what silently excludes barrels,
  decorations and anything else that does not bleed; no class list needed.
- `t.player != null` → return. Deterministic and netsafe, and keeps a splash
  out of the first-person camera.
- **Same-actor, same-tic dedupe** (`lastBurstThing` / `lastBurstTime` fields):
  a rocket delivers direct impact damage and radius damage in one tic, and a
  monster between two barrels gets two chain blasts. One burst per victim per
  tic.

Then `n = round(rt_gore_burst_count * clamp(e.Damage / 40.0, 0.5, 2.0))`, and
for each splat pick a random yaw, a radius in `[0, t.radius]`, a height in
`[0.25, 0.8] * t.height`, and set

```
b.Vel = (cos(ang) * sp, sin(ang) * sp, FRandom(lift * 0.4, lift));
```

with `sp = rt_gore_burst_speed * FRandom(0.5, 1.0)`. `64Blood` has
`Gravity 0.65` and gravity lives in `Actor::Tick`, not in the state machine, so
they arc and settle on their own — the same reason the persist splats already
fall correctly.

### `CVARINFO` — five new cvars, all `server noarchive`

| cvar | default | what it does |
|---|---|---|
| `rt_gore_burst` | `true` | master switch for the explosion splash |
| `rt_gore_burst_count` | `5` | splats at reference damage (40); scales 0.5×–2× with damage |
| `rt_gore_burst_speed` | `4.0` | outward horizontal speed, map units/tic |
| `rt_gore_burst_lift` | `3.0` | upward kick |
| `rt_gore_burst_debug` | `false` | `Console.Printf` one line per burst — the "is it actually live" instrument |

`noarchive` is not optional: an A/B arm that writes into the ini silently
poisons the next launch.

## Files to change

| File | Change |
|---|---|
| `tools/gen_blood_persist.py` | `CVARINFO` (L63) + `ZSCRIPT` (L152) constants; extend the module docstring with the explosion half |
| `Doom64-Retribution/d64r-blood-persist.pk3` | regenerated — `python tools/gen_blood_persist.py --apply` |
| `tools/d64rt-pins.cfg` | add the five cvars after the existing `rt_gore_*` block (L337–340) |
| `tools/ab-blood.cmd` | new arms + **every existing arm must pin every new cvar** |
| `docs/blood-persist.md` | new section; extend the cvar table |
| `AGENTS.md` | update the `tools/ab-blood.cmd` row with the new arms |

### `ab-blood.cmd` arms

New: `boom` (defaults + `rt_gore_burst_debug 1`), `noboom` (burst off, rest at
default — the flip-against baseline), `bigboom` (count 12, speed 7, lift 5).

The seven existing arms (`off`/`on`/`uncapped`/`tight`/`plain`/`wild`/`roll`,
lines 62–68) each set every `rt_gore_*` explicitly on purpose. That contract has
to hold: **all seven get the five new pins appended**, with `off` getting
`rt_gore_burst 0` (it reproduces stock Retribution) and the rest the defaults.

## Verification

Static, before launching anything:

1. `python tools/gen_blood_persist.py` (no `--apply`) — the report lists lump
   sizes; confirm `CVARINFO` and `ZSCRIPT` grew.
2. `python tools/gen_blood_persist.py --apply`, then re-read the pk3 with
   `zipfile` and diff the `ZSCRIPT` lump against the generator constant. The pk3
   is what GZDoom loads; the generator is not.
3. Kill any running `gzdoom` first — the pk3 is locked while the game is up.

In game (hand off to the user; do not launch it):

    .\tools\ab-blood.cmd boom 1

With `rt_gore_burst_debug 1` every burst prints
`RTBloodBurst: <class> dmg N -> M splats`. **Nothing printed means the feature
is not live** — check the startup log for `RTBloodPersistHandler` and that the
pk3 loaded. Do not conclude "explosions still have no blood" from the screen
alone.

Three shots to judge:

- **barrel next to zombies** — MAP01 has both. The existing harness
  `Doom64-Retribution/d64r-barrel-boom-test.pk3` spawns a `64ExplosiveBarrel`
  96 units away, backs the player off and detonates it; it is the negative
  control — a barrel with nothing near it must produce **no** blood, because the
  barrel itself does not bleed.
- **rocket into an imp** — the direct-impact + radius double hit; the dedupe
  should give one splash, not two.
- **rocket into a Lost Soul** — `+NOBLOOD`, so it must stay bloodless.

Then `.\tools\ab-blood.cmd noboom 1` for the flip, and `bigboom` to bracket the
count/speed from above before settling the defaults.

One thing with no static answer: a splat thrown outward can land on a ledge or
stick against a wall mid-air. If that reads badly the lever is
`rt_gore_burst_speed` down — not a new clamp.
