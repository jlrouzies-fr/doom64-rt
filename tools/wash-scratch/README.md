# WashScratch — isolated from-scratch ladder

Separate GZDoom runtime under `sourcecode/gzdoom-rt/build/WashScratch/`.
**Does not touch** the play tree `build/RelWithDebInfo/`.

Use this to re-introduce features one layer at a time and find which step brings the gallery wall wash back.

## Once

```bat
tools\wash-scratch\00-bootstrap.cmd
```

Copies our `gzdoom.exe` + stock `gzdoom-rt-1.0.2\rt\` into WashScratch, then overlays
`nvngx_dlss.dll` / **`nvngx_dlssd.dll`** (Ray Reconstruction) from the live build — stock 1.0.2 often lacks `dlssd`.

If you already bootstrapped and hit a missing-DLL error:

```bat
python tools\wash-scratch\apply_stage.py fix_nvidia
```

## Ladder (quit GZDoom between each)

| Step | Script | What you should see |
|---|---|---|
| S01 | `S01-stock-baseline.cmd` | Stock Doom II RT mats @ mapboost 200. Note if STONE2 already washes. |
| S02 | `S02-nuclear-scrub.cmd` | Strip **all** `emissiveMult` / `lightIntensity` + quarantine `*_e.png`. Walls **must** be clean (control). |
| S03 | `S03-patched-rtgl.cmd` | Stage live patched `RTGL1.dll` + shaders (INDIR×mult, no Saturate). Still scrubbed meta — still clean? |
| S04 | `S04-world-emis.cmd` | Authored world allowlist only (`textures_world_emis` + `_e`). Dialed mults ~1.0. |
| S05 | `S05-dynlights.cmd` | Same as S04 + `rt_dynlight` (MAP01 flashers). Gallery: optional. |
| S06 | `S06-map01-play.cmd` | Retribution MAP01 on this tree (spawn blink + wash check). |

Checklist: `00-RUN-ORDER.cmd` · status: `status.cmd` · reset: re-run `00-bootstrap.cmd`.

Plan update: `gallery-emis-wall-wash-fix-plan.md` § WashScratch.
