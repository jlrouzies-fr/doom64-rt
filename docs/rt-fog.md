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
switched off on purpose (§5). The fog therefore received **nothing**, and
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
| MAP26 | on, ramped 0.01 → 10 over 32 m at curve 2.4 | *Hardcore.* The map this was built for, and the one with a reference shot. Colour inherited from its own `fade` `00 56 56`; density, far density, ambient, reach and curve all **stated in the row**, the way `RT_MOON_PRESETS` states MAP13's azimuth. `illum` forced on — see §5. |
| MAP25 | the same medium, by name | *Cat and Mouse.* Its MAPINFO carries the **same** fog as MAP26 verbatim — `fade` `00 56 56` at `fogdensity 200` — under the same flat-teal `VOIDSKY`, and its moon is off the same way (§5). Those are the three things the MAP26 profile depends on, so it gets that profile rather than a tuned-alike copy of it. |
| MAP31 | the same medium, by name | *The secret map,* and the third and last `VOIDSKY` map. Identical on all three counts again, so the same row and the same moon change. |

### The three cyan maps are one family

That is worth stating as a fact about the game rather than three separate
judgements, because it was **checked in the WAD, not eyeballed**: the sky here is
a skybox *room*, and every map's MAPINFO `sky1` says `ISUCK`, so the sky cannot
be identified from MAPINFO at all. Scanning the `TEXTMAP` lumps for the `VOIDSKY`
texture finds exactly **MAP25, MAP26 and MAP31** in the main campaign — and those
same three are the only maps whose `fade` is `00 56 56` at `fogdensity 200`.
Same sky, same authored fog, same moon treatment, one medium.

(`VOIDSKY` also appears in three bonus-episode maps — `ABS05`, `OUT03`, `OUT10` —
but two of those fade dark red and the third has no fade at all, so the texture
is doing something else there. Look before assuming.)

The three rows share the numbers through **`RT_FOG_MEDIUM_MAP26`**, a nine-value
paste defined just above the table, for the reason the colour is inherited
rather than restated: a second literal copy is the one that goes stale the first
time the profile is retuned, and the maps then drift while all of them claim to
match. A map wanting a *different* look writes its own row out in full — the
shared medium is only for "the same medium", and being a compile-time paste it
leaves the `fog` CCMD printing an ordinary paste-ready row.

### The MAP26 profile

The shipping medium is a **luminous veil, not an occluder**:

    rt_fog_density       0.01     at the camera
    rt_fog_density_far   10       at rt_fog_far
    rt_fog_ambient       1        the unlit floor
    curve 2.4, reach 32 m         (the two values MAP26's row states itself)

| distance | | transmittance |
|---|---|---|
| 128 map units | 4 m | 1.00 |
| 256 | 8 m | 1.00 |
| 512 | 16 m | 0.98 |
| 768 | 24 m | 0.93 |
| 1024 | 32 m | 0.83 — and everything beyond |

So about a sixth of a distant surface is fog and **nothing is hidden**. What
makes it read is not extinction, it is the in-scattered light: `rt_fog_ambient 1`
is fifty times the floor the first, thick version used, so the medium **glows on
its own** and the level's lights modulate that glow rather than supply it.

That is a different design from where this started, and it is worth being
explicit about the trade, because it inverts the argument in §2: with the floor
dominating, less of what you see is the lights' doing. `tools/ab-fog.cmd
noambient` is the fog with the floor removed entirely — the lit component alone —
and it is now the more informative arm of that pair.

The heavy profile is one command away and still tuned:
`ab-fog.cmd ramp2` / `wall` are the occluding versions (transmittance 0.15 and
0.01 at 768 units), and the arithmetic below sizes any other.

**These numbers are baked into the row, not inherited**, exactly as
`RT_MOON_PRESETS` bakes MAP13's azimuth 90. This is the map's authored look
rather than a global that happens to suit it, so it must not depend on a
launcher pin or on whatever an `ab-fog.cmd` arm last left in the ini: launch the
game normally on MAP26 and this is what you get.

Reach 32 m is 1024 map units, past which everything takes the far slice, so the
fog stops deepening at corridor distance; curve 2.4 holds the near value out to
about half the volume before it climbs.

**Colour is the one thing still inherited** (`0` → the map's own `fade`), because
that genuinely is authored data living somewhere else, and a copy of it here is
the copy that goes stale. The cvar defaults and the launcher pins carry the same
densities, but only as the starting point for a map being tuned with
`rt_fog_presets 0` — they are not what MAP26 uses.

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

## 4. The flashlight, and the one thing lit fog gets wrong

Switch a flashlight on inside the medium and the screen whites out. Nothing is
broken: a light standing in fog lights the froxels around it by inverse square,
and the flashlight is at ~0 m, so the cells directly in front of the camera get
an enormous in-scattered term. That is exactly what a headlight in fog does, it
is why fog lamps are mounted low and aimed down, and in a first-person game it
is unplayable — the torch becomes a switch that blinds you.

It is also *only* a problem for lights you are carrying. The same effect a few
metres down the corridor is the shaft of light through fog that this whole
feature exists to produce.

So `rt_fog_light_near` (2 m) fades in-scattering out within that distance **of a
light** — keyed off the light's position, never the camera's. Glare from
something you are holding goes; the beam ahead of you survives; a lamp on a wall
five metres away is untouched. Muzzle flashes get the same treatment for free,
which they needed for the same reason.

**One exception, added later.** Muzzle flashes needed the fade because of what
they do to fog filling the whole screen. They do something else to *localised
smoke*: a muzzle flash is at ~0 m from its own puff, and lighting that puff from
inside is the entire point of `docs/rt-smoke.md`. So the fade is now chosen **per
froxel** — `rt_fog_light_near` in fog, `rt_smoke_light_near` (0) inside a puff —
rather than read from the uniform directly. A cell with no smoke in it is
unaffected, which is deliberate and is what `ab-smoke.cmd fogsafe` checks.

Directional lights are unaffected: `sampleLight` puts the moon's and the
lightning's sampled position far away, so the fade never triggers on them.

`0` restores the physical behaviour, and `tools/ab-fog.cmd flshraw` is that arm —
kept so the fade can be *seen* doing something rather than trusted. `flsh` is the
same profile with the fade at its default, and `flshwide` at 5 m if 2 still
glares.

The implementation is one clause in `traceDirectIllumination`, inside
`#if LIGHT_SAMPLE_METHOD == LIGHT_SAMPLE_METHOD_VOLUME`, so it touches the fog
and nothing else — surfaces still receive the light physically.

---

## 5. The moon is off on all three fogged maps, and that is part of this

`RT_MOON_PRESETS` already hid the moon **disc** on MAP25, MAP26 and MAP31: they
are the three `VOIDSKY` maps, whose skybox is a plain box of flat dark teal with
no starfield, no cloud and no horizon — a moon hanging in it is the one object on
screen with no reason to be there.

All three now also turn the moon's **light** off (`intensity 0`). Two reasons,
and both are about the fog:

- **A directional light is the one thing that wrecks a fogged level.** It rakes
  the froxel volume from a single bearing, so the fog reads as a lit slab with a
  hard edge across it instead of as the even medium the map was authored around.
- **There was nothing legitimate to arrive through.** None of these maps' rooms
  have an opening the moon could honestly come through, so under
  `rt_sun_require_sky` most of what it delivered was leak in the first place —
  see `docs/moon-and-sky-leaks.md`.

The fog's light now comes from the level's own lamps and lava, which is where it
should have come from. `tools/ab-fog.cmd moon` puts the moon back for the
comparison, rather than leaving the decision asserted.

This is also what makes the shared medium legitimate rather than a coincidence of
colour: `illum 1` is load-bearing on all three, because with the moon off the
single-light path leaves the fog with **no source at all** (§2).

**The two tables have to move together, and that is the thing to preserve.**
Taking a directional light away has a real cost — on a map with F_SKY1 openings,
rooms lit through them flatten — and what fills the space here is the fog's own
in-scattered floor, `rt_fog_ambient 1`. So an `intensity 0` moon row *without* a
fog row would leave a map simply darker, with nothing put back. Whichever way a
fourth map is added, add both.

---

## 6. Testing

`tools/ab-fog.cmd <arm> [map]`, default MAP26:

Transmittance below is at 128 / 256 / 512 / 768 / 1024 map units, computed from
the formula above rather than eyeballed.

**Profiles** — walk the same corridor in each:

| arm | ramp | T |
|---|---|---|
| `full` | the shipping row, via the preset table (MAP25 / MAP26 / MAP31 only) | 1.00 1.00 0.98 0.93 0.83 |
| `ramp` | the same profile forced onto any map — 0.01 → 10, curve 2.4, 32 m | as above |
| `veil` | 3 → 70, curve 2.0, 40 m. Air, not weather | 0.98 0.95 0.85 0.65 0.41 |
| `ramp2` | 6 → 320, curve 3.0, 32 m. Same clear air, harder wall | 0.95 0.89 0.60 0.15 0.00 |
| `wall` | 2 → 700, curve 4.0, 28 m. Nothing, then shut | 0.98 0.95 0.54 0.01 0.00 |
| `deep` | the shipping shape over 60 m, for rooms 32 m closes too early in | 0.97 0.95 0.87 0.74 0.54 |
| `even` | no ramp — the map's own density, uniform | 0.71 0.51 0.26 0.13 0.07 |
| `flatramp` | the shipping ends at curve 1.0 — the failure the curve avoids | 0.87 0.63 0.19 0.03 0.00 |
| `inverse` | backwards: thick around you, clear beyond | |
| `twotone` | the ramp with the tint split as well | |

On any of the three listed maps, `ramp` and `full` should be
**indistinguishable**: they are the same numbers by two different routes. If they
are not, the preset table did not apply, which makes this a free check that a row
is live — and on the two newer rows it is the check that they are live at all:

    .\tools\ab-fog.cmd full 25   against   .\tools\ab-fog.cmd ramp 25
    .\tools\ab-fog.cmd full 31   against   .\tools\ab-fog.cmd ramp 31

`even` and `flatramp` are the two failures this profile was arrived at through,
kept for that reason: `even` is a uniform MAPINFO-derived medium (**0.71 at 128
map units** — nearly a third of the wall two metres from your face is already
fog), and `flatramp` is a ramp whose curve starts thickening at the camera.

**Flashlight** (§4):

| arm | |
|---|---|
| `flsh` | the shipping profile, flashlight lit at launch |
| `flshraw` | the same with `rt_fog_light_near 0` — the whiteout |
| `flshwide` | fade at 5 m, if 2 still glares |

**Isolation:**

| arm | what it isolates |
|---|---|
| `off` | `rt_fog 0` — the global `rt_volume_*` values. What the map was before |
| `nolight` | `rt_fog_illum 0` — the fog lit by the one light it used to get, i.e. none on this map |
| `flat` | RTGL1's depth-based fog in the same colour: one `exp()` per pixel, no volume, no lighting |
| `ambient` | `rt_fog_ambient 4` — four times the shipping floor; the lights stop registering against it |
| `noambient` | `rt_fog_ambient 0` — nothing but what the level's lights scatter. Says how much of the fog is lit and how much is the floor |
| `grey` | the colour taken out, the density kept |
| `thin` / `dense` | a third / double the MAPINFO-derived density, so they bite only while a map is on the sentinel |
| `reach20` / `reach90` | `rt_fog_far` — the volume's reach and its precision at once |
| `moon` | the moon put back on (§5) |
| `debug` | `full` + `rt_fog_debug 1` |

`rt_fog_debug` is `RT_CVAR_NOARCH` on purpose, like `rt_sun_leak_debug` and
`rt_water_debug`: a debug mode that sticks in the ini is how a fix gets believed
to be inert for a whole round trip.

---

## 7. Files

| file | role |
|---|---|
| `rt_main.cpp` | `rt_fog_*`, `RT_FOG_PRESETS`, `RT_ResolveFog`, the `fog` CCMD, and the volumetric params handed to RTGL1 |
| `RTGL/.../RtVolumetric.rgen` | the froxel pass: `volumeMediaColor`, `ILLUM_VOLUME_ACTIVE` |
| `RTGL/.../CmScatterAccum.comp` | the depth-based path, tinted alike so `flat` is a real A/B |
| `RTGL/.../VulkanDevice.cpp` | `volumeAllLights` / `volumeMediaColor` uniforms |
| `RTGL/Include/RTGL1/RTGL1.h` | `illuminateFromAllLights`, `mediaColor` on `RgDrawFrameVolumetricParams` |
| `tools/ab-fog.cmd` | the arms above |

## 8. Known limits

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
  **Partly lifted since.** `docs/rt-smoke.md` adds world-space *spheres* of
  medium on top of this one, so the volume can now say "there is something here"
  after all. That is the mechanism per-sector fog would want; what it does not
  have is a way to bind to geometry rather than to a radius, and 32 spheres do
  not cover a room.
- **The sky is fogged too, at full strength.** A sky pixel's world position is
  past `rt_fog_far`, so it samples the far slice like any other distant surface
  and comes back fully covered. On MAP26 that is right — `VOIDSKY` is flat dark
  teal and the fog colour is its own `fade` — but a map with a painted sky and a
  strong fog colour would have that sky replaced by the fog, and that is the
  first thing to check when listing one.
- **Six fogged maps are still unlisted** (§3), and the cheap ones are gone: the
  cyan `VOIDSKY` family is complete, so what is left differs in colour, in
  density, or in both, and **none of it should be given `RT_FOG_MEDIUM_MAP26`
  without being looked at**. MAP17 `3C 14 0A`, MAP27 `80 1E 00`, and in the bonus
  episodes RTR03 (cyan, but density **64** — a third of the others, so not the
  same medium), RTR04 `80 1E 00`, ABS05 and OUT10 `64 00 00` at 180. A warm fog
  is also the case §8's sky warning is about: these maps do not have a flat teal
  void behind them.
- **Cost is a shadow ray per froxel cell** with `rt_fog_illum 1`. Measure before
  adding rows, not after.

## See also

- `docs/rt-fog-implementation.md` — the code path end to end: every file the
  fog touches in the order the data moves through them, the uniform layout, the
  optical-depth arithmetic, and the four traps
- `docs/moon-and-sky-leaks.md` — why MAP26's moon is off and what
  `rt_sun_require_sky` had already done to it
- `docs/rt-clouds-and-lightning.md` — the same opt-in per-map table shape, and
  the same "the table overrides your `+cvar` pin" trap
