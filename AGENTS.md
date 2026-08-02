# AGENTS.md — Doom 64 Retribution Path Tracing

## Read first

Living project plan (progress, checkboxes, corrections, next steps):

→ **`doom64-retribution-pathtracing-plan.md`**

Engine hardcoding / patch log:

→ **`compat-patches.md`**

Update those when phases complete or facts change. Do not invent parallel trackers.

## Workspace layout

| Path | Role |
|---|---|
| `sourcecode/gzdoom-rt/` | **Primary engine** (patched fork; build required) |
| `gzdoom-rt-1.0.2/` | Stock prebuilt — Doom II RT reference only |
| `Doom64-Retribution/` | Retribution v1.5 (+ `D64RTR_v15.WAD` shell-safe copy) |
| `sourcecode/Duke-RT/` | Material-authoring reference (NRI) |
| `sourcecode/prboom-plus-rt/` | Secondary RTGL1 reference |
| `tools/` | Helper scripts |
| `retribution-asset-inventory.md` | Phase 1 inventory |

## Hard rules

- Engine work is in `sourcecode/gzdoom-rt`. Prebuilt release is not mod-safe (Steam gates + `rt/scenes/map##` name collision).
- Retribution loads as `-file` on DOOM2.WAD. Prefer `D64RTR_v15.WAD` in PowerShell (`[v1.5]` is a wildcard).
- Prefer IWAD `D:\Games\GZDoom\doom2.wad` (Steam size 14604584). Avoid `D:\Games\Doom RT\DOOM2.WAD` (different size).
- Keep RT materials in a separate overlay pk3 — never edit Retribution originals in place.
- Log engine patches in `compat-patches.md`. Update plan Status when phases move.
- Phase 3 (`material-authoring-spec.md`) gates bulk Phase 4 authoring.

## Useful local paths

- IWAD: `D:\Games\GZDoom\doom2.wad`
- GPU: NVIDIA GeForce RTX 5090
- Build: `tools/build-gzdoom-rt.cmd` → `sourcecode/gzdoom-rt/build/RelWithDebInfo/`
- **SDKs / deps policy:** install only under `G:\AI\Doom64-RT\deps\` (or other `G:\AI\…`), never system Program Files.
  - Headers: `deps/RTGL` (`vs-shirokii/RTGL`)
  - Runtime: `deps/RTGL-1.6.3`
  - Older clones `deps/RayTracedGL1*` are unused for the build
- Launch Retribution (skips IWAD dialog): `tools/launch-retribution-rt.cmd`
- Patched engine output: `sourcecode/gzdoom-rt/build/RelWithDebInfo/gzdoom.exe`
