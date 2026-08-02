# Doom64-RT

Path-traced Doom 64: Retribution work on top of [gzdoom-rt](https://github.com/vs-shirokii/gzdoom-rt) (RTGL1).

## What’s in this repo

- **`tools/`** — launchers, texture/enemy galleries, PBR helpers (`gen_ai_pbr.py`), eye/Lost Soul generators
- **`Doom64-Retribution/Retribution-RT-Materials/`** — authored RT companions (`*_orm.png`, `*_n.png`, `*_h.png`, `*_e.png`) + scene `textures.json`
- **Docs** — start with **`AGENTS.md`** (agent handoff), then `doom64-retribution-pathtracing-plan.md`, `material-authoring-spec.md`, `compat-patches.md`

## Not in git (see `.gitignore`)

Engine builds, Python venv, upstream `sourcecode/gzdoom-rt` checkout, stock WADs/music, and gallery screenshot PNGs. Rebuild / obtain those locally.

## Quick start (local)

1. Build or install gzdoom-rt under `sourcecode/gzdoom-rt/build/RelWithDebInfo`.
2. Ensure `rt/RTGL1.json` has `"developerMode": true` for PNG overrides.
3. Sync materials from `Doom64-Retribution/Retribution-RT-Materials/rt/` into the engine `rt/` tree (generators also write both).
4. Play: `tools\launch-retribution-rt.cmd` (MAP01, DLSS-RR, Lost Soul pack).
5. Enemy eye debug hall: `tools\launch-enemy-gallery-rt.cmd` (MAP98).
6. Texture PBR gallery: `tools\launch-texture-gallery-rt.cmd` (MAP99).

## Enemy eyes / Lost Soul

```powershell
# Prefer the Python that has Pillow (see AGENTS.md)
python tools\gen_enemy_eye_emissives.py
python tools\pack_lostsoul_rt.py
python tools\build_enemy_gallery.py
```

Policy summary: brightmap-only eyes, no cast light on eyes, no `noShadow` on monster sprites. Full rules in `material-authoring-spec.md` / `AGENTS.md`.

## AI PBR pilot

```powershell
# venv once
# python -m venv tools\.venv-ai
# tools\.venv-ai\Scripts\pip install -r tools\requirements-ai-pbr.txt

powershell -NoProfile -ExecutionPolicy Bypass -File tools\review_ai_pbr_pair.ps1 `
  -Indices "0,1,2,3,4" -View corner -Orm heuristic `
  -Strength 4.5 -HeightCrazy 3.0 -NormalMapStren 3.5
```

Requires an RTX GPU for Marigold via Diffusers. For in-game normal strength while playing Retribution, keep launcher `rt_normalmap_stren` near **1** so Ray Reconstruction stays stable.
