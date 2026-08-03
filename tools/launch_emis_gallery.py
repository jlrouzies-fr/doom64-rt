"""Launch the world-emissives-only gallery (d64remis.wad / MAP99)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(r"G:\AI\Doom64-RT")
ENGINE = ROOT / r"sourcecode\gzdoom-rt\build\RelWithDebInfo"
PY_SYNC = ROOT / r"tools\sync_gallery_pbr_set.py"
BUILD = ROOT / r"tools\build_emis_gallery.py"
META = ROOT / r"tools\_gallery\emis_gallery.json"
OUT = ROOT / r"Doom64-Retribution"

IWAD = Path(r"D:\Games\GZDoom\doom2.wad")
MOD = OUT / "D64RTR_v15.WAD"
BM = OUT / "D64RTR_BRIGHTMAPS.PK3"
GAL = OUT / "d64remis.wad"
INFO = OUT / "d64r-texgallery-batches-mapinfo.pk3"
SKY = OUT / "d64r-rt-sky.pk3"

WIDTH = 2560
HEIGHT = 1440


def main() -> int:
    if not GAL.exists() or not META.exists():
        print("Building emis gallery…")
        subprocess.check_call([sys.executable, str(BUILD)], cwd=str(ROOT / "tools"))
    if not GAL.exists():
        print(f"ERROR: missing {GAL}")
        return 1

    subprocess.check_call([sys.executable, str(PY_SYNC), "baseline"])

    meta = json.loads(META.read_text(encoding="utf-8"))
    g = meta.get("grid") or {}
    print("=" * 60)
    print(f"  EMIS GALLERY  {GAL.name}")
    print(f"  count={meta['count']}  (world emissives only)")
    print(f"  {meta['textures'][0]} .. {meta['textures'][-1]}")
    print(
        f"  cell={g.get('cell')} pillar={g.get('pillar')} "
        f"grid={g.get('cols')}x{g.get('rows')}"
    )
    print(f"  window: {WIDTH}x{HEIGHT}")
    print("=" * 60)

    cfg = ENGINE / "gallery_emis_video.cfg"
    cfg.write_text(
        "\n".join(
            [
                "vid_fullscreen false",
                f"vid_defwidth {WIDTH}",
                f"vid_defheight {HEIGHT}",
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
        str(GAL),
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
        "gallery_emis_video.cfg",
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
