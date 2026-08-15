---
name: texture-material-labeller
description: Rebuild or extend the Doom 64 texture categorisation gallery — the keyboard-driven page where a human classifies every wall/flat texture by surface class (metal / concrete / dirt / wood / fluid / flesh / other) and roughness, and exports JSON for the RT material appliers. Use when asked to regenerate, change, extend or re-derive that page, its generator `tools/gen_material_labeller.py`, or its export format.
---

# The texture categorisation gallery

A self-contained web page where a human labels every Doom 64: Retribution wall and flat
texture. Two axes per texture: a **surface class** and a **roughness bucket**. It exists
because automatic classification failed, and it feeds two production appliers.

**Generator:** `tools/gen_material_labeller.py` → `tools/_gallery/material_labeller.html`
**Doc:** `docs/plan-metal-labelling.md` (how to run it, how to use it, how the JSON is applied)
**Published:** https://claude.ai/code/artifact/d78b5c38-e7f6-45d3-8880-abdb3fe17dba

Run it with the project Python (it has Pillow):

```
C:\Users\Winter\AppData\Local\Programs\Python\Python313\python.exe .\tools\gen_material_labeller.py
```

Never hand-assemble the HTML. The page is ~4.8 MB of generated markup with 1345 embedded
images; it only stays maintainable because one script emits all of it.

---

## Why it exists — do not re-litigate this

`tools/fix_orm_metallic_ai.py` ran a local Qwen2.5-VL pass over every albedo trying to derive
metalness. **It could not reliably tell painted steel (a dielectric) from bare metal.** They
look identical to a model that has never seen a Doom 64 wall lit. `docs/rt-feature-ideas.md`
idea 4 is marked rejected on that basis. This page is what un-rejects it: the human decides,
the page only records, and it records fast enough that 1345 textures is an evening's work
rather than a fortnight's.

If asked to "just use a model for this", the answer is that it was tried and it failed.

---

## Where the images come from

Worked out once; don't re-derive it.

- **`Doom64-Retribution\D64RTR_v15.WAD`** is the source of pixels. Note there is also a
  `D64RTR[v1.5].WAD` — same bytes, but the brackets are PowerShell wildcards, so anything
  touching it needs `-LiteralPath`. Use the `_v15` name and avoid the problem.
- **Scope is the `TX_START`..`TX_END` namespace** (1187 lumps: walls and flats), **plus** the
  163 names that maps reference but that live outside it and are defined as composites in the
  `TEXTURES` lump. Total **1345**.
- **Sprites (`SS_START`..`SS_END`, 1388 lumps) are deliberately excluded.** Metalness on a
  sprite is a different question and would triple the labelling job.
- **`rt/mat_dev/*.png` is NOT albedo.** Those 2753 files are `_n` / `_orm` / `_h` / `_e`
  companions. A human labelling metalness needs to see the albedo, which only the WAD has.
- **`rt/data/textures.json` is mostly sprites.** Of its 2262 entries only ~129 are wall/flat
  textures. It is the file the labels get *applied to*, not a list of what to label.
- Five names never render and are dropped: `C921F` and the four `FRSKY*` sky variants.

`tools/export_all_textures_gallery.py` already had the WAD/TEXTURES-lump decoding (plain PNG
lumps read as-is, composites rendered from their patch definitions with FlipX/FlipY/Rotate).
That machinery was lifted; only the scope changed. Reuse it again rather than re-writing a
WAD parser.

### Encoding, and the 16 MB budget

The artifact CSP blocks every external host, so all 1345 images are `data:` URIs and count
against the 16 MB rendered-page limit. Measured options for the full set:

| encoding | base64 total |
| --- | --- |
| original PNG lumps | 8.96 MB |
| PNG, 128 px, 128-colour quantised | 4.38 MB |
| **lossless WebP, 128 px cap** | **4.19 MB** |
| WebP q72 (lossy) | 1.76 MB |

**Lossless WebP at a 128 px cap is the right answer** and leaves enormous headroom — no
splitting into multiple pages is needed. 128 px is native resolution or better for ~95% of
the set (most textures are 64×64 or 63×128), so the labeller sees real pixels, and lossy
compression on pixel art buys nothing worth its artifacts. Downscale only what exceeds the
cap, with `Image.BOX`.

---

## The two axes

### Surface class — seven values, each earning its slot

| call | key | `metallicDefault` | impact effect |
| --- | --- | --- | --- |
| metal | `S` | 1.0 | sparks |
| concrete | `C` | 0.0 | dust, chips |
| dirt | `R` | 0.0 | dust, scatter |
| wood | `W` | 0.0 | splinters |
| fluid | `Q` | 0.0 | splash |
| flesh | `E` | 0.0 | blood |
| other | `A` | 0.0 | nothing |

Park (`X`) is orthogonal to all seven. The class list is generated from the `SURFACES`
constant in the generator — the sidebar buttons, the keymap, the status dropdown and the JS
`SURF` table all derive from it, so adding a class is one tuple, not four edits.

**The class is not only about shading.** It drives the impact system
(`docs/plan-impact-fx.md`): sparks shipped (`rt_spark_*`) and currently fire on *everything*
that is not flesh, liquid or sky. Concrete should throw dust, water should splash, hell-meat
should bleed. That distinction cannot be recovered from `metallicDefault` alone, because
concrete and glass and nukage and flesh are all "not metal" and want different answers. Say
so in the UI — the labeller is answering **"what is this made of"**, not just "how does it
shade".

Two distinctions people get wrong:

- **dirt is not concrete.** Poured stone chips; loose ground (gravel, soil, ash, sand,
  rubble) scatters. Same metalness, different effect.
- **fluid is a label even though GZDoom has a terrain table.** The spark hook already checks
  `Terrains[...].IsLiquid` in `p_map.cpp`, but that only knows about **flats a map marks as
  liquid**. It says nothing about wall textures that read as fluid, animated falls
  (`BFALL*`, `SFALL*`), or anything the table misses — and it cannot tell a splash effect
  *what kind* of fluid it hit.

Do not grow this list without a system that consumes the new value. Every extra call is a
decision a human makes 1345 times.

### Roughness — buckets, never a slider

mirror 0.05 / polished 0.20 / satin 0.40 / **rough 0.80** / very rough 0.95 (plus matte 0.60).
Nobody can pick 0.37 by eye, and buckets are far faster.

**The bias toward rough is deliberate.** Doom 64 is painted steel, cast iron, worn plate and
grating — nearly all of it metal *and* rough. `S` alone means "metal at 0.80", so the common
case costs **one keystroke**; the two roughest buckets also get home-row aliases `D` and `F`
beside the call keys. A labeller who forgets this produces a chrome game, which is the
failure mode `dont-over-apply-retro-styling` warns about. Keep the standing hint that
metallic means the surface *answers light differently* (no diffuse, specular tinted by the
albedo, grazing sheen), not that you can see yourself in it.

**Roughness barely matters on `fluid`.** RTGL1 handles water and lava as media types
(`RG_MESH_PRIMITIVE_WATER` / `LAVA`), not through the ordinary BRDF. The page says so inline,
under the roughness ladder, *only while a fluid is selected* — a caveat shown on the other
1300 textures would be permanent noise.

---

## Export format — additive only

```json
{
  "SPACEB1":   { "metallicDefault": 1.0, "roughnessDefault": 0.8,  "surface": "metal" },
  "__skipped": ["C10F", "CDOR1"],
  "__meta":    { "scope": "MAP01 + metal", "total": 84, "labelled": 79,
                 "surfaces": { "metal": 51, "concrete": 14, "...": 0 } }
}
```

**`metallicDefault` and `roughnessDefault` must keep their exact names and shape.** Two
production scripts consume this file:

- `tools/apply_material_labels.py` — filters on `FIELDS = ("metallicDefault",
  "roughnessDefault")` and skips `__`-prefixed keys.
- `tools/bake_material_labels_orm.py` — reads the same two by name.

Both **ignore unknown keys**, so adding a field (as `surface` was) is safe; renaming one
breaks production. After any export-shape change, prove it with a dry run of both:

```
python tools\apply_material_labels.py <export.json> --dry-run
python tools\bake_material_labels_orm.py <export.json> --dry-run
```

`surface` **is consumed**, by `tools/build_spark_surfaces.py`, which reads
`tools/_material_labels/*.json` and emits `rt/data/spark_surfaces.txt` — a two-column
`NAME class` table that `rt_sparks.cpp` loads, with `*` prefix matching and a
`spark_surfaces` CCMD for hot reload. That script is **read-only** on the labelling
pipeline: it never writes a label file and never touches `textures.json`. Keep it that way.
A separate table exists because `tools/` is not in the engine's lump search path, so the data
has to be copied into `rt/data/` regardless — and it may as well arrive in a shape the
renderer can parse without JSON.

---

## Hard constraints of the medium

- **Self-contained.** A strict CSP blocks every external host — no CDN, no webfonts, no
  remote images. Everything inline.
- **Downloads are inert in the artifact viewer.** `<a download>`, blob saves and
  script-driven saves are all blocked. Export must be **copy-to-clipboard plus a selectable
  `<textarea>`** — never a download button. The same textarea takes a paste back for import.
- **`localStorage` on every keystroke.** Losing an hour of clicks to a refresh would make the
  whole thing worthless. Keys: `d64rt-metal-labels-v1` plus `:at`, `:map`, `:stat`.
- **Nearest-neighbour scaling.** `image-rendering: pixelated`, integer scale factors, and
  `object-fit: contain` so a clamped box cannot distort the aspect. This is pixel art.
- **Republish in place.** Pass `url` to the Artifact tool. A publish without it creates a
  second page and orphans the owner's link.

---

## Behaviours that took thought — keep them if you rebuild

**Ordering groups by prefix.** Natural sort (digits compared numerically) puts `C1, C2, …,
C10, C100` and all 30 `SPACE*` panels adjacent. Labelling a family in a row is most of the
speed. The filmstrip draws a vertical prefix marker at each group boundary.

**Two composed filters, one `view` array.** A map picker and a label-state picker
(`unlabelled` / `labelled` / `parked` / each class) narrow the working set, and they
**compose** — `MAP01 + metal` is how you re-check a pilot batch after seeing it in game.
Everything reads one `view` array of surviving indices: arrows, `Space`, the filmstrip, the
counter, the prefix jump, the name search. Nothing may silently step outside the filter;
search that matches something outside it says where it actually is.

**Label one map first.** 1345 is too many to commit to before anything is proven. The map
filter exists so the owner can label MAP01 (84 textures), apply it, look at it in game, and
*then* decide. The counter reads `N of 84 in MAP01 · G of 1345 overall` so a pilot is never
mistaken for the whole job.

**Labels are global, never scoped by filter.** A texture called under `MAP01` stays called
when the filter clears. Export sends everything labelled by default; scoping is an opt-in
checkbox, because the applier should never have to guess what it was handed.

**`unlabelled only` must drain like a queue.** Labelling an item under a live status filter
removes it from the view mid-keystroke. Capture the view *position* before writing, rebuild,
then land on whatever moved into that slot — so you advance to the next unlabelled instead of
being thrown to the top. `undo` must rebuild too, since restoring a label changes what
qualifies.

**Empty filter combinations are explained, not refused.** `MAP01 + flesh` with no match says
"No texture is MAP01 + flesh" on the stage and in place of the filmstrip. Refusing the choice
makes a legitimate query look broken when the honest answer is "there is none".

**Migrate silently, never force a re-label.** The owner has real labelled work in
`localStorage` and in production. When the schema grows, read a missing field rather than
demanding it: a label saved before `surface` existed is read as `metal` when
`metallicDefault` is 1 and `other` when it is 0, and stored state is **not** rewritten. Same
for re-importing an older export.

---

## Bugs found here before — check for them

- **`+localStorage.getItem(k)` is `0` when the key is missing.** That shipped a version where
  a fresh browser silently started filtered to MAP00 (3 textures) and looked broken. Test for
  `null` before coercing.
- **Truncating per-texture data breaks a later feature.** The map list was first stored as
  `[:6]`, which would have made the map filter wrong for any texture used in more than six
  maps. Store full data; compress by indexing into a shared array if size matters.
- **`max-width`/`max-height` on an `<img>` with explicit width and height can distort it**
  when only one dimension clamps. `object-fit: contain`.

### How to test it without a browser

`node --check` catches syntax only. For behaviour, extract the script and run it against a
minimal DOM shim, then drive the internals:

1. Pull the payload out of `<script id="tex">`, blank every `d` field (the base64) — it makes
   the fixture ~200× smaller and nothing under test reads it.
2. Stub `document.getElementById` / `createElement` / `localStorage` / `navigator`.
3. Append `global.__probe = {view, idx, setFilters, call, exportObj, labels, …};` just before
   the IIFE's closing `})();` and `eval` the result.
4. Assert on real scenarios: seed old-shape labels and confirm they survive; hold an arrow
   for 5000 steps and confirm the cursor stays inside the view; label under `unlabelled` and
   confirm the cursor advances; check an empty combination.

This is how both shipped bugs above were caught before the owner saw them.

---

## Style

Committed dark, single-theme, painted explicitly so it holds on either host ground. Doom 64's
own palette: `#0A0909` void, `#C8501E` blood-orange accent spent on state rather than
decoration, Consolas/`ui-monospace` throughout. Each surface class owns a hue — steel
blue-grey, teal, khaki, brown, cool blue, rose-red, orange, with gold for parked — carried
consistently across the verdict chip, the stage glow, the filmstrip underline and the button
hairline. Sibling artifact for visual reference:
`tools/export_all_textures_gallery.py`'s output.
