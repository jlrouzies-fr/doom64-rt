# The lamp pane, the cage grating, and why three bulbs are broken

**Date:** 2026-08-14 · **Subject:** `SFLATAS`, the ceiling lamp pane, and MAP01's `SPACECM` cage

The short version, for anyone arriving cold:

> A grating casts a legible shadow only when one compact light throws it. Doom 64
> paints `SFLATAS`'s bulbs 32 map units apart — **one metre** — which is wider than
> the grating's openings, so one-light-per-painted-bulb produces N offset copies of
> the mesh shadow that fill in each other's gaps and cancel. The fix is to **break
> three of the four bulbs** in the art and light only the survivor. Nothing moves,
> so the relief maps stay authored and no sector needs panning.

Everything below is a fact that cost a round trip. **Read §1 before touching any of it.**

---

## 1. The traps, in the order they bit

### 1.1 A ceiling flat's world Y is `64 − imageY`

The bulb the PNG draws at image (16, 48) lives at world (16, **16**). X is not
flipped; Y is. Get it wrong and the light lands on a *smashed* bulb one position
away, which on screen is precisely "the lights are misplaced".

This cannot be reasoned out from `BulbLatticeAS = {15.5, 47.5}` — that set is
**symmetric**, so it is consistent with every flip and proves nothing. It was
settled by measurement:

```
tools\shot.ps1 -Map map93 -WarpTo "96 96" -Pitch 40 ^
    -ExtraFiles "d64rshadowlab.wad,d64r-sflatas-broken.wad" ^
    -Extra "+rt_solo_lamps 1 +rt_solo_lamp_radius 0.02 +rt_solo_lamp_intensity 100"
...and the same shot again with +rt_solo_lamps 0
```

Subtract the two frames. The difference **is** the light's contribution, and the
lights-off frame shows only the emissive bulb. They must land on the same pixels.

| offset tried | light landed | separation from the intact bulb |
|---|---|---|
| (16, 48) — the image's own coordinates | left | 1010 px |
| (48, 48) | bottom | — |
| **(16, 16)** | **top, on the intact bulb** | **77 px** (its own halo) |

### 1.2 Materials exist in FOUR places and the game reads the easy one to forget

* `rt/RTGL1.json` sets **`developerMode: true`**, so RTGL1 prefers **`rt/mat_dev`**
  over `rt/mat`.
* `tools/build-gzdoom-rt.cmd:124` **xcopies the tracked `Retribution-RT-Materials\rt`
  over the build tree on every build** — `mat_dev` included.

So writing three of the four dirs holds exactly until the next build. This produced
"the new texture is drawn on top of the old one" through three separate fix attempts:
a stale four-blob `_e` in the tracked `mat_dev` was being composited over the new
albedo, ghosts visible even in the isolation lab. `gen_broken_bulb_flat.py` writes
**all four**. When a material edit appears to do nothing, `ls -la` the same texture
across all four dirs *before* debugging anything else.

### 1.3 Don't move painted geometry if you can change its state instead

The first attempt rebuilt `SFLATAS` as one bulb in the centre of the tile. It works
optically and was a mess: moving a bulb means moving it in the albedo **and** `_n`,
`_h`, `_orm`, then keeping the light on it, then panning every pane so a wall does
not slice the single remaining bulb, then keeping the panning and the light in sync.
Four rounds went into a bug that was really §1.2.

Breaking three bulbs gets the same optics for none of it:

* all four housings still physically exist, so **the authored relief is still
  correct** — `_n`/`_h`/`_orm` are untouched (the generator actively *restores*
  them, in case an earlier run rearranged them);
* the art keeps its original tiling, so **no sector needs an offset** and no light
  has to chase one;
* only `_e` changes, and only to stop the three dead bulbs glowing.

### 1.4 Scope

The instruction was **"IT IS ONLY SFLATAS NOTHING ELSE"**. An earlier round remapped
`SFLATAQ`, `SFLATAP`, `SFLATCH` and `SPACEAZ` onto SFLATAS — wall faces included — to
cure a "both textures visible" symptom whose real cause was §1.2. That machinery is
deleted. `rt_solo_lamp_radius`/`_intensity` are **shared with SFLATCH** and were left
at their pinned values for the same reason; see §3.

---

## 2. Why one light per painted bulb can never work

Measured in the shadow lab (`tools/build_shadow_lab.py` — the same fixture alone in a
dark room, no other light of any kind in the map):

| lights on the pane | source radius | result |
|---|---|---|
| 1 | 0.35 m = 11.2 map units (shipped) | nothing |
| 1 | **0.02 m = 0.64 units** | **crisp diamond shadows on floor, walls and ceiling** |
| 4 | 0.02 | a trace only, until the intensity beats the bounce fill |
| 16 | 0.02 | nothing |

The criterion is *bulb spacing vs occluder feature size*: `SPACECM`'s openings are
~16 units and SFLATAS's bulbs are 32 apart, so `Δ/c ≈ 2` and the copies land a cell
out of phase. A real ceiling of metre-spaced bulbs behind a half-metre mesh washes
out too — this is not a renderer bug.

Corollary: **spreading the bulbs further apart makes it worse.** `SFLATCH` has one
bulb per 64-unit tile (Δ/c ≈ 4) and its 4-bulb configuration washed out harder than
SFLATAS's 16.

---

## 3. What shipped

| piece | where |
|---|---|
| `SFLATAS` → solo light family, offset **(16, 16)** | `SoloBulbTextures`, `rt_lights_fixtures.cpp` |
| broken-bulb albedo + working-bulb-only `_e`, authored `_n/_h/_orm` restored | `tools/gen_broken_bulb_flat.py` → `d64r-sflatas-broken.wad` |
| the A/B | `tools/ab-texswap.cmd <off\|on\|crisp> [map]` |
| the isolation map | `tools/build_shadow_lab.py`, `tools/shadow-lab.ps1` |
| capture aiming: `-Turn`, `-Pitch`, `-WarpTo` | `tools/shot.ps1` |

**The engine entry and the art must ship together.** With the stock four-bulb art the
table lights one bulb and leaves three painted-but-dark; with the new art and no entry,
the lattice puts a light inside three visibly smashed bulbs.

`SFLATDE`'s **verySmall** class (`rt_solo_small_intensity` 45, `rt_solo_small_radius`
0.06) is unrelated to any of this and stays.

### Still open: the pane is dim at shipping values

The shadow wants radius **0.02** (the flashlight's) and intensity **~100**; the pins
carry 0.06 and 45, and at those values the lab room is dark and the diamonds are soft.
Those two cvars are **shared with SFLATCH**, so they were not moved. If the crisp look
is wanted, SFLATAS should earn its own pair exactly as SFLATDE did — that is a small,
idiomatic engine change, not a pin edit. `ab-texswap.cmd on` vs `crisp` is the
comparison.

---

## 4. Current numbers, MAP01

The cage (sector 33, an octagon at (800,96)–(896,192)) shows **one lit bulb**, the
intact one, with the three broken bulbs dark. No panning is applied to any sector and
no other texture is remapped.

---

## 5. The process lesson, which cost more than any of the bugs

**When a report names a place, get the surface from the game.** `whatsthat` exists for
this, it is rule §30 of `rt-lighting-practices.md`, and it was ignored three times in
favour of inferring the texture from a screenshot. Every one of those inferences was
wrong.

Related, and equally expensive: a `whatsthat` at the cage returned `SPACEAF`, which was
written down as fact — but **`SPACEAF` has zero transparent pixels**. The grating is
`SPACECM` (56.2 % transparent). `whatsthat` reports the surface the ray **hit**, which
is the one you meant only if you were aimed at it. Confirm a texture from its pixels
(§17) before building on the name.

And the one this round added: **a screenshot aimed at nothing proves nothing.** Two
captures were taken facing away from the cage entirely before `-Turn` existed. If the
subject is not in frame, the null result is about the camera.
