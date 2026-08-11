# Illuminated fog

Doom 64 fogs whole levels, and Retribution's `MAPINFO` says so out loud:

```
map MAP26 lookup "D64HUSTR_26" // Hardcore
{
	...
	fade = "00 56 56"
	fogdensity = 200
}
```

Under RT that produced nothing at all, on any of the nine maps that ask for it.
`fade` and `fogdensity` are consumed by the rasterizer's fog, and the RT path
never looks at either. `screen/doom64original_level26fog.png` is what was
missing: the console game's MAP26, teal to the point that the far end of a
corridor is simply gone.

---

## 1. What was built, and what was deliberately not

**Not that fog.** Rasterizer fog is a per-pixel lerp toward a colour by
distance. It cannot be lit — a lamp standing in it gets no halo, and an unlit
corridor fogs exactly as brightly as a lit hall. Reproducing it under a path
tracer would mean writing a post-effect that ignores every light in the scene,
on a renderer whose entire point is that it does not.

What is here is the **medium**: a participating volume in RTGL1's froxel grid,
which real lights scatter through. The map supplies the colour and the density —
its own authored `fade` and `fogdensity`, read at level load — and the renderer
supplies what the fog does with the level's own light. Fog around a torch glows;
fog in a dark corridor stays dark.

The single test that tells the two apart, in any arm: **is the fog brighter near
a light source than it is twenty feet away in the dark?** `tools/ab-fog.cmd
ambient` is the same scene with that taken out, and is the fastest way to see
what the difference is worth.

---

## 2. The two things RTGL1 was missing

Both in `RtVolumetric.rgen`, the raygen shader that fills the froxel volume.

### `volumeMediaColor` — the medium had no colour

The froxel pass had no notion of a coloured medium. The only colour available
was `volumeAmbient`, the flat unlit term, which tints the fog you see in the
dark and leaves everything the fog does with **light** white. A cyan fog built
that way has white haze around every lamp in it.

`volumeMediaColor` is the scattering albedo and multiplies the whole in-scattered
term, ambient and lit alike. `{1,1,1}` is the identity, which is what every map
without fog passes, so nothing else in the game moved.

**Extinction stays monochrome.** The transmittance channel is a single float
from `RtVolumetric.rgen` through `CmVolumetricProcess.comp` to the
`hdr * volumetric.a + volumetric.rgb` in `CmPrepareFinal.comp`; making it
per-channel is a framebuffer change, not a shader one. The visible consequence
is that distance fades **toward** the fog colour rather than being filtered by
it — which is what the console game does anyway, its fog being a lerp.

### `volumeAllLights` — the fog was lit by exactly one light

This is the one that decides whether the feature exists.

`LightManager::TryGetVolumetricLight` picks **one** light for the whole volume:
a `RG_LIGHT_ADDITIONAL_VOLUMETRIC` light if one exists, otherwise the sun.
Nothing in this game sets that flag, so it is always the sun — which on MAP26 is
switched off on purpose (§4). The fog therefore received **nothing**, and
collapsed to flat `rt_fog_ambient`: a coloured pane of glass over the screen,
i.e. exactly the rasterizer fog this was supposed to improve on.

`volumeAllLights` runs the full per-froxel direct estimate instead
(`processDirectIllumination`, the same NEE/ReSTIR path surfaces use), so every
lamp, lava pool and monitor in the level lights the fog it sits in.

That branch already existed — it is the `ILLUMINATION_VOLUME` block — but it was
gated on `illumVolumeEnable`, which is `rt_illum_volume`, which **also** switches
how `RsWorld.inl` shades every rasterized translucent primitive in the game
(see that cvar's description: tried for ghost sprites, rejected, kept only so the
path could be re-tested). Asking for lit fog would have meant accepting that.
The two are now separate flags:

| flag | who wants it | what it does |
|---|---|---|
| `illumVolumeEnable` (`rt_illum_volume`) | the raster path | makes `RsWorld.inl` **read** `g_illuminationVolume` |
| `volumeAllLights` (`rt_fog_illum`) | the fog | makes the froxel pass **compute** all-lights radiance |

Both **write** the volume. That is not optional: the estimate is temporally
blended at 0.05 against what it stored last frame, so without the store it would
read a stale image forever and never converge.

**Cost.** One NEE + shadow ray per cell of a 160×88×64 grid, every frame. That
is the reason fog is per-map rather than global.

---

## 3. Per-map, and opt-in

`RT_FOG_PRESETS` in `rt_main.cpp`, the same shape as `RT_MOON_PRESETS` and
`RT_CLOUD_PRESETS`, applied at level load and gated by `rt_fog_presets`.

**A map has no fog unless it is listed**, for the reason the cloud deck is
opt-in: fog is not neutral scenery. It changes every distance judgement in a
level, and it is not free. A map gets fog because someone looked at it.

| map | fog | why |
|---|---|---|
| MAP26 | on, ramped 6 → 190 over 32 m at curve 2.4 | *Hardcore.* The map this was built for, and the one with a reference shot. Colour inherited from its own `fade` `00 56 56`; density **stated**, because a ramp is not something one `fogdensity` can say (below). `illum` forced on — see §4. |

### The MAP26 profile, and why it is a ramp

The reference shot is not uniform fog and it is worth being precise about what
it is: the wall beside the player keeps its rivets and only takes a tint, and
the far end of the corridor is **gone**. A single density cannot do both — at
the strength that removes the corridor, the near wall is already a silhouette.

So the shipping row is clear near and heavy far, and the numbers come off that
description rather than off feel:

| distance | | transmittance |
|---|---|---|
| 128 map units | 4 m | 0.95 — the air you stand in, essentially clear |
| 256 | 8 m | 0.88 |
| 512 | 16 m | 0.59 — half-gone across a large room |
| 768 | 24 m | 0.20 |
| 1024 | 32 m | 0.02 — the far slice, and everything beyond it |

The arithmetic, if a map needs different ones. `RtVolumetric.rgen` uses a flat
`density × 0.001` per cell over 64 cells spread evenly across `rt_fog_far`, so
for a ramp `d0 → d1` at curve `k`, optical depth to depth fraction `t` is

    tau(t) = 0.064 · [ d0·t + (d1 − d0)·t^(k+1)/(k+1) ]      T = exp(−tau)

**The curve is what makes it work, not the ends.** At `curve 1` those exact same
densities start hazing the room you are standing in immediately — 0.86 at 128
units instead of 0.95 — because linear thickening begins at the camera. 2.4
holds the near value out to about half the volume and then closes hard.
`tools/ab-fog.cmd flatramp` is that failure, kept as an arm because it is the
first thing anyone will try.

**`rt_fog_far 32` is part of the look, not a budget.** Everything past it is
shaded with the far slice, so the wall of teal closes at corridor distance —
1024 map units — instead of a room-and-a-half further out. It is also where the
volume spends its 64 slices of precision.

**This row states its densities, and that is a deliberate exception** to the
"take it from the map" rule below. `fogdensity` is one number; it can say how
thick, not where. A map that wants a uniform medium should still inherit.

The other eight maps that carry `fade` + `fogdensity` — MAP12, 21, 25, 27, 29,
30, 31, 33 — are **not** listed yet. Adding one is a single row; the authoring
loop is below.

### The values come out of the map, on purpose

Two cvars are sentinels rather than settings:

    rt_fog_color    000000   use the map's own MAPINFO `fade`
    rt_fog_density  -1       use the map's own MAPINFO `fogdensity`

and both preset rows and the launcher pin them that way. A row that restated
`00 56 56` would be a second copy of data the map already carries, and the copy
is the one that goes stale. Black is safe as a sentinel because a black medium
scatters nothing and would be invisible anyway, so no setting is given up.

`rt_fog_density_mult` (0.3) is the conversion from Doom 64's density to this
one. Doom 64's number is a rasterizer fog factor with no physical meaning here,
so this is an eyeballed constant settled against the reference shot, and it lives
in a cvar for exactly that reason.

**The colour dims the fog as well as tinting it**, and that is left uncorrected,
the same way `rt_clouds_tint`'s luminance is. `00 56 56` is an albedo of
`(0, 0.34, 0.34)`: its red channel scatters *nothing*, so a fogged corridor is
about a third as bright as the same corridor under a white medium of the same
density. That is what a saturated medium physically does, and normalizing it
away would mean a dark authored colour and a bright one delivering the same
light, which is not something any of these maps asked for.
`rt_fog_lightmult` is the knob if a specific map wants it back.

### Near and distant fog are separate

One density cannot be both thin enough to see your own feet through and thick
enough to swallow a corridor. So the medium is a **ramp**, not a constant:

    rt_fog_density       at the camera
    rt_fog_density_far   at rt_fog_far
    rt_fog_curve         the shape between them
    rt_fog_color_far     the tint at the far end, if it should differ

This is nearly free, and the reason is worth knowing before anyone proposes a
second volume: the froxel grid's slices are **uniform in distance**
(`VOLUMETRIC_DISTANCE_POW` is 1), so `cell.z` already *is* a depth fraction. The
ramp is one `mix()` per cell in `RtVolumetric.rgen` — no extra rays, no second
pass, no shadow-ray cost at all.

**Both far values keep a "same as near" sentinel** — `rt_fog_density_far -1`,
`rt_fog_color_far 000000` — and both default to it. A map that inherited its
density from MAPINFO has said nothing about a far value, and that is exactly the
case that must not invent one; it gets the uniform medium.

`rt_fog_curve` is usually the knob that is wrong, not the two ends. At 1 the
thickening is linear, which starts immediately and makes a room you are standing
in already hazy. Above 1 the near value is held further out, so the room stays
clear and the corridor beyond it still closes — `tools/ab-fog.cmd ramp` against
`ramp2` is that comparison with the densities held fixed.

Reversed (`density_far` **below** `density`) reads as smoke you are standing
*in* rather than distance haze. `ab-fog.cmd inverse` — mostly useful as proof
the ramp is doing anything at all.

From the console:

```
fog near 12          the air around you
fog far  90 004848   at rt_fog_far, optionally its own colour
fog curve 2.5
fog                  reports the ramp as `density 12 -> 90 (x7.50), curve 2.50`
```

**Scale, if you are wondering why the density is in the tens.**
`RtVolumetric.rgen` uses a flat `volumeScattering * 0.001` per cell over 64
cells, so `rt_fog_density 60` is an optical depth of ~3.8 across the whole
volume — dense. And because the coefficient is per *cell* rather than per metre,
**shortening `rt_fog_far` makes the same density read thicker**. The two knobs
are not independent; `rt_fog_far` is simultaneously the fog's reach and where
the volume's 64 slices of precision are spent.

Everything past `rt_fog_far` is shaded with the far slice — fully fogged — which
is what lets a bounded volume read as unbounded fog.

### The level-load trap this has that the others do not

`RT_OnLevelLoad` is called from `G_InitNew`, which runs **before**
`P_SetupLevel`. At that moment `primaryLevel` still holds the *previous* map's
`fadeto` and `fogdensity`. Resolving the fog there gives every fogged map the
fog of whatever was played before it — and on a first load, of nothing.

So the level load only *requests* fog (`g_fog_pending`), and
`RT_ResolveFogIfPending()` does the work on the first rendered frame, by which
point the level is certainly loaded. `rt_fog_debug 1` prints what it resolved
and where each number came from.

The trap it shares with the cloud table: the row is applied **after** the command
line is parsed, so on a listed map it overrides a `+rt_fog_*` pin. That is why
every `ab-fog.cmd` arm except `full` and `debug` sets `rt_fog_presets 0`.

With `rt_fog_presets 0` the cvars decide alone, on **whatever map is loaded** —
which is how you put fog on an unlisted map to look at it, and also why that
setting is not the shipping one.

### Authoring loop

Same as `moon` and `clouds`:

```
rt_fog_presets 0
fog on 00A0A0 60 45        (colour, density, far)
fog                        prints a paste-ready RT_FOG_PRESETS row
```

Bare `fog` also reports **where each number came from** — the map's MAPINFO or a
cvar — which matters more here than it does for the moon, because two of them
default to being read out of the map rather than set anywhere greppable.

---

## 4. MAP26's moon is off, and that is part of this

`RT_MOON_PRESETS` already hid MAP26's moon **disc**: it is one of the three
`VOIDSKY` maps, whose skybox is a plain box of flat dark teal with no starfield,
no cloud and no horizon — a moon hanging in it is the one object on screen with
no reason to be there.

MAP26 now also turns the moon's **light** off (`intensity 0`), which MAP25 and
MAP31 do not. Two reasons, and both are about the fog:

- **A directional light is the one thing that wrecks a fogged level.** It rakes
  the froxel volume from a single bearing, so the fog reads as a lit slab with a
  hard edge across it instead of as the even medium the map was authored around.
- **There was nothing legitimate to arrive through.** MAP26's rooms have no
  opening the moon could honestly come through, so under `rt_sun_require_sky`
  most of what it delivered was leak in the first place — see
  `docs/moon-and-sky-leaks.md`.

The fog's light now comes from the level's own lamps and lava, which is where it
should have come from. `tools/ab-fog.cmd moon` puts the moon back for the
comparison, rather than leaving the decision asserted.

---

## 5. Testing

`tools/ab-fog.cmd <arm> [map]`, default MAP26:

| arm | what it isolates |
|---|---|
| `full` | the shipping configuration — the preset table on |
| `off` | `rt_fog 0`; the volumetrics fall back to the global `rt_volume_*`. What the map looked like before |
| `nolight` | `rt_fog_illum 0` — the fog with the one light it used to get, i.e. none on this map |
| `flat` | RTGL1's depth-based fog in the same colour: one `exp()` per pixel, no volume, no lighting |
| `thin` / `dense` | a third / double the MAPINFO-derived density — so they only bite while a map is still on the sentinel, not on the ramp arms, which state theirs |
| `ramp` | the shipping profile forced onto any map (6 → 190, curve 2.4, reach 32 m). On MAP26 it should be indistinguishable from `full`; if it is not, the table did not apply |
| `ramp2` | same near end, far end 320 at `curve 3.0` — the teal wall closes harder |
| `flatramp` | the shipping ends at `curve 1.0` — the failure the curve exists to avoid |
| `inverse` | the ramp backwards: thick around you, clear beyond |
| `twotone` | colour split as well as density: cyan near, deep teal far |
| `reach20` / `reach90` | `rt_fog_far` 20 m / 90 m — the volume's reach and its precision at once. Named for the reach because `fog near`/`fog far` are the *ramp*, a different knob |
| `ambient` | a big unlit floor: what fog looks like painted rather than lit |
| `grey` | the colour taken out, the density kept |
| `moon` | the moon put back on (§4) |
| `debug` | `full` + `rt_fog_debug 1` |

`rt_fog_debug` is `RT_CVAR_NOARCH` on purpose, like `rt_sun_leak_debug` and
`rt_water_debug`: a debug mode that sticks in the ini is how a fix gets believed
to be inert for a whole round trip.

---

## 6. Files

| file | role |
|---|---|
| `rt_main.cpp` | `rt_fog_*`, `RT_FOG_PRESETS`, `RT_ResolveFog`, the `fog` CCMD, and the volumetric params handed to RTGL1 |
| `RTGL/.../RtVolumetric.rgen` | the froxel pass: `volumeMediaColor`, `ILLUM_VOLUME_ACTIVE` |
| `RTGL/.../CmScatterAccum.comp` | the depth-based path, tinted alike so `flat` is a real A/B |
| `RTGL/.../VulkanDevice.cpp` | `volumeAllLights` / `volumeMediaColor` uniforms |
| `RTGL/Include/RTGL1/RTGL1.h` | `illuminateFromAllLights`, `mediaColor` on `RgDrawFrameVolumetricParams` |
| `tools/ab-fog.cmd` | the arms above |

## 7. Known limits

- **Monochrome extinction** (§2). Distance fades toward the fog colour rather
  than filtering by it.
- **The ramp is along the view ray, not through the world.** It is indexed by
  froxel depth, so "far" means far *from the camera*, and it follows you as you
  walk. That is the right model for distance haze and the wrong one for a
  fogbank sitting in one end of a level — which would need the medium bound to
  world space, and the froxel volume is camera-fitted.
- **The fog is global to the level.** Doom 64 authored it that way — one `fade`,
  one `fogdensity` per map — but it means an indoor room in a fogged level is
  fogged too. Per-sector fog would need the medium bound to geometry, which the
  froxel volume has no notion of.
- **The sky is fogged too, at full strength.** A sky pixel's world position is
  past `rt_fog_far`, so it samples the far slice like any other distant surface
  and comes back fully covered. On MAP26 that is right — `VOIDSKY` is flat dark
  teal and the fog colour is its own `fade` — but a map with a painted sky and a
  strong fog colour would have that sky replaced by the fog, and that is the
  first thing to check when listing one.
- **Eight fogged maps are still unlisted** (§3), and their `fade` colours differ
  (brown, dark red). Each is one row and a look.
- **Cost is a shadow ray per froxel cell** with `rt_fog_illum 1`. Measure before
  adding rows, not after.

## See also

- `docs/moon-and-sky-leaks.md` — why MAP26's moon is off and what
  `rt_sun_require_sky` had already done to it
- `docs/rt-clouds-and-lightning.md` — the same opt-in per-map table shape, and
  the same "the table overrides your `+cvar` pin" trap
