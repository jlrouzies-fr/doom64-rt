"""Use Retribution's player art in Unseen Evil under RT.

Unseen Evil's ``sprites/player/PLAY*.png`` files are colour masks.  Its
``GLDEFS.player`` reconstructs the visible player from a second true-colour
texture in a custom GZDoom fragment shader.  RTGL1 does not execute that
shader, so the mask itself becomes the traced player surface: a neon-green
rectangle/silhouette that can tint nearby walls and cast duplicate-looking
shadows.

This late-loaded compatibility package:

* copies Retribution's exact PLAY frames over UE's colour masks;
* aliases UE's PLYC crouch frames to the matching Retribution PLAY frames;
* makes UE's already-registered player shader use GZDoom's normal material
  sampling, so raster and RT both see the replacement art.

The Player page itself is removed by ``make_unseenevil_rtmenu.py``.  That menu
overlay already owns the UE main-menu bridge, so it can route Customization to
an additive subclass without relying on cross-archive ``#include`` replacement.

The original UE archive and Retribution WAD are never modified.

Usage:
    py -3 tools/make_unseenevil_player.py --write
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


ROOT = Path(__file__).resolve().parents[1]
UE = ROOT / "Doom64-UnseenEvil" / "D64UnseenEvil-v1.0.3.pk3"
RETRIBUTION = ROOT / "Doom64-Retribution" / "D64RTR_v15.WAD"
OUT = ROOT / "Doom64-UnseenEvil" / "d64ue-retribution-player.pk3"

NORMAL_MATERIAL_SHADER = b"""void SetupMaterial(inout Material material)
{
\tmaterial.Base = ProcessTexel();
\tmaterial.Normal = ApplyNormalMap(vTexCoord.st);
\tmaterial.Bright = texture(brighttexture, vTexCoord.st);
}
"""


def retribution_player_frames() -> dict[str, bytes]:
    # Reuse the project's established WAD reader; do not duplicate the format.
    sys.path.insert(0, str(ROOT / "tools"))
    from make_map_3dfloor_rtfix import read_wad_lumps

    frames = {
        name: data
        for name, data in read_wad_lumps(RETRIBUTION)
        if name.startswith("PLAY")
    }
    expected = {
        *(
            name
            for state in "ABCDEFG"
            for name in (
                f"PLAY{state}1",
                f"PLAY{state}2{state}8",
                f"PLAY{state}3{state}7",
                f"PLAY{state}4{state}6",
                f"PLAY{state}5",
            )
        ),
        *(f"PLAY{state}0" for state in "HIJKLMNOPQRSTUV"),
    }
    missing = sorted(expected - frames.keys())
    extra = sorted(frames.keys() - expected)
    if missing or extra:
        raise SystemExit(
            "unexpected Retribution PLAY frame census: "
            f"missing={missing or 'none'}, extra={extra or 'none'}"
        )
    bad_png = sorted(name for name, data in frames.items()
                     if not data.startswith(b"\x89PNG\r\n\x1a\n"))
    if bad_png:
        raise SystemExit(f"Retribution PLAY frame(s) are not PNG: {bad_png}")
    return frames


def crouch_names(source: ZipFile) -> list[str]:
    prefix = "sprites/player/"
    names = sorted(
        Path(info.filename).stem.upper()
        for info in source.infolist()
        if info.filename.startswith(prefix)
        and Path(info.filename).stem.upper().startswith("PLYC")
    )
    if len(names) != 35:
        raise SystemExit(f"expected 35 UE PLYC frames, found {len(names)}")
    return names


def verify_output(frames: dict[str, bytes], crouch: list[str]) -> None:
    with ZipFile(OUT) as package:
        packaged_play = {
            Path(info.filename).stem.upper(): package.read(info.filename)
            for info in package.infolist()
            if info.filename.startswith("sprites/player/PLAY")
        }
        if packaged_play != frames:
            raise SystemExit("generated PLAY frames differ from Retribution")

        for name in crouch:
            data = package.read(f"sprites/player/{name}.png")
            if data != frames["PLAY" + name[4:]]:
                raise SystemExit(f"generated crouch alias differs: {name}")

        shader = package.read("shaders/d64ue/playercolor.fp")
        if shader != NORMAL_MATERIAL_SHADER:
            raise SystemExit("generated player shader differs from normal material path")

    print(
        f"verified: {len(frames)} exact PLAY frames, {len(crouch)} crouch aliases, "
        "normal shader"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    if not UE.exists():
        raise SystemExit(f"missing {UE}")
    if not RETRIBUTION.exists():
        raise SystemExit(f"missing {RETRIBUTION}")

    frames = retribution_player_frames()
    with ZipFile(UE) as source:
        crouch = crouch_names(source)

    print(f"Retribution PLAY frames: {len(frames)}")
    print(f"UE crouch aliases: {len(crouch)}")
    if not args.write:
        print(f"census only; pass --write to build {OUT.name}")
        return

    with ZipFile(OUT, "w", compression=ZIP_DEFLATED) as out:
        for name, data in sorted(frames.items()):
            out.writestr(f"sprites/player/{name}.png", data)
        for name in crouch:
            standing_name = "PLAY" + name[4:]
            if standing_name not in frames:
                raise SystemExit(
                    f"no Retribution standing frame for UE crouch frame {name}"
                )
            out.writestr(f"sprites/player/{name}.png", frames[standing_name])
        out.writestr("shaders/d64ue/playercolor.fp", NORMAL_MATERIAL_SHADER)

    print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")
    verify_output(frames, crouch)


if __name__ == "__main__":
    main()
