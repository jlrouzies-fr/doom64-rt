# First-person weapon models under RT: how it works, and what is missing

## What `rt/replace/` actually is

It is not GZDoom's VOXELDEF voxel renderer. It is RTGL1's **glTF replacement** system.
Each `set_*.gltf` in `rt/replace/` (the folder name is fixed — `REPLACEMENTS_FOLDER` in
`deps/RTGL/Source/Const.h:62`) contains nodes **named after sprite frames** — `HEADA`,
`TROOB`, `SHTGA`. When the engine uploads a sprite primitive, RTGL1 looks the name up and,
on a hit, discards the billboard quad and instances the authored mesh instead. The models
look voxelised only because they were modelled that way; the engine neither knows nor cares.

Only `.gltf` files are read — `GetGltfFilesSortedAlphabetically` (`Scene.cpp:161-190`) filters
on `FileType::GLTF`, so a `.gltf_unfinished` is skipped entirely.

## First-person weapons are already wired for this

The viewmodel path is complete in the engine; nothing was missing. Chain:

| Where | What it does |
|---|---|
| `hw_weapon.cpp:136-145` | `DrawPlayerSprites` pushes `RtPrim::FirstPerson`, and for a plain sprite layer (`!mframe && texture`) also `RtPrim::ExportInstance` + `push_exportinstance_name(texture->GetName(), weapon->GetFrame())` |
| `rt_state.h:210-233` | builds the 5-char key: first 4 chars of the texture name + `'A' + frame` — e.g. `SHTG` + `A` |
| `rt_main.cpp:2919-2930` | turns those tags into `.pMeshName`, `.isExportable = true`, `RG_MESH_EXPORT_AS_SEPARATE_FILE` |
| `Scene.cpp:565-592` | `UploadPrimitive` requires exactly those three, then `find_p(replacements, mesh.pMeshName)` |
| `VertexCollectorFilterType.cpp:98-107` | replacement geometry keeps `PV_FIRST_PERSON`, so a replaced viewmodel still gets the first-person instance mask |

The three real blockers were assets and packaging, not code:

1. `rt/replace_old/` was renamed away from the folder RTGL1 reads, so *nothing* was replaced.
2. `set_1_weapons.gltf_unfinished` was skipped by the extension filter.
3. The set is the stock **Doom 1/2** weapon shapes with ~19 of 118 frames modelled.

Items 1 and 2 are now fixed (`rt/replace/set_1_weapons.gltf`, in both
`gzdoom-rt-1.0.2/rt/` and the live `sourcecode/gzdoom-rt/build/RelWithDebInfo/rt/`).

## Authoring contract for real D64 weapon models

Derived from the shipped sets, and confirmed against the transform code:

- **One glTF node per psprite frame**, named `<4-char sprite><frame letter>`: `SHTGA`,
  `SHTGB`, … `PISGA`, `SAWGA`. The letter is `'A' + DPSprite::GetFrame()`. Nodes whose names
  are not in this shape (`meshBFGGA`, `Cube`, `PUNGA.001`) are never looked up.
- Parent everything under a `rtgl1_main_root` node carrying the rotation
  `[0, -0.7071068, -0.7071068, 0]`, as the existing sets do.
- **Vertices in view-space metres.** `MakeFirstPersonQuadInWorldSpace` (`rt_main.cpp:2681-2765`)
  hands RTGL1 the **camera-to-world** matrix as `mesh.transform`, so the model's own
  coordinates are relative to the eye. The existing `SHTGA` sits at roughly z ≈ −0.3 m with
  extents ±0.15 m. Copy that placement rather than re-deriving it. (World-sprite replacements
  are the other convention: `HEADA` is ~2 m tall around the origin.)
- **Model every frame of a weapon, or it pops.** An unmatched frame silently falls back to the
  flat billboard mid-animation. Frames with no visible motion can reuse one mesh under a
  second node name.

Suggested route: model against the D64 sprites in Slab6/MagicaVoxel, export `.kvx`/`.vox`,
then run the fork's own converter — `-vox2gltf`, in
`sourcecode/gzdoom-rt/src/common/models/models_voxel.cpp` (`VOXEL_TO_GLTF`, enabled under
`HAVE_RT`) — and rename/reparent the resulting nodes to the contract above. That keeps the
`vx_<lump>` palette-texture naming the RT material path expects.

## Known limitation: no bob

A replaced viewmodel rides **only** the camera matrix. The psprite x/y offset and the weapon
bob live in the quad's vertices, which the replacement throws away, so the gun is rigid
relative to the eye. Fixing that means folding the psprite offset into `mesh.transform`; it is
deliberately out of scope for this pass.

## Coverage: Retribution psprite frames vs `set_1_weapons.gltf`

Frames read from `Doom64-Retribution/D64RTR_v15.WAD` (between `SS_START`/`SS_END`); model
nodes read from the glTF. Retribution reuses the classic lump names, so the names match even
though the artwork is Doom 64 — meaning the stock models will render **Doom 1/2 weapon shapes**.

| weapon | sprite | WAD frames | modelled | missing |
|---|---|---|---|---|
| Fist | `PUNG` | A (1) | A | — |
| | `PUNF` | ABCDEFGHIJKL (12) | — | ABCDEFGHIJKL |
| Chainsaw | `SAWG` | ABCD (4) | — | ABCD |
| | `SAWF` | AB (2) | — | AB |
| Pistol | `PISG` | ABCDEF (6) | — | ABCDEF |
| | `PISF` | AB (2) | — | AB |
| Shotgun | `SHTG` | ABCDEFGHIJ (10) | A | BCDEFGHIJ |
| | `SHTF` | AB (2) | — | AB |
| Super shotgun | `SH2G` | ABC (3) | — | ABC |
| | `SH2F` | BCDEFGHIJKLMNOPQRS (18) | — | BCDEFGHIJKLMNOPQRS |
| | `SSGF` | AB (2) | — | AB |
| Chaingun | `CHGG` | ABCD (4) | AB | CD |
| | `CHGF` | ABCD (4) | AB | CD |
| Rocket launcher | `MISG` | ABC (3) | AB | C |
| | `MISF` | ABCD (4) | ABCD | — |
| Plasma rifle | `PLSG` | ABCDEFGHR (9) | A | BCDEFGHR |
| | `PLSF` | AB (2) | AB | — |
| BFG 9000 | `BFGG` | ABCDE (5) | AB | CDE |
| | `BFGF` | ABCDEFGH (8) | AB | CDEFGH |
| Unmaker | `UNMA` | A (1) | — | A |
| | `UNMF` | A (1) | — | A |
| | `UNML` | A (1) | — | A |
| Alt / classic | `BFUG` | A (1) | — | A |
| | `CBFG` | ABCDE (5) | — | ABCDE |
| | `CLCG` | ABCD (4) | — | ABCD |
| | `CSSG` | ABCD (4) | — | ABCD |

**19 of 118 psprite frames have a model; 99 fall back to the flat sprite.**

Model nodes with no matching Retribution frame (dead weight): `PUNGB`, `PUNGC`, `PUNGD`.

Two weapons have **zero** coverage and are entirely absent from the set: the pistol (`PISG`)
and the chainsaw (`SAWG`), plus the Doom 64 Unmaker and Retribution's alt/classic weapons.

## Why the stock models look wrong, and the two fixes

Diagnosed after the first pass. Both are **asset-only** — no engine change is needed.

### The blocky look is a shading problem, not a geometry problem

Duke-RT 0.4.2's fix was *"calculate normals at the whole voxel level based on neighbor
occupancy"*. Its before/after screenshot is a normals debug view: the left half has two or
three flat colours because every face normal is axis-aligned; the right half has a continuous
gradient. **The silhouette is identical in both.** Only lighting changes.

Our stock enemy models are exactly the "before" half — `set_5_doom1a` POSSA is 100%
axis-aligned (27,157 of 27,157 vertices), as is `set_5_head` HEADA (143,575 of 143,575). The
weapon set is mixed: SHTGA is 5.7% (hand-modelled and smooth-shaded), CHGGA is 100%.

RTGL1 honours normals baked into a replacement glTF. `VertexPreprocessPartial.inl:66`
overwrites vertex normals with the flat face normal whenever `GENERATE_NORMALS` is set (which
the importer never clears), **but** `Scene.cpp:545` only dispatches
`VERT_PREPROC_MODE_ONLY_DYNAMIC`, `CmVertexPreprocess.comp:47` gates on
`GEOM_INST_FLAG_IS_DYNAMIC`, and replacements upload with `isDynamicVertexData = false`. So
replacement normals are never touched.

**The raw occupancy gradient is not safe to use on its own.** These models are thin shells —
POSSA has 5046 surface voxels but only 9 interior cells — and for a one-voxel-thick plate the
empty neighbours sit symmetrically on both sides, so the gradient can point straight through
the surface. Measured on POSSA: **34.6% of faces got a normal facing the wrong way**, which
shades worse than the blocky original. `rt_voxel.shade_normal` keeps only the gradient's
component *tangential* to the face normal, so the normal can tilt along the surface but never
leaves the face's hemisphere.

### Every enemy model is ~30% too short

Doom 64 redrew its sprites larger at the same 1px = 1 map unit mapping; the stock models were
built to the DOOM II sprites. Retribution's actors confirm it — `64ZombieMan` declares
`Height 80` with no `Scale` override, and `POSSA1` is 80px.

| sprite | model height | D64 sprite px | actor Height | ratio |
|---|---|---|---|---|
| POSS | 55 | 80 | 80 | 0.69 |
| CYBR | 108 | 163 | 160 | 0.66 |
| HEAD | 67 | 95 | 56 (floats) | 0.71 |
| SARG | 54 | 84 | — | 0.64 |
| PAIN | 57 | 102 | — | 0.56 |

### Pilot results

`tools/rt_voxel.py` + `tools/gen_d64_poss.py` + `tools/gen_d64_psprite.py`. Both write a new
higher-priority set rather than editing stock files — RTGL1 reads `rt/replace` in reverse
alphabetical order and keeps the first insertion per mesh name (`Scene.cpp:854-942`), so
`set_9_*` wins over `set_5_*`. Delete the output to revert.

| | POSS (`set_9_d64_poss`) | PISG (`set_9_d64_pisg`) |
|---|---|---|
| frames | 21 (A–U) | 6 (A–F), full coverage |
| axis-aligned normals | 100% → 7.1% | 19.2% |
| wrong-side normals | 0 / 14,684 | 0 / 113,796 |
| height | 55 u → **80.0 u**, foot plane still z=0 | scaled to the measured quad |

PISG is generated from the D64 art itself: depth per pixel follows `sqrt(distance to
silhouette edge)` so it reads as a rounded solid, and frames are positioned by their own
`grAb` offsets — those vary 15px vertically across PISGA–F (`-71` to `-86`), which *is* the
pistol's recoil. Anchoring frames on a common top would have flattened the animation out.

**Viewmodel space is CAMERA space, not world space.** A replacement viewmodel rides
`m_mainCameraView_Inverse` as its mesh transform, so its vertices are in the usual GL camera
convention: **X right, Y up, −Z forward**. This is *not* the Z-up that world-space enemy
replacements use (those are placed by `CalculateTrueTransformAndItsVerts`), and assuming Z-up
here produces a model rotated 90° — you see the extrusion's depth profile edge-on as a lens.
Confirmed against the stock SHTGA mesh: 7.6 cm wide in x, 5 cm tall in y and entirely below
the eye, 13 cm long in z pointing away, at node translation `z = -0.106`. Note the axis map
from sprite space has determinant −1, so triangle winding must be reversed with it.

**Measured psprite quad (1440p-ish, default FOV).** From `rt_wpn_debug 1`:

```
RTWPNQUAD PISGA0 min=(-0.0175 -0.0596 -0.0778) max=(0.0107 -0.0162 -0.0778) size=(0.0282 0.0433 0.0000) m
```

Two things to note. The quad is **flat** (`size z = 0`), so the model extrudes symmetrically
about `z = -0.0778`. And it is **not centred on x** — its centre is `-0.0034`, so a model
centred on zero sits visibly right of where the sprite was. The real quad is 2.82 x 4.33 cm;
a placeholder guessed from SHTGA was 3x too big.

**Load order is ambiguous from the log.** RTGL1 warns `"Ignoring a replacement as it was
already read from another .gltf file"` for the *loser*, but prints its path as
`'<TODO: GET NAME>'`, so the log never says which file won. `Scene.cpp:856-905` reads
reverse-alphabetically and keeps the first insertion, which should make a later-sorting name
win — but that was not observable. Until it is confirmed, `gen_d64_enemy.py` takes `--out-set`
twice and publishes identical content at both ends of the sort order. Only the winner is
cached (the `isNew` gate), so the duplicate costs disk and import time, not VRAM.

**Old open item — psprite scale.** A viewmodel is not at 1px = 1 unit; its size comes from
`GetWeaponRect` (viewwidth/viewheight, SCREENWIDTH/HEIGHT, WidescreenRatio, screenblocks,
baseScale) and then the inverse projection in `MakeFirstPersonQuadInWorldSpace`. Rather than
reproduce that offline, `rt_wpn_debug 1` now prints the view-space box the engine actually
built:

```
RTWPNQUAD PISGA0 min=(x y z) max=(x y z) size=(W H D) m
```

Feed those to `gen_d64_psprite.py --quad-min ... --quad-max ... --quad-frame A` and regenerate.
Until then the set ships with a placeholder box: roughly the right size, wrong position.

## Making an enemy actually D64-shaped: silhouette carving

Rescaling fixes height, not shape. `tools/gen_d64_carve.py` reconstructs the real shape from
the art: frames A–G of a monster have all 8 rotations, which is enough for
shape-from-silhouette. This is required rather than optional, because RTGL1 keys replacements
on sprite+frame with **no rotation** — one model serves all eight viewing angles, so a
single-view extrusion cannot work for a monster the way it does for a viewmodel.

**Strict intersection fails on this art.** Doom sprite rotations are hand-drawn, not renders
of one 3D model, so they are not geometrically consistent. Requiring all 8 views to agree
deletes every voxel below z=18 on POSSA — the entire legs — because a thin feature vanishes as
soon as one view disagrees by a pixel. Voting fixes it. Measured on POSSA:

| views required | height | mean IoU vs source silhouettes |
|---|---|---|
| 8 of 8 | 61 u | 0.599 — legs deleted |
| **7 of 8** | **77 u** | **0.774 — best agreement** |
| 6 of 8 | 78 u | 0.717 |
| 5 of 8 | 80 u | 0.645 — hull bulges outside the silhouettes |

**The rotation convention cannot be found by scoring.** With 8 rotations at uniform 45°
spacing, every convention carves the *same hull* and differs only in final orientation and
chirality, so all 8 candidates score identically. Scoring against the (correctly oriented)
stock model separates them only weakly — a humanoid is near-symmetric front-to-back, and the
stock mesh is a hollow shell against our solid carve, capping IoU near 0.29. So it is derived
instead: Doom's rotation 1 is the view from the direction the actor faces, rotations advance
45° from there, and with the camera at +x looking along −x with +z up, screen-right is +y →
`base=0, direction=+1, flip=+1`. That matches the top empirical candidate within noise.
`--base/--direction/--flip` override it if a monster faces the wrong way.

Voting can shave the soles off, so each frame is dropped back onto z=0 — the sprite origin is
the feet (`topoffset == height`) and in a walk cycle some foot always touches.

Colour comes from whichever rotation most directly faces each surface voxel, written to a
palette-strip texture like the stock `vx_*.tga`. POSS and SPOS have byte-different lumps but
identical silhouettes, so they carve to the same hull and differ only in palette (13 shared
colours of 125/106) — that is correct, not a bug.

### Set naming and load order

Load-order priority is still unconfirmed (see above), so each generator publishes at both ends
of the sort order, arranged so the carve beats the rescale either way:

| | low end | high end | supplies |
|---|---|---|---|
| carve | `set_00_d64_carve` | `set_99_d64_carve` | POSS/SPOS frames A–G |
| rescale | `set_01_d64_rescale` | `set_98_d64_rescale` | frames H–U (death/pain, rotation 0 only) |

Only the winner is cached, so the duplicates cost disk and import time, not VRAM. Budget check:
27.2M of 33.5M vertices (`replacementsMaxVertexCount`, `rt_main.cpp:4728`).

## All D64 weapons: one calibration, no further measurements

`tools/gen_d64_psprite.py` now generates every weapon from one RTWPNQUAD line. The two scale
factors in `GetWeaponRect` depend on the screen setup only — **not on the sprite** — so a single
measurement fixes metres-per-pixel for all weapons, and each frame's position follows from its
own `grAb`:

```
left_px = (-grAb.x) - 160        top_px = (-grAb.y) - C
```

with `C` absorbing the constant `YAdjust`/`ftextureadj` terms. Calibrated on PISGA it
reproduces the measured quad to 0.1 mm on every edge. Re-calibrate only if the resolution or
status bar changes.

**Flash frames are deliberately not replaced.** A muzzle flash is a billboard glow, not an
object; extruding one into a solid is wrong, and the stock set models them as flat 4-vertex
planes for that reason. Leaving `*F*` frames alone keeps the engine's own sprite and drops the
vertex cost from 5.57M to 3.36M — the difference between 1.1M and 3.3M headroom.

47 frames: PUNG, SAWG, PISG, SHTG, SH2G, CHGG, MISG, PLSG, BFGG, UNMA, UNML.
Sets `set_02_d64_wpn` / `set_97_d64_wpn` (both ends of the sort order, as above).

Verified: 0 wrong-side normals across 260,752 triangles, no non-unit normals, all 47 textures
present, 30.2M of 33.5M vertices cached. Axis-aligned normals fall to 18–33% per weapon
(PISGA 18.4%, BFGGA 32.6%), i.e. two thirds to four fifths of vertices carry a tilted
occupancy normal rather than a raw face normal.

## Verifying it in game

`rt_wpn_debug 1` now prints, per first-person primitive, the exact lookup key and the three
conditions that gate replacement (`rt_main.cpp`, in the existing `rt_wpn_debug` block):

```
RTWPN SHTGA0 mesh="SHTGA" exportable=1 sepfile=1 replaceable=1 flags=0x... ...
```

Read it as three separate answers:

- `mesh="..."` — must match a glTF node name **character for character**. `mesh="(null)"`
  means the layer was not tagged `ExportInstance` at all (this is what a HUD *model* layer
  looks like, and it can never be replaced).
- `replaceable=1` — all three RTGL1 preconditions hold; the lookup will be attempted.
- Then, on screen: the frame renders as geometry rather than a billboard — parallax when
  strafing, and it takes RT lighting instead of staying flat.

If names match and `replaceable=1` but nothing changes visually, check RTGL1's own
`debug::Verbose` replacement-import log — a glTF with missing material textures is imported
but reported, and `replacements` is keyed on the node name at import time (`Scene.cpp:854-942`).
