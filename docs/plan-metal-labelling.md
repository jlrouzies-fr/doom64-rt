# Metal / roughness labelling

`metallicDefault` and `roughnessDefault` in the RT material metadata are what turn a flat
albedo into a surface that reflects and catches highlights under path tracing. Getting them
right is nearly free rendering quality. Getting them *derived* turned out to be impossible:
`tools/fix_orm_metallic_ai.py` ran a local Qwen2.5-VL pass over the albedos and could not
reliably separate painted steel (a dielectric) from bare metal — the two look identical to a
model that has never seen a Doom 64 wall lit. `docs/rt-feature-ideas.md` idea 4 is marked
rejected on exactly that basis.

So a human makes the call, and the tooling gets out of the way. One keystroke per texture.

Rebuilding the page itself — image sources, the size budget, the design decisions and the
bugs already found — is `docs/skill-texture-material-labeller.md`. This document is about
*running* it and applying what comes out.

## 1. Generate the page

```
C:\Users\Winter\AppData\Local\Programs\Python\Python313\python.exe .\tools\gen_material_labeller.py
```

Reads `Doom64-Retribution\D64RTR_v15.WAD` and writes
`tools\_gallery\material_labeller.html` (~4.8 MB, fully self-contained).

Scope is **1345 wall/flat textures**: all 1187 lumps in the WAD's `TX_START`..`TX_END`
namespace, plus 163 names that maps actually reference and that are defined as composites in
the `TEXTURES` lump. Sprites (`SS_` namespace, 1388 lumps) are out — metalness on a sprite is
a separate question. Five names fail to render and are dropped: `C921F` and the four
`FRSKY*` sky variants.

Thumbnails are lossless WebP capped at 128 px on the long edge, which is native resolution or
better for ~95% of the set, so the labeller is looking at the real pixels. Existing
`metallicDefault` / `roughnessDefault` values from `rt/data/textures.json` are shown as a
"already in textures.json" fact on the textures that have them (189 and rising, as applied
batches land) — as reference, not as a
pre-filled answer.

Published as an artifact: <https://claude.ai/code/artifact/d78b5c38-e7f6-45d3-8880-abdb3fe17dba>
(republish the same file path to update it in place).

## 2. Label — start with one map

**Do not commit to 1345 textures before anything is proven.** The "working set" map picker in
the sidebar narrows the page to the textures a single map actually uses. MAP01 is 84 of them:
an evening, not a fortnight. Label that, apply it, look at MAP01 in game, and only then decide
whether the rest is worth doing.

The filter drives everything — arrows, `Space`, the filmstrip, the search box and the prefix
jump all stay inside it, and none of them will silently walk you out. The counter reads
"N of 84 in MAP01 · G of 1345 overall" so the pilot never gets mistaken for the whole job, and
an active filter carries a permanent flag in the top bar with a "clear filters" button. The
choice persists to `localStorage` with the labels.

Labels themselves are **global**. A texture called while filtered to MAP01 is still called
when the filter clears — and since most Doom 64 walls appear in a dozen maps, the pilot pass
already covers a good slice of map 2 onward. Export sends everything labelled by default,
filter or not; there is an opt-in checkbox for "only the current working set" if you want a
strictly map-scoped file.

### Reviewing what you already called

A second picker narrows the set by **label state**: `any label state` (default),
`unlabelled only`, `labelled (any class)`, `parked`, or one entry per class. It **composes**
with the map filter rather than replacing it, so `MAP01 + metal` is expressible — which is
the point, because that is how you re-check a pilot batch after seeing it in game. The top-bar
flag names the whole combination (`working set MAP01 + metal`) and its button clears both.

Two behaviours worth knowing:

- **`unlabelled only` drains like a queue.** Label the current texture and it filters itself
  out; the page holds your *position*, so you land on the next unlabelled one rather than
  being thrown back to the top. Undo puts it back.
- **An empty combination is allowed and explained.** `MAP01 + flesh` with no flesh in MAP01
  says "No texture is MAP01 + flesh" on the stage and in place of the filmstrip, instead of
  refusing the choice or showing a blank rail.

Both filters persist in `localStorage` alongside the labels.

Textures are ordered by natural sort, which groups by name prefix — 30 `SPACE*` panels in a
row, then all the `C1x`, then the `SMON*`. Similar surfaces stay adjacent, which is most of
the speed. The facts row shows how many maps use the current texture and names the first few:
a wall in thirty maps is worth a second look, a one-map trim is not.

The keyboard is the interface:

| key | does |
| --- | --- |
| `S` | metal, roughness 0.80, advance |
| `C` | concrete, advance |
| `R` | dirt, advance |
| `W` | wood, advance |
| `Q` | fluid, advance |
| `E` | flesh, advance |
| `A` | other (none of the above), advance |
| `D` / `F` | roughness 0.80 / 0.95 |
| `1`–`6` | roughness ladder: mirror 0.05, polished 0.20, satin 0.40, matte 0.60, rough 0.80, very rough 0.95 |
| `X` | park it — ambiguous, decide later |
| `Backspace` | unlabel the current texture |
| `←` `→` | previous / next |
| `Space` | jump to the next unlabelled |
| `U` or `Ctrl+Z` | undo |
| `/` | jump to a name (within the working set) |

Set roughness first, then make the call. `S` on its own means metal at 0.80, so the common
case is one key.

### The surface class, and why it is not just metalness

The seven calls — **metal / concrete / dirt / wood / fluid / flesh / other** — are mutually
exclusive, and parking is orthogonal to all of them. They feed two different systems:

- **Shading.** metal sets `metallicDefault: 1.0`; the other six set `0.0`. Roughness is an
  independent pick in every case.
- **Impact effects.** `docs/plan-impact-fx.md` — sparks shipped (`rt_spark_*`) and currently
  fire on *everything* that is not flesh, liquid or sky. A bullet into a concrete wall should
  throw dust and chips, into water a splash, and only metal should spark at all. That
  distinction cannot be recovered from `metallicDefault` alone, because concrete and flesh and
  nukage and glass are all "not metal" and want four different answers.

| call | key | `metallicDefault` | impact | what it means |
| --- | --- | --- | --- | --- |
| metal | `S` | 1.0 | sparks | steel, iron, plate, grating |
| concrete | `C` | 0.0 | dust, chips | poured stone, brick, tile |
| dirt | `R` | 0.0 | dust, scatter | gravel, soil, ash, sand, rubble — *loose* ground |
| wood | `W` | 0.0 | splinters | planks, crates |
| fluid | `Q` | 0.0 | splash | water, blood, nukage, lava |
| flesh | `E` | 0.0 | blood | `SKINWAL*`, `SKINFL*`, the `HELLA*` organic set |
| other | `A` | 0.0 | nothing | goo, glass, screens, cloth |

**dirt is not concrete.** Poured stone chips; loose ground scatters. They are separate calls
because they want separate impact effects, not because they shade differently — both are
`metallicDefault: 0`.

**flesh** exists because Doom 64 has a large organic wall set that otherwise had nowhere to
go, and because a bullet into hell-meat should bleed rather than throw dust.

**Why `fluid` is a label and not just a terrain lookup.** The spark hook already asks
GZDoom's terrain table (`Terrains[...].IsLiquid` in `p_map.cpp`) and skips liquids. But that
table only knows about **flats a map marks as liquid**. It says nothing about wall textures
that read as fluid, animated falls (`BFALL*`, `SFALL*`), or anything the terrain table simply
misses — and it is not a place the eventual splash effect can look up "what kind of fluid".
The label covers those and gives the effect one source of truth.

**Roughness on a fluid barely matters.** RTGL1 handles water and lava as media types
(`RG_MESH_PRIMITIVE_WATER` / `RG_MESH_PRIMITIVE_LAVA`), not through the ordinary BRDF, so the
roughness pick on a `fluid` texture is mostly cosmetic. The page says so inline — the note
appears under the roughness ladder only while a fluid is selected — so nobody spends thirty
seconds agonising between polished and satin on a nukage fall.

So the labeller is answering **"what is this made of"**, not only "how does it shade". The
sidebar hint says so. Every value on that list exists because some impact effect wants to
tell it apart from its neighbour. Do not grow the list without a system that consumes the new
value — each extra call is a decision the labeller has to make 1345 times.

**The bias is deliberate.** Doom 64 is painted steel, cast iron, worn plate and grating.
Almost none of it would mirror-reflect. The buckets are skewed rough, the default is rough,
and the two roughest sit on the home row next to the metal keys. Metallic means the surface
answers light differently — no diffuse, specular tinted by the albedo, sheen at grazing
angles — not that you can see yourself in it. A labeller who forgets that produces a chrome
game, which is exactly the failure mode `dont-over-apply-retro-styling` warns about.

Every keystroke writes to `localStorage`. A refresh costs nothing.

## 3. Get the JSON out

Downloads are inert inside the artifact viewer, so export is **copy JSON** (clipboard) or
**show / paste** (a textarea you select). The same box takes a previous export back, so work
can move between machines. Shape:

```json
{
  "SPACEB1":  { "metallicDefault": 1.0, "roughnessDefault": 0.8,  "surface": "metal" },
  "AZTEC01":  { "metallicDefault": 0.0, "roughnessDefault": 0.95, "surface": "concrete" },
  "__skipped": ["C10F", "CDOR1"],
  "__meta":    { "source": "tools/gen_material_labeller.py", "scope": "MAP01",
                 "total": 84, "labelled": 79,
                 "surfaces": { "metal": 51, "concrete": 14, "dirt": 4, "wood": 3,
                               "fluid": 2, "flesh": 2, "other": 3 },
                 "exported": "..." }
}
```

Keys beginning `__` are metadata, never texture names. `__meta.scope` is `"all"` unless the
"only the current working set" checkbox was ticked, in which case it names the combination
(`"MAP01"`, `"metal"`, or `"MAP01 + metal"`).

`metallicDefault` and `roughnessDefault` keep their exact names and shape. `surface` is
**additive** — `apply_material_labels.py` filters on `FIELDS = ("metallicDefault",
"roughnessDefault")` and `bake_material_labels_orm.py` reads the same two by name, so both
ignore it. Verified with a `--dry-run` of each against an export carrying the new field.
Renaming either of the original two would break both scripts; adding beside them does not.

**Backward compatibility is handled in both directions.** A label saved before the surface
axis existed has no `surface` value; the page reads a missing one as `metal` when
`metallicDefault` is 1 and `other` when it is 0, and does not rewrite stored state, so nothing
needs re-labelling. Re-importing an older export works the same way.

## 4. Apply it

Two scripts consume the export today. Both take the same file, both `--dry-run`, both
`--revert` from their own backups.

```
python tools\apply_material_labels.py tools\_material_labels\map01.json
python tools\bake_material_labels_orm.py tools\_material_labels\map01.json
```

- **`apply_material_labels.py`** merges `metallicDefault` / `roughnessDefault` into
  `rt/data/textures.json`, in **both** trees — the gitignored engine build directory that
  RTGL1 actually reads, and the tracked `Retribution-RT-Materials` copy that survives a
  rebuild. Writing one and not the other is the classic ghost change. It merges rather than
  rewrites, so the `emissiveMult` / `lightIntensity` / `lightColorHEX` / `isMirror` authoring
  on those entries is preserved.
- **`bake_material_labels_orm.py`** exists because `textures.json` defaults are only consulted
  when a texture has **no** `_orm.png`. Where one exists it wins, so the values have to be
  baked into the ORM channels too, or the label does nothing for most of the set.

Neither touches the split `textures_*.json` overlays — RTGL1 does not read them
(`rtgl1-reads-only-textures-json`).

### `surface` — consumed by the spark surface table

`tools/build_spark_surfaces.py` reads the `surface` values out of
`tools/_material_labels/*.json` and writes `rt/data/spark_surfaces.txt` into **both** trees,
the same two-tree rule this page's other applier follows. `rt_sparks.cpp` loads that table;
the `spark_surfaces` CCMD reloads it in-game with no restart and no rebuild.

The table is `NAME class` per line, case-insensitive, `#` comments, and a trailing `*` makes
the name a prefix (`SPACE* metal`) — so a whole texture family can be covered without
labelling each member. A bare `NAME` with no class means metal, for compatibility with the
first version of the file.

That script is deliberately **read-only** on everything here: it never writes a label file,
never edits `textures.json`, never touches `apply_material_labels.py`. If this page's export
shape changes it breaks loudly there rather than corrupting anything upstream. Preserve that
boundary.

Still open on the impact side:

1. **Gate sparks on `metal`.** Sparks fired on "everything else"; with the table in place
   only `metal` should keep them and every other class should stop.
2. **Give each class its own effect** — concrete throws dust and chips, dirt scatters, wood
   splinters, fluid splashes, flesh bleeds, `other` most likely does nothing. That is new
   work, not a re-tint of the spark.
3. **Keep the terrain table in play.** `fluid` is consulted **in addition to** the existing
   `Terrains[...].IsLiquid` test, not instead of it — the terrain table is authoritative for
   flats, the label covers walls and anything the table misses.
4. **Label coverage is the limit, not the plumbing.** A texture with no label falls back to
   whatever the table's default is, so the useful next step is labelling more maps rather
   than more engine work.

Labelling is the expensive human step, so it is done once with the class captured, and each
consumer reads what it needs from the same export.

### The pilot loop this is meant to serve

1. Filter the page to MAP01, label its 84 textures, copy the JSON out.
2. Run `apply_material_labels.py`, then `bake_material_labels_orm.py`.
3. Launch MAP01 and look at it. Handing the launcher to the owner, not running it —
   `dont-launch-the-game-yourself`.
4. Only then decide whether the remaining ~1260 are worth the evenings.

Verify afterwards from the data and with `rt_tex_probe` on a live surface, not from a
screenshot — `whatsthat` names the sector, proximity guesses have been wrong every time.
