# The Doomguy mugshot, and the HUD around it

Doom 64 replaced the Doom status bar with a numeric HUD, so the `STF*` mugshot
frames were never part of its asset set and Retribution inherits none of them.
The face this adds is generated from a painted sheet, and the HUD it sits in was
rearranged around it: screen-anchored instead of boxed into a 4:3 area, with the
opacity and the layout style exposed as options.

Everything here is generated. Nothing in `d64r-mugshot.pk3` is hand-authored, so
the whole thing can be rebuilt from the source sheet in two commands.

The sheet lives in **`tools/mugshot-art/`** and is tracked in git. It used to sit in
`screen/`, which is gitignored — so the pk3 shipped while the art it derives from did
not, and "rebuilt in two commands" was only true on the machine that made it.

```
py -3 tools\gen_mugshot.py --sheet "tools\mugshot-art\doomguy_grittry-removebg-preview.png" ^
    --raw --grain 0 --sharpen 0 --scale 1 --idle brow --pad 3 --lift 0.5 --out <dir>
py -3 tools\build_mugshot_pk3.py --frames <dir> --scale 1 --pad 3
```

---

## 1. The art was already there, and it is not a sprite

The engine runs Retribution over `doom2.wad`, which carries the **complete
46-lump mugshot set** — `STFST00`–`STFST42`, `STFTL*`/`STFTR*`, `STFOUCH*`,
`STFEVL*`, `STFKILL*`, `STFGOD0`, `STFDEAD0`. They live in the *graphics*
namespace, not `S_START`/`S_END`, which is why exporting sprites finds nothing
and concludes the faces are missing.

Two more pieces were already in place:

- `ACTOR 64DoomPlayer : DoomPlayer` inherits `Player.Face "STF"`, so the prefix
  the mugshot state machine looks for is correct and untouched by the mod.
- Retribution's `SBARINFO` wins the status bar selection over gzdoom-rt's
  `DoomStatusBar_RT` (`shared_sbar.cpp:366` — the PWAD's SBARINFO file index
  beats the statusbarclass file index).

So the missing piece was one `DrawMugShot` line. Everything after that is about
making our own art work in place of the IWAD's.

## 2. Reading the sheet

The painted sheets follow the vanilla layout — 8 expressions across, 5 health
tiers down, `DEAD`/`GOD` on the last row:

```
col   0     1     2     3     4     5     6     7
      EVL   KILL  OUCH  ST0   ST1   ST2   TL    TR
```

That column order was verified against the real doom2 lumps rather than
eyeballed; row 4 matches `OUCH, ST0, ST1, ST2, TL, TR` in sequence, each its own
best match.

**Do not slice the sheet into six equal bands.** The painted rows drift
vertically, so a band edge cuts through faces: one chin gets sliced off while the
top of the head below leaks into its neighbour's crop. `segment_sheet()` finds
connected blobs over the *whole* image and recovers rows from the blob centroids
by cutting at the five largest vertical gaps.

**The alpha threshold is load-bearing.** On the background-removed sheet:

| threshold | result |
|---|---|
| `> 128` | the drop shadow bridges neighbouring heads into merged blobs |
| `> 200` | exactly 42 clean blobs, and the shadow is excluded for free |

**But 200 also shaves hair.** `STFEVL0`'s crown sits at alpha ~124 and was simply
excluded; `STFGOD0`'s is opaque (248) but a *detached* component, so the
largest-blob pick dropped it. Both rendered with a flat, chopped skull. Neither
was a margin problem — both had *more* top room than the frames that looked fine.

`grow_hair()` resolves it with hysteresis: keep the strict threshold to separate
heads, then extend each head into adjacent softer alpha (`> 100`, 3 steps),
**upward only and only above the head's midpoint** so it can never reach the
shadow under the chin. Growing in all four directions instead sprouts nubs off
the ears, and — because the fit preserves aspect — a taller mask scales every
head down.

## 3. Frame geometry

Vanilla keeps frames of different sizes aligned through their `grAb` offsets.
**SBARINFO ignores them**: `DrawGraphic` treats x,y as the top-left and only
applies offsets under the `CENTER` flag (`sbarinfo.cpp:1195`). Left alone, the
face would jump a pixel or two whenever the expression changed, because `OUCH` is
31px tall at offset −1 while the idle frames are 29px at −2.

So all 42 frames are composited onto **one shared canvas** whose geometry
reproduces the offset alignment, and the HUD draws them all at a single fixed
position. `STFB0`–`STFB3` (the 35×31 multiplayer background) must be excluded
from that union or it inflates the canvas by 7px of dead space.

**`--pad` is not cosmetic.** The renderer shaves the outermost row or two of the
destination rect. With the heads flush against the canvas edge — which they are,
since the union is sized by full-height `OUCH` — that shave eats hair and chin.
Every frame carries a 3px transparent border and the draw position moves up-left
by the same amount, so the head keeps its size and its place while the border
absorbs the shave.

## 4. The idle rotation

The engine cycles `{ST00, ST01, ST02}` every 17 tics (`sbarinfo.txt`, mugshot
"Normal"), re-rolling the index because `FMugShot::Tick` nulls the state when it
finishes and the next `SetState("normal")` calls `Reset()`.

The sheet paints those three as one head with **brow variants**: col3 raises the
viewer-left brow, col4 is neutral, col5 the viewer-right. Feeding the three
paintings straight in makes the rotation read as the head swapping identity
(~50% of pixels differ; vanilla's trio differ by 5%). `--idle brow` keeps the
neutral head and its silhouette and blends in only the brow band, feathered at
both seams. The result differs **only in rows 9–16** of 31 and the alpha channel
is byte-identical, so the head cannot move.

`--idle single` is the static version, `--idle sheet` the literal one. Both
`single` and `brow` also borrow the centre frame's *target geometry* — sharing
only the source painting is not enough, because each vanilla frame has its own
alpha bbox and fitting to those shifts the result by a pixel, which at this size
changes half the image.

**Note:** with god mode on (`d64rt-pins.cfg` pins `god`), the mugshot state is
`God { GOD0 -1; }` — a delay of −1 means "stay indefinitely", so the face is
frozen and the idle rotation never runs. That is not a bug in the art.

## 5. Screen-anchored layout

Retribution's HUD is `ForceScaled`, which maps 320×240 into a **centred 4:3
box**. On an ultrawide that box stops well short of the screen edges, so "put the
ammo on the right" can never reach the right of the monitor — x=298 is already
the right edge of the box.

All three `StatusBar` blocks now carry `ForceScaled|FullScreenOffsets`, where a
negative x anchors from the real right edge and a negative y from the bottom
(`sbarinfo.cpp:1284`). Current layout:

```
BATTERY 6 | HEALTH 84 | face 102      [ weapon ]      keys -134·-120·-106 | ARMOR -70 | AMMO -24
                                                      labels -32, values -23, keys -22
```

Keys are one slot **per colour** (red/blue/yellow) rather than a 2×3 card/skull
grid; each slot draws that colour's card and skull at the same spot, and a map
gives you one or the other.

## 6. Two styles, one lump

`d64_hud_style` selects Classic (0) or Modern (1). `FullScreenOffsets` is a
**StatusBar header flag and cannot be switched per branch**, so Classic could not
simply keep its old coordinates — they would be read as offsets from the left
edge and smear across an ultrawide. It is emitted instead using SBARINFO's
`<int> + center` form (`sbarinfo.cpp:164`, `adjustRelCenter`), which offsets from
screen centre: `HEALTH -136 + center`, `Ammo1 0 + center`, `ARMOR 136 + center`.
That reproduces the stock centred arrangement on any aspect ratio.

Both layouts live in the lump; the cvar picks one. Classic has no mugshot.

## 7. Opacity

`StatusBar Normal, ForceScaled, 0.55` — that trailing float is the whole HUD's
**alpha**, not a scale (`sbarinfo.cpp:349` parses it straight into `alpha`), and
it is baked in rather than exposed. The parser demands a float *literal*
(`MustGetToken(TK_FloatConst)`), so a cvar name cannot go there — and a bare `1`
instead of `1.00` aborts startup.

`d64_hud_alpha` (0–100, step 10) works around it: the body is emitted once per
notch, each inside `ifcvarint d64_hud_alpha, N { alpha N/100 { … } }`. **A value
that is not a multiple of 10 draws nothing**, which is why the slider's step must
stay 10.

**The face needs more alpha than the rest to look the same.** It is much darker
than the world behind it (~34 vs ~103 measured), so blending drags it toward the
background far harder than it does the bright text:

| alpha | dark face | bright ammo digit |
|---|---|---|
| 1.0 | 34 | 150 |
| 0.9 | 41 (**+21%**) | 145 (−3%) |
| 0.7 | 55 (**+62%**) | 136 (−9%) |

So the mugshot draws in its own **sibling** alpha block at `hud_alpha ** 0.35`
(0.9 → 0.96). It has to be a sibling: nested alphas multiply, so from inside the
body block the face could only go darker.

## 8. The HUD font has eight letters

`D64HUDFONT` defines exactly `A E H L M O R T` — precisely what HEALTH, ARMOR and
AMMO need. `BATTERY` therefore rendered as ` ATTER `: **B and Y do not exist in
the font** and drew as blanks. Not a length limit.

The pk3 ships the two missing glyphs (`graphics/D64HF066.png`, `D64HF089.png`)
plus a `FONTDEFS` redefining the font with all ten. The format is 6 rows tall,
one fixed grey per row (64, 88, 104, 128, 152, 176 top to bottom) and binary
alpha, so new letters match exactly.

## 9. The battery is a different mod

The meter comes from `d64r-rt-flashlight.pk3`'s ZScript, not the SBARINFO, so it
has to be kept in step by hand. Three couplings:

- **Opacity.** It hardcoded `0.55` to match the old baked-in HUD alpha; it reads
  `d64_hud_alpha` now, with the per-state levels expressed as ratios of that
  baseline so the off/flashing/low dimming is preserved. The *label* draws at
  full HUD opacity and only the meter dims with state.
- **Position.** It derived its x from a hardcoded HEALTH at 24 and clamped to
  −72, i.e. it drew *outside* the 320-wide HUD and relied on the ultrawide
  margin. It is anchored inside now and follows `d64_hud_style`.
- **Scale.** This is the subtle one. `SBarScale = h × hud_scalefactor ×
  (1/ViewportPixelAspect) / 240` (`base_sbar.cpp:385-405`). A plain `sh/240`
  omits the pixel-aspect divisor and draws the battery ~17% large. Reading
  `StatusBar.GetHUDScale()` at runtime is *worse* — it returns `SBarScale` as
  left by whatever draw pass ran last, which came out about half size. It is
  derived analytically instead, with `HUD_ASPECT = 1.098` measured in game. That
  constant is the one number to move if it ever drifts.

## 10. rt/wad cannot be overridden from a pk3

The menu changes (Fluid removed, Quality submenu, HUD Style/Opacity) live in
`rt/wad`, which belongs to the **engine**, not the mod — and it is appended after
every `-file` pwad (`d_main.cpp:1960`), so nothing loaded that way can win
against it. Both `rt/wad` trees are also gitignored.

The tracked master is `rt-wad-overlay/`, mirrored into both trees by
`py -3 tools\sync-rt-wad.py` (`--check` reports drift). The live tree is the one
under `build\RelWithDebInfo` — the launcher `cd`s there before running.

## 11. Knobs

| flag | effect |
|---|---|
| `--scale` | texels per HUD unit; <1 chunkier, >1 finer. Needs a matching TEXTURES `Scale` |
| `--pad` | transparent border, must match between both scripts |
| `--lift` | highlight-preserving brightness; the painting is ~63% of a key icon's mean |
| `--idle` | `sheet` / `single` / `glance` / `brow` |
| `--face-gamma` | mugshot alpha = `hud_alpha ** gamma`; 1.0 disables compensation |
| `--hud-alpha` | build-time whole-HUD alpha (the runtime one is `d64_hud_alpha`) |
| `--debug-grid` | draw all 42 frames at once instead of the mugshot |
| `--colors` / `--flatten` / `--dither` / `--outline` | styling, unused by the shipping build |

Layout positions are constants at the top of `build_mugshot_pk3.py`.

## 12. Limits

- **Tier 3–4 frames are rough.** The source art for the low-health rows is very
  dark with hard red streaks, so `STFST41` converts to a literal red block over
  one eye. Faithful to the cell, not a pipeline fault.
- **The battery's size is derived, not shared.** `HUD_ASPECT` is an empirical
  constant. If GZDoom's viewport pixel aspect changes, it needs remeasuring.
- **Classic's battery position** is computed from the stock HEALTH at 24; if the
  Classic layout is ever moved, that expression moves with it.
- **`d64_hud_alpha` off-step values draw nothing** — see §7.
