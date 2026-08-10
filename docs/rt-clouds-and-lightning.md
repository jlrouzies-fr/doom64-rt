# Clouds and lightning

MAP11, "Terror Core", is the only storm level in Doom 64 Retribution. It is
authored as a storm in three separate places, and under RT exactly one of those
three still worked. This is the write-up of finding the other two and putting
them back.

---

## 1. What the map actually does

Nothing in MAP11 *triggers* lightning. There is no timer, no ambient thing, no
polling script. The whole schedule is engine-side, switched on by one keyword.

### The keyword

`MAPINFO`, extracted at `tools/_mapinfo_extract.txt:284`:

```
map MAP11 lookup "D64HUSTR_11" // Terror Core
{
	levelnum = 11
	titlepatch = "CWILV10"
	next = "MAP12"
	secretnext = "MAP12"
	sky1 = "ISUCK"
	cluster = 1
	par = 175
	music = "$MUS_MAP11"
	lightning
}
```

`lightning` is Hexen's, and it spawns `DLightningThinker`
(`src/playsim/mapthinkers/a_lightning.cpp`). No other map in the game has it.

### The schedule

`DLightningThinker::Construct` waits `((rand&15)+5) * TICRATE` — 5 to 20 seconds
— so the level never opens on a flash. After that, `LightningFlash()` picks its
own next wake-up:

| roll | next strike |
|---|---|
| `pr_lightning() < 50` | 16–31 **tics** — the quick second flash of a burst |
| `< 128` and `!(time&32)` | 2–9 s |
| otherwise | 5–20 s |

### What a strike does, in stock GZDoom

`LightningFlash()`, `a_lightning.cpp:104`:

1. Picks `flashLight = 200 + (rand&31)`.
2. Raises **every sector whose ceiling is `F_SKY1`** to that level, plus any
   sector with `Light_IndoorLightning1/2` or `Light_OutdoorLightning`. MAP11 has
   **106** sky-ceiling sectors and **none** of the specials — its sector
   specials are only 1024, 26, 27 and 81. The originals are saved in
   `LightningLightLevels` and restored exactly.
3. Decays for `(rand&7)+8` tics at `ChangeLightLevel(-4)` per tic.
4. Sets `LEVEL_SWAPSKIES`. MAP11 defines no `sky2`, so this does nothing here.
5. **Plays the sound**: `S_Sound(CHAN_AUTO, 0, "world/thunder", 1.0, ATTN_NONE)`.
   Full volume, `ATTN_NONE`, so it is global. `world/thunder` is a `$random`
   alias in the WAD's SNDINFO over `world/thunder1` and `world/thunder2`
   (`DSTHNDR1` / `DSTHNDR2`).
6. Fires the `WorldLightning` event and runs `SCRIPT_Lightning`.

### The two ACS scripts

MAP11's `SCRIPTS` lump (lump 647 of `D64RTR_v15.WAD`):

```c
// Skybox scroll clouds
script 670 OPEN
{
	Scroll_Ceiling(1, 4, 4, 0);
	Scroll_Floor(2, 15, 15, 0);
}

// Lightning effect in skybox
script 671 LIGHTNING
{
	Light_Fade(1, 255, 2);
	Light_Fade(2, 255, 2);
	Delay(3);
	Light_Fade(1, 180, 2);
	Light_Fade(2, 180, 2);
}
```

Both address the same two sectors, a skybox room in the far corner of the map
(`TEXTMAP` sectors 213 and 214):

| sector | id | floor | ceiling | heights | light |
|---|---|---|---|---|---|
| 213 | 1 | `ALLBLACK` | `CLOUDPRP` | 0 → 104 | 180 |
| 214 | 2 | `CLOUDPRP` | `CLOUDPRP` | 96 → 100 | 180 |

Two `CLOUDPRP` sheets, the outer drifting at 4/4 and the inner slab at 15/15 for
parallax, viewed through a `SkyViewpoint` (thing type 9080 at `2688,-192`).
`script 671` is the flash: 180 → 255 → 180 across five tics.

---

## 2. Why two thirds of it is invisible under RT

Sector skybox rooms are **ignored** by the RT path — the white/black box bug;
see `hw_walls.cpp:354` and the comment in `tools/d64r-rt-sky/ZSCRIPT`. Instead
`rt_sky_always` fills every `F_SKY1` opening with the flat night sky, and
`D64RtSkyFix` forces that flat to `MOONSKY` on every map.

So on MAP11 today:

- **the clouds never render.** `script 670` is scrolling a room nobody sees.
- **`script 671` lights nothing.** It brightens two sectors that are not on
  screen.
- the engine sector flash and the thunder sample survive, because neither one
  goes through the skybox.

What you get is a starfield that briefly turns pale, and a bang. The
schedule is right, the sound is right, and everything you would actually *look
at* is gone.

---

## 3. What was built

Both missing pieces, rebuilt as **sky geometry**, which is the one thing the RT
path does render here: `HWSkyPortal::DrawContents` rasterises it into the
cubemap RTGL1 samples on ray miss, so anything drawn there is a real environment
map.

### Clouds — `RT_DrawCloudDeck`, `hw_skyportal.cpp`

A **stack of horizontal discs** over the player, each drawing a different
horizontal **cut** through one 3D density field (`CLOUDV1`..`CLOUDV8` in
`d64r-rt-sky.pk3`, index 1 = cloud base). The disc mesh is built once in
`CreateDome` (`hw_skydome.cpp`) and drawn `rt_clouds_shells` times with a
different model matrix, slice and object colour each time.

**Not layers on the sky dome.** The first version of this *was* two sheets
scrolled around the dome, and that is the one motion a cloud layer must not
have: a dome layer rotates about the viewer, so the clouds visibly orbit, come
round again, and do it identically wherever you stand. A horizontal deck
translates its texture along a fixed wind vector instead — linear, unbounded,
never repeating a lap — and perspective then supplies the rest for free,
crowding distant clouds toward the horizon the way a real overcast does.

**Volumetric** means the shells really are at different heights, so they occlude
each other, parallax against each other as you move, and give the deck a visible
underside and visible tops. It is not N copies of one sheet — that arrangement
produces obvious repeated ghosts. `tools/ab-storm.cmd flat` collapses it to one
shell and shows what the stack is worth.

Geometry, in mesh units, with the model matrix supplying real scale:

```
x,z = f·cos t, f·sin t     f = radial fraction 0..1
y   = -f²                  a shallow BOWL — the rim bends down toward the
                           horizon instead of ending in a hard flat edge
u,v = x,z                  world-planar, so translating (u,v) IS wind
```

`rt_clouds_shear` offsets each shell a little further downwind than the one
below it, so the stack leans. Real cloud decks shear with height, and it is the
cheapest thing here that makes the volume unmistakable — without it the shells
line up vertically and the eye reads concentric rings rather than depth.

`rt_clouds_horizon` (default 9°) is the intuitive control — how close to the
horizon the clouds reach — and the deck's radius and base height follow from it
on a sphere of fixed radius 9200, so the geometry always stays inside the sky
dome's 10000 however the angle is set. Only the ratio matters: this is all
direction from the origin, drawn with no depth test.

### Lightning — `RT_OnLightningFlash`, `rt_main.cpp`

One call added to `LightningFlash()`, next to the `S_Sound` (so it fires even
when the sector flash is suppressed — see below). Each strike picks, once:

- a **bearing** (uniform 0–360) and an **altitude**
  (`rt_lightning_alt_min`..`_max`, 25–55°),
- a **bolt variant**, `BOLT1`..`BOLT4`,
- **1–3 sub-strokes** at 40–140 ms apart, the first at full amplitude and the
  rest at 0.35–0.8.

Strokes combine with **max, never sum**. Summing would make a three-stroke
strike three times brighter than a one-stroke strike, which turns
`rt_lightning_intensity` into a knob whose meaning depends on
`rt_lightning_strokes`. With max, strokes change the *rhythm* only.

The envelope runs on wall clock (`RT_GetCurrentTime`), not tics: it is ~0.5 s
of pure visual, and this way it decays correctly on the pause menu instead of
freezing mid-flash.

Three things then happen off that one envelope:

1. **the bolt** — a quad on the dome at the strike bearing (`RT_DrawSkyQuad`),
   alpha tracking the envelope, so it inherits the multi-stroke stutter for
   free. Cut off below 0.12 rather than faded out: a real channel does not dim
   gracefully, and a ghost bolt hanging in the sky is the one thing here that
   looks obviously fake.
2. **the cloud flash** — each shell re-drawn **additively** at
   `rt_clouds_flash` × envelope, immediately after its own translucent pass.
   Additive because `SetObjectColor` is a multiply and can only ever darken.
   The slice's own alpha gives the pass the right shape for nothing — only
   cloud brightens, the sky between stays black.

   Weighted toward the **lower** shells (`1 - 0.7·f`), because the strike is
   under the deck. Weighting it evenly, or toward the top, makes the whole deck
   flash like a lamp behind a curtain — the one thing here that reads as fake.
3. **the light** — an analytic directional light down the same bearing.

### Why the light has to be separate from the bolt

This is the moon's arrangement repeated, for the moon's reason (see
`rt_moon_geo` and `tools/gen_moon_sky.py`): **RT's sky is a rasterised cubemap
sampled on ray miss and is not importance-sampled.** A bright thing painted into
it is found only by rays that happen to point at it, which at 1 spp is far too
noisy to light a room. The bolt is scenery; `rt_lightning_intensity` is the
source. They agree by construction because both read the same stored bearing.

`tools/ab-storm.cmd nolight` is the demonstration: bolt and cloud flash on,
directional off, and the map barely brightens.

### One directional light. Exactly one.

**This crashed MAP11 on the first strike.** RTGL1's `LightManager::Add`
(`deps/RTGL/Source/LightManager.cpp:461`) answers a second directional light in
a frame with

```cpp
if( dirLightCount > 0 )
{
    debug::Error( "Only one directional light is allowed" );
    return;
}
```

and `debug::Error` exits the game. So the strike does not *add* a light — it
**takes over `SunLightId`**, and the brighter of moon and storm wins the slot.

That is not a compromise. A strike peaks at 2200 against the moon's 90, and the
handover happens exactly where the two are equal, so there is no pop at either
end: the moon's shafts are replaced only while something ~20× brighter stands in
for them, and they come back as the flash decays past the crossing point. Both
ends of every strike cross it continuously. Reusing the id also makes the swap a
parameter change on a light RTGL1 already knows, rather than one light vanishing
and another appearing in the same frame.

### The strike casts real shadows — and one cvar decides whether you see them

It is an analytic directional light handed to RTGL1, not a screen flash, so
every shadow it throws is genuinely ray-traced and genuinely dynamic: barrels,
pillars, the player, monsters, all of it, cast from wherever that strike
happened to be. Nothing extra was needed for that; it falls out of using a real
light instead of a post effect.

What decides how *readable* those shadows are is **`rt_lightning_angdiam`**, the
light's angular size. Read `rt_sun_angdiam`'s note first: a wide disc makes the
shadow test proportional rather than binary, so a pinhole sky leak admits a
sliver instead of a full-strength shaft — at the cost of softening every real
shadow by the same amount.

The first value here was **14°**, picked purely for leak safety, and that was a
mistake worth recording: at 14° the penumbra is so wide at room distances that
the shadows dissolve and the strike reads as a fullscreen brightness pulse — the
light was doing the work and none of it was visible. The default is now **6°**,
which keeps shadows clearly directional while staying 12× wider than the moon.
That margin matters: the strike is ~24× brighter than the moon, so a leak that
is invisible at `rt_sun_intensity 90` is glaring at 2200.

`tools/ab-storm.cmd sharp` drops it to 1.5° for hard, dramatic shadows — worth
trying per map, and worth watching for leaks when you do. `soft` restores the
old 14°.

### Colour, and why the art is grey

`rt_clouds_tint` owns the deck's hue outright, because the slice art is
generated **near-achromatic** — it carries shape and luminance only.

That is deliberate and it was a change: the slices used to be baked cool-blue,
which was fine until the deck had to serve a map with a dark purple skybox.
`SetObjectColor` is a *multiply*, so tinting blue art purple gives a muddy
grey-violet, and there is no tint that can remove a hue already in the texture.
Neutral art means any tint reproduces cleanly — including the old blue, which is
now just the cvar's default (`B4C0DC`).

The tint reaches the **light**, not only the picture. `rt_clouds_transmit` (0.22)
is what a fully covered patch still passes, coloured by the tint, so the
per-channel transmittance is

```
T_c = Π_shells [ (1 - a) + a · tint_c · transmit ]
```

Clear sky passes everything; solid cloud passes a dim tinted remainder. Moonlight
under a purple deck arrives purple, and the shafts it throws are purple with it.
In `rt_main` the luminance of `T` scales `rt_sun_intensity` and the hue (`T`
divided by that luminance) multiplies `rt_sun_color` — split that way because
`RgLightDirectionalEXT` keeps intensity and colour separate, and folding both
into the colour would make a saturated tint quietly dim the light as well.

Lightning is **not** filtered through the deck: the strike is inside or under the
clouds, not behind them.

### Per-map, and opt-in

`RT_CLOUD_PRESETS` in `rt_main.cpp`, the same shape as `RT_MOON_PRESETS` and for
the same reason — one global setting cannot serve 32 maps authored with
different skies. Applied at `RT_OnLevelLoad`, gated by `rt_clouds_presets`, with
the launcher's values captured once so a map with no entry falls back to the
global instead of inheriting the last map's preset.

**The deck is off unless a map is listed.** A cloud layer is not neutral
scenery — it changes what the moon does — so it opts in rather than out.

| map | clouds | why |
|---|---|---|
| MAP01 | **off** | Listed explicitly rather than left to the default, so the decision is on the record. Its moon preset is altitude 90 — straight overhead, light falling vertically through the roof slots, which is the whole look of the map. A deck sits directly across that path. |
| MAP11 | on, `9AA6C8` | The storm. The map the deck exists for. Desaturated cool grey rather than the default blue — the level is lit green-grey and a strongly blue sky reads as a separate scene behind it. |
| MAP14 | on, `8C7AB4` | Purple. Thinner and slower than MAP11: weather, not a storm. |

Each row carries `clouds`, `tint`, `alpha` and `wind`; 0 / negative means "keep
the global".

Authoring loop, same as `moon`'s: set `rt_clouds_presets 0`, tune in game with
the `clouds` CCMD (`clouds on B4C0DC 0.9 0.014`), then type bare `clouds` and
paste the row it prints. Printing the row rather than writing a file keeps the
table a reviewable constant instead of runtime state nobody can grep for.

**One trap this creates.** The table writes `rt_clouds`, `_tint`, `_alpha` and
`_wind` at level load, *after* the command line has been parsed — so on a listed
map it silently overrides `+cvar` pins. That is why every `ab-storm.cmd` arm
except `preset` sets `rt_clouds_presets 0`; without it the `still` arm
(`rt_clouds_wind 0`) on MAP11 comes back with MAP11's 0.014 and looks like the
cvar does nothing.

### Clouds dim the moon

The deck is sky geometry — rasterised into RTGL1's cubemap, never in the
acceleration structure — so it cannot cast a shadow, and the moon's directional
light would otherwise pour through a solid overcast at full strength. That would
make the clouds wallpaper.

So it is computed instead of traced. `RT_DrawCloudDeck` walks the moon's own ray
up through the same shells it is about to place, samples each slice's alpha
where the ray crosses it, and multiplies the transmittances — Beer-Lambert
again, the same model the slice art was baked with, just along one ray instead
of straight down. The product scales `rt_sun_intensity`. Cloud drifting over the
moon really does fade the shafts, and it changes as the wind moves.

Sampling is on the CPU against a cached 64×64 reduction of each slice, not the
full 1024² image: it runs once per frame and the moon is a half-degree disc, so
per-texel precision would be measuring nothing. Bilinear, so the moon's
brightness never steps as the wind crosses a texel boundary.

Two deliberate limits. It is **floored at 0.12** — taking a moon-lit map to zero
is a worse failure than blocking too little. And it is **not** a light cut:
cover changes at wind speed, over seconds, so it must not flush the denoiser,
which is for lights that switch.

`rt_clouds_occlude` scales the whole effect; 0 restores the old behaviour.

### DLSS-RR

A strike is the largest transient light in the game by an order of magnitude, so
`RT_OnLightningFlash` raises `g_rt_lightcut` (`why = "lightning"`) and the frame
flushes RR's temporal history. Without it the flash smears for several frames
after it is over.

---

## 4. The one thing left deliberately as-is

`rt_lightning_sectorflash`, default **on**.

The stock engine flash raises 106 `F_SKY1` sectors to 200+ for ~8–15 tics. Under
RT that is not merely a brightness change: `rt_sector_emis` makes any sector over
the map's threshold a *surface emitter*, so for a fifth of a second MAP11's
entire outdoors radiates with nothing casting it. That is precisely the
sourceless-glow pattern `d64r-seqlight-fix.wad` exists to remove — see
`docs/sequence-light-chains.md`.

It is kept anyway, for two reasons: here there genuinely *is* a source, and it
lasts 0.15 s rather than pulsing forever. But it is the first knob to reach for
if a strike washes out an open area. `tools/ab-storm.cmd nosect` is that
comparison.

One implementation note: the suppression gates the **sector loop only**.
`flashLight` and `LightningFlashCount` are still drawn from `pr_lightning`
unconditionally, so turning the flash off cannot desync the storm's random
sequence — otherwise the cvar would change strike *timing* as well as strike
appearance, and the two arms would not be comparable.

---

## 5. The art

`tools/gen_clouds.py`, packed by `tools/pack_rt_sky.py` into `d64r-rt-sky.pk3`.
It builds one 3D density field at 8×512×512 and writes 8 horizontal slices,
tileable in X and Y only — Z is the cloud's own vertical axis and has hard
limits (clear air below the base, clear air above the tops), so a field that
tiled vertically would put cloud tops directly under cloud bases.

**Threshold by percentile, not by an absolute level.** The textbook cloud remap,
`(n - thresh) / (1 - thresh)`, was tried first and cannot work on this field:
FBM values cluster near 0.5 and essentially never reach 1, so dividing by
`1 - thresh` rescales a narrow band that tops out well below full density.
Interiors come out translucent grey, the deck reads as haze, and turning
`coverage` down to fix the haze *deletes* the clouds instead of solidifying
them — both failure modes are the same bug. A percentile says directly what is
wanted ("this fraction of the sky is cloud") whatever the noise distribution is,
and a `smoothstep` over a narrow band above it gives solid middles and feathered
rims at the same time.

**Base-heavy vertical profile.** The first attempt ramped in over the bottom 18%
of the stack and peaked in the middle, which put the *widest* cut halfway up —
so the underside you actually look at was the thin end of the cloud, and the
deck read as a flat grey slab with no bottom to it. The base is now full almost
immediately and tapers upward.

**Lighting is baked, because there is nowhere to compute it.** RTGL1 rasterises
sky geometry into its cubemap with `RsSky.frag`, a plain textured shader — no
gzdoom material shader runs on the sky at all. So the slices carry Beer-Lambert
transmittance integrated top-down through the density field, a
single-scattering approximation of moonlight from above. That is what gives the
deck lit tops and dark undersides, and it is most of what makes a stack of flat
discs read as cloud. What it explicitly is *not*: no multiple scattering, no
light angle, no horizontal transport. A cloud lit from the side would need the
real thing.

Two lighting terms are therefore left to the engine, because a bake cannot know
them: the per-shell brightness ramp (`rt_clouds_dark`) and the lightning flash,
which comes from *below*.

**Bolts** are straight runs between 5–8 jittered waypoints, not a per-pixel
random walk. A walk that steps x every row produces a frayed rope; real
lightning is a chain of straight sections that change direction at a handful of
kinks. Lateral drift is a *fraction of each segment's own height*, which is the
fix for the first four attempts: with a fixed pixel budget a short run — a fork
near the bottom, with little height left — zigzags sideways across the whole
texture. The halo is two box blurs of the channel mask; a lightning channel is
the one thing in this sky that genuinely is a bloom around a hot line.

`gen_clouds.py` is the only generator in `tools/` that needs **numpy**, so run
it with the venv rather than the bare 3.13 the Pillow-only scripts use:

```
tools\.venv-ai\Scripts\python.exe tools/gen_clouds.py --preview
python tools/pack_rt_sky.py
```

`--preview` writes `CLOUDV_preview.png` (contact sheet of all 8 slices),
`CLOUDSTACK_preview.png` (the slices composited top-down, i.e. what you look up
at) and `BOLTS_preview.png`. None are packed, same rule as
`MOONSKY_preview.png`: a copy under a resolvable name would be an extra, wrong
texture in the archive.

### One trap worth knowing before touching the draw code

`state.SetColor()` **does nothing** on anything drawn out of `FSkyVertexBuffer`.
That buffer declares `VATTR_COLOR`, so the Vulkan pipeline sets `UseVertexData`
and `main.vp` takes `vColor` from the vertex attribute, ignoring `uVertexColor`
entirely. Per-shell brightness and opacity go through **`SetObjectColor`**,
which is a separate uniform applied as `texel *= uObjectColor` (alpha included)
and which also survives into RT — `rt_main` packs `uObjectColor * uVertexColor`
into the primitive colour `RsSky.frag` multiplies in. The deck's radial fade is
the other half: baked per-vertex, where vertex colour *is* what the shader
reads.

---

## 6. Testing

The storm's own schedule makes it useless to sit and wait, so there is a CCMD:

```
thunder
```

Forces a strike on **any** map, including maps with no `lightning` keyword,
because the strike is renderer-side. It drives the same `RT_OnLightningFlash`
the thinker calls, so it exercises the exact path. It does **not** play the
thunder sound — that is `S_Sound` in the thinker, not here.

`rt_lightning_debug 1` prints one line per strike (bearing, altitude, bolt
variant, stroke pattern) and one per frame while the flash is live. It is
`RT_CVAR_NOARCH`, so it cannot stick in the ini the way `rt_rr_reset_debug`
once did.

Arms — `tools/ab-storm.cmd <arm> [map]`, default MAP11:

| arm | what it isolates |
|---|---|
| `full` | deck forced on, preset table off — behaves the same on any map |
| `preset` | the shipping configuration: opt-in per map via `RT_CLOUD_PRESETS` |
| `nocloud` | `rt_clouds 0` — was the cloud deck worth it |
| `flat` | one shell, zero thickness — the volume, removed |
| `thick` | 8 shells at double thickness — the other end of that knob |
| `still` | `rt_clouds_wind 0` — static clouds |
| `nobolt` | light and cloud flash, no visible bolt |
| `nolight` | bolt and cloud flash, no directional light |
| `nosect` | the vanilla sector flash suppressed |
| `hard` | one stroke, fast decay, no cloud flash |
| `sharp` | `rt_lightning_angdiam 1.5` — hard strike shadows (watch for leaks) |
| `soft` | `rt_lightning_angdiam 14` — the old leak-safe default |
| `debug` | `full` + per-strike logging |

---

## 7. Known limits

- **The deck has a rim.** It reaches down to `rt_clouds_horizon` (9°) and fades
  out over its outer rings; below that there is bare sky between cloud and
  horizon. `rt_clouds_curve` bows the rim downward so it recedes rather than
  ending in a line, but the gap is real. In a Doom map the horizon is almost
  always walls, so it rarely shows.
- **Cost scales with `rt_clouds_shells`.** Every shell is a full disc
  re-submitted to RTGL1 and rasterised into all six cubemap faces each frame —
  and twice during a flash, for the additive pass. 5 is the default; 8 is
  available and `flat` (1) is the floor.
- **Only listed maps get clouds.** `RT_CLOUD_PRESETS` is opt-in; MAP11 and MAP14
  are in it, MAP01 is explicitly out. Adding a map is one table row — use the
  `clouds` CCMD's authoring loop above.
- **Cloud occlusion of the moon assumes the deck is flat.** The ray/shell
  intersection ignores `rt_clouds_curve`, because solving against
  `y = h(1 - curve·r²)` needs iteration and the error only matters out near the
  rim, where the deck has already faded to nothing.
- **MAP11's `script 671 LIGHTNING` still runs** and still brightens the two
  skybox sectors nobody sees. Harmless, and left alone: it costs nothing and
  editing the map to remove it would be a change with no visible effect.

## See also

- `docs/moon-and-sky-leaks.md` — the sky dome, `rt_sun_require_sky`, and why a
  directional light in a Doom map leaks
- `docs/sequence-light-chains.md` — the sourceless-glow problem
  `rt_lightning_sectorflash` is the storm's version of
- `tools/gen_moon_sky.py` — the same painted-vs-analytic argument, for the moon
