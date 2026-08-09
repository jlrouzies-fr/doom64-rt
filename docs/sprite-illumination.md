# Making sprites emit light under RTGL1 — torches, Unmaker puffs, Baron-family fists

Reference for how sprite glow and sprite *lighting* actually work in this project,
written after doing several of them in one pass (2026-08-09). Read the three mechanism
sections before touching any sprite emissive — most of the time lost on this went to
mechanisms that look correct and silently do nothing.

## STATUS

| Sprite | What it needed | State |
| --- | --- | --- |
| `A030`/`A031`/`A032` torches | nothing — already correct | verified in the live file |
| `LPUF` Unmaker laser puff | wrong light colour (blue on a red sprite) | fixed, live |
| `TL*` / `TS*` standing torches | **no RT meta at all** — 40 sprites, no light | flame-masked emissive + light, live |
| `BOS2` Hell Knight fists | glow + per-fist analytic lights | implemented, built, verified in-engine |
| `BOSS` Baron of Hell fists | same treatment, red | implemented, built, verified in-engine |
| `BAL2` / `BAL8` projectiles | wrong light colour (violet & green on red sprites) | fixed in every `textures.json` + the generator |

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
| `rt_hand_light_intensity` | `45` | **per fist** — two per knight, so perceived total ~double |
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

GLDEFS lifts these lights `80` (long) / `64` (short) units up, onto the flame. RTGL1
attaches a sprite light at the **centre of the billboard quad** and texture meta has no
offset field — the same wall the `BOS2` fists hit. So the light sits mid-pole, roughly
30 units below the flame on a long torch. Fixing it properly means a real light-upload
path like `RT_UploadHellKnightHandLights`; for a static prop the misplacement is far less
visible than it was on moving fists, so it is logged, not built.

---

## Tuning

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
8. **Saturation-normalising a dark, low-saturation colour shifts its hue.** Scaling to
   peak 255 multiplies *every* channel equally, so a dark red `(93,28,2)` comes out
   orange. Fine for a channel-dominant colour like BOS2's green; wrong for anything
   muted. Check the sampled hex by eye before shipping it, and pin an override when the
   art's intent and the arithmetic disagree.
