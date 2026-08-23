# The fire skies

**Status:** two things exist now, and they are **alternatives, not stages**.
Since **v0.1.14 it is §3a that ships**, and §2 is what you get with it off.

- **§2, the fallback.** The five hell maps keep the WAD's own animated fire dome
  and it was a *number* that was wrong: `rt_sky` 1.2 / 2.7 → **175 / 400**, five
  rows of `RT_MOON_PRESETS`. Shipped, judged in play on MAP23. Reached with
  `rt_fireskies_new 0`.
- **§3a, `rt_fireskies_new` — SHIPS ON since v0.1.14.** A different sky for the
  same five maps: the dome swapped for volumetric clouds with fire in the gaps
  and cascades falling out of the cloud base (`rt_firesky_vclouds`, and the
  `rt_vclouds_fire*` / `rt_vclouds_cascade*` block in the pins).
  **The cvar's compiled default is `false` and `tools/d64rt-pins.cfg` pins it to
  1** — the pin is what ships, so do not read the default as the shipped state.
  This doc said "ships off" over a pin of 1, and a v0.1.14 release note was
  drafted from it before the pin was checked.

§1 is measured. §4 onward remain proposals; §5 in particular is untouched by
either of the above and is now the biggest single win left for the default sky.

**The complaint, from play (2026-08-23):** the levels are path traced, and then
there is a fire sky behind them that emits no light and looks weird.

Both halves of that are separately true and they have separate causes. The
"emits no light" half is probably a *number*, not a missing feature, and it is
worth spending one launch on before building anything (§2). The "looks weird"
half is the art and the way the dome maps it, and no amount of light fixes it.

Related: [`docs/rt-clouds-and-lightning.md`](rt-clouds-and-lightning.md) — the
sky-geometry deck, the painted-vs-analytic argument, and the generator loop this
would follow; [`docs/moon-and-sky-leaks.md`](moon-and-sky-leaks.md) — why a
directional light in a Doom map leaks; [`docs/plan-light-shafts.md`](plan-light-shafts.md)
— the froxel volume the shafts live in, and the point-light-cannot-leak
argument this reuses in §4.

---

## 1. What is actually there today, measured

Five maps: **MAP22 / MAP24 / MAP28** on `FRSKYNRM` (orange), **MAP23 / MAP32**
on `FRSKYGRN` (green). Chosen by `D64RtSkyFix::SkyForMap` in
`tools/d64r-rt-sky/ZSCRIPT`, because Retribution's own `MAPINFO` says
`sky1 = "ISUCK"` on all 34 maps and the real sky is a skybox room the RT path
never draws.

Two more complete families sit unused in `D64RTR_v15.WAD` and are referenced by
nothing — no map, no MAPINFO, no ZScript case: **`FRSKYRED`** (`SKY-R052`…`R151`)
and **`FRSKYBLU`** (`SKY-B052`…`B151`). `FRSKYRED` is the brightest of the four.

### The art

`TEXTURES` composites each one from a single patch, `Texture FRSKYNRM, 63, 128`.
`ANIMDEFS` then runs 100 frames at 2 tics — `SKY-0052`…`SKY-0151`. `hw_sky.cpp`
fetches the sky with `GetGameTexture(tex, true)`, so the flipbook does run on
the dome.

Frame 052 of each family, and the `F_SKY1` dummy:

| texture | size | mean RGB | bottom-25% rows |
|---|---|---|---|
| FRSKYNRM | 63×128 | 108, 65, 17 | 197, 173, 65 |
| FRSKYGRN | 63×128 | 37, 62, 0 | 93, 114, 0 |
| FRSKYRED | 63×128 | 110, 32, 0 | 234, 80, 0 |
| FRSKYBLU | 63×128 | 0, 37, 110 | 0, 93, 233 |
| F_SKY1 | 64×64 | 8, 8, 14 | — |

`F_SKY1` is **not a sky**. It is the placeholder ceiling flat that means "show
sky here"; that is why `whatsthat` names it and why it looks like nothing.

### Two numbers that decide everything downstream

**Vertical energy distribution**, per-row luminance of `SKY-0052`:

| rows | mean Y | share of total |
|---|---|---|
| 0–31 (top quarter) | 0.1 | **0.0 %** |
| 32–63 | 18.8 | 6.7 % |
| 64–95 | 94.8 | 33.3 % |
| 96–127 (bottom quarter) | 170.4 | **60.0 %** |

`FRSKYGRN` is flatter but the same shape: top half 11.1 %, bottom quarter 48.2 %.

The art is black at the top and burning at the bottom. **All of its energy is
within a band at and below the horizon** — which in a Doom map is the one part
of the sky that walls block.

**Horizontal tiling.** `FSkyVertexBuffer::SetupMatrices`
(`hw_skydome.cpp:523`):

```cpp
if (xscale == 0) xscale = texw < 1024.f ? floorf(1024.f / float(texw)) : 1.f;
...
textureMatrix.scale(mirror ? -xscale : xscale, yscale, 1.f);
```

`texw` is **63**, so `xscale` is **16**. The fire sky is wrapped **sixteen
times** around the dome — one copy every 22.5° of azimuth, each 63 texels wide.
Every other sky in this game is 1024 wide and gets `xscale 1`; that is the whole
reason `tools/gen_d64_skies.py` bakes everything at 1024×128, so the horizon
does not move from map to map. The fire skies are the exception and nobody
noticed, because at 63 px the repeat reads as noise rather than as a pattern
until you look for it. The wrap is also not seamless: `FRSKYNRM`'s column 0 vs
column 62 differ by a mean of **12.3/255** per channel, so there are sixteen
faint vertical seams.

That is most of "looks weird" on its own: a 63-pixel image, stretched 240/128
vertically, repeated sixteen times, upscaled across the whole sky, on a renderer
whose entire pitch is that it resolves detail.

### What lights the level on those maps

Nothing analytic. `RT_MOON_PRESETS`, `rt_presets.cpp:155-163`:

```cpp
{ "map22", -1.f, -1.f, 0.f, false, 1.2f, "Fire sky. Moon off entirely ..." },
{ "map23", -1.f, -1.f, 0.f, false, 2.7f, "Green fire sky -- ..." },
```

- `intensity 0` — the directional light is off.
- `disc false` — no moon quad.
- `sky` writes **`rt_sky`**, which becomes RTGL1's `skyColorMultiplier`
  (`rt_main.cpp:2543`).

None of the five maps is in `RT_CLOUD_PRESETS` either. So on a fire map there is
**no directional light, no deck, no disc** — every photon in the level comes
from map fixtures, lava emissives, and the sky-on-ray-miss term.

And that last term is the only one, at:

| | `rt_sky` |
|---|---|
| pinned global (`tools/d64rt-pins.cfg:143`) | **25** |
| MAP22 / 24 / 28 | **1.2** |
| MAP23 / 32 | **2.7** |

---

## 2. The hypothesis, and the launch that settles it

`rt_presets.cpp:152` says those numbers are "parity with the cloud families at
the global 25, off the measured mean radiances (953× and 410× the starfield)".

**A whole-image mean is the wrong statistic for this art.** 60 % of the fire
sky's luminance is in its bottom quarter and 0 % is in its top quarter, so the
953× is carried almost entirely by rows that map to directions at and below the
horizon. What a room actually receives is the sky in the directions its opening
subtends — cosine-weighted, so biased toward *up* — and up is black. Dividing
the multiplier by 21 to compensate for a mean the geometry never collects is how
you get a sky that measures three orders of magnitude brighter than the
starfield and delivers nothing.

Compounding it: `getSkyAlbedo` is reached on **ray miss only**
(`RaygenCommon.h:302`) and the environment is **not importance-sampled**. The
argument in `rt_presets.cpp` that this is fine — "a fire sky is the whole
hemisphere, which is the case where un-importance-sampled environment light
works" — is exactly the claim the table above contradicts. It is not the whole
hemisphere. It is a band near the horizon, which is the *small-source* case the
same comment says does not work.

**Test it before building anything:**

```
.\tools\ab.cmd firesky-loud 23     rt_sky 400, everything else shipping
```

Run it standing in an open, sky-ceilinged area of MAP23, then in a corridor with
a sky slot. Three outcomes and they point three different directions:

| result | means |
|---|---|
| open areas light up, corridors stay dark | **the number is right and the geometry is the problem.** The sky reaches what can see it; §4's ring is the answer, because a horizon band cannot get into a room through a ceiling opening |
| nothing lights up anywhere | the sky term is not reaching lighting at all on these maps — a plumbing bug, and every idea below is premature |
| everything lights up and it looks bad (noisy, flat, washed) | the multiplier alone is not the answer; the variance argument holds, and §4 is again the direction |

Run `firesky-loud` **first**. It is the absurd arm, in the sense
`lampshaft-fat` is: "the sky doesn't light anything" has two causes that look
identical from a screenshot — too dim to see, and never reached the shader — and
only a value far past reasonable separates them.

### Measured 2026-08-23: it was the number. Shipped.

`firesky-loud` on MAP23 **looked right** — not blown out, not noisy: a good
base to build the rest on. So the absurd arm was not absurd, and the fourth
outcome, the one the table above did not think to list, is the one that
happened.

The fix is five rows of `RT_MOON_PRESETS`, which is already a per-map field and
therefore cannot reach any other map — a map with no row gets `g_moon_base_sky`,
the launcher's pinned `rt_sky 25`:

| maps | was | now |
|---|---|---|
| MAP22 / 24 / 28 (`FRSKYNRM`) | 1.2 | **175** |
| MAP23 / 32 (`FRSKYGRN`) | 2.7 | **400** |

**Only 400 is judged in play.** 175 is derived, and MAP22 is the first thing to
look at if either family reads wrong.

**Where 175 comes from, and what the measurement says about the split.** The old
rows differed by 2.25×, justified as "`FRSKYGRN` is 2.3× dimmer than
`FRSKYNRM`". That number **reproduces exactly** — over all 100 frames of each in
linear radiance, `FRSKYNRM` is `0.15792` against `FRSKYGRN`'s `0.06805`, a ratio
of **2.32×**. But over the **upper half** the two measure `0.00913` and
`0.00925` — **0.99×, identical**. The entire 2.32× lives in the horizon band,
which is the part a wall blocks.

So the split does not do what it says: it is not buying "the same delivered
light" from a dimmer sky. It was kept anyway, and the reason is worth recording
because it is not the reason it was written for — `rt_sky` scales the dome's
**appearance** as well as its light, and equalising the two families would
render the orange band dimmer than its own art. Doom 64's orange fire sky is
brighter than its green one and should stay so. Both rows were therefore scaled
by the same factor from the value that was actually judged.

**This does not retire §4.** What it settles is that the *first* outcome in the
table above was the right one — the multiplier was wrong, and a room that can
see the sky now gets light from it. A room that cannot see the horizon band
still gets nothing, because no multiplier can put a band below the horizon into
a room through a ceiling opening. The ring is still the answer to that, and it
is now a smaller, better-posed job: an addition to a sky that works, rather than
a replacement for one that does not.

---

## 3. The ideas, ranked

Cheapest-and-biggest first. §4 and §5 are the two that matter; §6–§9 are
additive once those land.

Re-ranked after §2 shipped. §5 moved up: with the sky now bright enough to
*see*, the 63-pixel art and its sixteen repeats are the loudest remaining
problem, and no lighting work improves them.

**§6 is now built, inside §3a** — the ember deck exists as part of
`rt_fireskies_new` rather than as `RT_CLOUD_PRESETS` rows, because it has to
come and go with the mode. §5 and §4 are untouched and are the two that would
improve the **default** sky, which is what most players will see.

| § | idea | buys | costs |
|---|---|---|---|
| 5 | **real art** — generate 1024×128 fire, kill the 16× repeat | the sky stops looking like a 63-px flipbook — now the top complaint | a generator + a pk3 ANIMDEFS override |
| 4 | **horizon fire ring** — analytic lights at the flame band | rooms that *cannot* see the horizon band, which §2 cannot reach | 8–16 sphere lights/frame, one new file |
| 6 | **ember deck** — `RT_CLOUD_PRESETS` rows, lit from below | a ceiling to hell instead of black above the band | 5 table rows + one weight change |
| 7 | **flame ring geometry** — cylindrical shells at the horizon | parallax; the flame front reads as volume | N sky draws × 6 cubemap faces |
| 8 | **embers** — rising motes on the dust lattice | scale and motion near the player | reuses `rt_dust.cpp` wholesale |
| 9 | **breathing** — global flicker from the live frame | the room pulses with the fire | ~free, once §4 exists |

---

## 3a. `rt_fireskies_new` — the alternative sky

**Ships ON since v0.1.14**, via the `rt_fireskies_new 1` pin in
`tools/d64rt-pins.cfg` (the compiled default is `false`; the pin overrides it).
`rt_firesky.cpp`, plus a draw pass in `hw_skyportal.cpp` and art from
`tools/gen_fire_sky.py`. Built and run.

It is opt-in and it is not a fix to the default: §2 made the old dome work, and
this replaces it. Both are runnable, and the pair `firesky-base` /
`firesky-new` is the comparison.

### What it does

Three of the ideas below, wired to the existing machinery rather than to new
renderers:

1. **The dome goes dark.** `FRBACKO` / `FRBACKG` — 1024 wide, a cubed vertical
   ramp with an ember glow only in the bottom rows, and **no painted fire at
   all**. That is the `SKYSTORM` arrangement (§6 of
   `rt-clouds-and-lightning.md`): a map's fire comes from the deck and the
   effects, or from the dome, never both, or you get two unrelated fires on
   screen.
2. **The cloud deck, ember-tinted and thicker than the storm's** (`thick 1.15`
   vs 0.7), with `rt_clouds_dark` raised to **0.85** rather than the storm's
   0.45. The storm darkens its bottom shell because the light is a moon
   *above*; here there is no moon at all — `RT_MOON_PRESETS` turns it off on
   these five maps — and the underside is the whole thing you look at.
3. **Meteors and coloured strikes.** Both are scenery-plus-source in the
   arrangement the storm already uses.

### The dome swap is engine-side, and that was a decision

Every other per-map sky choice is made in `d64r-rt-sky.pk3`'s `SkyForMap`, and
this one is not. `SkyForMap` runs at `WorldLoaded`, so a cvar toggled from the
console would not take until the next level load — and A/B-ing it in place is
the entire point of the cvar. So `HWSkyPortal::DrawContents` substitutes the
texture at the draw site, and falls through to the map's own dome if the
backdrop is missing. **ZScript is not touched.**

### Meteors are scenery. They light nothing, on purpose

Same argument as the moon disc, and it is the one that governs this whole
document: the RT sky is a rasterised cubemap sampled **on ray miss** and is not
importance-sampled, so a bright sprite painted into it is found only by rays
that happen to point at it. A meteor that has to light the room raises a
**strike** instead — `rt_firesky_impact_flash`, default 0.35, so roughly a
third of landings flash. Not all of them: every impact flashing turns a rare
event into a strobe, and the scheduled strike is pushed back when one fires so
two flashes never land half a second apart.

The art is `screen/fire_meteor.png` / `_green.png`, eight cells each: **five
flight frames and three ground-burst frames**. Three details that are load
bearing:

- **The sheet is not an even grid.** 707/8 = 88.375 looks right and is wrong —
  cell 2 runs 81..135 and cell 3 runs 158..220, so an even cut slices both and
  puts a sliver of each meteor's tail into its neighbour's frame. The generator
  segments on the sheet's own empty columns instead. The green sheet's 6th and
  7th cells *touch*, so it yields six gaps rather than seven and borrows the
  missing cut from the orange sheet.
- **The five flight frames share one canvas.** They are a size ramp — that is
  how the sheet says "closer" — and tight-cropping each one would delete the
  ramp entirely, leaving five same-sized meteors that merely change shape. The
  engine then applies a *modest* further angular growth (`SIZE_GROW` 1.7) on
  top; doubling it reads as a zoom rather than as an approach.
- **The trail always runs up-right**, so every meteor drawn from this art
  travels down-**left**. Half of them are mirrored — `RT_DrawSkyQuad` negates
  the quad's half-width, which is a *bug* for the moon (it mirrors the disc
  east-west against the light's bearing) and the whole of the variety here. The
  azimuth sweep follows the mirror, so motion and picture agree.

### Strikes needed a scheduler and nothing else

These maps carry no `lightning` keyword in their `MAPINFO`, so
`DLightningThinker` never spawns. But the strike is **renderer-side** —
that is what makes the `thunder` CCMD work on any map — so all that was missing
was something to call `RT_OnLightningFlash`.

Colour is one cvar. `rt_lightning_color` is read by *both* the bolt quad and
the analytic directional in `rt_main.cpp`, so setting it once (`FFB060` orange,
`A8FF60` green) recolours scenery and source together. The bolt was previously
drawn white and now passes that colour through — the one engine change either
end needed.

### Restoring is not optional

`rt_clouds*` and `rt_lightning_color` are `CVAR_ARCHIVE`, and
`RT_CloudApplyPresets` **returns early and writes nothing** when
`rt_clouds_presets` is 0. So without an explicit restore, one visit to MAP23
would leave an ember deck on every map for the rest of the session *and* in the
ini. `RT_FireSkyOnLevelLoad` captures the launcher's values once and always
writes one branch or the other.

It is also called **after** `RT_OnLevelLoadPresets`, never before — the cloud
table writes `rt_clouds` unconditionally when presets are on, so a fire sky
that set up its deck first would have it silently overwritten and would look
like the cvar does nothing.

### Ticked from the frame loop, not from the sky draw

`RT_FireSkyTick()` sits next to `RT_DrawDust()` in `rt_main.cpp`. A sealed room
submits no sky portal, so scheduling from the draw would stop the storm exactly
while the player is indoors — which is where a flash through a doorway is worth
most. The meteor *quads* are still drawn from `hw_skyportal.cpp`, which owns the
sky vertex buffer.

The tick also re-bases its schedulers after any gap over 2 s (a level load, a
long menu, a save restore) rather than spawning the backlog, which would fire a
dozen meteors on the frame the menu closes.

### How to judge it

    .\tools\ab.cmd firesky-fat       23   <- RUN THIS FIRST. The absurd arm.
    .\tools\ab.cmd firesky-new       23   the shipping values, green
    .\tools\ab.cmd firesky-new       22   the shipping values, orange
    .\tools\ab.cmd firesky-base      23   the default sky, for comparison
    .\tools\ab.cmd firesky-nometeor  23   is the deck+strikes carrying it?

`firesky-fat` is 20 meteors at 3× size every 0.3 s with every impact flashing.
"I don't see any meteors" has two causes that look identical in a screenshot —
too rare to notice, and never reached the draw — and only a setting far past
reasonable separates them.

The console command is the other half:

- `firesky` — is this a fire map, which backdrop resolved, how many meteors are
  live. Three failures separate immediately: *"not a fire map"* (wrong map),
  *live 0* (the pool or the tick), *live > 0 and nothing on screen* (the draw,
  or `d64r-rt-sky.pk3` is stale).
- `firesky meteor` — spawn one now, instead of waiting out the schedule.
- `firesky strike` — force a flash, and print the colour it used.

### Regenerating the art

    tools\.venv-ai\Scripts\python.exe tools/gen_fire_sky.py --preview
    python tools/pack_rt_sky.py

`--preview` writes `METEOR_preview.png` (every cell as split — the contact sheet
is how the even-grid bug was caught, and is worth a look after any change) and
`FRBACK_preview.png`. Neither is packed, same rule as `MOONSKY_preview.png`.

### 3b. The embers do not read, and why — plus what to build instead

**Reported 2026-08-23: "it doesn't really work / is not visible."** Correct, and
the reasons are structural rather than tuning. Sky embers were put into the
shared spark pool because that pool already owns a sim, collision, a draw and a
glow budget. It also owns three things that are right for an impact spark and
wrong for a drifting ember.

**1. The heat ramp is keyed to AGE, and it cools to black.** `RT_SPARK_RAMP`
(`rt_sparks_internal.h:57`) is seven entries from `F8F8B0` — hot pale yellow —
to `180800`, indexed by `t = age / life`. At `rt_firesky_ember_life 7` an ember
is bright for about the first second and near-black for the last four or five.
Mine spawn 16 m overhead and only enter useful view part-way down, by which
point they are brown. **An ember that should glow the whole way cannot use a
monotonic cooling ramp** — a coal in a scorch cools, a spark falling out of a
burning sky does not.

**2. There is no angular size floor.** `rt_dust_size_ang` exists precisely
because a sub-pixel speck under an upscaler is not a dim speck but a *shimmering*
one. The spark path has no equivalent, because it is a close-range impact
effect: a 5 cm ember at 25 m subtends about 0.11°, one to three pixels, and DLSS
eats it.

**3. Additive over a bright deck adds nothing.** The deck now fills the sky with
saturated orange or green. A dark-brown particle drawn additively over that is
arithmetically invisible.

So the pool was the wrong host. What follows is what to build instead.

#### A. `rt_fireembers.cpp`, modelled on `rt_dust.cpp` — the recommendation

Not on the spark pool. **`rt_dust.cpp` is already 80% of this** and it solved
every one of the three problems above for its own reasons:

- **No pool, no spawning, no state.** The motes live on a hashed lattice fixed
  in *world* space and the frame draws the cells near the camera, so the system
  is a pure function of (camera, time). Density is uniform and exact, nothing
  pops as the player moves, walking away and back shows the same field, and no
  budget can quietly run out. Every one of those properties is what a sky full
  of embers wants and what a spawn-and-age pool cannot give.
- **Size is angular**, with the shimmer fix already in it.
- **Distance is handled by SHRINKING, never by fading** — below RTGL1's 0.98
  alpha the whole batch is demoted to the rasterized overlay and goes
  fullbright. That trap is waiting for anyone who reaches for alpha here.
- **The sky-ceiling sector gate** (`rt_dust_moon`, `rt_dust_clip`) is already
  written and is exactly the gate an ember needs.

What has to differ from dust, and each one is deliberate:

- **Drift, not stillness.** A downward velocity plus lateral wander, evaluated
  as a *function of time on the lattice* rather than integrated — so it stays
  stateless. The lattice cell supplies the seed; the time supplies the offset.
- **They ARE emissive.** Dust is explicitly not, because "emissive dust is
  fireflies" — a mote glowing in a pitch-black room. An ember genuinely is
  self-luminous, so it carries emission, and the fireflies failure is prevented
  by the **sky-ceiling gate** instead: embers exist under open sky and nowhere
  else. That is the same trade `rt_dust_moon` already makes.
- **Colour cycles on a per-ember PHASE, not on age.** This is the direct fix for
  problem 1: each ember pulses along a short hot ramp on its own phase, so it
  flickers the way a wind-blown coal does and never monotonically dies. Nothing
  is "old" on a stateless lattice anyway, which is what makes this natural
  rather than a workaround.

#### B. Let the nearest few cast real light

The `rt_spark_glow_max` pattern: a global cap, nearest-first, so a handful of
embers are actual spherical lights and the rest are traced geometry. That is
what makes the effect land on the *level* instead of only on the sky, and it is
the difference between "there are specks" and "the sky is on fire".

#### C. Emit them from the deck

Tie the spawn band to the deck's own base height rather than to a fixed offset
from the eye, so embers visibly come **out of** the burning cloud rather than
appearing in mid-air below it. The deck's geometry is already computed in
`RT_DrawCloudDeck`; this is one exported number.

#### D. Streak, not dot

`rt_spark_style 1` already stretches a particle along its velocity, capped by
`rt_spark_streak`. At sky distances a short line reads as motion where a dot
reads as a stuck pixel, and this is most of what sells falling.

#### Cheaper alternatives, and what they cost

- **An additive ember layer on the deck's own flash pass.** No new system at
  all — a scrolling texture in the pass that already re-draws the shells. But it
  is *painted on the sky*, so it cannot parallax, cannot be occluded by
  geometry, and cannot light anything. It is the sprite-meteor mistake in a
  different costume.
- **An "ember mode" inside `rt_dust.cpp`** rather than a new file. Less code,
  but dust's shaft-weighting is entangled with its albedo gate and an emissive
  second population would have to opt out of most of it. A sibling file that
  borrows the lattice is cleaner.

**Recommendation: A + B + D.** C is a refinement once it works.

### 3d. Making the deck read as HELL rather than as tinted weather

Asked for 2026-08-23. The deck is currently the storm's cloud with a hot colour
multiplied over it, and that is why it reads as weather in a strange hue rather
than as a burning sky. There is one structural reason for that and it is worth
stating before any of the ideas, because most of them follow from it.

#### The bake is lit from ABOVE, and you are looking at the underside

`gen_clouds.py` integrates Beer-Lambert transmittance **top-down** through the
density field, a single-scattering approximation of *moonlight from above*. That
is what gives the deck lit tops and dark undersides, and the doc for it says so
outright: it is "most of what makes a stack of flat discs read as cloud".

A fire sky is the opposite. The light is **under** the cloud, so the underside
is the incandescent part and the tops are dark smoke. And the underside is
exactly the surface the player looks at. So every texel of the current art is
shaded backwards for this use, and `rt_clouds_tint` — a multiply — can change
its hue but cannot move where the light is coming from. No tint value fixes
this, which is why tint sweeps will keep disappointing.

#### A. Bake a bottom-up variant — the real fix

`gen_clouds.py --lit-from-below`, writing `CLOUDF1..8` beside the existing
`CLOUDV1..8`: same density field, same generator, transmittance integrated
**upward from the base** instead of downward from the top. Dense low cloud comes
out bright, the tops come out dark, and the deck stops being a lid with a light
behind it.

Cheap to try — it is one sign change in the integration plus a new output name —
and it reuses a generator that already exists and is already tuned for shape.
The engine picks the family by cvar, so both are runnable side by side.

#### B. A per-shell tint GRADIENT, not just a brightness ramp

`rt_clouds_dark` ramps *brightness* from the bottom shell to the top, and one
`rt_clouds_tint` colours all of them. Real fire-lit cloud does not change only
in brightness through its depth — it changes in **hue**: incandescent orange
where it is close to the fire, dull red above that, near-black smoke at the top.

Two tints and a lerp across the shell index gives that for the cost of one extra
colour cvar, and it is per-draw state the deck already sets (`SetObjectColor`
per shell). This is the single cheapest change here and it is independent of A.

#### C. Flicker the underside

A slow low-frequency modulation on the lowest shells' brightness — the deck
pulsing as if something under it is burning unevenly. That is what makes a cloud
read as *lit by* something rather than *painted*. The machinery exists: the
lightning cloud-flash already re-draws each shell additively weighted toward the
lower ones (`1 - 0.7·f`), and a standing version of that pass driven by noise
instead of by a strike envelope is a small change to the same loop.

**It must not be a light cut.** `g_rt_lightcut` flushes the denoiser and is for
lights that switch; a continuous flicker that raised it would destroy temporal
history every frame. Same rule the cloud occlusion already follows.

#### D. Churn, not drift

The deck translates along a fixed wind vector — linear, unbounded, never
repeating, which is right for weather and wrong for hell. A burning sky roils.
Adding a slow per-shell UV rotation on top of the translation, or a second
counter-scrolled sample, would give the boil without losing the non-repeating
property that made the translation the right choice in the first place.

#### E. Fewer shells, further apart

Eight shells at `thick 1.0` currently stack into something close to a solid lid.
Five or six with more vertical separation shows actual gaps and undersides —
more visible structure for *less* cost, since every shell is a full disc
rasterised into all six cubemap faces.

**Recommendation: B first** (one cvar, no art), then **A** (the real fix, one
generator flag), then C. D and E are refinements.

### 3c. There is no thunder on these maps — investigated, not changed

The sound is played by the stock thinker, not by anything RT:

```cpp
// playsim/mapthinkers/a_lightning.cpp:205, in DLightningThinker::LightningFlash
S_Sound( CHAN_AUTO, 0, "world/thunder", 1.0, ATTN_NONE );
```

`world/thunder` is a `$random` alias in the WAD's `SNDINFO` over
`world/thunder1` / `world/thunder2` → `DSTHNDR1` / `DSTHNDR2`. **Both lumps are
present in `D64RTR_v15.WAD`**, so nothing is missing.

What decides whether that thinker exists at all is one MAPINFO keyword. Seven
maps in the game carry it:

| maps with `lightning` | MAP11, MAP12, MAP14, MAP30, RTR05, RTR10, OUT08 |
|---|---|
| the five fire maps | MAP22, MAP23, MAP24, MAP28, MAP32 — **none of them** |

So on a fire map `DLightningThinker` never spawns, `LightningFlash` never runs,
and the sound never plays. The fire sky's strikes come from its own scheduler
calling `RT_OnLightningFlash` directly — which is renderer-side, which is
exactly why it works on a map with no storm, and equally why it is silent.

**The fix is small and is not applied yet.** One `S_Sound` from the fire sky's
scheduler, with two things worth getting right rather than copying:

- **Delay it.** Light arrives before sound. The stock thinker plays the sample
  on the same tic as the flash because Hexen did; a strike a few hundred metres
  away should rumble a second or so later, and this scheduler already runs on
  the wall clock, so the delay is free.
- **Do NOT add `lightning` to those maps' MAPINFO instead.** It would work, and
  it would also start the stock thinker's *own* 5–20 s schedule and its
  106-sector lightlevel flash, both fighting the fire sky's schedule. Two
  storms, one map.

### Known limits

- **Not compiled, not run.** Nothing in this section claims a look.
- **Meteors do not cast light.** By design, above. The room brightens on a
  strike, not on a meteor.
- **Meteors are drawn in front of the deck.** Behind it is the more physical
  order, but the deck reaches down to `rt_clouds_horizon`, so a meteor under it
  is invisible for most of its fall. A missing effect is the worse failure.
- **Deck cost is per shell**, six of them, each a full disc rasterised into all
  six cubemap faces every frame. `rt_firesky_cloud_shells` is the knob and
  `D64RT_SPIKE_MS` is how to measure it — not assumption.
- **The backdrop is flat.** It is a ramp with noise, deliberately, so the deck
  and the effects are what the eye goes to. If the sky reads as empty when the
  meteors are sparse, that is this, and §5's generated fire is the answer rather
  than painting the backdrop up.

---

## 4. The horizon fire ring

**The moon's argument, run in reverse.** For the moon, the *picture* is a quad
on the dome and the *light* is a separate analytic directional, because a
half-degree disc painted into a non-importance-sampled cubemap lights nothing.
Here the picture is a band at the horizon and it has the same problem for the
same reason — it is a small source in solid angle terms, and worse, it is in the
one direction a room cannot see.

So: **a ring of N sphere lights** at horizon altitude, on a circle around the
camera, colour and intensity read from the current animation frame.

```
for k in 0..N-1:
    azimuth  = 360k/N
    colour   = mean of the live frame's bottom band, columns for this azimuth
    position = camera + R·(cos az, sin az) at horizon height
    radius   = large (a soft source; a flame band is not a point)
```

Why this shape and not the alternatives:

- **Not a directional light.** RTGL1 allows exactly one
  (`LightManager.cpp:461`, and a second one calls `debug::Error`, which *exits
  the game* — see `rt-clouds-and-lightning.md`). Lightning already takes over
  `SunLightId` for that reason. More importantly a fire ring is not
  directional in the first place: it arrives from every azimuth at once, which
  is precisely what `rt_presets.cpp:136` says and precisely why it set
  `intensity 0` rather than picking a bearing.
- **It cannot leak the way the moon does.** `rt_sun_require_sky` exists because
  a directional light's shadow ray runs to `MAX_RAY_LENGTH`, escapes a
  non-watertight map, hits nothing and is scored *lit*
  (`RtMissShadowCheck.rmiss`). **A point light's ray terminates at the light**,
  so there is nothing to escape and no sky probe to write. That is the argument
  §4d of `plan-light-shafts.md` makes about lamps, and it applies here
  unchanged. It is the single strongest reason to prefer a ring of point lights
  over any attempt to reintroduce a directional on these maps.
- **It is importance-sampled.** These are lights in `LightManager`, not
  radiance in a cubemap, so a room with a sky slot gets a clean estimate at 1
  spp instead of the variance the environment term has. `LIGHT_ARRAY_MAX_SIZE`
  is 4096; sixteen more is nothing.
- **It shadows correctly and for free.** Light raking in through a sky slot at
  horizon altitude, throwing long shadows across the floor, is the Doom 64 hell
  look and it falls out of using real lights.

Open questions this needs a decision on, none of which should be guessed:

- **Where is the ring?** A circle at fixed radius around the camera moves with
  the player, which is right for something meant to be at infinity but means the
  lights are *not* at infinity for shadowing — a pillar's shadow will swing as
  you walk, which is wrong. Alternative: place the ring once per level at the
  map's bounding-box scale, so it behaves like distant geometry. That costs
  nothing extra and is probably correct; it should still be a cvar.
- **Does a ring segment behind a wall get culled?** It has to be, or a sealed
  room gets sixteen lights' worth of ambient it should not have. The shaft
  registry (`rt_light_shafts.cpp`) already solves the "which of these do we
  send" problem and the same machinery applies. But the honest answer may be
  that the shadow ray handles it and no cull is needed — measure before adding
  one.
- **Colour per segment, or one colour?** Per-segment is what makes the ring
  *agree* with the picture the way the lightning bolt and its directional agree
  by construction — both read the same stored bearing. Sampling the live frame's
  bottom band per azimuth costs a CPU reduction per frame, which is exactly what
  `RT_DrawCloudDeck` already does to sample cloud slices for the moon's
  transmittance.

Proposed cvars, following the house pattern (`rt_firesky_*`, all pinned, a
`RT_FIRE_PRESETS` table if it turns out to want per-map values):
`rt_firesky_ring` (master), `_lights` (N, default 12), `_intensity`,
`_radius`, `_alt` (altitude of the band in degrees, default a few degrees
*below* horizon — the art puts its fire below the horizon line), `_angdiam` /
sphere radius, `_flicker`, `_debug`.

**Judge in play.** Nothing here is measurable from a scanner, and a bright
outdoor area showing little change is correct, not a null result.

---

## 5. Replace the art

`tools/gen_fire_sky.py`, packed by `tools/pack_rt_sky.py` into
`d64r-rt-sky.pk3` — the same loop `gen_clouds.py` and `gen_moon_sky.py` use.
The pk3 already carries an `ANIMDEFS`-capable path and GZDoom takes the **last**
definition loaded for a texture, so an override needs no WAD surgery.

Three things it has to fix, and they are independent:

1. **1024 wide.** That alone sets `xscale` to 1 and deletes the sixteen repeats
   and the sixteen seams. It also puts the fire skies on the same branch of
   `SetupMatrices` as every other sky in the game, which is what
   `gen_d64_skies.py` standardised for.
2. **Structure above the band.** The top half of the current art carries 6.7 %
   of its luminance and 0 % in the top quarter — it is *black*, and a black
   upper dome under a path tracer is a black upper dome. Smoke lit from below by
   the fire, thinning with altitude, gives the eye something to resolve and
   gives cosine-weighted rays something to collect. This is the half that most
   directly answers "looks weird".
3. **Real fire motion.** The current flipbook is 100 frames at 2 tics — 17.5 fps
   of a 63-px image. A generated field can be advected properly (curl noise, or
   the classic cellular fire propagation Doom 64's own sky came from) and can be
   made to **tile in X only** — the sky's vertical axis has hard limits (ground
   below, black above), exactly the argument `gen_clouds.py` records for why its
   field tiles in X and Y but not Z.

**Keep the palette.** The measured bottom-band colours in §1 are the target, and
`docs`' standing rule applies — this is a resolution and motion fix, not a
recolour. `dont-over-apply-retro-styling` and `keep-the-art-add-shading-on-top`
both point the same way: the hue is Doom 64's and stays.

**The trap is memory, and it is worth sizing before writing the generator.**
100 frames × 1024 × 128 is 12.6 M texels per family. Two shipping families is
~100 MB uncompressed. Options, cheapest first: fewer frames at more tics; a
shorter loop scrolled horizontally so the loop point is not visible; or 512
wide, which still gives `xscale 2` rather than 16.

**And one that will bite:** an animated 1024-wide sky is re-rasterised into all
six cubemap faces every frame. That is already true at 63 px, so this is a
texture-fetch cost rather than a new draw, but it should be measured with
`D64RT_SPIKE_MS` rather than assumed.

---

## 6. The ember deck

`RT_CLOUD_PRESETS` has no fire rows, and the deck is the piece of machinery this
project already has that would help most for the least work.

The lightning path is *already* the fire case: `RT_DrawCloudDeck` re-draws each
shell **additively** at `rt_clouds_flash` × envelope, weighted toward the
**lower** shells by `1 - 0.7·f`, because — in the doc's own words — "the strike
is under the deck. Weighting it evenly, or toward the top, makes the whole deck
flash like a lamp behind a curtain."

A fire sky is a permanent strike under the deck. So the proposal is five table
rows with a dark, low-saturation smoke tint and a **standing** below-lit term
rather than a transient one — i.e. the flash weighting, driven by the ring's
intensity instead of by `RT_OnLightningFlash`'s envelope.

Two things to get right, both already documented failures:

- **`transmit` matters more here than anywhere.** These maps have no moon, so
  the deck is not filtering a directional light — but if §4's ring lands, the
  deck should filter it, and the slab form (`clear + (1-clear)·tint·transmit`)
  is what makes that correct independently of `rt_clouds_shells`. The per-shell
  form that shipped first raised `transmit` to the power of the shell count and
  delivered 1e-4 under real cover.
- **The tint must stay near-achromatic in the art.** `SetObjectColor` is a
  multiply and cannot remove a hue already baked in. Ember-orange belongs in the
  tint cvar, never in the slice.

---

## 7. Flame ring geometry

The dome band is flat by construction: one texture, one distance, no parallax,
and it rotates about the viewer as you turn — the exact motion
`rt-clouds-and-lightning.md` records as the reason the deck is a *deck* and not
a dome layer.

The fire's equivalent of the deck is a **cylinder**: 2–4 concentric rings at the
horizon, at different radii, each scrolling **upward** at its own rate and with
its own slice of the fire field. Nearer rings move faster; the flame front then
has depth, occludes itself, and never repeats a lap.

This is a genuine "is it worth it" question rather than a clear win — it is N
more full sky-geometry submissions rasterised into six cubemap faces per frame,
for an effect that only shows where the horizon is actually visible, which in a
Doom map is rarely. **Do §4 and §5 first and re-ask.**

---

## 8. Embers

`rt_dust.cpp` is most of this already: a hashed lattice fixed in world space,
drawn near the camera, a pure function of (camera, time), no pool and no
spawning. Embers are that with an upward drift and a warmer albedo.

**The one real decision is emission**, and the dust doc is explicit that getting
it wrong is the whole failure mode: *"Emissive dust is fireflies. A mote
carrying its own light glows in a pitch-black room, which is the opposite of the
effect."* An ember genuinely is self-luminous, so the rule does not transfer
cleanly — but the room it must not glow in is exactly hell's dark interiors.

The gate already exists and is exactly right: `rt_dust_moon` counts a mote only
if **its sector has a sky ceiling**. Embers get the same gate, so they exist
outdoors under the fire and nowhere else. Start non-emissive with a high albedo
lit by §4's ring — that is the honest version and it costs nothing to try
first — and only add emission if the ring cannot carry them.

---

## 9. Breathing

Once the ring exists, scale it by the **live frame's own mean luminance**, so
the room brightens and dims with the sky rather than sitting at a constant while
the picture flickers.

The sampling pattern is `RT_DrawCloudDeck`'s: a cached small reduction of the
current frame, bilinear, once per frame — per-texel precision would be measuring
nothing.

**It must not be a light cut.** `g_rt_lightcut` flushes the denoiser's temporal
history and is for lights that *switch* — the lightning strike raises it for
exactly that reason. Fire luminance moves continuously at 17.5 fps; flushing on
it would destroy the denoiser every other frame. This is the cloud-occlusion
rule (*"cover changes at wind speed, over seconds, so it must not flush the
denoiser"*) applied to a faster signal where it matters more.

---

## 10. Traps, all previously paid for elsewhere

- **`RT_MOON_PRESETS` writes `rt_sky` at level load**, after the command line is
  parsed. On these five maps a `+rt_sky` pin is silently overridden. Any arm
  that touches `rt_sky` on a fire map must set `rt_moon_presets 0`, or it will
  measure the preset and report the cvar — the same trap `leak-base` documents
  for `rt_sun_a/b`.
- **Positions crossing into RTGL1 are metres**, never map units. A ring built in
  map units and handed over unconverted is 32× out and reads as absent.
- **One directional light, ever.** A second one exits the game.
- **`state.SetColor()` does nothing** on anything drawn from
  `FSkyVertexBuffer` — per-primitive colour goes through `SetObjectColor`.
- **A/B cvars must not persist.** `RT_CVAR_NOARCH` for anything diagnostic, and
  every arm sets every value explicitly.
- **The generated uniform header is not a tracked build dependency.** If any of
  this adds uniform fields, `build-rtgl.cmd` must clear objects and
  `tools/check_uniform_layout.py` must pass, or the new fields read zero.

## 11. Not proposed

- **Heat shimmer / refraction at the horizon band.** Real, and the wrong order
  of business — it decorates a band that currently reads as a repeating
  63-pixel flipbook.
- **Assigning `FRSKYRED` or `FRSKYBLU` to a map.** They exist and they are
  wired to nothing, but which map should get one is a content decision, not a
  rendering one. `FRSKYRED` is the brightest of the four and is the obvious
  candidate if a hell map ever wants to be hotter than MAP22.
- **Touching `F_SKY1`.** It is the placeholder flat, not a sky.

## See also

- [`rt-clouds-and-lightning.md`](rt-clouds-and-lightning.md) — the deck, the
  bake, and the painted-vs-analytic split this reuses
- [`moon-and-sky-leaks.md`](moon-and-sky-leaks.md) — `rt_sun_require_sky` and
  why §4 does not need it
- [`plan-light-shafts.md`](plan-light-shafts.md) — the froxel volume, and the
  selection machinery a ring cull would borrow
