# Solo bulb lamps — SFLATDE and SFLATCH

Lighting two ceiling textures that each show a single lit bulb in the art. Not
the same feature as [[faux-lamp-panels]] (SFLATC/SPACECE) — the distinction is
the whole reason this is a separate system rather than two more names added to
that one.

## Why this is not the faux system

SFLATC and SPACECE show **blank, unlit sockets** — no bulb in the art at all,
and the invented light is a lie told to lift a room that reads as too dark.

SFLATDE and SFLATCH show an **actual lit bulb**: a bright white blob centred in
an X-shaped or ringed housing. The base game simply never wired a light to it.
That is the same "texture implies a fixture" reasoning behind the *real* bulb
arrays (SFLATAS/SFLATAQ/SPORT\*, `RT_IsCeilingInsetLampTexture`), not an
invention — these two names just aren't in that classifier.

They weren't added to it. `RT_UploadCeilingInsetLamps`' shared intensity (700,
and currently switched off entirely — `rt_ceiling_lamps 0` in the launcher) is
tuned for a different fixture family; folding SFLATDE/SFLATCH into it would
either relight nothing (feature off) or retune those other fixtures as a side
effect of this request. So this is its own cvar family, own budget, own colour,
exactly like the faux system is kept apart from the real one for the same
reason.

## Where they were found

Traced from a moving-ceiling report — the room turned out not to use SPACECE
(see [[faux-lamp-panels]]'s placement section for that dead end) but SFLATDE:

| map | sectors | tags | notes |
|---|---|---|---|
| MAP03 | 24, 25, 26, 27, 28, 29, 30, 43 | none, 6–11 | nested/stepped shafts, ceiling 480 throughout — sector 24 (768×768) contains 25→26→27→28 (768→352→352→96 wide), each independently tagged. Reads as a Doom64-style sequential mover puzzle |
| MAP08 | 95, 97, 99, 100, 101, 102, 108, 109, 188 | none, 28, 29, 31 | ceiling 256 throughout |

SFLATCH is used in MAP03 (sectors 51/47, light 200) — the wall ledge dressed in
SPACECE from the placement investigation sits directly under an SFLATCH
ceiling, which is almost certainly the room originally being described.

## Detected bulb centres

Same method as the faux system's socket detection (`tools/make_bulb_textures.py`):
flood-fill the bright blob, take its centroid. Both textures are 64×64.

| texture | centre | housing |
|---|---|---|
| SFLATDE | (31.5, 30.5) | X-shaped cross |
| SFLATCH | (32.0, 32.0) | plain ring |

Off-square by design, not rounding: SFLATDE's blob is not exactly centred, and
the code carries **separate x/y offset arrays** rather than reusing one array
for both axes (the faux system's SFLATC lattice is square, so one array served
both axes there — generalizing to `offX[]`/`offY[]` was needed to carry an
asymmetric single point).

## Cvars

| cvar | default | notes |
|---|---|---|
| `rt_solo_lamps` | `1` | master switch |
| `rt_solo_lamp_color` | `FFFFFF` | plain white, used **raw** like the faux colour — but with no darkening intent, this is just "white," not a design choice worth tuning |
| `rt_solo_lamp_intensity` | `90` | well under the real ceiling-edge walk (180), faux (500), and the real inset lamps (700) — "not too strong," on request |
| `rt_solo_lamp_radius` | `0.06` | tighter than faux/real (0.35/0.10): a single visible bulb reads better as a harder, more precise source |
| `rt_solo_lamp_zofs` | `8` | drop below the ceiling plane |
| `rt_solo_lamp_max` | `64` | own budget — SFLATDE alone tiles across MAP03's 768×768 sector 24 (144 positions at stride 1), which must not be able to starve the faux or real lattices |
| `rt_solo_lamp_stride` | `1` | light every bulb by default — unlike SFLATC's dense invented grid, these are a handful of genuine fixtures per map |

## Implementation: one shared lattice walk, three independent budgets

The placement mechanism generalizes the faux system's tile-lattice walk
(`addLattice`, formerly `addFauxLattice`) rather than duplicating it: given a
sector, a set of per-tile offsets, and where to push the result, it walks every
64-unit tile the sector's bounding box touches, tests each candidate point with
`PointInSector` (so an L-shaped room doesn't leak lights into its neighbour),
and respects a max-distance cull. SFLATC calls it with its 4×4 grid; the solo
textures call it with a single `(ox, oy)` point.

What does **not** get shared: color, intensity, radius, z-offset, stride, or
light budget. Each candidate now carries its own `intensity` and `radius`
(previously the code carried a `bool faux` and picked between two hardcoded
values at emit time — that stopped generalizing past two classes, so `Cand`
now just stores the final numbers directly, set once per candidate at push
time). All three candidate lists — real perimeter walk, faux lattice, solo
lattice — trim against their own cap independently, and only then merge and
sort by distance for the marker/emit pass. A solo bulb can never outcompete a
faux panel or a real fixture for a light slot, in either direction.

Light IDs live in their own range too: `SoloLatticeId_Base = 1ull << 40`, well
above anything `FauxLatticeId_Base`'s `secIndex << 20` encoding could reach on
a map with thousands of sectors — a "next round number" would not have been
provably safe.

## Not yet done

- **Not judged in game.** Verified only by reading cvar names and the two
  texture literals back out of the built `gzdoom.exe`, same discipline as the
  rest of this session.
- **No emissive/texture work.** Unlike SFLATC/SPACECE, these textures already
  show a lit bulb, so no repaint or `_e` mask was needed — this is purely the
  missing light source.
- MAP08's usage hasn't been walked in the same detail as MAP03's — the
  classifier will light it identically, but nobody has looked at whether 90
  intensity reads right there too.
