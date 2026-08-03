"""Print batch gallery info + launch GZDoom with an explicit arg list.

Cmd.exe + start + nested %% quoting was breaking the banner and sometimes
dropping -width/-height. This keeps resolution forcing reliable.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(r"G:\AI\Doom64-RT")
ENGINE = ROOT / r"sourcecode\gzdoom-rt\build\RelWithDebInfo"
PY_SYNC = ROOT / r"tools\sync_gallery_pbr_set.py"
BATCHES = ROOT / r"tools\_gallery\batches"
OUT = ROOT / r"Doom64-Retribution"

IWAD = Path(r"D:\Games\GZDoom\doom2.wad")
MOD = OUT / "D64RTR_v15.WAD"
BM = OUT / "D64RTR_BRIGHTMAPS.PK3"
INFO = OUT / "d64r-texgallery-batches-mapinfo.pk3"
SKY = OUT / "d64r-rt-sky.pk3"

WIDTH = 2560
HEIGHT = 1440


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: launch_gallery_batch.py 1..8")
        manifest = BATCHES / "manifest.json"
        if manifest.exists():
            m = json.loads(manifest.read_text(encoding="utf-8"))
            for b in m["batches"]:
                print(
                    f"  {b['batch']:02d}  {b['wad']}  "
                    f"[{b['global_start']}..{b['global_end']}]  {b['count']}  "
                    f"{b['first']} .. {b['last']}"
                )
        return 1

    n = int(sys.argv[1])
    stem = f"d64rtexg{n:02d}"
    gal = OUT / f"{stem}.wad"
    meta_path = BATCHES / f"batch_{n:02d}.json"

    if not gal.exists() or not meta_path.exists():
        print("Building batches…")
        subprocess.check_call(
            [sys.executable, str(ROOT / r"tools\build_gallery_batches.py")],
            cwd=str(ROOT / "tools"),
        )
    if not gal.exists():
        print(f"ERROR: missing {gal}")
        return 1

    subprocess.check_call([sys.executable, str(PY_SYNC), "baseline"])

    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    g = meta["grid"]
    print("=" * 60)
    print(f"  BATCH {n:02d}  {gal.name}")
    print(f"  wad: {gal}")
    print(
        f"  textures [{meta['global_start']}..{meta['global_end']}]  "
        f"count={meta['count']}"
    )
    print(f"  {meta['textures'][0]} .. {meta['textures'][-1]}")
    print(
        f"  cell={g['cell']} pillar={g['pillar']} standoff={g['cam_standoff']}"
    )
    print(f"  window: {WIDTH}x{HEIGHT} (forced)")
    print("=" * 60)

    # Video override executed after config load so saved 1280x720 cannot stick.
    cfg = ENGINE / "gallery_batch_video.cfg"
    cfg.write_text(
        "\n".join(
            [
                "vid_fullscreen false",
                f"vid_defwidth {WIDTH}",
                f"vid_defheight {HEIGHT}",
                # Some GZDoom builds honor these for the OS window:
                f"win_w {WIDTH}",
                f"win_h {HEIGHT}",
                "",
            ]
        ),
        encoding="utf-8",
    )

    exe = ENGINE / "gzdoom.exe"
    args = [
        str(exe),
        "-width",
        str(WIDTH),
        "-height",
        str(HEIGHT),
        "-iwad",
        str(IWAD),
        "-file",
        str(MOD),
        str(BM),
        str(gal),
        str(INFO),
        str(SKY),
        "-rtnolauncher",
        "+vid_fullscreen",
        "false",
        "+vid_defwidth",
        str(WIDTH),
        "+vid_defheight",
        str(HEIGHT),
        "+exec",
        "gallery_batch_video.cfg",
        "+queryiwad",
        "false",
        "+sv_cheats",
        "1",
        "+map",
        "map99",
        "+god",
        "+fly",
        "+rt_mod_compat",
        "1",
        "+r_drawvoxels",
        "0",
        "+rt_fluid",
        "false",
        "+rt_autoexport",
        "false",
        "+rt_upscale_dlss",
        "2",
        "+rt_rayreconstr",
        "1",
        "+rt_framegen",
        "0",
        "+gl_noskyboxes",
        "true",
        "+rt_sky",
        "80",
        "+rt_sky_always",
        "true",
        "+rt_classic",
        "0",
        "+rt_flsh",
        "0",
        "+rt_mzlflsh",
        "true",
        "+rt_emis_mapboost",
        "200",
        "+rt_emis_additive_dflt",
        "0.15",
        # 12 clips saturated reds (SEXIT) to white; 3 keeps red albedo+emis readable.
        "+rt_emis_maxscrcolor",
        "3",
        "+rt_autoexport_light",
        "50",
        "+rt_normalmap_stren",
        "1",
        "+rt_heightmap_stren",
        "1",
    ]
    print("launch:", " ".join(args[:8]), "...")
    subprocess.Popen(args, cwd=str(ENGINE))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
