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
