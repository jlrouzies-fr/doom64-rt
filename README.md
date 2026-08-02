# Doom64-RT

Path-traced Doom 64: Retribution work on top of [gzdoom-rt](https://github.com/vs-shirokii/gzdoom-rt) (RTGL1).

## What’s in this repo

- **`tools/`** — gallery review, PBR map generation (`gen_ai_pbr.py`, Marigold normals + sparse ORM + height), launch scripts
- **`Doom64-Retribution/Retribution-RT-Materials/`** — authored RT companions (`*_orm.png`, `*_n.png`, `*_h.png`) + scene `textures.json`
- **Docs** — material authoring notes, texture review status, compat notes

## Not in git (see `.gitignore`)

Engine builds, Python venv, upstream `sourcecode/gzdoom-rt` checkout, stock WADs/music, and gallery screenshot PNGs. Rebuild / obtain those locally.

## Quick start (local)

1. Build or install gzdoom-rt under `sourcecode/gzdoom-rt/build/RelWithDebInfo` (or your engine path).
2. Ensure `rt/RTGL1.json` has `"developerMode": true` for PNG overrides in `rt/mat_dev/`.
3. Copy materials from `Doom64-Retribution/Retribution-RT-Materials/rt/` into the engine `rt/` tree (or point the engine at them).
4. Launch: `tools\launch-retribution-rt.cmd`

## AI PBR pilot

```powershell
# venv once
# python -m venv tools\.venv-ai
# tools\.venv-ai\Scripts\pip install -r tools\requirements-ai-pbr.txt

powershell -NoProfile -ExecutionPolicy Bypass -File tools\review_ai_pbr_pair.ps1 `
  -Indices "0,1,2,3,4" -View corner -Orm heuristic `
  -Strength 4.5 -HeightCrazy 3.0 -NormalMapStren 3.5
```

Requires an RTX GPU for Marigold via Diffusers.
