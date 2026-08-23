# Poison bubbles

Bubbles that swell out of a nukage lake, burst into a ring of droplets, and
throw a little green onto the wall while they do it.

Built by `tools/gen_poison_fx.py` into `Doom64-Retribution/d64r-poison-fx.pk3`.
A/B it with `tools\ab-poison.cmd <arm> [map]`.

## Why this is a mod and not more shader

The same split as the [lava sprays](../tools/gen_lava_fx.py). Everything else
about a fluid is a **surface** — the flat, its relief maps, the light it throws.
A bubble is an **object**: it grows, it leaves the plane of the floor, it pops
and it is gone. That is the game sim's job, not the renderer's.

It also lands on the one place RTGL1 texture meta actually works. `lightIntensity`
in `rt/data/textures.json` gives a **sprite** a light; on a flat it does nothing,
which is the whole reason `rt_lava_light_*` had to be written in C++. So the
bubbles get their glow for free, from data.

## Which floors

The match is the prefix **`D64N`** — `D64N1_*`, `D64N2_*` and the two `D64NUKG`
stills, and nothing else in the texture set.

It has to be a prefix. `D64N1_01` is frame **1 of 64**: the ANIMDEFS sequence
runs `D64N1_01..D64N1_64` and `Sector.GetTexture()` returns whichever frame is
showing this tic. An exact-name match therefore succeeds on one tic in 64, and
the bubbles strobe on and off instead of appearing. Same trap as the animated
flats' relief maps.

Poison floors in Retribution, from the UDMF:

| Map | Sectors | |
|---|---|---|
| MAP07 | 50 | the one map where this is a room rather than a puddle — test here |
| MAP22 | 4 | |
| MAP24 | 4 | |
| MAP18 | 2 | |
| MAP16 | 1 | |
| MAP25 | 1 | |
| MAP34 | 1 | the texture sampler: one pool of each fluid side by side |

## The sprites are sliced, not drawn

`tools/_assets/poisonbubble.png` is authored art — five growth stages and a
burst on one row, with uneven gaps. The slicer finds the occupied column runs
and merges the **smallest gaps** until exactly six clusters remain. That matters
because the burst is a *ring of separate droplets*: it reads as four column runs
of its own and a fixed gap threshold would either split it into four frames or
swallow the last bubble into it. Merging by relative gap size needs no magic
number and survives a redrawn sheet.

Each frame is then cropped to its own bounding box and scaled so the **last
growth stage** is 20 px tall, and that is where it stays — the sprites are never
baked smaller. Shipping draws them at `d64_poison_size 0.35` against a 0.7–1.25
spread, so the biggest bubble is about **9 map units**. Shrinking at *render*
rather than at build keeps the shading and the highlight: baked down to 9 px the
first growth frame would be 2 px and the drawing would be gone.

**The scale is absolute and the spread does not move.** Two rounds of retuning
were lost to the other arrangement — the multiplier baked into the spread *and*
the cvar still defaulting to `1`, so "make it 0.7" meant a different absolute
size each round and the lab's `small` arm drifted underneath it. One number, one
place: `d64_poison_size` is the only thing that sets how big a bubble is. The burst does not set the scale: it is wider than the
bubble it came from, and letting it drive the ratio would shrink every bubble to
pay for it.

Two things the output must get right:

- **`grAb`.** PIL drops the PNG offset chunk, so a sprite written with plain
  `im.save()` is anchored at its top-left and renders sunk into the floor. The
  chunk is written by hand. Growth frames anchor at their own bottom, so a
  bubble meets the fluid where it was spawned. The burst anchors on the ring's
  **centroid pushed down by half the last bubble's height**, so the ring appears
  where the bubble *was* rather than jumping up the moment it pops.
- **Hard alpha.** RT rasterizes these sprites as an alpha-tested cutout: a soft
  edge becomes a hard edge at the 0.5 threshold anyway, and the actor's own
  `Alpha` is never applied. So the alpha is binarised in the tool, at the same
  threshold the renderer will use, and none of the look is left to a
  `RenderStyle` this path ignores. (This is why the lava haze layer had to be
  dropped — see the note at the top of `gen_lava_fx.py`.)

## The spawner

Everything lives in the **EventHandler**, and that is not a style choice. The
lava sprays first put their per-lake emitters in a custom `Thinker` created with
`new(...)`, and its `Tick` never ran — the handler reported the lakes fine and
not one spark was thrown. `WorldTick` is guaranteed to run.

It samples the **poison sectors**, not the world. Each burst it collects the
poison sectors whose bounding box is within `d64_poison_dist` of the camera,
picks one, and draws a point inside it. The `PointInSector` check stays — a bbox
is not the sector, and an L-shaped pool has corners outside it — but it now
rejects the odd corner instead of the entire map.

**The version before it threw a dart at a disc around the player** and kept it
only if it happened to land on poison. Measured hit rate:

| | disc | sector |
|---|---|---|
| lab lake (768×1024) | 17% | 96% |
| lab corridor (192 wide) | 5% | 97% |
| MAP07 | ~5% | 74% |

At 10 attempts per bubble, a 5% hit rate places about 40% of what you asked for,
and places it wherever the disc happened to clip some *other* pool. That is why
the effect looked fine in the lab and dead in the game: the report was a bubble
"1000 from player" while the nukage underfoot stayed still. A lake hides this
completely — **test spawner changes on MAP92, the corridor**, not on the lake.

The residual 26% on MAP07 is real map geometry: bounding boxes of irregular
sectors contain rock. That is the cost of the bbox, and it is cheap.

**Distance and rate are coupled.** Doubling `d64_poison_dist` quadruples the
area the same burst has to cover, so the rate has to go up with it or the near
field visibly thins out.

## The light

The bubble carries a **real dynamic light**, attached from ZScript at spawn with
`LF_DONTLIGHTSELF`, plus the `textures.json` emissive that makes the billboard
itself glow.

Getting here took two wrong answers, both worth keeping:

1. **GLDEFS pointlight per frame.** Every bubble rendered as a **white pill**: a
   light inside a 20-unit billboard is at zero distance from it, so the sprite lit
   *itself* into clipping and the art was gone. The lava spark survives this
   because it is 6 px and is meant to read as a white-hot dot.
2. **Emissive only.** Dropping GLDEFS and leaning on `emissiveMult` /
   `lightIntensity` looked right — in the *lit* lab. In MAP93, the same corridor
   at lightlevel 0 with nothing else in it, the bubbles were dull olive dots on
   black nukage casting **nothing**. The "glow" signed off earlier was the ceiling
   grid lighting their albedo. That is the "no light on MAP07" report exactly.

`LF_DONTLIGHTSELF` is what makes both work at once: the bubble lights the room
and not its own billboard. And it is attached from ZScript rather than declared
in GLDEFS because a GLDEFS light is fixed at parse time — this one has to be
tunable, which is what `d64_poison_light` is for.

**Judge it in the dark.** A lit room proves the sprite draws and proves nothing
about whether it emits. `poison-lab.cmd chandark` is the room; `nolight` is the
A/B that separates the two halves.

**Size is not brightness.** Above `rt_dynlight_rsoft` (pinned at 20) a larger
radius is *dimmer*, so `d64_poison_lsize` is clamped under it and brightness
comes from the colour scale instead.

## Knobs

Declared in the pk3's `CVARINFO`, all **`nosave`** — an A/B knob that persists
means the next run silently inherits whichever arm was tried last, and a null
result gets blamed on the change instead of on the leftover value.

| cvar | default | |
|---|---|---|
| `d64_poison_fx` | `1` | master switch |
| `d64_poison_rate` | `2.0` | multiplier on a base of 3 bubbles per 9 tics, so shipping is **6 per 9 tics**. Fractional works: the remainder is the probability of one more |
| `d64_poison_dist` | `1100` | draw distance, in map units |
| `d64_poison_size` | `0.35` | **absolute** scale on the per-bubble spread (0.7–1.25), where `1` draws the sprite at its authored 20 px. It multiplies the whole spread, so raising it makes a bigger lake, not a uniform one. Clamped at 0.05 — a zero-scale bubble is invisible but still ticks and still lights, which reads as a broken effect; `d64_poison_fx` is the off switch |
| `d64_poison_z` | `1.0` | where the bubble's **foot is drawn**, relative to the fluid plane. **Negative sinks it into the surface** — the useful direction, since a bubble that breaks the plane reads better than one resting on it |
| `d64_poison_sat` | `1.0` | colour saturation **relative to shipping**. Five baked rungs — `0` grey, `1` matched to the pool, `2` roughly the original art. See below |
| `d64_poison_light` | `0.1` | scales the bubble's **dynamic light**. `0` turns it off. This is the light that lands on walls |
| `d64_poison_lsize` | `16` | that light's radius, clamped to 20. **Size is not brightness** — above `rt_dynlight_rsoft` (pinned at 20) a larger radius is *dimmer*. Brightness is `d64_poison_light` |
| `d64_poison_debug` | `0` | log the sector count, the first three spawn positions, and the sample hit rate |

## Arms

`tools\ab-poison.cmd <on|off|dense|sparse|near|far|nodyn|debug> [1-34]`,
defaulting to MAP07. Each writes `rt-poison.log` rather than `rt-console.log`,
so an unrelated launch cannot destroy the evidence before it is read.

`nodyn` is the one that found the blowout: `rt_dynlight 0` kills every dynamic
light in the game. The bubbles kept glowing and kept tinting the pool, which is
what proved the sprite meta was carrying the light on its own and the GLDEFS
lights were pure loss.

## Verifying it is live

At level load the log must carry:

```
D64PoisonFx: 50 poison sector(s), 3 bubble(s) every 9 tics near the player
```

No line means either the pk3 is not loaded or MAPINFO did not register the
handler — a ZSCRIPT lump does **not** register an EventHandler on its own, it
needs `GameInfo { AddEventHandlers = ... }`. `AddEventHandlers` appends rather
than replaces, so this coexists with `d64r-lava-fx.pk3`'s line. Nothing about
rate or distance can help until that line is there.

## The lab

`toolsuild_poison_lab.py` → `d64rpoisonlab.wad`, driven by
`tools\poison-lab.cmd <dark|lit|nowater|dense|still|big|small|sunk|nodyn>`.

MAP07 has 50 poison sectors and is therefore the obvious place to test this, and
it cannot answer the question. Its nukage is at z = -256, in pits: the spawner
logged bubbles 583–810 units away and 256 units *below* the player, where a
20-unit sprite is two pixels. "It does not work" and "it works and you cannot
see it" produce the identical screenshot there. That is what the first round of
this feature was judged on.

The lab is one room with one pool, the surface at eye level 128 units in front
of the spawn, and nothing else in it:

| | |
|---|---|
| **MAP90** | dark — lightlevel 0 and **not one light thing**. Whatever green lands on the wall came from a bubble. |
| **MAP91** | lit — lightlevel 160 and a ceiling grid. Read the sprite as a shape: size, growth, whether the burst reads as a burst. |
| **MAP92** | channel — the same room with the poison as a 192-unit **corridor** instead of a lake, which is the shape the real maps have. The lake is a comfortable test and hides sampler bugs; this one does not. |

**The probe row is the first thing to read.** Six static bubbles, one locked to
each frame, stand down the west walkway (`D64PoisonProbe`, DoomEdNum 9910,
`args[0]` picks the frame; 9911 runs the whole cycle on a loop). They are the
control the spawner cannot give you:

- six green bubbles → the sprites load and the `grAb` offsets are right;
  anything still wrong is the spawner or the water surface, not the art
- six `!` placeholders → GZDoom never found `sprites/PBUB*.png`, and nothing
  downstream matters
- nothing at all → the pk3 is not loaded or ZSCRIPT failed; read
  `rt-poison-lab.log` before touching anything else

They stand on the walkway **floor** on purpose: a probe floating at an arbitrary
height would hide exactly the offset bug it exists to catch.

The `nowater` arm exists because the RT log tags every `D64N1` frame as
`RG_MESH_PRIMITIVE_WATER, liquid 1 (nukage)`, and a sprite spawned one unit
above a water surface could plausibly be occluded by it. It is not — the bubbles
render fine with the tagging on — but that had to be ruled out rather than
assumed, and the arm stays for the next time something on a fluid surface
disappears.

## Colour: matched to the pool, and why it's a ladder

The first pass read as too vivid next to the poison, and the numbers agreed.
Measured off a lab frame (MAP91, `dense`):

| | hue | sat | val |
|---|---|---|---|
| pool | 105° | 0.40 | 0.25 |
| bubble, before | 98° | 0.73 | 0.60 |

1.8× the pool's saturation and 7° off its hue. Shipping now rotates the hue onto
105° — a **rotation**, so the art's own variation survives, since the highlights
run yellower than the body — and scales chroma by 0.575 onto the pool's. Value
gets a 1.06 nudge so desaturating doesn't read as dulling; the bubbles still sit
around 2× the pool's brightness, which is the "just a bit brighter" half.

**Do not sample the flat for this.** `D64NUKG1`, the patch `D64N1_01` is built
from, is nearly black — mean RGB `4,12,1`, value never above 0.22. Almost all
the green you see is the RT water shader on top of it, so the albedo tells you
nothing and the reference has to be a rendered frame.

**Why five baked rungs instead of a dial.** Tinting a sprite at runtime means a
GZDoom translation, and `RTHardwareTexture` appends a per-translation **suffix**
to the RTGL1 material name — it has to, or every translation of a sprite
collides on one name and RTGL1 keeps the first. A translated bubble is therefore
a *different material*, with no `textures.json` entry: it would change colour and
**stop glowing**. Per-actor `SetShade` fails from the other end — the RT path
never reads it. So each rung is its own sprite set with its own meta, baked at
build time, and `d64_poison_sat` picks the nearest. To land between two rungs,
move one in `SAT_SETS` and rebuild.

`lightColor` is retinted with the art, per rung. A grey bubble throwing saturated
green light is the one combination that can't happen in the world, and the grey
rung exists precisely to answer "where is the green coming from".

## Why `d64_poison_z` is a SpriteOffset

Negative values did nothing at first. The bubble was spawned at `floorz + z`, and
`P_ZMovement` clamps an actor to `floorz` on its first tic — every bubble asked
to sit below the surface was pushed straight back onto it. The actor now spawns
*on* the plane and the offset goes to `SpriteOffset.Y`, which is added directly
to the sprite quad's world z (`hw_sprites.cpp`: `z1 += offy; z2 += offy`) with no
clamp anywhere, so it works in both directions.

## The hit-rate instrument

`d64_poison_debug 1` prints, once a second:

```
D64PoisonFx: 93 spawned, 93/125 samples hit poison (74%)
```

The spawn-position lines only print for the first three bubbles, and "nothing is
happening" and "one sample in twenty lands on poison" look identical from inside
the game. The rate is the number that tells them apart, and it is what turned a
guess about MAP07 into a measurement.

One trap, paid for once: the counter field must **not** be called `tries`. The
sampling loop already declares `for( int tries = 0; ... )`, which shadows it — the
counter reads 0 forever *and* the loop quietly runs half its attempts per bubble.
The instrument reported `18/0` before that was spotted.
