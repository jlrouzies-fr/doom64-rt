# Making voxel models for Doom 64 RT

Everything learned building the D64 weapon and enemy replacement models. Read this before
touching `rt/replace/` or the `tools/gen_d64_*.py` scripts.

Companion doc: [`rt-weapon-model-coverage.md`](rt-weapon-model-coverage.md) holds the
per-sprite coverage tables and the first-person plumbing trace.

---

## 1. What this system actually is

`rt/replace/` is **RTGL1's glTF replacement system**, not GZDoom's VOXELDEF voxel renderer.
Each `set_*.gltf` contains nodes **named after sprite frames** — `POSSA`, `SHTGB`, `PISGA`.
When the engine uploads a sprite primitive, RTGL1 looks the name up and, on a hit, throws away
the billboard quad and instances the authored mesh instead. The models look voxelised only
because they were built that way; the engine neither knows nor cares.

Only `.gltf` files are read (`Scene.cpp:161-190`, `FileType::GLTF`), so renaming a file to
`.gltf_unfinished` disables it. The folder name is fixed as `replace`
(`REPLACEMENTS_FOLDER`, `deps/RTGL/Source/Const.h:62`) — renaming the folder disables
everything.

### The name key

Built in `rt_state.h:210-233` as **4 sprite chars + `'A' + frame`** — so `SHTG` + `A`. Note
what is *not* in it: **no rotation**. One model serves all eight viewing angles of a monster.
This single fact drives most of the design decisions below.

### Conditions for a replacement to be found

`Scene::UploadPrimitive` (`Scene.cpp:565-592`) needs all three:

- `mesh.isExportable`
- non-empty `mesh.pMeshName`
- `RG_MESH_EXPORT_AS_SEPARATE_FILE` in `mesh.flags`

`rt_main.cpp:2919-2930` sets these from the `RtPrim::ExportInstance` tag. Both world sprites
(`hw_sprites.cpp:123-134`) and first-person weapons (`hw_weapon.cpp:136-145`) already set it.

---

## 2. Coordinate spaces — the two are different

**This is the single easiest thing to get wrong.** Get it backwards and the model renders
rotated 90°, showing its extrusion depth profile edge-on as a lens.

| | world sprites (monsters, items) | first-person weapons |
|---|---|---|
| placed by | `CalculateTrueTransformAndItsVerts` | `MakeFirstPersonQuadInWorldSpace` |
| mesh transform | world transform at the thing's feet | `m_mainCameraView_Inverse` (camera→world) |
| model space | **Z up**, origin at the feet | **camera space**: X right, **Y up**, **−Z forward** |
| scale | 1 sprite px = 1 map unit = 1/32 m | calibrated, see §4 |

Confirmed against the stock hand-made `SHTGA` mesh: 7.6 cm wide in x, 5 cm tall in y and
entirely below the eye, 13 cm long in z pointing away, at node translation `z = -0.106`.

**The axis map from sprite space to camera space has determinant −1**, so triangle winding
must be reversed with it. Apply the map to positions *and* normals — applying it to one only
leaves half the faces shaded as if lit from behind.

### Node transforms are discarded

`AppendMeshPrimitives(..., srcNode, nullptr)` in `GltfImporter.cpp` passes **no transform** for
a frame node's own mesh. So the frame node's translation/rotation is ignored — those
`[10, -1, 0]` values in the stock sets are Blender layout offsets and are correctly dropped.
Child nodes *do* get a transform relative to their parent frame node. The
`rtgl1_main_root` rotation is likewise not applied to frame meshes; the geometry must already
be in the correct space.

---

## 3. Normals — the Duke-RT improvement

Duke-RT 0.4.2: *"calculate normals at the whole voxel level based on neighbor occupancy"*.
Its before/after screenshot is a normals debug view — the left half has two or three flat
colours because every face normal is axis-aligned, the right half has a continuous gradient,
and **the silhouette is identical in both**. Geometry stays blocky; only lighting changes.
This is most of the "less Minecraft" look, and it is free.

### It works here because replacements skip vertex preprocessing

`VertexPreprocessPartial.inl:66` overwrites every vertex normal with the flat face normal when
`GENERATE_NORMALS` is set — which is the default, and the glTF importer never clears it. But
`Scene.cpp:545` only ever dispatches `VERT_PREPROC_MODE_ONLY_DYNAMIC`,
`CmVertexPreprocess.comp:47` gates on `GEOM_INST_FLAG_IS_DYNAMIC`, and replacements upload with
`isDynamicVertexData = false`. **Replacement normals reach the shader untouched.** No engine
change is needed — this is entirely an offline asset problem.

### The trap: the raw gradient is not a usable normal

The rule is: normal = sum of unit offsets to the 26 neighbours that are *empty*, normalised —
the outward gradient of the occupancy field. That is correct for a **solid** volume. It is
dangerous for a **thin shell**: for a one-voxel-thick plate the empty neighbours sit
symmetrically on both sides, so the gradient is free to point straight through the surface.

Measured on the stock POSSA mesh (5046 surface voxels, only 9 interior — it is a shell):
**34.6% of faces got a normal facing the wrong way.** That shades worse than the blocky
original.

`rt_voxel.shade_normal` fixes it by keeping only the component of the gradient **tangential to
the face normal**:

```
n = normalize(face + strength * (gradient - dot(gradient, face) * face))
```

On a flat wall the tangential part is ~zero and the normal is unchanged; on an edge or a curve
it tilts along the surface. The result is guaranteed to stay in the face's hemisphere.
`strength = 1.0` allows up to a 45° tilt.

**Always verify with the wrong-side check**: recompute each triangle's geometric normal from
its winding and assert `dot(vertex_normal, face_normal) > 0` for every triangle. Current
weapon set: 0 of 2,773,280.

### How to read the result

Report the share of vertices still carrying an exactly axis-aligned normal. Lower is better.

| | axis-aligned |
|---|---|
| stock enemy meshes | 100% |
| enemies after re-bake | 5–10% |
| weapons, thin extrusion (`--depth-k 1.6`) | ~24% mean |
| weapons, thick extrusion (`--depth-k 5.0`) | **4.5% mean** |

A thicker volume gives the gradient more to work with, so depth and shading quality improve
together.

---

## 4. Scale

### Monsters and world sprites

1 sprite pixel = 1 map unit = 1/32 m, and Doom 64 redrew its sprites larger at that same
mapping. The stock replacement models were built to the **DOOM II** sprites, so they are all
~30–45% too short. Derive the ratio from the WAD rather than hardcoding it: target height is
the D64 sprite's `A`-frame pixel height, confirmed by the actor's `Height` in DECORATE
(`64ZombieMan` declares `Height 80`, `POSSA1` is 80px, stock model is 55 → ×1.4545).

Scale about the **foot plane**, not the origin — though for the stock sets the feet already sit
at z=0, so a plain uniform scale works.

### First-person weapons — one measurement calibrates all of them

A viewmodel is **not** at 1px = 1 unit. The quad comes from `HUDSprite::GetWeaponRect`
(`hw_weapon.cpp:553`), which depends on `viewwidth`/`viewheight`, `SCREENWIDTH`/`HEIGHT`,
`WidescreenRatio`, `screenblocks` and `baseScale`, then goes through the inverse projection in
`MakeFirstPersonQuadInWorldSpace`. Do not try to reproduce that offline.

Instead measure it once. `rt_wpn_debug 1` prints:

```
RTWPNQUAD PISGA0 min=(-0.0175 -0.0596 -0.0778) max=(0.0107 -0.0162 -0.0778) size=(0.0282 0.0433 0.0000) m
```

Two things to note: the quad is **flat** (`size z = 0`), so a model extrudes symmetrically about
that z plane; and it is **not centred on x** (centre −0.0034 here), so a model centred on zero
sits visibly right of where the sprite was.

Crucially, **the two scale factors depend on the screen setup only, not on the sprite**. So one
measurement fixes metres-per-pixel for every weapon, and each frame's own position follows from
its `grAb` offsets:

```
left_px = (-grAb.x) - 160        top_px = (-grAb.y) - C
```

`C` absorbs the constant `YAdjust`/`ftextureadj` terms. Calibrated on PISGA this reproduces the
measured quad to 0.1 mm on every edge. Re-calibrate only when resolution or status bar changes.

---

## 5. grAb sprite offsets

Doom sprite offsets live in the PNG `grAb` chunk, and **Pillow drops them** — walk the chunks
by hand. They matter twice over:

- **Monsters**: `grAb = (leftoffset, topoffset)`, with `topoffset == height` meaning the origin
  is at the feet. This is what aligns the 8 rotations into one actor space.
- **Weapons**: the offsets vary *per frame* and that variation **is the animation**. PISG A–F
  span `-71` to `-86` vertically — 15 px of recoil. Anchoring frames on a common top edge
  flattens the animation out entirely.

A mirrored view's origin becomes `width - leftoffset`.

Packed lumps: `POSSA2A8` serves rotation 2 normally and rotation 8 mirrored.

---

## 6. What works, and what does not

### Works: single-view extrusion, for weapons

A psprite has exactly one camera view, so extruding it invents nothing structural. Thickness
per pixel follows `sqrt(distance to the silhouette edge)` — the sqrt stops the middle of a broad
shape ballooning while the outline still tapers to a single voxel, giving a rounded solid
rather than a slab with hard edges.

Depth matters more than expected. A gun viewed from behind is *longer* than it is wide:

| | depth ÷ width |
|---|---|
| `--depth-k 1.6` | 0.24 — reads as a flat card |
| `--depth-k 5.0` | 0.39–0.87 |
| stock hand-made shotgun | 1.72 |

Even at 5.0 these are flatter than a modelled gun, because that model has a real barrel
pointing forward — 3D information a single sprite does not contain. A symmetric extrusion
cannot invent a barrel; pushing further gives a stretched cigar, not a gun.

**Do not extrude muzzle-flash frames** (`*F*`). A flash is a billboard glow, not an object; the
stock set models them as flat 4-vertex planes. Leave them alone and the engine draws its own
sprite. They are also over half the frames — excluding them took the weapon set from 5.57M
vertices to 3.36M.

### Does not work: silhouette carving, for monsters

Tried and abandoned. Because the name key has no rotation, one model must serve all 8 angles,
so a monster needs real 3D — and frames A–G do have all 8 rotations, which is enough for
shape-from-silhouette in principle.

Two problems, one fatal:

**1. Hand-drawn rotations are not geometrically consistent.** They are art, not renders of one
3D model. Strict intersection of all 8 silhouettes deletes everything below z=18 on POSSA — the
entire legs — because a thin feature vanishes as soon as one view disagrees by a pixel. Voting
(keep a voxel if ≥7 of 8 agree) recovers them:

| views required | height | mean IoU vs source silhouettes |
|---|---|---|
| 8 of 8 | 61 u | 0.599 — legs deleted |
| 7 of 8 | 77 u | 0.774 — best |
| 6 of 8 | 78 u | 0.717 |
| 5 of 8 | 80 u | 0.645 — hull bulges outside the silhouettes |

**2. Fatal: a visual hull cannot represent a concavity.** The gap between two legs, the space
under an arm, the set of a face — none of it is recoverable from outlines, at any resolution,
with any convention. Eight views is also very few, and the voting needed to save the legs makes
the hull fatter still. The result is a correctly-proportioned blob with the right outline and no
interior structure. **This is the ceiling of the method, not a tuning problem.**

The stock Doom 1/2 voxels look good because a human built them in a voxel editor. For
D64-shaped monsters the realistic routes are hand-authored models (MagicaVoxel/Slab6, then the
fork's own `-vox2gltf` converter in `common/models/models_voxel.cpp`), or an existing community
model pack. Rescaling + re-shading the stock models is the best automated option.

`tools/gen_d64_carve.py` is kept for reference and is not used.

### Aside: the rotation convention cannot be found by scoring

With 8 rotations at uniform 45° spacing, every convention carves the *same hull* and differs
only in final orientation and chirality — all 8 candidates score identically on silhouette IoU.
Scoring against the correctly-oriented stock model separates them only weakly (a humanoid is
near-symmetric front-to-back, and the stock mesh is a hollow shell against a solid carve,
capping IoU near 0.29). Derive it instead: Doom's rotation 1 is the view from the direction the
actor faces, rotations advance 45° from there, and with the camera at +x looking along −x with
+z up, screen-right is +y → `base=0, direction=+1, flip=+1`.

---

## 7. Load order and set naming

RTGL1 reads `rt/replace` and keeps the **first** entry per mesh name
(`Scene.cpp:856-905`), warning `"Ignoring a replacement as it was already read from another
.gltf file"` for the loser. **The warning prints the loser's path as `'<TODO: GET NAME>'`, so
the log never tells you which file won.** The code reads reverse-alphabetically, which should
make a later-sorting name win, but this was never confirmed observationally.

Until it is, publish identical content at **both ends** of the sort order, arranged so the
preferred set beats the fallback either way:

| | low end | high end |
|---|---|---|
| weapons | `set_02_d64_wpn` | `set_97_d64_wpn` |
| enemy rescale | `set_01_d64_rescale` | `set_98_d64_rescale` |

Only the winner is cached (the `isNew` gate), so the duplicate costs disk and import time, not
VRAM. Since `replacements` is keyed per mesh name, a set that defines only some frames leaves
the rest to another set — that is how the carve set could have supplied A–G while the rescale
set supplied the single-view death frames H–U.

---

## 8. Vertex budget

All replacements share one arena: `replacementsMaxVertexCount`, set to **32 × 1024 × 1024**
in `rt_main.cpp:4728`. Exceeding it is **not silent** — RTGL1 logs `"Failed to upload vertex
data of a replacement primitive"`. If models start vanishing, check for that line first.

Measure the real figure by resolving winner-per-mesh-name, not by summing files.

Current usage with everything enabled: **32.1M of 33.5M**, ~1.5M headroom. That is thin.
Levers, cheapest first: drop flash frames (done), lower `--depth-k`, weld vertices on
`(position, normal, uv)`.

**Welding note:** with voxel-level normals a voxel's 24 face-corners collapse to 8, but
vertices can no longer be shared *between* voxels because their normals differ. Net effect on
the enemy sets was 1.44× the stock count, versus 1.62× for naive de-indexing.

---

## 9. The tools

| script | does |
|---|---|
| `tools/rt_voxel.py` | shared: glTF read/write, occupancy extraction, interior fill, occupancy normals, `shade_normal` |
| `tools/gen_d64_psprite.py` | weapons — sprite → extruded voxel glTF, calibrated scale |
| `tools/gen_d64_enemy.py` | enemies — re-bake normals + height-correct the stock models |
| `tools/gen_d64_carve.py` | silhouette carving; **reference only, output not used** (see §6) |

Pure stdlib + Pillow. No numpy/scipy — the sprites are ~64×96 and the meshes are small enough
that a real EDT would be a dependency for no gain.

All of them take `--replace-dir` twice, because the release package
(`gzdoom-rt-1.0.2/rt/replace`) and the live build dir
(`sourcecode/gzdoom-rt/build/RelWithDebInfo/rt/replace`) are separate copies. **The build dir
is what the game actually reads**; `build-gzdoom-rt.cmd` only copies `rt/` when it does not
already exist.

### Verification checklist

Never ship on IoU scores alone — they do not tell you whether the thing looks right. But these
catch real defects:

1. `wrong-side normals == 0` over every triangle
2. no non-unit normals
3. every primitive has POSITION, NORMAL and TEXCOORD_0 — the importer rejects a primitive
   missing any (`GltfImporter.cpp:404`)
4. `buffers[0].byteLength == len(bin)`, and no accessor overruns its bufferView
5. heights/bboxes match the intended target; foot plane still at z=0
6. resolve winner-per-mesh-name at **both** ends of the sort order
7. vertex budget under 33.5M
8. referenced `ext/*.png` files exist on disk

---

## 10. Enabling and disabling

Voxel models are **currently disabled**: the folder is renamed `rt/replace_old`, which no
longer matches `REPLACEMENTS_FOLDER`, so RTGL1 loads nothing. All generated content is intact.

To re-enable, in **both** `gzdoom-rt-1.0.2/rt/` and
`sourcecode/gzdoom-rt/build/RelWithDebInfo/rt/`:

```
mv replace_old replace
```

To disable only the generated sets while keeping the stock ones, rename those files'
extensions instead (`set_02_d64_wpn.gltf` → `.gltf_unfinished`, and the same for
`set_97_d64_wpn`, `set_01_d64_rescale`, `set_98_d64_rescale`).

No rebuild is needed either way — RTGL1 hot-reloads replacements (`Scene.cpp:1320`).
