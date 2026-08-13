# Blood on explosive kills — the design record

**SHIPPED.** The live reference — cvars, arms, how to judge it — is
`docs/blood-persist.md`; this file is why it is built the way it is, kept so the
reasoning does not have to be re-derived. Do not treat it as a tracker.

## The asymmetry, and where it comes from

Shooting an enemy with the pistol or shotgun leaves BLUD splats, and since
`d64r-blood-persist.pk3` those splats stay on the floor. Blowing the same enemy
up with a rocket or a barrel left **nothing**. That is not a renderer setting
and not a Retribution authoring choice — it is stock GZDoom, confirmed in the
engine source:

- Blood actors are spawned **only by attack code**, never by damage code.
  `P_DamageMobj` (`src/playsim/p_interaction.cpp`) contains no blood at all.
- Hitscan reaches blood through the actor virtual `SpawnLineAttackBlood`
  (`wadsrc/static/zscript/actors/attacks.zs:742`), called from `P_LineAttack`
  at `src/playsim/p_map.cpp:4875`.
- `P_RadiusAttack` (`src/playsim/p_map.cpp:6136`; the two damage sites are 6234/6243 and 6288/6289) calls
  `P_DamageMobj(..., DMG_EXPLOSION)` and then **only `P_TraceBleed`**. There is
  no `P_SpawnBlood` anywhere in that function. `P_TraceBleed`
  (`p_map.cpp:5098`) spawns no actor — it makes a wall **decal**, plus the RT
  fluid particles under `HAVE_RT`. Crushing is the same.
- A rocket's direct impact (`p_map.cpp:1337`) only splatters if the missile has
  `+BLOODSPLATTER`; `64Rocket` does not. But the rocket explodes on contact, so
  the victim takes the radius hit at distance 0 — **`DMG_EXPLOSION` alone covers
  both rockets and barrels.**

Goal, met: an explosion throws a splash of the *same* BLUD splats outward from
the victim, which arc down and settle on the floor exactly like the hitscan
ones — and therefore persist and get capped by the machinery that already
existed.

## Why it is entirely inside the pk3

No engine rebuild was needed for this half. Everything is edited in the
generator `tools/gen_blood_persist.py`, which holds all four lumps as string
constants and writes the pk3 with `--apply`.

`WorldThingDamaged` is the hook: it carries `DamageFlags` (`DMG_EXPLOSION =
2048`, `wadsrc/static/zscript/constants.zs:962`), `Damage`, `Inflictor` and
`DamageAngle`. It fires from both `p_interaction.cpp:1494` (the fatal path,
before `CallDie`) and `:1515`, so an enemy killed outright by the blast still
gets its burst.

### Why the splats are spawned directly and not only via `SpawnBlood()`

The look is *thrown outward, then falls*, which needs a per-splat `Vel` — and
`Actor.SpawnBlood()` returns nothing. Setting the velocity from
`WorldThingSpawned` instead does **not** work: that event fires from
`AActor::CallPostBeginPlay` (`p_mobj.cpp:4920`), which the thinker list runs on
a later pass (`dthinker.cpp:608`), not synchronously inside `Spawn()`. Any
"burst is active" latch would already be stale by the time the event arrived.

So the burst does both:

1. **one** `t.SpawnBlood(...)` call — the engine path, and the only thing that
   emits the RT fluid particles (`RT_SpawnBlood_Thing`, called at
   `p_mobj.cpp:6140`), which has no ZScript export and cannot be reproduced by
   hand;
2. **N** splats spawned directly so their `Vel` can be set:
   `Actor.Spawn(t.GetBloodType(0), pos, NO_REPLACE)` — `GetBloodType`
   (`actor.zs:559`) already applies the replacement chain
   `Blood → 64Blood → RTBloodPersist`, hence `NO_REPLACE`, matching what
   `P_SpawnBlood` does. `t.BloodTranslation` is copied onto each unless
   `bDontTranslate` — which is also what carries **per-monster blood colour**
   into the burst, added later.

Both kinds land in the existing `WorldThingSpawned`, so scale jitter, `bXFLIP`,
optional roll, the FIFO and `rt_gore_max` apply with **no change to that
method**. The `RTBloodPersist` DECORATE Spawn state still throws its 1–3
satellites, which trail slightly behind a moving parent — free extra scatter.

### The guards, and why each one is there

In order (the first three mirror `SpawnLineAttackBlood`'s own test at
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
for each splat a random yaw, a radius in `[0, t.radius]`, a height in
`[0.25, 0.8] * t.height`, and

```
b.Vel = (cos(ang) * sp, sin(ang) * sp, FRandom(lift * 0.4, lift));
```

with `sp = rt_gore_burst_speed * FRandom(0.5, 1.0)`. `64Blood` has
`Gravity 0.65` and gravity lives in `Actor::Tick`, not in the state machine, so
they arc and settle on their own — the same reason the persist splats already
fall correctly.

## The contract that made this a five-file change

`noarchive` on every cvar is not optional: an A/B arm that writes into the ini
silently poisons the next launch.

And every `ab-blood.cmd` arm sets **every** `rt_gore_*` explicitly, on purpose,
so a value from a previous arm can never leak into the next. That contract is
why adding one family of five cvars meant editing all seven arms that already
existed and not only the new ones — there is no default-by-omission. `off` gets
`rt_gore_burst 0`, since it reproduces stock Retribution.

## The one thing with no static answer

A splat thrown outward can land on a ledge or stick against a wall mid-air. If
that reads badly the lever is `rt_gore_burst_speed` down — not a new clamp.
