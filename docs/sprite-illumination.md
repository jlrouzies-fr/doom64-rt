# Making sprites emit light under RTGL1 — torches, Unmaker puffs, Baron-family fists

Reference for how sprite glow and sprite *lighting* actually work in this project,
written after doing several of them in one pass (2026-08-09). Read the three mechanism
sections before touching any sprite emissive — most of the time lost on this went to
mechanisms that look correct and silently do nothing.

## STATUS

| Sprite | What it needed | State |
| --- | --- | --- |
| `A030`/`A031`/`A032` torches | nothing — already correct | superseded: now engine-lit, see Case 7 |
| `LPUF` Unmaker laser puff | wrong light colour (blue on a red sprite) | fixed, live |
| `TL*` / `TS*` standing torches | **no RT meta at all** — 40 sprites, no light | flame-masked emissive, live; light moved to the engine (Case 7) |
| every open flame + `CAND` candle | light stuck at billboard centre, and dead steady | `rt_flame_light_on`: offset onto the flame, flickering, built |
| `BOS2` Hell Knight fists | glow + per-fist analytic lights | implemented, built, verified in-engine |
| `BOSS` Baron of Hell fists | same treatment, red | implemented, built, verified in-engine |
| `BAL2` / `BAL8` projectiles | wrong light colour (violet & green on red sprites) | fixed in every `textures.json` + the generator |
| `FIRE` bonfire | **missing from `RT_FLAME_KINDS` entirely** — 117 placements | added, built; see Case 7 and `docs/flame-lighting.md` |
| `A028` / `A029` gargoyle statues | red eyes painted in the art, never emissive | `_e` masks + `emissiveMult`, live; see Case 8 |
| `SWXC*` / `CMPSW*` switches | 54 of 95 faces had no emissive at all, and none cast light | composites masked + `rt_switch_lights`, built; see Case 9 |
| `DART` trap dart / nailgun nail | near-black sprite, dark red head, no meta — invisible in flight | `_e` masks + `emissiveMult`, live; see Case 10 |

Verified running: `rt_hand_light: uploaded=10 of 10 wanted (cap 48, within 2048u) I=45`
in MAP05 (5 knights × 2 fists), and `uploaded=14 of 14` in MAP13 (Barons + Hell Knights
together), no errors.

---

## Mechanism 1 — where the data actually lives

**RTGL1 reads exactly two material-meta files**: the global `rt/data/textures.json` and
the current scene's `rt/data/scenes/<scene>/textures.json` (`TextureMeta.cpp`,
`TEXTURES_FILENAME`).

The split files under `Doom64-Retribution/Retribution-RT-Materials/rt/data/` —
`textures_fx.json`, `textures_enemy_eyes.json`, `textures_world_emis.json`, … — are
**overlay source-of-record only and are never read by the engine.**

The live file the running game reads is:

```
sourcecode/gzdoom-rt/build/RelWithDebInfo/rt/data/textures.json
```

The `tools/gen_*_emissives.py` generators write **both**, plus `_e.png` masks into
`build/RelWithDebInfo/rt/mat`, `…/rt/mat_dev`, and `Retribution-RT-Materials/rt/mat`.

> **Trap paid for in this session.** Editing only the overlay file looks entirely
> correct — right schema, right values, clean git diff — and changes nothing in game.
> Two "fixes" were reported as done while completely inert. Always grep the **live**
> `textures.json` before and after.

`rt/mat_dev` is the raw-PNG folder the dev image loader reads, and
`gen_enemy_eye_emissives.py` writes there too. A stale mask left in `mat_dev` can win
depending on which loader is active — write all three folders.

## Mechanism 2 — glow is not light

Two different things, controlled by different fields:

| Want | Field | Effect |
| --- | --- | --- |
| the sprite *looks* bright | `emissiveMult` | screen emission only |
| the sprite *lights the room* | `lightIntensity` + `lightColorHEX` | real analytic light |

`emissiveMult` **can never illuminate anything at any value.** RTGL1 collects emission
only when an indirect bounce ray happens to hit the surface (`HitInfo.inl` /
`RtRaygenIndirect.inl`), never through `processDirectIllumination` — spelled out in the
`rt_wall_strips` cvar comment, `rt_main.cpp` ~line 188.

`textures_enemy_eyes.json` is deliberately emissive-only ("no cast light" per
`gen_enemy_eye_emissives.py`'s docstring): eyes glow, they do not illuminate.

### Why triangle/area lights are not the answer

The obvious wish — "make emissive surfaces real light sources" — is not reachable.
`TRIANGLE_LIGHTS` is `0`, and it is dead code, not a disabled feature:

- `Shaders/Light.h:84` contains a deliberate `#error Refine decoding, as it's obsolete for TriangleLight`.
- `EncodeAsTriangleLight` writes `lt.color[]`, `lt.data_0[]`… — fields that no longer
  exist. `ShLightEncoded` was compressed to 24 bytes (`lightType`, `colorE5`,
  `ldata0..3`); sphere and spot were migrated, triangle never was. A triangle needs
  ~13 floats and **cannot fit**.
- `EncodeAsTriangleLight` also opens with `assert( !transform ); // not implemented`, so
  dynamic meshes (all monsters) are excluded regardless.

Reviving it means widening the light encoding for every light type (paid across the
light buffer and ReSTIR reservoirs) or building a separate triangle-light path. It also
would not *simplify* the existing lamp systems: their hard part is selection and budget
(MAP03: ~1001 ceiling-edge candidates against a cap of 320), and per-triangle emitters
make that strictly worse.

## Mechanism 3 — the `_e.png` mask must not sample the albedo

`RsWorld.inl` builds screen emission as:

```
ldrEmis = baseColor().rgb * emisTex.rgb;   // then *= emissiveMult
```

**The albedo is already a factor.** A mask painted with colours sampled from the
sprite's own albedo multiplies it in a second time and squares it. On dark source art
that annihilates the glow.

Measured on BOS2, whose fists are painted dark green (brightest texel `(0,104,40)`):

| mask | peak channel | avg RGB |
| --- | --- | --- |
| albedo-sampled (wrong) | 104 / 255 | (0, 86, 25) |
| full-saturation (right) | **255** | (0, 255, 62) |
| `TROOA1_e.png` (eye gen reference) | 255 | (227, 9, 0) |

With the wrong mask, raising `emissiveMult` 2 → 4 was visually indistinguishable — it
was doubling almost nothing. `gen_enemy_eye_emissives.py` avoids this by construction:
`mask_to_red_e` paints a flat saturated `RED = (255,10,0)` and takes **intensity from
the brightmap, hue from a constant.**

Rule: saturate the colour to full range, let the brightmap supply the intensity ramp,
and verify the written mask peaks at 255.

---

## Case 1 — torches (`A030` / `A031` / `A032`)

No work needed. All 15 entries (3 colours × 5 animation frames) already carry
`emissiveMult 0.35`, `lightIntensity 700`, `noShadow true`, with per-frame
`lightColorHEX` that tracks the flicker — yellow `eac257`, blue `6a93ea`, red `ea655b`.
Confirmed present in the **live** file, not just the overlay. `GTCH`/`GFLM` (green
torch/flame) follow the same pattern.

## Case 2 — Unmaker laser puff (`LPUF`)

`LPUFA0/B0/C0` had `lightColorHEX: "aaccff"` — pale blue. Decoding the sprites' PNG
palettes showed the hot pixels are red-orange (`d63100`, `ff4a10`, `ff9463`); nothing
blue anywhere. Almost certainly copy-paste from another effect.

Fixed to `f15a26` in both the overlay and the live file. `emissiveMult 0.55`,
`lightIntensity 300`, `noShadow true` were correct and untouched.

## Case 3 — Hell Knight fists (`BOS2`) — the full treatment

### What was wrong

1. **Only one frame had anything.** 39 of the 40 living frames were bare
   `{"textureName":"BOS2xx"}`. Only `BOS2F4F6` had `emissiveMult: 2`.
2. **The attack light was never the hands.** It is the `64BaronBall` projectile
   (`BAL7`, green `66ff55` @ 1000). The fists contributed nothing, ever.

**Why only one frame:** `gen_enemy_eye_emissives.py` is an *eye* generator.
`is_valid_eye_mask()` rejects masks >70 texels, taller than `h/5`, wider than `w/2`, or
outside the head band. Fists are mid-body and wide apart, so 39 were rejected.
`BOS2F4F6` is the attack-windup pose where the raised fist lands in the head band and
looks eye-shaped to the validator — it passed **by accident**.

### Picking which texels glow

The mod ships authoritative brightmaps in `D64RTR_BRIGHTMAPS.PK3`
(`brightmaps/bd64/BOS2*B.png`) for **precisely the 40 living frames A1–H5 and none of
the death frames I0–N0**.

That distinction is load-bearing: **BOS2's gibs reuse the same green palette ramp as
the hand glow**, so a naive green-pixel filter would turn the death animation into a
flare. The mod authors already drew the line; use their mask, don't re-derive it.

Verified every lit texel is green (the apparent "non-green" ones are `(0,56,0)`, dark
pure green), so full-saturation recolouring cannot mis-tint anything.

### Why texture meta could not finish the job

RTGL1 attaches a sprite's light at the **centre of the billboard quad**
(`VulkanDevice.cpp` ~1910: `center = average of the 4 quad verts`, `radius 0.1`). So:

- the green hand glow emitted from the **torso**, and
- the two fists **collapsed into one point between them**.

Measured offset of the real glow from where the light sat:

| frame | pose | offset |
| --- | --- | --- |
| `BOS2A1` | idle | dx −1.7, dy −0.8 px |
| `BOS2G1` | attack | dx −9.1, dy −2.4 px |
| `BOS2E1` | arm raised | dx +7.6, **dy −27.9 px** |

Combined with "emissive is not a light source", the bright fists could never light the
forearm beside them at any `emissiveMult`. Texture meta has no offset field. The only
fix is to stop using the attached light and upload real lights.

### What was built

**`tools/gen_hand_glow_emissives.py`** — the glow.
Brightmap + albedo → 40 `_e.png` masks, per-texel hue saturated to full range and scaled
by the brightmap ramp, written to all three mat folders. Writes `emissiveMult: 4.0` to
the live and overlay JSON. Deliberately writes **no** light fields, and actively strips
`lightIntensity` / `lightColorHEX` / `lightEvenOnDynamic` — leaving them would stack the
old torso light on top of the new fist lights.

**`tools/gen_hand_light_offsets.py`** — the geometry.
Flood-fills each front-rotation brightmap into connected components, drops blobs under 8
texels (this is what excludes the eye dots), takes the two largest, and resolves their
centroids against each sprite's real **`grAb` origin** — not the image centre, since
these sprites are not symmetrically padded. Emits
`sourcecode/gzdoom-rt/src/common/rendering/rt/rt_hand_lights.h`:

```
A: grAb=(29,101)  (lat-19.9, up50.6), (lat+26.4, up46.5)
E: grAb=(28,95)   (lat+29.7, up81.9), (lat-5.7, up63.8)   <- raised arm
G: grAb=(27,95)   (lat -9.9, up49.6), (lat-24.2, up44.2)
```

`fwd` is left at 0 on purpose: the front rotation cannot show forward extension, so any
value there would be invented.

**`RT_UploadHandGlowLights()`** in `rt_main.cpp` — the lights.
Walks actors, matching `BOS2` and `BOSS` by sprite name **in full** — never on a `BOS`
prefix, since the two differ only in the 4th character and need different colours — with
`64HellKnight` / `64BaronOfHell` class-name fallbacks. Frames outside A–H are skipped,
which is what keeps corpses dark. Offsets are rotated by the actor's yaw (Doom angle 0 =
+X, right-of-facing = yaw − 90°) and uploaded as one `RgLightSphericalEXT` per fist. The
colour is read from the generated `RT_HAND_COLOR[]`, never a literal in the engine, so
the cast light cannot drift from the mask tint.

Follows the house pattern from `RT_UploadHangingTechLamps`: distance cull, **nearest-N
budget trim** (a distance filter alone does not bound the count — that is what caused
the lamp pop-in), and stable per-actor unique IDs so RTGL1 does not see the light set
vanish and reappear each tick.

### Cvars

| cvar | default | note |
| --- | --- | --- |
| `rt_hand_light_on` | `true` | master switch |
| `rt_hand_light_intensity` | `65` | **per fist** — two per knight, so perceived total ~double |
| `rt_hand_light_radius` | `0.06` | small; a wide source washes the body flat |
| `rt_hand_light_maxdist` | `2048` | map units |
| `rt_hand_light_max` | `48` | 2 per knight → 24 simultaneous knights |
| `rt_hand_light_debug` | `false` | **`RT_CVAR_NOARCH`** |

`rt_hand_light_debug` is NOARCH unlike the older `*_debug` cvars beside it: it uploads
magenta markers at intensity 350, and archived, one debug launch would burn them into
the ini and wreck every later visual judgement.

New IDs use `HandLightId_Base = 1ull << 42` — bit 42, not "the next value after
`SoloLatticeId_Base`" (`1<<40`), because that base adds `secIndex<<20 + cell` and climbs
well past itself. IDs derive from the actor pointer, so the two monsters cannot collide.

## Case 4 — Baron of Hell fists (`BOSS`) — "the red hell knight"

Same treatment, two wrinkles.

**BOSS ships no brightmaps of its own.** `D64RTR_BRIGHTMAPS.PK3` has 40 `BOS2*B.png` and
zero `BOSS*`. But BOSS is the *same artwork palette-swapped* — verified before relying on
it: **12/12 checked frames have a pixel-identical silhouette**, so the BOS2 masks transfer
exactly. `grAb` is *not* identical though (`BOSSA5` is `(29,94)` where `BOS2A5` is
`(29,93)`), so each sprite is still resolved against its own origin. Generalising beat
auto-detecting red pixels, which is precisely the failure `gen_enemy_eye_emissives.py`
documents ("it painted armor/blood/backs on soldiers & pinkies").

**Sampling gave orange, and orange was wrong.** The measured lit average is `(93,28,2)`,
which saturation-normalises to `ff4c06` — visibly orange. That is an artefact of the
normalisation, not the art: scaling a dark red to peak 255 multiplies **green by the same
2.7× as red**. Both generators therefore carry a matching aesthetic override, and BOSS is
pinned to a true red `e01000`.

The same commit pins **BOS2 to `08ff5e`** as well. Left unpinned it now samples to
`09ff4b`, because the offsets generator averages only the front rotations while the value
accepted in play came from all 40 frames. Small, but not a shift worth making silently.

For BOSS the mask uses a **flat tint** rather than per-texel hue (BOS2's mode): the Baron's
ramp is dark red where green dominates BOS2's, so per-texel normalisation is what produced
the orange. The generator's "mask must reach full range" guard compares against the tint's
own peak (`224` for `e01000`), not a blanket 255 — a deliberately deep tint is not a dim
mask.

## Case 5 — projectile light colours vs. the actual sprite art (`BAL2`, `BAL8`, `LPUF`)

Reported 2026-08-09: *"BAL2 causes a bright, more-white light, but the projectile is
red."* It is the same defect the nightmare-imp fireball had (`BAL3`, see
`docs/spectre-issue-log.md`) — an attached-light hex pinned in `gen_fx_emissives.py`
that nobody ever compared against the sprite.

Measured straight out of `D64RTR_v15.WAD` (opaque texels, peak-normalized):

| prefix | actor | art | was pinned | now |
| --- | --- | --- | --- | --- |
| `BAL2` | `64CacodemonBall` | red-orange, avg `(99,24,8)` → `ff3e14` | `b65cff` pale violet | **`ff5a28`** |
| `BAL8` | `64BaronBall2` | red, brightest `(248,48,0)` → `ff3100` | `88ff66` baron green | **`ff4a20`** |
| `LPUF` | Unmaker impact puff | `ff4004` / `ff0d04` | `aaccff` pale blue | **`ff1408`** |
| `UNMF` | Unmaker muzzle flash | `ff0b08`, brightest `(239,16,16)` | `ff3366` pink | **`ff1408`** |
| `UNML` | Unmaker beam | literally `(255,0,0)` | `ff2255` pink | **`ff1408`** |
| `IFOG` | `64ItemFog` | zero red, brightest `(0,57,247)` → `0000ff` | `66ffaa` mint green | **`1a44ff`** |
| `RBAL` | `64MotherBall` | zero blue, `ff1d01`, death frames `ff0000` | `ff4040` washed pink | **`ff2606`** |
| `TRCR` | `64TracerMissile` | `ff8840` flight, `ff5e1f` death | `ffaa55` pale tan | **`ff8a38`** |
| `APLS` | `64ArachnotronPlasma` | r == g, blue-dominant → `6262ff` | `88fa84` green | **`6666ff`** |
| `APBX` | vanilla plasma boom | *unreachable in Retribution* | `6eff69` green | **`6666ff`** |
| `MANF` | `64FatShot` | `ff7b3c` – `ff8229` | `ff8c20` orange | **unchanged — correct** |

Why `b65cff` read as *white* rather than *purple*: it is a low-saturation, high-value
hex (`182,92,255`) driven at `lightIntensity 900`. High-value pale hues bleach out under
path tracing long before a saturated one does — the hue barely survives, the luminance
does. Same reason `88ff66` on `BAL8` washed the hell-knight shot pale green.

Where each came from:

- `BAL2`'s violet is inherited from **stock RTGL1**: `gzdoom-rt-1.0.2/rt/data/textures.json`
  ships `BAL2A0`/`BAL2B0` at `b65cff` (its own `BAL2C0`–`E0` are correctly warm, so
  upstream mis-typed only the flight frames). Patched in the vendor copies too.
- `BAL8`'s green is a `BAL7` copy-paste — `BAL8` *is* `BAL7` recoloured red and shares
  its exact frame layout (`A1A5`, `A2A8`, …), so the rule was cloned wholesale.
- `LPUF` was already fixed in the JSON (Case 2) but **the rule in `gen_fx_emissives.py`
  was left stale at `aaccff`**, so the next run of the generator would have silently
  reverted a shipped fix. Fixed at the source now — and the JSON's `f15a26` was itself
  too orange: Case 2 read the puff's few hot *rim* texels, not the mass of the sprite.
- The **Unmaker fires a pure red laser**, so `LPUF` / `UNMF` / `UNML` now share one
  `UNMAKER_RED = ff1408` constant in the generator rather than three hand-picked hexes
  drifting apart. `UNMLA0` is a 2×2 lump of literal `(255,0,0)` — there is no ambiguity
  about this one. The token `20/8` of green/blue keeps it off a degenerate
  single-channel light while still reading pure red.
- `IFOG` was pinned `66ffaa` on the assumption that the item fog matches the teleport
  fog. It does not: `TFOG` is green (`00ff05`, and its `40ff40` pin is correct — leave
  it), `IFOG` is blue. Note `TFOGI0`/`TFOGJ0` carry a violet `8866ff` at intensity 500;
  those frames do not exist in `D64RTR_v15.WAD` and are inert stock RTGL1 entries.
- `APLS` is the biggest single miss in the table: `88fa84` green on a projectile whose
  every frame is `r == g` with a dominant blue. `APBX` (the vanilla boom) was green for
  the same reason and is pinned to match, though nothing in Retribution can spawn it —
  `64ArachnotronPlasma REPLACES ArachnotronPlasma` and fades out on `APLSE0`–`H0`.
- `RBAL` and `TRCR` were not *hue* errors, they were **saturation** errors, which the
  hue-delta audit below cannot see. `ff4040` is hue 0° — nominally perfect red — but its
  equal green and blue make it a washed pink at `lightIntensity 1100`, on art that has
  literally zero blue in it. Same for `ffaa55` on `TRCR`. Watch the channel spread, not
  just the hue.
- `MANF` (`64FatShot`) was checked and left alone — `ff8c20` against art that normalizes
  to `ff7b3c`–`ff8229` is 2.8° off and correctly orange.

### The audit that found most of these

Comparing every `PREFIX_RULES` hex against its own sprites' average hue is a two-minute
check and worth re-running after any FX edit — group the WAD lumps by prefix, average
the opaque texels above `sum>120`, peak-normalize, and compare HSV hue. `BAL2`, `APLS`,
`IFOG` and `BAL8` sat at 151°, 122°, 90° and 63° of hue error; all are under 11° now.

Its blind spot is the `RBAL`/`TRCR` failure mode above: a hex can have the right hue and
still be far too desaturated, and a pale light bleaches under path tracing while a
saturated one keeps its colour. Compare the channel spread as well.

IWAD-resident sprites (`APBX`, the chaingunner fire frames) need the Doom picture-format
decode with `PLAYPAL` — `open_sprite()` returns `None` for them, so they are invisible to
any PIL-only sweep and their hexes have never been checked against art.

The remaining large deltas are **deliberate, not bugs** — do not "fix" them blind:
`BAR1`/`BEXP` (poison-green barrels, documented in the generator), `TFOG` (green GLDEFS
teleport fog), and the pickup auras `PINS`/`PINV`/`MEGA`/`ART1`–`ART3`,
where the colour is the powerup's aura, not the item's paint. The muzzle-flash family
(`CHGF`/`CSHT`/`CSSG`/`SAWG`) shows large deltas only because the art is the whole
grey-blue gun body; they carry `lightIntensity 0` and cast nothing.

## Case 6 — the standing torches (`TL*` / `TS*`) — 40 sprites with no meta at all

Not a wrong colour this time: **the eight standing-torch families had no RT entry
whatsoever.** No light, no emission, in a mod where torches are the main room lighting.
`GTCH` and the `A030`–`A032` wall sconces were covered; the floor braziers never were.

| family | actor | flame art (saturation-gated) | now |
| --- | --- | --- | --- |
| `TLBL` / `TSBL` | `64TorchLong/ShortBlue` | `5090ff` | `FLAME_BLUE` `4488ff` |
| `TLGR` / `TSGR` | `64TorchLong/ShortGreen` | `58ff51` | `FLAME_GREEN` `44ff66` |
| `TLRD` / `TSRD` | `64TorchLong/ShortRed` | `ff5252` | `FLAME_RED` `ff4020` |
| `TLYL` / `TSYL` | `64TorchLong/ShortYellow` | `ffc350` | `FLAME_YELLOW` `ffcc33` |

### Why they needed their own generator

**They are not drawn `BRIGHT`.** `64TorchLongBlue` runs `TLBL ABCDE 4` — no flag —
whereas every wall torch runs `ABCDE 4 BRIGHT`. The mod deliberately shades the stone
pole. And the pole is most of the sprite: ~90 flame texels out of ~970 opaque on a `TL`
frame, so a blanket `emissiveMult` would make an 82 %-grey-stone brazier self-illuminate.
That is the `PLSG`/`BFGG` whole-gun-body failure, on a prop that stands in every room.

`gen_fx_emissives.make_emissive_png()` cannot save you here — it keeps any texel with
`sum >= 200`, and the stone reads `(176,168,168) = 512`. It would mask in the entire pole.

So `tools/gen_torch_emissives.py` gates the mask on **saturation, not brightness**: the
flame is the only coloured thing on the sprite (pole `max-min <= 8`, flame `>= 45`). Then
per Mechanism 3 it repaints at full saturation, intensity ramp from the source texel,
normalized so the hottest flame texel lands on 255. Verified: 0 grey texels survive into
any of the 40 masks, all peak at exactly 255.

### Reading the colours off the mod, not guessing

The WAD ships its own `GLDEFS` and it is authoritative for intent:

```
flickerlight TORCHLONGBLUE { color 0.0 0.2 1.0  size 40  secondarySize 48  offset 0 80 0 }
flickerlight TORCHSHORTRED { color 1.0 0.1 0.1  size 40  secondarySize 48  offset 0 64 0 }
flickerlight GREENTORCH    { color 0.0 1.0 0.0  size 28  secondarySize 32  offset 0 24 0 }
```

Two things fall out of it. **Intensity**: `TL*` and `TS*` share size 40/48 against the
wall torches' 28/32, so both get one value, `900`, above the sconces' 700. **Colour**: the
GLDEFS hues are fully-primary (`0.0 1.0 0.0`) and bleach under path tracing, so the shared
`FLAME_*` palette is used instead — every entry within 10° of its measured art, and now a
named constant in both generators rather than eight loose hexes.

`TLRD`/`TSRD` are the `RBAL` trap again: the flame art averages `(155,50,50)`, hue 0° but
green == blue. Taken literally that is a pink light. `FLAME_RED ff4020` keeps the hue and
restores the saturation.

### The limitation you cannot fix in texture meta

> **Resolved by Case 7 (2026-08-10).** These sprites now carry `lightIntensity: 0` and are
> lit by the engine. The paragraph below is kept because it is *why* Case 7 exists.

GLDEFS lifts these lights `80` (long) / `64` (short) units up, onto the flame. RTGL1
attaches a sprite light at the **centre of the billboard quad** and texture meta has no
offset field — the same wall the `BOS2` fists hit. So the light sits mid-pole, roughly
30 units below the flame on a long torch. Fixing it properly means a real light-upload
path like `RT_UploadHellKnightHandLights`; for a static prop the misplacement is far less
visible than it was on moving fists, so it is logged, not built.

---

## Case 7 — the candle, and making fire behave like fire (`rt_flame_light_on`)

> **Full write-up: `docs/flame-lighting.md`.** That file is the one to point another agent
> at — it carries the sprite inventory, the three-way invariant, the file list, what was
> and was not verified, and the known limitations. What follows here is the summary.

Two requests, one answer: give `CAND` a light of its own, and make the torches *flicker
and move* instead of sitting there like a fluorescent tube. Both land in the same place,
because a candle is just the smallest flame in a family that all had the same two defects.

### The two things texture meta cannot do

1. **Offset.** Case 6's logged limitation, above. RTGL1 anchors a sprite light to the
   centre of the billboard quad, so a 100-unit standing torch lit the room from its own
   midriff, ~30 units under the flame. GLDEFS wants these lights `8`–`80` units up.
2. **Flicker.** Texture meta is static per sprite frame. The only data-only way to vary it
   is a per-frame intensity ramp across the `A`–`E` animation — and **every one of these
   props spawns at map load, so their frame counters are in lockstep.** A whole room of
   torches pulsing in perfect unison reads as an electrical fault, not as fire. That is
   the trap to remember: the data-only version is not merely worse, it is actively wrong.

So the lights moved into the engine, exactly as the `BOS2` fists did:
`RT_UploadFlameLights()` in `rt_main.cpp`, table `RT_FLAME_KINDS`, master switch
`rt_flame_light_on` (default **true**).

### The table is the mod's own GLDEFS

`up` and the relative intensities are read straight out of the mod's `flickerlight`
blocks — nothing invented:

| GLDEFS block | sprites | `size` | `offset` | RT intensity |
| --- | --- | --- | --- | --- |
| `TORCHLONG*` | `TLBL` `TLGR` `TLRD` `TLYL` | 40 | 80 | 900 |
| `TORCHSHORT*` | `TSBL` `TSGR` `TSRD` `TSYL` | 40 | 64 | 900 |
| `*TORCH` (wall) | `A030` `A031` `A032` `GTCH` | 28 | 24 | 700 |
| `*FIRE` (loose) | `BFLM` `GFLM` `RFLM` `YFLM` | 32 | 8 | 650 |
| `BIGFIRE` | `FIRE` | 32 | 32 | 650 |
| `CANDLE` | `CAND` | 16 | 16 | 260 |

`FIRE` was **missing from this table until 2026-08-10**, excluded on the written grounds
that it "is not a GLDEFS flame prop". The WAD says otherwise, and it is the most-placed
fire in the game by 30×. See the placement census in `docs/flame-lighting.md`.

Colours do **not** come from GLDEFS, which asks for fully-primary hues (`0.0 1.0 0.0`
green, `1.0 0.1 0.1` red) — those bleach to white under path tracing, per Case 5. They
are the same four `FLAME_*` hexes the mask generators tint with, so cast light and
on-screen glow stay on one palette.

The candle is the one exception, and it is deliberate: it takes `RT_FLAME_CANDLE`
`ff4a14`, a warm **red**, not `FLAME_YELLOW`. Its old attached light was `ffaa55` @ 280 —
straight amber, the same hue family as a pitch torch four times its size. A candle is one
wick; it should read as a dim ember at the edge of a dark room. (The art *is* amber:
`CAND?0` is 8×31 with a brightest texel of `(232,168,0)`. But on a sprite that small the
amber is the wax body catching its own light as much as the flame, so the art average is
not the authority here that it was for the projectiles.)

### The flicker

Three incommensurate sines per actor, summed at weights `0.55 / 0.30 / 0.15` and
normalised, so the pattern has no short period — stand next to a torch for a minute and it
never visibly loops. Each actor gets a **phase derived from its own pointer**, which is
what stops the lockstep problem; the same phase drives a second set of sines at different
frequencies that *moves* the light a couple of units on each axis (half that vertically —
a flame licks upward far more than it slides). Pulsing alone reads as a fault; pulsing
plus wander reads as combustion.

Timebase is `primaryLevel->maptime`, not wall clock, so a paused game freezes the fire
with everything else. 35 Hz stepping is not a compromise: GLDEFS' own `flickerlight` is a
hard two-state switch re-rolled once per tic (`size` ↔ `secondarySize` at `chance 0.5`),
which strobes under a path tracer where every flicker also moves the indirect bounce. Same
depth, delivered smoothly.

### The data half — and the double-light trap

Every sprite in `RT_FLAME_KINDS` now carries `lightIntensity: 0` (the muzzle-flash
convention: a 0 casts nothing) and keeps its `emissiveMult`, because the flame must still
glow on screen. Applied by `tools/strip_flame_sprite_lights.py`, which is idempotent.

**Three places must agree**, and the generators own two of them:

- `RT_FLAME_KINDS` in `rt_main.cpp` — the engine light
- `PREFIX_RULES` in `gen_fx_emissives.py` — the wall torches, fires and `CAND`
- `INTENSITY` in `gen_torch_emissives.py` — the 40 `TL*`/`TS*`

Both generators were set to `0` in the same commit. Re-attaching a light in either without
deleting the matching `RT_FLAME_KINDS` row lights the flame **twice, from two different
heights** — worse than the bug this replaced. This is trap 5 with a second way to bite.

### Cvars

| Cvar | Default | Notes |
| --- | --- | --- |
| `rt_flame_light_on` | `true` | master switch. Off = flames cast **nothing** (meta is zeroed) |
| `rt_flame_light_scale` | `1.0` | multiplies the whole table; retune the family here, not one row |
| `rt_flame_light_radius` | `0.09` | metres. Wider softens the shadows a torch throws down a corridor |
| `rt_flame_light_flicker` | `0.15` | depth, 0..1 of base intensity. `0` = steady |
| `rt_flame_light_speed` | `0.25` | radians/tic of the base sine (~1.4 Hz); harmonics at 2.37× and 4.11× |
| `rt_flame_light_wobble` | `2.0` | map units of drift per axis. Past ~4 the light detaches from its sprite |
| `rt_flame_light_maxdist` | `3072` | wider than the fist cull: torches are room lighting, and popping one in is visible |
| `rt_flame_light_max` | `64` | nearest-first budget |
| `rt_flame_light_debug` | `false` | **`RT_CVAR_NOARCH`** — cyan markers at 350 intensity |

All of these are live at runtime; only the table itself needs a rebuild. They are also
pinned in `tools/launch-retribution-rt.cmd` — every `RT_CVAR` is `CVAR_ARCHIVE`, so a
compiled-default change alone is not enough once the ini has a value.

**First pass shipped at `0.28` / `0.42` and was too strong and too fast.** The reason is
worth keeping: a torch is not a prop with a light on it, it is *the ambient light of the
room it stands in*. Depth that looks right on an isolated campfire swings the whole
room's indirect bounce with it, and under a path tracer the bounce moves too. Halving
both was the fix. If it still reads as too busy, drop `speed` before `flicker` — the
4.11× harmonic is what sets the perceived rate.

---

## Case 8 — the gargoyle statues (`A028`, `A029`) — when auto-detect *is* the right tool

`tools/gen_statue_eye_emissives.py`. Two decorations, one frame each: `64StatueDragon`
(`A028A0`, 64×72) and `64StatueDemon` (`A029A0`, 64×64). Both are painted with red eyes
that had no `_e` mask and no meta, so under RT they were dead pixels on a stone face.

The interesting part is the mask source. Neither of the enemy pipeline's two sources
exists here — `D64RTR_BRIGHTMAPS.PK3` has nothing for `A02*`, and with one frame apiece
there is no donor to clone from. Which leaves the red-pixel auto-detect that
`gen_enemy_eye_emissives.py` explicitly disables (`AUTO_EYES = False`) because it painted
armour, blood and soldiers' backs.

**Here it is exactly right, and the reason generalises.** On the monsters the detector was
matching a hue *range* over sprites that contain plenty of legitimate red. On these two the
red is a single exact palette entry that appears nowhere else on the sprite:

| sprite | art colour | texels | positions |
| --- | --- | --- | --- |
| `A028A0` | `(128, 32, 0)` | 4 | `y39: x24,25 ǀ x31,32` |
| `A029A0` | `(104, 0, 0)` | 6 | `y43: x23 ǀ x29` · `y44: x24,25 ǀ x27,28` |

Symmetric pairs, in the head, and a measured **zero** other pixels above saturation 0.45 in
the red hues anywhere on either sprite. So the rule is a lookup, not a threshold. The tool
also pins the expected texel coordinates and **aborts** if the art ever stops matching,
rather than quietly inventing eyes on a sprite it no longer understands — the trap from
"check the source art before lighting a fixture".

**Colours differ on purpose.** The enemy eyes all share `ff0a00`; these two do not agree
with each other in the art — the dragon's are orange (`128,32,0` is 4:1 red:green), the
demon's are pure blood red — and they stand in the same rooms in MAP23 and MAP34. Each
keeps its own hue at full saturation: `ff4000` and `ff0a00`. Full saturation is Mechanism 3,
not taste: the shader multiplies by baseColor, so a mask painted at the art's own dim value
gets the darkness applied twice.

`emissiveMult 2.0`, the enemy-eye house value. **No cast light** — a 4-pixel eye on a lump
of stone is not a lamp, and `lightIntensity` here would anchor at the billboard centre
anyway (Mechanism 2). If a room later wants a red pool at a statue's feet, that is an
engine-side light on the `RT_FLAME_KINDS` pattern, not a number in `textures.json`.

Placement, all 71 UDMF maps: `A028` ×62 (MAP13 ×17, 15 ×12, 17 ×8, 23 ×9, 21 ×6, plus 22,
24, 30, 34), `A029` ×26 (**MAP23 ×24**, 22 ×1, 34 ×1). MAP23 is the room to check.

Registered in `check_emis_hygiene.py` — `textures_statue_eyes.json` in `OVERLAY_KEEPS` and
`A028A0|A029A0` in `KEEP_E_RE`, both anchored to the exact frame names so they can never
widen into a bare `A02` prefix and swallow the other seven `A02x` decorations. Without that
registration a later `gen_world_emissives.py` scrub would treat them as strays.

**Not verified in-engine.**

---

## Case 9 — the switches (`SWXC*`, `CMPSW*`) — a patch is not what the engine names

Retribution's switches change art when thrown (ANIMDEFS `CMPSW##A → ON → CMPSW##B`) and
the ON art lights up: `SWXC`'s demon face gains red eyes, `SWXSG`'s plate gains a pink
gem. Two separate defects, and the first is the more instructive.

### 1. The allowlist named patches; the engine names composites

`SWITCH_ON_EMIS` in `gen_world_emissives.py` lists **patches**. `SWXCB` had a correct `_e`
mask and `emissiveMult 0.4`, so the 41 sidedefs using the bare 32×32 texture lit their eyes
properly. But Retribution stamps that patch into 56 `CMPSW*` wall panels, and it is the
**panel** the engine renders and names. None had a mask or an entry.

So the same switch lit up on a bare wall and was completely inert on a panel — **41 uses
working, 54 dead**, across 14 maps. The generator now expands over the `TEXTURES` lump:
for each composite embedding a lit patch, it pastes **that patch's own `_e`** at the
recorded offset. Never re-derived; one source of truth, so the two forms cannot drift.

**The lit frame is not the letter.** `SWXC` lights on `B`, but `SWXCL` and `SWXCKL` light
on `A` — their eyes go *out* when pressed. Keying the expansion off the allowlist rather
than the A/B suffix is what keeps those two right; a letter rule lights them backwards.

Two latent bugs fell out of this, both in `gen_world_emissives.py` and both silent:

- `patch_global_inline()` appended a new entry in single-line form, then its
  "drop later duplicates" pass — which deletes *every* match, not every match after the
  first — removed the line it had just written. Only ever hit genuinely **new** names, so
  56 masks and 56 overlay rows produced **zero** rows in `textures.json`, the only file
  RTGL1 reads.
- Running the tool drops authored names out of the overlay (`replace=True` rewrites it
  from that run's entries). One run removed `SFLATAQ`, `SFLATAS`, `SPACEAZ` and nine
  `SMONF*`/`SMONLB*`. Harmless in game — the global keeps its meta — but
  `_authored_emis_keep()` builds the allowlist *from* the overlay, so the next scrub
  would strip exactly those as strays. **Diff the overlay against HEAD after running it.**

### 2. Glow is not light — `rt_switch_lights`

Mechanism 2 again: the eyes now glowed and still lit nothing. `lightIntensity` is no help,
it is sprite-only. So the switches get an engine light, `RT_UploadSwitchLights()`, on the
`RT_UploadWallStripLights` pattern — walk sidedefs, match the texture, place a light on the
face.

The table is **generated** (`tools/gen_switch_lights.py` → `rt_switch_lights.h`), and every
number in it is measured from the `_e` mask that the emissive pass already wrote:

| field | source |
| --- | --- |
| position | centroid of the mask's lit texels, in texel space |
| colour | those texels' average hue at full saturation |
| `lit` | lit texel count — 7 for the `SWXC` eyes, 46 for the `SWXSG` gem |

Cast light and on-screen glow therefore come from the same pixels and cannot drift — the
`LPUF` failure mode, designed out rather than watched for. Intensity scales by
`sqrt(lit/7)`, not linearly: linear would hand the gem 6.5× the eyes and read as a
spotlight.

**No state tracking.** The walk reads `side->GetTexture()`, which *is* the swapped texture,
so the light exists exactly while the lit face is on the wall — correct across a save, a
level reset, or the switch thrown back off, for free.

**The one convention is vertical placement**, from the sidedef's pegging flags and row
offset. That is derived, not measured, and this project has been bitten by exactly that
twice (`RT_UploadWallStripLights`' normal direction, `rt_spin_panel_yaw`). Hence
`rt_switch_light_zofs` and a debug dump that prints *which pegging branch* placed each
light. A light computed outside its own band is dropped rather than buried in a wall,
where it would be indistinguishable from the feature not working.

`rt_switch_lights 0` is a **true** revert, unlike `rt_flame_light_on`: the eyes keep
glowing, they just stop lighting. Verify with `tools/ab-switch.cmd debug` — MAP20 has 21
`SWXC` faces. Throw a switch first; the A frame is unlit and correctly emits nothing.

**Not verified in-engine.** Nobody has confirmed a marker sits on a pair of eyes.

---

## Case 10 — the dart (`DART`) — a sprite you cannot see coming

`tools/gen_dart_emissives.py`. Reported 2026-08-14: the dart's dark red parts are
invisible in game. They are — the sprite is five lumps of pure grey ramp (`8,8,8` up to
`56,56,56`) with a red head painted in exactly two shades, and neither actor that uses it
draws `BRIGHT`:

    ACTOR 64Dart       Spawn: DART A 1     the trap dart, thing 896
    ACTOR 64NailShot   Spawn: DART AA 1    the nailgun's nail, FastProjectile

No RT entry existed for any of them. Against a dark floor a projectile whose brightest
texel is `(56,56,56)` reads as nothing at all until it lands.

| lump | size | `(40,0,0)` | `(56,0,0)` |
| --- | --- | --- | --- |
| `DARTA1` | 16×12 | 8 | 4 |
| `DARTA2A8` | 32×11 | 9 | 7 |
| `DARTA3A7` | 32×11 | 12 | 3 |
| `DARTA4A6` | 32×11 | 5 | 3 |
| `DARTA5` | 16×10 | — | — |

`DARTA5` is the rear view and has no red on it at all; it is in the table with zero counts
and deliberately gets no mask and no meta, rather than an empty `_e` for the hygiene
checker to trip over.

**Auto-detect is right here for Case 8's reason, only more so.** Every non-red texel in
all five lumps is a pure grey (`r == g == b`), so the red is not a hue *range* to threshold
— it is two exact palette entries. `ART_COUNTS` asserts the counts on every run and the
tool aborts rather than guess if the art ever changes.

**The mask is painted `e01000`, not the art's `(56,0,0)`.** That is Mechanism 3 and it is
the whole bug in miniature: under RT the primary emission is the **raw** `_e` sample, so a
mask painted at the art's own 0.22 renders at 0.22 and stays exactly as invisible as
before. "Dark red" is the hue, delivered by a full-range deep red — the same `e01000`
pinned for BOSS in Case 4, because saturation-normalising a dark red scales green with it
and comes out orange. The art's two shades survive as a two-step ramp (`(56,0,0)` at the
peak, `(40,0,0)` at 40/56 of it) so the head keeps its shading instead of flattening.
`emissiveMult 2.0`, the enemy-eye / statue-eye house value.

**No cast light.** A nail is a `FastProjectile` fired in bursts, and a sprite's attached
light anchors at the billboard centre (Mechanism 2) — a burst would drop one light per
nail for the length of its flight. The ask was visibility, and on-screen emission is what
delivers it. Do **not** add a `DART` rule to `gen_fx_emissives.py`'s `PREFIX_RULES` to
get one; that is trap 5, and it would attach exactly the light this decided against.

Registered in `check_emis_hygiene.py` (`textures_dart.json` in `OVERLAY_KEEPS`, `DART` in
`KEEP_E_RE`) so a later `gen_world_emissives.py` scrub cannot strip it.

**Not verified in-engine.**

---

## Case 11 — the armors (`ARM1`, `ARM2`) — the pickup family the table forgot

Reported from play: *"the ARM1 / ARM2 armors are blinking, but their texture is not
really emitting light"*. Both halves of that are literally true, and the data says why.

`ARM1A0` and `ARM2A0` were in the global `textures.json` as bare `{"textureName": …}`
with no fields at all, and `ARM1B0` / `ARM2B0` had **no entry anywhere**. Every other
animated pickup in the game already carried identical meta on *every* frame:

| family | emissiveMult | lightIntensity | hex | frames | noShadow |
|---|---|---|---|---|---|
| SUIT | 0.35 | 120 | `44ff66` | A | yes |
| **ARM1 — green armor** | **0.6** | **160 / 70** | **`44ff88`** | **A / B** | **no** |
| keys / skulls | 0.6 | 160 | per key | A, B | yes |
| PINS / PINV | 0.5 | 200 | per item | A–D | yes |
| **ARM2 — blue armor** | **0.6** | **200 / 94** | **`4488ff`** | **A / B** | **no** |
| SOUL | 0.6 | 260 | `4488ff` | A–D | yes |
| MEGA | 0.7 | 300 | `8866ff` | A–D | yes |

The armors are the only two rows with a **per-frame** light, so they live in `FORCE`
rather than `PREFIX_RULES` — a prefix cannot say "A one value, B another". `BAR1A0` /
`BAR1B0` set that precedent for a two-frame blinking sprite.

So the armors were the one hole in an otherwise complete ladder, and the two new rows
sit on rungs that already existed — 160 is the key rung, 200 the PINV rung. 39 pickups
game-wide (13 green, 26 blue) across 34 maps, roughly one per map: nowhere near the
scale where a per-frame light would matter.

### The light blinks with the sprite, and A is the bright frame

First shipped with a steady light, on the keys' pattern; asked for in play as
*"those armor textures are blinking sprites, any chance to match their light to blink
in time?"*. It costs nothing — the attached light is a property of the **texture**, so
tying it to the frame syncs it by construction: no thinker, no phase to keep, and it
cannot drift.

**The phase is the half worth checking.** Vanilla marks the *B* frame bright —
`ARM1 A 6` / `ARM1 B 7 bright`, `ARM2 A 6` / `ARM2 B 6 bright` — and that is the
opposite of what RT shows. Measured per pixel, A against B:

| | ARM1 | ARM2 |
|---|---|---|
| alpha masks | identical | identical |
| pixels brighter in B | **0** | **0** |
| per-pixel B/A luminance, median | 0.424 | 0.478 |
| whole-sprite output | A = **2.29×** B | A = **2.13×** B |

So B is a flat ~0.44× darkening of the same art — the classic palette-shift blink, a
whole-sprite brightness pulse with no moving highlight in it. Vanilla pairs that
darker paint with `bright` so it reads as a twinkle under sector light. Under RT there
is no such pairing: `forceSpriteUnlitAlbedo` (`rt_draw.cpp`) drops lightlevel from
sprite vertex colour and the path tracer lights the billboard, so the flag does
nothing and what the player sees is the paint. **A is the bright frame on screen**, and
the light follows the screen, not the flag.

The B values are the art's own ratio — 160/2.29 = 70, 200/2.13 = 94. Two things
deliberately do *not* move with the blink:

- **The hue.** Sampled 145.7° vs 147.1° for ARM1 and 214.3° vs 213.7° for ARM2 — the
  same colour either way. A hue that shifted with the blink would read as colour
  flicker rather than a pulse.
- **`emissiveMult`.** It stays 0.6 on both frames because the sprite's own glow is
  `baseColor × emissiveMult` and `baseColor` already carries the 2.29×, so the glow
  blinks in time *for free*. The attached light was the only part that was a fixed
  number, and therefore the only part that needed a second value.

**Rate** is the sprite's own: 13 tics for green (0.371 s, 2.7 Hz), 12 for blue
(0.343 s, 2.9 Hz). That is fast for a light, and the `SMONBA` monitors in
[sequence-light-chains.md](sequence-light-chains.md) are the warning next door — but
those were 199 fixtures pulsing in phase across one wall, and this is 39 pickups over
34 maps, about one per level. If it reads as too busy, raise the B values toward A
(a 1.5× swing is 105 and 133); do not slow it, because the sprite's rhythm is not
ours to change.

**The hex had to be forced, and for once that is load-bearing rather than convention.**
`sample_hex()` returns **`None`** on `ARM1B0`. The B frames are painted *darker* than
the A frames — mean luminance 18.9 vs 43.3 for ARM1, 14.0 vs 29.9 for ARM2 — because
vanilla draws the B frame `BRIGHT` and the darker paint is what stops a fullbright
frame blowing out. With `hx=None` the fallback chain in `main()` lands on `"ffffff"`,
so the green armor would have blinked **green → white**. The values are still derived
from the art, not chosen: peak-normalised brightest decile is `#2EFF88` for ARM1
(H 145.7°) and `#2E88FF` for ARM2 (H 214.3°), and `4488ff` sits within 4° of ARM2's own
hue — the same blue `BKEY`, `BSKU` and `SOUL` already use, which is why the blue armor
now matches the blue key.

Note also that the A/B luminance runs *backwards* from every other pickup here
(`BKEYA0` 36.2 → `BKEYB0` 70.5; `YKEY` 67.7 → 120.0). With one `emissiveMult` across
both frames the armor's own glow therefore dips on the frame vanilla calls bright. That
is left alone: which frame reads brighter is invisible once the sprite is in a
path-traced room, and chasing it would need an `emissiveMult` above 1.0 on the darker
frame.

### `noShadow` came along for the ride, and had to come back off

The first version of this entry copied the pickup profile wholesale, `noShadow: true`
included, and that was reported straight back: *"why that armor sprite now doesnt seem
to cast shadows? e.g. with flashlight on it"*. Correct, and the flag is exactly why.

`noShadow` is not cosmetic and it is not scoped to the sprite's own light:

    TextureMeta.cpp              meta->noShadow  ->  RG_MESH_PRIMITIVE_NO_SHADOW
    VertexCollectorFilterType    that flag       ->  PV_WORLD_1
    VulkanDevice.cpp:599         rayCullMaskWorld_Shadow = WORLD_0 | RESERVED_0

`WORLD_1` is absent from the shadow mask, so the primitive is invisible to **every**
shadow ray in the scene. The flashlight has nothing to do with the armor's attached
light; the flag had taken its shadow too.

**Why the other pickups still carry it.** The attached light is a spherical light
placed at the **quad's centre** (`VulkanDevice.cpp`, the `quad` branch averages the
four vertices), i.e. in the billboard's own plane. Let the billboard occlude and it
shadows its own light across roughly half that sphere's samples — a hard split
through the small pool of light under the pickup, turning with the camera because the
billboard does. That is the same failure as the *"black stripe down the middle of
every enemy in the beam"* in [sprite-shadows-and-ao.md](sprite-shadows-and-ao.md).

**Why the armors go the other way.** They are the largest and lowest pickups, they
lie flat where a flashlight beam actually rakes them, and their light is the weakest
in the table (160/200 against SOUL's 260 and MEGA's 300) — so the missing shadow is
the conspicuous half and the self-occlusion is the subtle one. Pickups are also
explicitly **out** of the sprite-shadow proxy system (*"corpses and pickups keep their
stock billboard shadow, exactly as before the feature"*), so this one flag was the
only thing standing between them and any shadow at all.

Implemented as `KEEP_SHADOW_PREFIXES` in `gen_fx_emissives.py` rather than a fifth
tuple field, so the 100-odd existing rows stay untouched. If the self-occlusion turns
out to be the worse artefact in play, empty that tuple to put the flag back — do
**not** drop `lightIntensity` instead, which is the thing that was asked for.

One propagation trap this exposed: an upsert that merges keys can add `noShadow` but
never remove it, which `upsert_json` already warns about in its own comment. The
entries had to be rewritten **whole** in all six merged/scene JSONs, not merged, or
the flag would have survived in `dist` and the release path after the generator had
stopped emitting it.

### The generator was writing nothing, and said it had

Adding the two `PREFIX_RULES` rows was not enough — the first run reported both armors
in its summary and changed **no file**. `patch_global_inline()` had two bugs that only
bite a name it has never written before:

1. `pat_multi` required a **comma** after `"textureName"`, which a bare entry carrying
   no other fields does not have. `ARM1A0`/`ARM2A0` matched neither the single-line
   pattern nor this one.
2. Both armors then fell to the append branch — and the "drop later single-line
   duplicates" pass that runs immediately after deleted the line it had just written,
   because it dropped *every* match rather than every match after the first.

Fixed in `gen_fx_emissives.py`: the comma is optional, and the dedupe now measures
"later" against the first occurrence of the name in the file. That unblocked 14 more
entries the same bug had been swallowing — `PUNF*` (12) and `SAWG*` (4), siblings of
the `PISF`/`SHTF`/`CHGF` weapon-flash rule block, all `lightIntensity 0` so they glow
without casting — plus `noShadow` on the 47 `RECT*` trail frames.

**Verified from the data**, all nine `textures.json` the game can read — the `fx`
overlay, the merged source, the build dir, `dist`, the release path, and the
`d64rtr_v15_map01` scene overlay in four of those — asserting three things per file:
the hex and the **per-frame** intensity are the intended ones, `noShadow` is
**absent** on all four ARM frames, and `BKEYA0` still **has** it, so neither the
opt-out nor the per-frame light leaked into the rest of the table. Not verified
in-engine.

---

## Case 12 -- Unseen Evil's model beam and HUD-flash name collision

Retribution's Unmaker trail is a family of `UNML` sprite cards, so its existing
texture metadata can make those cards glow and cast. Unseen Evil never draws
that texture: `D64UE_UnmakerBolt` is one stretched OBJ skinned with
`models/beam_unmaker.png`. Mapping more `UNML` names therefore cannot affect it.
The UE compatibility path handles the exact model skin as a screen-emissive,
no-shadow primitive and places three analytic lights along the reconstructed
beam segment. `A_Light1` still drives the immediate world muzzle source, but
that light alone did not reliably illuminate the first-person gun quad. During
the same three-tic edge, the exact UE Unmaker class now borrows the plasma
weapon-glow geometry anchor and places a red light centimetres in front of the
actual `UNMA` quad. Both its content identity and class gate are UE-only;
Retribution and the passive plasma core keep their existing paths.

The opposite failure happened after copying Retribution HUD art into UE.
Texture metadata is global by rendered name, not by the archive the patch came
from. Copied `UNMF` inherited its 900-intensity attached light and cast from the
first-person quad, bleaching the gun and room; copied `CHGF` inherited a screen
multiplier that was too bright under UE exposure. The compatibility package
keeps the exact art/offsets but aliases them to `UEMF` and `UECF`, then retains
`Bright A_Light1` / `A_Light2` in the weapon states. UE's required
`rt_mod_compat 0` also skipped the engine's additive Flash-layer setup, making
the metadata-free `UECF` flame disappear; the exact UE identity now restores
additive composition only for `PSP_FLASH`. This separates visible HUD art from
the analytic world source without changing Retribution's metadata.

Rule: when two mods share a sprite name but use different presentation paths,
do not tune the global metadata until the actual rendered primitive is known.
First-person composites, world sprite trails, and model skins are three
different attachment points even when they depict the same effect.

---

## Tuning

- **Fire too bright / too dim, too twitchy, too still** → the `rt_flame_light_*` cvars in
  Case 7. All live, no rebuild. `rt_flame_light_flicker 0` gives back a steady light
  without giving back the wrong position.
- **Fists too bright / too dim on screen** → `EMISSIVE_MULT` in
  `gen_hand_glow_emissives.py` (currently 4.0; the enemy-glow house value is 2.0), then
  re-run it. No rebuild.
- **Light they throw too strong / weak** → `rt_hand_light_intensity`. No rebuild.
- **Colour** → two places that must agree, both in the generators, never in the engine:
  `COLOR_OVERRIDE` in `gen_hand_light_offsets.py` (the cast light, emitted into
  `RT_HAND_COLOR[]`) and `MONSTERS`' tint in `gen_hand_glow_emissives.py` (the mask).
  Re-run **both**, then rebuild — `RT_HAND_COLOR[]` is compiled in.
  Changing the light colour is the one tweak here that is not data-only.

## Traps for next time

1. **Edit the live `textures.json`, not just the overlay.** Two inert "fixes" this session.
2. **`emissiveMult` cannot light anything.** If a glow lights nothing, look for
   `lightIntensity`; don't raise the multiplier.
3. **Never sample the albedo into an `_e.png`.** Measure the written mask's peak.
4. **Hot-reload is developer-mode only.** `LibConfig().developerMode` gates the
   `FolderObserver`; without it *nothing* reloads, JSON included. And `TryHotReload` only
   swaps textures that already occupy a slot — a brand-new `_e.png` needs a restart
   regardless.
5. **Fixing the JSON without fixing the generator rule is a time bomb.** `LPUF` sat
   fixed-in-JSON / stale-in-`gen_fx_emissives.py` for a whole release. Any hand edit to a
   value a `gen_*` tool owns must be mirrored into that tool in the same commit.
6. **A "too bright / white" light is usually a wrong hue, not a wrong intensity.**
   Pale, low-saturation hexes bleach under path tracing; check the hex against the
   sprite art before touching `lightIntensity`.
7. **`gen_enemy_eye_emissives.py` will regress `BOS2F4F6`.** It is the one frame that
   passes the eye validator, so re-running it hard-replaces that entry with
   emissive-only and overwrites the mask red. The other 39 are untouched. Add a BOS2 skip
   to that script if this needs to be permanent.
9. **A `gen_*` tool reporting an entry does not mean it wrote one.** `patch_global_inline`
   prints from its in-memory `entries` dict, and for a name it has never written before
   it could match nothing, append, and then delete its own append — a clean-looking run
   that changed no file. Diff the JSON before and after, by entry, not by exit code.
10. **Saturation-normalising a dark, low-saturation colour shifts its hue.** Scaling to
   peak 255 multiplies *every* channel equally, so a dark red `(93,28,2)` comes out
   orange. Fine for a channel-dominant colour like BOS2's green; wrong for anything
   muted. Check the sampled hex by eye before shipping it, and pin an override when the
   art's intent and the arithmetic disagree.
