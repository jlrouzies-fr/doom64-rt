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

3. **Both at full strength.** The fix for (2) raised `lightIntensity` ~4.5× and
   `emissiveMult` ~2×, *and* added the ZScript light — and nobody saw the result,
   because `patch_texjson` wrote only the gitignored build tree and the next
   build wiped it every time. The first run with both halves actually alive read
   as far too bright, and the numbers say why: at `emissiveMult` 0.60–1.05 and
   250–650 lm the bubbles were calibrated like a **lava spark** (`LSPK*`:
   0.30–0.70, 100–760 lm) — a white-hot molten droplet — and sat in the top ~15%
   of all 956 emissive sprites in the game, whose median is 0.35–0.40.

**Two things, and conflating them is what made the knob feel dead.** The report
was *"`d64_poison_light` doesn't do anything any more and the bubbles are too
bright"*, and both halves of that were true at once:

| | what it sets | tunable? |
|---|---|---|
| `emissiveMult` | how bright the billboard **looks**. Screen glow; casts nothing. | no — material meta, rebuild with `--emis` |
| `lightIntensity` | light the sprite **throws**. Also meta, also untunable, *and* co-located with the billboard with no `LF_DONTLIGHTSELF` — the white-pill mechanism from (1). | no |
| `d64_poison_light` | scales the ZScript `A_AttachLight` only. | yes |

So the cvar governed the one term that was not carrying the picture.
`lightIntensity` is now **0 on every frame** and the cast light is entirely
`AttachPoisonLight()`'s — tunable, and unable to light its own sprite. That is
not an invention here: it is exactly what the game's **84 flame sprites** do,
`lightIntensity: 0` in the meta and lit by `RT_UploadFlameLights` in C++
instead, for the same reason — meta cannot express a tunable light.

`d64_poison_light` therefore now governs **all** the light a bubble throws, and
its default is back to **1.0**, the value that was actually in play through the
whole period the meta was missing. Every arm pins it, so the arms moved with it.

`emissiveMult` lands at **0.22–0.42** — below the set's median, an order of
magnitude under a torch, and the brief unchanged: a thing you notice on the
surface, not a lamp. It is the one number for how bright a bubble *looks*, and
it is a **rebuild** knob, not a cvar, because material meta cannot be scaled at
runtime — a tinted sprite is a different RTGL1 material with no `textures.json`
entry, the same wall `d64_poison_sat`'s baked rungs exist to get round. It is on
the command line so a level costs one command rather than an edit:

```
tools/.venv-ai/Scripts/python.exe tools/gen_poison_fx.py --apply --emis 0.6
```

`lightColor` is still written even though the intensity is 0, so bringing the
sprite light back is one number and not a re-derivation.

And the light is attached from ZScript rather than declared in GLDEFS because a
GLDEFS light is fixed at parse time — this one has to be tunable.

**Judge it in the dark.** A lit room proves the sprite draws and proves nothing
about whether it emits. `poison-lab.cmd chandark` is the room; `nolight` is the
A/B that separates the two halves.

**Size is not brightness.** Above `rt_dynlight_rsoft` (pinned at 20) a larger
radius is *dimmer*, so `d64_poison_lsize` is clamped under it and brightness
comes from the colour scale instead.

## Under a 3D floor

Since the 3D floors came back (2026-08-23) MAP07's nukage rooms have their
authored bridge decks again, and the bubbles drew **on the metal** —
`screen/poison3Dfloor.png`, the deck by the EXIT signs. The deck hides the
poison, so it has to hide the bubbles.

**It is not a spawn-height bug, and that is worth keeping** because the obvious
reading is that the bubble got clamped up onto the deck. It does not. Out of the
UDMF:

| rover | control sector | slab | target | fluid |
|---|---|---|---|---|
| line 1712, tag 23 | 282, untagged | −30 … 42 | sec 164 | `D64N1_01` at −174 |
| line 837, tag 26 | 169, untagged | −30 … 102 | sec 202 | `D64N1_01` at −174 |

Both `type 1` (plain `FF_SOLID`), `alpha 255`, and these two are the **only**
nukage sectors in the game with a rover over them — MAP11/14/23 are water,
MAP20 is lava, ABS05 is blood. So:

- **144 units of clearance** between fluid and deck top.
- `Actor.Spawn` calls `P_FindFloorCeiling(FFCF_ONLYSPAWNPOS)`, which sets
  `FFCF_3DRESTRICT` and disables the step-up branch of `NextLowestFloorAt`, so
  `floorz` stays on the poison and `ceilingz` becomes the rover's underside.
- The rise is 0.06–0.20 damped ×0.94 a tic — about **3 units** total.

The bubble is exactly where it belongs and is drawn through solid geometry. That
is the same 3D-floor blindness `docs/rt-impact-fx.md` records for every RT
particle system: the renderer contains **no `F3DFloor` iteration at all**, and
every subsystem reads `sec->floorplane.ZatPoint` and nothing else.

So the fix is the game sim's half, which is where this whole effect lives
anyway. `RoofedByRover()` rejects a sample that a solid, plane-rendering rover
stands over, and `d64_poison_roofgate` is the switch. It is correct whether or
not the renderer's half is ever closed, and it takes the tick and the dynamic
light with the sprite.

**`FF_SOLID` *and* `FF_RENDERPLANES`**, both deliberate. An invisible
collision-only rover is not a lid, and neither is a see-through decorative slab
— ABS05's floating blood is `type 7`, and you can see the fluid through it, so a
bubble under one is right. `FF_SOLID` is also the predicate the engine's own
`NextLowestFloorAt` uses for "is this a floor".

**Rejected as a SAMPLE, not as a spawn.** The `continue` sends the ten-try loop
looking for another point, so a partly-decked pool keeps its full density over
the part you can see instead of losing one bubble per covered draw. `hits++`
still fires first, and that is right — the sampler *did* find poison there. The
two numbers stay apart in the instrument, because "the lake is roofed" and "the
sampler cannot find the lake" are different faults:

```
D64PoisonFx: 515 spawned, 1026/1112 samples hit poison (92%), 511 roofed by a 3D floor
```

`spawned == hits - roofed`, always. If that stops holding, something else is
dropping bubbles.

The same gate is in `gen_lava_fx.py`. It changes nothing today — the one rover
over lava is MAP20's, `type 7`, not solid — and it is there so the two liquid FX
cannot drift apart.

### MAP94, and the Stalagtite

MAP07 cannot test this, for the same reason it cannot test anything else here.
`.\tools\poison-lab.cmd bridge` is MAP94: one pool cut in half, a solid rover over
the south half with its top **flush with the walkway** so you walk straight out
over it from the spawn, the north half uncovered as the control, and MAP07's
144-unit clearance reproduced exactly. `nobridge` is the before-picture.

**The Stalagtite under the deck is the point of the map, not scenery.** It
stands on the poison with a light of its own, so it cannot fail to be visible
for a lighting reason, and it is a stock prop rather than a second bubble
because a green dot down there could not be told from a spawned one. It answers
the question this gate deliberately does not:

- hidden → RT occludes ordinary actors under a rover, and whatever loses the
  bubbles is specific to how they are submitted.
- **still visible through the deck** → RT occludes *nothing* under a rover.
  That is 209 rovers in Retribution and 22 water sectors under bridges on MAP11
  alone, and it is a separate, bigger bug to write up — not something this gate
  should be stretched to cover.

## Options > Effects

`d64_poison_bubbles` is the player's switch, and it is the **one archived cvar**
in this family. Everything else here is `nosave` so an A/B arm cannot leak into
the next run; a setting that forgets itself on quit is simply broken, so the
switch is split in two:

| cvar | | |
|---|---|---|
| `d64_poison_bubbles` | archived | what the **player** chose. The menu writes it. |
| `d64_poison_fx` | nosave | the **A/B master**. Arms and labs write it. |

The handler needs both. Merging them would archive the A/B master, and then one
`ab-poison.cmd off` would turn the effect off for good on a machine that never
asked — the exact fault the rest of the family is `nosave` to avoid. The other
half of the same coin: because it is archived, **every arm and every lab launch
pins it to 1**, or a player who turned the effect off in the menu silently kills
every future A/B run.

The page is a `MENUDEF` in the pk3, not in the engine's `menudef.txt`, because
the cvar it drives is declared in the pk3's `CVARINFO` — an engine menu item
bound to a cvar that does not exist when the pk3 is absent is a menu that cannot
draw itself. It appends with `AddOptionMenu ... AFTER "HUDOptions"`:
`OptionsMenu` is declared `protected`, which blocks *replacing* it but not
extending it (`menudef.cpp:703` guards the replace path; `ParseAddOptionMenu`
never checks `mProtected`), and `AFTER` matches on an item's **action**, so the
new page lands with the other option pages rather than below the console and
config commands at the bottom.

It is the first `MENUDEF` in the project, so it is also the shape the next
effect toggle should copy.

## Two tints, and why only one of them is a cvar

The bubbles have two colours and they are set in different places, because only
one of them *can* be moved at runtime.

| | what | how |
|---|---|---|
| the light it **throws** | `d64_poison_tint_r/g/b`, scaled by `d64_poison_light` | **cvars.** Live. |
| the **billboard** itself | `--tint R,G,B` on the generator, applied per channel after the hue rotation | **rebuild.** |

The light is a cvar because it is *built* in `AttachPoisonLight()` rather than
declared in data, so ZScript can put whatever it likes in it. Confirm it is
reaching the light rather than being too small to see — the mistake this project
keeps paying for — with the game's own instrument:

```
.\tools\poison-lab.cmd dense -- +rt_dynlight_debug 1 +d64_poison_tint_r 250 +d64_poison_tint_g 10 +d64_poison_tint_b 200
  near[0] dist=163 owner='D64PoisonBubble' rgb=(250,10,200) r=16 type=0
```

**The sprite's colour has no runtime path at all**, and all three candidates were
checked in the source rather than assumed:

- **Vertex colour.** RTGL1 writes `ShTriangle.vertexColors` (`VertexData.inl:296`)
  and **no shader ever reads it**. Only the *rasterized* path uses a vertex
  colour (`RsWorld.inl:54`), and these bubbles are opaque alpha-tested, i.e.
  traced. A cvar on this would have been inert, and inert looks exactly like a
  value that is too small.
- **`RG_MESH_PRIMITIVE_EMISSIVE_OVERRIDE`.** Carries a *scalar* (`prim.emissive`),
  so it can move how strongly a primitive glows but not what colour it glows.
- **A GZDoom translation.** `RTHardwareTexture` appends a per-translation suffix
  to the RTGL1 material name — it has to, or every translation of a sprite
  collides on one name — so a tinted bubble is a **different material** with no
  `textures.json` entry: it would change colour and stop glowing. Per-actor
  `SetShade` fails from the other end; the RT path never reads it.

That is the same wall `d64_poison_sat`'s baked rungs exist to get round, and the
answer is the same one: repaint the art.

```
tools/.venv-ai/Scripts/python.exe tools/gen_poison_fx.py --apply --tint 1.4,0.8,0.8
```

`--tint` carries into `lightColor` as well as the pixels, so the meta cannot
drift from the art it is supposed to be the light of. It does **not** touch
`d64_poison_tint_*`: those stay the live knob, and at their defaults they are the
green this shipped with.

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
| `d64_poison_light` | `1.0` | scales the bubble's **dynamic light**, which since 2026-08-26 is the *only* light a bubble throws (`lightIntensity` in the meta is 0). `0` turns it off. This is the light that lands on walls — it does **not** change how bright the sprite looks; that is `emissiveMult`, a rebuild knob |
| `d64_poison_lsize` | `16` | that light's radius, clamped to 20. **Size is not brightness** — above `rt_dynlight_rsoft` (pinned at 20) a larger radius is *dimmer*. Brightness is `d64_poison_light` |
| `d64_poison_tint_r` | `40` | the colour of the light the bubble **throws**, before `d64_poison_light` scales it. See [Two tints](#two-tints-and-why-only-one-of-them-is-a-cvar) — this is **not** the billboard's colour |
| `d64_poison_tint_g` | `170` | |
| `d64_poison_tint_b` | `35` | |
| `d64_poison_debug` | `0` | log the sector count, the first three spawn positions, the sample hit rate and the roofed count |
| `d64_poison_roofgate` | `1` | suppress bubbles under a solid 3D floor. `0` is the before-picture — see [Under a 3D floor](#under-a-3d-floor) |
| `d64_poison_bubbles` | `1` | **the only archived one.** The player's switch, Options > Effects. `d64_poison_fx` stays the nosave A/B master and both must be on |

## Arms

`tools\ab-poison.cmd <on|off|dense|sparse|near|far|nodyn|debug|roof|noroof> [1-34]`,
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
| **MAP94** | bridge — a solid 3D floor over half the pool, deck flush with the walkway, MAP07's 144-unit clearance, plus the Stalagtite control underneath. See [Under a 3D floor](#under-a-3d-floor). |

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

**Both copies of `textures.json`, and the second is not optional.** The
generator wrote only `build/RelWithDebInfo/rt/data/textures.json` until
2026-08-26, and that is why every machine had **zero** `PBU*` entries: `build/`
is gitignored and every build re-stages the *tracked* copy over it, so a
build-dir-only meta edit is reverted by the next build and a fresh clone never
had it at all. Nothing errors — the meta simply has fewer entries and the
bubbles quietly stop glowing, which is the "emissive only, looked fine in the
lit lab" failure above happening a second time by a different route. After any
run, `git status Doom64-Retribution/Retribution-RT-Materials/` must not be
empty.

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
