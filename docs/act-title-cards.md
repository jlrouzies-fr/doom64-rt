# Act title cards — the fullscreen card on the first map of an act

The card that fades up a second and a half into MAP01, MAP09 and MAP20 and reads
**ACT I / INCURSION**, **ACT II / CITADEL**, **ACT III / HELL**.

It is not a HUD message, not a WAD graphic, and not text the engine draws. It is
a **fullscreen image handed to RTGL1 under a texture name the engine invents at
runtime**, and almost every wrong turn in building it came from not knowing that.
This document is mostly about the wrong turns, because they are all repeatable.

## Before any theory: it is not in the WAD

The card began as a bug report — a cyan **EPISODE III / HELL** in a generic sans,
over MAP21 "Pitfalls". Finding what drew it took an exhaustive and completely
fruitless search, and the search was fruitless for a structural reason worth
writing down:

- The string `EPISODE` does not appear in any lump of `D64RTR_v15.WAD`, in
  `doom2.wad`, in any loaded pk3, or in `rt/wad`. Not as a lump, not in
  `LANGUAGE`, not in the ACS — including after decrypting all 486 `STRE`
  strings, which are XOR-scrambled and invisible to grep.
- The built `gzdoom.exe` contains exactly one `EPISODE` string: `$MNU_EPISODE`,
  the episode-select menu. There is no format string and no roman-numeral
  routine anywhere in `src/`.
- Extracting every game *texture* finds nothing either, because the card is not a
  game texture. It lives in RTGL1's material tree, `rt/mat`, keyed by a name no
  lump ever had.

**One frame contained two rasterisers, and that was the tell.** In the same
screenshot the level-title card ("PITFALLS" / "TIM HEYDELAAR", drawn by the mod's
ACS `script 666 ENTER` with `BIGFONT`/`CR_RED`) had hard, un-antialiased pixel
edges, while the cyan text had a smooth anti-aliased ramp and a flat `#70E8E8`
that matches no entry in GZDoom's `CR_CYAN` ramp. Bitmap font and sampled image,
side by side. The smooth one is an image drawn with `RG_SAMPLER_FILTER_LINEAR`.

## The mechanism

| | |
|---|---|
| `rt_main.cpp:13416` | `RT_InjectTitleIntoDoomMap()` — maps map name to a card name |
| `rt_main.cpp:13294` | `RT_StartTitleImage()` — arms it with begin/end/fade tics |
| `rt_main.cpp:13323` | `RT_DrawTitle()` — uploads, draws, fades, plays the sting |
| `rt_main.cpp:13051` | `RT_RegisterFullscreenImage()` — registers a **1×1 placeholder** |

`RT_RegisterFullscreenImage` hands RTGL1 a one-pixel texture named `title/act3`
with `RG_SAMPLER_FILTER_LINEAR`. RTGL1 then substitutes a real file from disk.
Nothing about that name exists in any WAD, which is exactly why it is unfindable
by lump search.

Timing, all in `RT_InjectTitleIntoDoomMap`: begins at **1.5 s**, total window
**7.0 s**, fade-out **3.0 s**. The fade is the **tail end of the window, not
extra on top** — `RT_DrawTitle` derives alpha from `endtick - maptime`. So the
card is up from 1.5 s to 8.5 s and spends the last 3 s of that fading. It also
dims the whole scene behind itself by `alpha * 0.3` and plays
`sounds/cutscene/boom.ogg` on its first frame.

## Why DOOM II's cards fired on Doom 64's maps

The feature is stock DOOM II RT: `map12 → title/ep2` ("CITY"), `map21 →
title/ep3` ("HELL"), gated on `rt_isdoom2`. And `rt_isdoom2` is set
(`src/d_iwad.cpp:879`) purely because the IWAD autoname is
`doom.id.doom2.commercial` — which **Doom 64: Retribution requires**. So the
Doom II chapter cards fired on Doom 64's maps, at Doom II's act boundaries.
"EPISODE III / HELL" landed on "Pitfalls", which is 94% stone and one of the
least hellish maps in the back half.

### The trap: do not detect the TC with a lump lookup

The obvious second test is "does Retribution's own `DBIGFONT` lump exist":

```cpp
const bool isdoom64tc = fileSystem.CheckNumForName( "DBIGFONT" ) >= 0;  // WRONG
```

It compiles, it looks right, and **it silently returns −1**. The result was a
build that behaved exactly like the unfixed one — old card on MAP21, nothing on
MAP01 — costing a full rebuild-and-launch cycle to discover. A null result from a
name lookup is indistinguishable from "feature not wired".

The working test keys on **where the map lump came from**:

```cpp
extern FString RT_GetMapWadName( const char* mapname );
const bool ispwadmap = !RT_GetMapWadName( mapname ).IsEmpty();
```

`RT_GetMapWadName` (`src/p_openmap.cpp:387`) returns empty for maps out of
doom2.wad — it special-cases the IWAD — and the pwad's name otherwise. This is
the same call `DoLoadLevel` already uses to build `RT_MapName`, so it is
load-bearing production code rather than an assumption about filesystem
namespaces.

Stock Doom II still gets its own `ep2`/`ep3` cards; those files are untouched.

### It says what it did

Every map that could produce a card now prints one line:

```
RT_Title: MAP20 from wad "d64r-seqlight-fix" (mod) -> title/act3
RT_Title: MAP21 from wad "d64rtr_v15" (mod) -> no card
```

This exists because the first attempt produced a silent no-card, and "trigger
never fired" and "trigger fired, image failed to load" looked identical from the
outside. `-> title/actN` with no card on screen means the image; `-> no card` or
no line at all means the trigger, and the printed wad name says why.

## Where the acts come from

Doom 64 ships **no** episode data: no clusters (every map is `cluster = 1`), no
episode definitions beyond campaign select, and `sky1 = "ISUCK"` on every single
map, so sky is not a signal either. Music is 1:1 for MAP01–15, so that is not a
signal. The boundaries were deduced from two things that *are* in the data.

**One authored story break.** Walking `next`/`secretnext` across all maps, the
main campaign has exactly one mid-campaign intermission: `MAP08 → INTER03 →
MAP09`. Everything else is a secret-level gateway or the finale.

**Texture families.** Bucketing every texture and flat in the 25 campaign maps
into Doom 64's three sets — `SPACE*/SFLAT*/SDFLT*` (tech), `C*/CASF*/CTRAK/CDOR`
(stone), `H*/HELLA*/HFL*/HTRAC` (hell):

| maps | tech | stone | hell |
|---|---|---|---|
| MAP01–08 | 99–100% | **0%** | **0%** |
| MAP09–19 | 0% | dominant | 0–44% accent |
| MAP20–24, 28 | 0% | minority | 84 / 5 / 0 / 60 / 96 / 69% |

MAP01–08 are *perfectly* clean — not one stone or hell texture across eight maps
— and that seam coincides with the only authored intermission. Two independent
signals, same boundary. **MAP09 is solid.**

**MAP20 is a judgement call.** Hell bleeds in gradually from MAP12 (5%) through
MAP13 (30%), MAP15 (36%) and MAP17 (44%), takes over at MAP20 (84%), then MAP21
and MAP22 fall back to 94%/99% stone before MAP23 goes hellish again. MAP20 is
the first map where hell dominates outside the MAP11 outlier ("Terror Core", an
88%-hell island mid-run — the portal level). MAP23 is the defensible alternative
and is a one-line change.

Regenerate the table with the bucketing described above if the map set changes.

## The typography

`tools/gen_act_card.py`. **No glyph art was drawn.** `D64RTR_v15.WAD` lump
`DBIGFONT` is a self-describing FON2 binary that GZDoom auto-registers as
`BIGFONT`, and it is the face every stylised graphic in the game was baked from —
`CWILV*` level titles, `E_DOOM64`, `M_EPISOD`, `WIENTER` are all this font
pre-rendered. The script parses it directly:

- height 14 (13 px ink), ASCII 32–122, 12-entry palette, RLE'd glyph bitmaps
- palette index 0 transparent; indices 1–10 are a dark→light vertical gradient
  with a 1 px drop shadow **baked into the glyphs**, so both come free
- recoloured through `#290000 → #CE0000`, which is what the WAD's `TEXTCOLO` lump
  redefines the `Red` range to, precisely so live-drawn `BIGFONT` colour-matches
  the baked `E_*` episode plates

Two layout rules that are not obvious:

- **The title scale is shared, not per-card.** It is solved once from the widest
  of the three titles (`INCURSION`, nine glyphs) so all three cards are set at
  one size and read as a series. Width is the binding constraint, not height.
- **Vertical placement dodges the level-name card.** The mod's ACS card is on
  screen at the same moment at y=80 and y=95 of a 520×400 virtual HUD — the band
  from **19% to 27% of screen height is occupied**. The act card sits at
  36.4%–68.0%.

## Installing the images

RTGL1's loader order (`deps/RTGL/Source/TextureOverrides.cpp`, `Const.h:58-59`)
tries **`mat/<name>.ktx2` first**, and only falls back to `mat_dev/<name>.png`
when `rt/RTGL1.json` has `developerMode: true`. Consequences:

- A `.ktx2` of the same name silently masks a `.png`. `--install` warns if one
  appears.
- The new names `act1/act2/act3` have no `.ktx2`, so the PNGs win with no need to
  disturb the stock `ep2/ep3.ktx2`. **No compressonatorcli in the loop** — which
  matters, because it is not installed on this machine.
- `--install` refuses outright if `developerMode` is false, rather than writing
  files that would never be read.

Written to **all four** material trees, the convention `tools/gen_lava_material.py`
established: `Retribution-RT-Materials/rt/{mat,mat_dev}` is the source of truth
and survives a re-stage of `build/rt`; `build/RelWithDebInfo/rt/{mat,mat_dev}` is
what the launcher actually reads. `mat_dev` is not a scratch folder — a stale
copy there is a bug waiting to happen.

## Reading a KTX2 with no decoder

Worth keeping. To find out what the stock `ep2.ktx2`/`ep3.ktx2` actually said,
with no ffmpeg, no compressonator and no BC7 decoder available: BC7 is a fixed
**16 bytes per 4×4 block**, so a 3840×2160 level-0 payload is exactly a 960×540
grid of blocks. Take the most common 16-byte block (80–87% of these images — the
fully transparent one), mark every block that differs, and print the mask as
ASCII. The lettering appears. `ep3` reads `HELL`, `ep2` reads `CITY`.

## Things that do not work

- **Volume above 1.0 on the sting.** `oalsound.cpp:1332-1333` sets `AL_MAX_GAIN`
  to `SfxVolume` and `AL_GAIN` to `SfxVolume * vol`, so any `vol > 1` clamps and
  does nothing. Making `boom.ogg` louder means amplifying the asset, and there is
  no encoder on this machine (no ffmpeg — the PATH entry is stale — no mpv, no
  `soundfile`). Not attempted.
- **`python` on PATH is mpv's** and has no PIL. Use `py -3`.

## Verification

```
py -3 tools/gen_act_card.py                       # gallery -> screen/act-gallery/
py -3 tools/gen_act_card.py --install             # all three, all four trees
.\tools\build-gzdoom-rt.cmd                       # kill gzdoom first; it locks the exe
.\tools\launch-retribution-rt.cmd 1               # 9, 20 for the others; 21 = no card
```

Check the binary rather than trusting a null result — `title/act1`, `title/act2`,
`title/act3` and `RT_Title: %s from wad` must all be present as strings in
`build/RelWithDebInfo/gzdoom.exe`. Then read the `RT_Title:` line in
`rt-console.log` before judging the card itself.

The build staging step only copies `rt/` when it is absent, so installed cards
survive a rebuild. A `LNK1104` on `gzdoom.exe` means the game is running.
