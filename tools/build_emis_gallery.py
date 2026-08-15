"""Build a MAP99 gallery with only authored world emissives.

Sources textures from Retribution-RT-Materials/rt/data/textures_world_emis.json
(the gen_world_emissives allowlist — monitors, EXIT, keys, CRT, lava, …).

Outputs:
  Doom64-Retribution/d64remis.wad
  tools/_gallery/emis_gallery.json
  rt/data/scenes/d64remis_map99/textures.json  (engine + overlay)
"""
from __future__ import annotations

import json
from pathlib import Path

from build_texture_gallery import GALLERY_MAP, build_gallery_textmap, write_wad
import build_texture_gallery as btg

# Repo root, derived from this file so a clone can live anywhere.
PROJ_ROOT = Path(__file__).resolve().parents[1]

ROOT = PROJ_ROOT
WORLD_EMIS = (
    ROOT / r"Doom64-Retribution\Retribution-RT-Materials\rt\data\textures_world_emis.json"
)
OUT_WAD = ROOT / r"Doom64-Retribution\d64remis.wad"
META_JSON = ROOT / r"tools\_gallery\emis_gallery.json"
ENGINE_SCENES = ROOT / r"sourcecode\gzdoom-rt\build\RelWithDebInfo\rt\data\scenes"
OVERLAY_SCENES = (
    ROOT / r"Doom64-Retribution\Retribution-RT-Materials\rt\data\scenes"
)

STEM = "d64remis"

# Browse order: signs/keys first, then screens, then lava.
FAMILY_ORDER: list[str] = [
    "SEXIT",
    "SKEYFL",
    "SMON",
    "CFACE",
    "CRTR",
    "CRT",
    "C22",
    "C23",
    "D64LOGO",
    "HLAVA",
    "D64LAVA",
    "LAVA",
    "NUKAGE",
    "NUKE",
]


def family_key(name: str) -> tuple[int, str]:
    u = name.upper()
    for i, pref in enumerate(FAMILY_ORDER):
        if u.startswith(pref):
            return (i, u)
    return (len(FAMILY_ORDER), u)


def load_emis_textures() -> list[str]:
    if not WORLD_EMIS.exists():
        raise SystemExit(
            f"missing {WORLD_EMIS} — run tools/gen_world_emissives.py first"
        )
    data = json.loads(WORLD_EMIS.read_text(encoding="utf-8"))
    names = [
        str(e["textureName"])
        for e in data.get("array", [])
        if e.get("textureName")
    ]
    # Unique, stable family sort
    return sorted(set(names), key=family_key)


def write_scene(world_data: dict) -> None:
    text = json.dumps(world_data, indent=2) + "\n"
    for root in (ENGINE_SCENES, OVERLAY_SCENES):
        d = root / f"{STEM}_map99"
        d.mkdir(parents=True, exist_ok=True)
        (d / "textures.json").write_text(text, encoding="utf-8")


def main() -> None:
    world_data = json.loads(WORLD_EMIS.read_text(encoding="utf-8"))
    textures = load_emis_textures()
    if not textures:
        raise SystemExit("world emis allowlist is empty")

    textmap = build_gallery_textmap(textures, close_spawn=False)
    booths = getattr(build_gallery_textmap, "last_booths", [])
    grid = getattr(build_gallery_textmap, "last_grid", {})

    OUT_WAD.write_bytes(
        write_wad(
            [
                (GALLERY_MAP, b""),
                ("TEXTMAP", textmap.encode("utf-8")),
                ("ENDMAP", b""),
            ]
        )
    )
    write_scene(world_data)

    meta = {
        "stem": STEM,
        "wad": str(OUT_WAD),
        "count": len(textures),
        "textures": textures,
        "grid": grid,
        "booths": booths,
        "cell": btg.CELL,
        "pillar": btg.PILLAR,
        "source": str(WORLD_EMIS),
    }
    META_JSON.parent.mkdir(parents=True, exist_ok=True)
    META_JSON.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")

    print(
        f"emis gallery: {OUT_WAD.name}  {len(textures)} pillars  "
        f"grid {grid.get('cols')}x{grid.get('rows')}"
    )
    print(f"  first={textures[0]}  last={textures[-1]}")
    print(f"  meta -> {META_JSON}")
    print(f"  scene -> {STEM}_map99")
    print("launch: tools\\launch-emis-gallery.cmd")


if __name__ == "__main__":
    main()
