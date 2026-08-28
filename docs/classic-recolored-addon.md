# Classic recoloured Cacodemon and Pain Elemental — the optional add-on

Off by default. Not shipped, and not in this repo — it is someone else's art, so you
download it yourself. [**D64ClassicRecolored**](https://www.moddb.com/games/doom-64/addons/d64classicrecolored)
repaints Doom 64's Cacodemon and Pain Elemental in classic Doom hues. Underneath it is
Retribution's own artwork — all 69 frames are the same drawing, pixel for pixel, 100%
silhouette match — so it drops straight in.

Put the wad in `Addons\` and the startup window grows a **Classic recoloured Cacodemon /
Pain Elemental** checkbox. It is loaded exactly as downloaded; nothing here modifies or
redistributes it.

## Which of the two files

The download offers a plain wad and an `_OffsetFix` one, with identical art and different
sprite offsets. Both were cut for Doom 64 CE, whose offsets are not Retribution's, so
neither is exactly right here:

| | Cacodemon | Pain Elemental |
|---|---|---|
| `D64ClassicRecolored.wad` | **exact** on all 36 live frames; 4 death frames up to 13 px high | floats 15–30 px high |
| `D64ClassicRecolored_OffsetFix.wad` | whole animation sits 5 px low | within 10 px |

**Take the plain wad** unless the Pain Elemental's hover height bothers you. The
Cacodemon is the one you spend the game looking at and it comes out pixel-exact, while
both monsters fly — there is no ground contact to give a vertical offset away, and the
Pain Elemental dies in a mid-air explosion.

## Why there is no patch pk3 for the offsets

Two routes exist and both are dead ends, recorded here so nobody spends an afternoon on
them:

- GZDoom's own sprite-offset lump, `SPROFS`, only adjusts sprites that come from the
  **same file as the lump** (`wadno == ofslumpno`, `texturemanager.cpp`). A companion pk3
  cannot reach into their wad.
- Redeclaring the sprites in `TEXTURES` with the right `Offset` looks like it works, and
  silently does not. The patch reference is self-referencing, and gzdoom resolves that by
  scanning the texture list from the **oldest** end — which is Retribution's original
  sprite, not the add-on's. The recolour would simply never appear, with nothing in the
  log to say so.

Correcting the offsets properly would mean recutting their frames onto Retribution's
canvas, which puts their pixels in our files — so it is not done here. One RT-side detail
comes with the same trade: their frames are trimmed 1–7 px narrower than the `_orm`
material maps in `Retribution-RT-Materials`, and RTGL1 samples `_orm` with the albedo's
UVs, so the roughness/metal map is squeezed by a few per cent across those sprites.

## What we add on top: the fireball

The add-on is 71 lumps and **not one of them is BAL2**. It repaints the Cacodemon and
the Pain Elemental and stops there, so a classic-hued Cacodemon went on throwing Doom
64's own orange fireball — the one thing about it the player looks straight at.

`Doom64-Retribution\d64r-caco-ball-recolor.pk3` is our BAL2, and it is loaded **only when
the box is ticked**: the launcher hangs it off `RECOLORARGS`, the same variable the
add-on wad itself rides on, so it appears and disappears with the recolour and never
touches a default install. It is generated from **Retribution's** sprite by
`tools\gen_caco_ball_recolor.py` — none of the add-on's own pixels are read, copied or
redistributed, which is the same line the rest of this page draws.

The look, all ten frames (`BAL2 ABC` flight loop, `D`–`J` burst):

| | |
|---|---|
| core | untouched — the fire stays fire |
| midtones | violet, which is the hue classic Doom's own BAL2 carries around its rim |
| fringe and flying speckles | blue |

Three things the generator has to get right, each of which fails silently:

- **`grAb` survives.** These lumps are PNGs with sprite offsets in a `grAb` chunk and PIL
  drops it on save. The chunk is lifted out of the source bytes and spliced back in
  before `IDAT`; without it the ball renders sunk and off-centre and nothing warns.
- **The gradient runs on the silhouette, not the palette.** A palette-only remap is
  tempting — the 13-entry ramp really is a luminance ramp, and the `IDAT` would stay
  byte-identical — but a palette has no idea *where* a pixel is. The dark maroon that
  fills the gaps inside the burst would turn into blue confetti scattered through the
  fire. What "extremity" actually means is distance to the transparent edge, so a chamfer
  distance transform drives it, with luminance as a second, weaker term.
- **Luminance is preserved.** Every recoloured pixel is scaled back onto the source
  pixel's luma (×1.05 violet, ×1.15 blue so the fringe still reads as a halo). The hue is
  swapped; the drawing is not touched.

The silhouette, the frame sizes and the offsets are asserted identical to Retribution's
after the round-trip. The recoloured art needs no metadata of its own: `textures.json`
keys BAL2 **by name**, so the existing `emissiveMult 0.35` / `lightColorHEX ff5a28`
entries apply to it unchanged — the ball goes on casting the warm light its **core**
emits, and the blue fringe glows blue on its own through the emissive multiplier. What
the RT side does add is the other half of that light and the fire the ball leaves behind;
both are below.

Comparison sheet, regenerated with the art: `tools\_caco_recolor\bal2-blue-fringe.png`.

## The RT side: the light it throws, and the fire it leaves

Both follow the sprite, and both are on **only when the pk3 is** — `RT_CacoBlueFire()`
asks the file system whether `d64r-caco-ball-recolor.pk3` is loaded, which is the launcher
answering the tick-box. Nothing is pinned to say so: a pin carrying the same fact is a
second source of truth, and it goes stale the first time somebody unticks the box.

**The gate says which way it went, once per session, in `rt-console.log`:**

    RT caco fire: d64r-caco-ball-recolor.pk3 loaded -- ... burns half blue
    RT caco fire: no d64r-caco-ball-recolor.pk3 -- ... stays all red

That line exists because the lookup shipped wrong once and there was nothing to catch it:
`CheckIfResourceFileLoaded` compares against `ExtractBaseName( name, true )`, whose second
parameter is **`include_extension`**, so it wanted `"…-recolor.pk3"` and answered *not
loaded* to the stem. The pk3 was loaded, the sprite was blue, and every impact flame came
out red with nothing anywhere saying why. `adding …recolor.pk3, 11 lumps` in the log did
not catch it either — that proves the file is there, which was never the thing in doubt.

### The ball in flight — two lights, because one light has one colour

Red-and-blue out of a single sphere light is not a thing, so the mix is two lights adding
at the ball:

| | source | colour | intensity |
|---|---|---|---|
| the core | RTGL1's attached light, from `textures.json` `BAL2*` | `ff5a28` | 900 |
| the fringe | the ball's own GLDEFS light, recoloured in `rt_lights_sector.cpp` | `3164ff` | `rt_fire_caco_blue_light`, 450 |

The warm half is **keyed by name and cannot be made conditional** — `MakeTextureName`
returns `BAL2A0` whether that sprite came from Retribution's WAD or from our pk3, which is
also why the recoloured art keeps its emissive and its light with no new metadata. So the
conditional half is the cool one, and rather than adding a light it recolours the one the
ball already carries (`CACOBALL`, and `CACOBALL_X1`–`X5` down its death frames): right
position, right lifetime, id already assigned.

**Recolouring it alone is invisible, and that is the trap.** `CACOBALL`'s 64-unit radius
lands at about **49** after `rt_lights_sector`'s arithmetic — clamped to `rt_dynlight_max`,
then scaled by `(rt_dynlight_rsoft / hi)²` — against the attached light's 900. A hue swap
on a light eighteen times dimmer than its neighbour does nothing you can see, and **radius
cannot buy it back**: above `rt_dynlight_rsoft` a wider light is a *dimmer* one, and under
`rt_dynlight_minradius` it is dropped outright. Hence an absolute intensity override
rather than a multiplier. The blue rides the ball's own death ramp, so it fades on the
curve `CACOBALL_X1`–`X5` already draw instead of snapping off at the burst.

### The impact — half red flames, half blue

Seven flames on the mark (`rt_fire_count`), **alternating by index**: four red, three blue.
Alternating rather than hashed, because at seven a fair coin per flame deals 6-1 or 7-0
about one mark in eight, and "half blue" that is occasionally all red is a bug report.

The one light a fire mark is allowed is the **average** of the two ramps, which lands on
the violet the ball's own midtones pass through — so the wall reads as lit by both halves
rather than by whichever flame happens to be index 0. Each flame's own halo keeps its own
colour.

The blue ramp is the red one run through the recolour's own `cold_twin`, the same
transform that put the blue on the sprite: retune the recolour and the flames follow.
`py -3 tools/gen_caco_ball_recolor.py --ramp` prints the table, and refuses to emit a
stale one if the header's red ramp has moved under it.

Knobs: `rt_fire_caco_blue` (1 follow the add-on, 0 never — the honest before-picture, 2
always, even without it) and `rt_fire_caco_blue_light` (0 leaves the ball's red light
alone). The full account, including why the blue ramp is derived rather than read off the
art the way every other fire ramp is, is `docs/plan-projectile-impact-fx.md` §9.8.

### Reaching it from the dev tree

`tools\launch-retribution-rt.cmd` **loads the fireball pk3 by default**, which the
shipped launcher deliberately does not. The two disagree on purpose: everything on this
page is gated on that pk3 being loaded, so with it absent none of it is reachable from a
dev launch and "is the blue half working" cannot be asked at all. Two switches, and they
are independent — the fireball is Retribution's own sprite repainted and stands on its own
against the stock Cacodemon:

| | |
|---|---|
| `D64RT_CACOBALL=0` | the shipped default: stock orange ball, red fire |
| `D64RT_RECOLOR=1` | add the ModDB monster recolour on top, if you have it |

Colours, ramps and a mark drawn with the game's own flame sheet:
`tools\_caco_recolor\bal2-impact-fire.png`.
