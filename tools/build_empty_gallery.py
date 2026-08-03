"""Build MAP99 empty twin of the texture gallery: same shell size, zero pillars.

Uses grid dims from tools/_gallery/booths.json so wallturned / east spawn
coordinates still line up. For wash QA without booth emissives in the TLAS.

Outputs:
  Doom64-Retribution/d64remptyg.wad
  Doom64-Retribution/d64r-emptygallery-mapinfo.pk3
  rt/data/scenes/d64remptyg_map99/textures.json  (minimal)
"""
from __future__ import annotations

import json
import struct
import zipfile
from pathlib import Path

ROOT = Path(r"G:\AI\Doom64-RT")
BOOTHS = ROOT / r"tools\_gallery\booths.json"
OUT_WAD = ROOT / r"Doom64-Retribution\d64remptyg.wad"
OUT_MAPINFO = ROOT / r"Doom64-Retribution\d64r-emptygallery-mapinfo.pk3"
SCENE_DIR = (
    ROOT / r"sourcecode\gzdoom-rt\build\RelWithDebInfo\rt\data\scenes\d64remptyg_map99"
)
OVERLAY_SCENE = (
    ROOT
    / r"Doom64-Retribution\Retribution-RT-Materials\rt\data\scenes\d64remptyg_map99"
)

FLOOR = "FLOOR0_1"
CEIL = "CEIL1_1"
HALL_H = 128
SHELL_TEX = "STONE2"


def write_wad(items: list[tuple[str, bytes]]) -> bytes:
    body = b""
    directory = b""
    offset = 12
    for name, data in items:
        directory += struct.pack(
            "<II8s", offset, len(data), name.encode("ascii")[:8].ljust(8, b"\0")
        )
        body += data
        offset += len(data)
    return struct.pack("<4sII", b"PWAD", len(items), 12 + len(body)) + body + directory


def emit_block(kind: str, fields: dict) -> str:
    lines_out = [f"{kind}", "{"]
    for k, v in fields.items():
        if isinstance(v, bool):
            if v:
                lines_out.append(f"{k} = true;")
        elif isinstance(v, str):
            lines_out.append(f'{k} = "{v}";')
        elif isinstance(v, float):
            lines_out.append(f"{k} = {v:.3f};")
        else:
            lines_out.append(f"{k} = {v};")
    lines_out.append("}")
    return "\n".join(lines_out)


def build_empty_textmap(cols: int, rows: int, cell: int) -> str:
    margin = cell * 2
    shell = cell
    width = cols * cell + margin * 2
    height = rows * cell + margin * 2

    verts: list[tuple[float, float]] = []
    lines: list[dict] = []
    sides: list[dict] = []
    sectors: list[dict] = []

    def add_vert(x: float, y: float) -> int:
        verts.append((x, y))
        return len(verts) - 1

    def add_side(sector: int, mid: str, top: str = "-", bottom: str = "-") -> int:
        sid = len(sides)
        sides.append(
            {
                "sector": sector,
                "texturemiddle": mid,
                "texturetop": top,
                "texturebottom": bottom,
            }
        )
        return sid

    v0 = add_vert(-margin, -margin)
    v1 = add_vert(width - margin, -margin)
    v2 = add_vert(width - margin, height - margin)
    v3 = add_vert(-margin, height - margin)
    o0 = add_vert(-margin - shell, -margin - shell)
    o1 = add_vert(width - margin + shell, -margin - shell)
    o2 = add_vert(width - margin + shell, height - margin + shell)
    o3 = add_vert(-margin - shell, height - margin + shell)

    hall = len(sectors)
    sectors.append(
        {
            "heightfloor": 0,
            "heightceiling": HALL_H,
            "texturefloor": FLOOR,
            "textureceiling": CEIL,
            # Dark like emis-iso (32). Gallery's 160 washes out PT — looks "classic"
            # and hides rt_mzlflsh / sky GI on STONE2.
            "lightlevel": 24,
        }
    )
    solid = len(sectors)
    sectors.append(
        {
            "heightfloor": HALL_H,
            "heightceiling": HALL_H,
            "texturefloor": FLOOR,
            "textureceiling": CEIL,
            "lightlevel": 0,
        }
    )

    def add_onesided(v_a: int, v_b: int, mid: str, sector: int) -> None:
        lines.append(
            {
                "v1": v_a,
                "v2": v_b,
                "sidefront": add_side(sector, mid),
                "blocking": True,
            }
        )

    def add_shell_wall(va: int, vb: int, mid: str = SHELL_TEX) -> None:
        sf = add_side(hall, mid, top=mid, bottom=mid)
        sb = add_side(solid, "-", top="-", bottom="-")
        lines.append(
            {
                "v1": va,
                "v2": vb,
                "sidefront": sf,
                "sideback": sb,
                "blocking": True,
                "twosided": True,
                "dontpegtop": True,
            }
        )

    add_shell_wall(v1, v0)
    add_shell_wall(v2, v1)
    add_shell_wall(v3, v2)
    add_shell_wall(v0, v3)
    add_onesided(o1, o0, SHELL_TEX, solid)
    add_onesided(o2, o1, SHELL_TEX, solid)
    add_onesided(o3, o2, SHELL_TEX, solid)
    add_onesided(o0, o3, SHELL_TEX, solid)

    # Same default start as full gallery (south side, looking north)
    thing = {
        "x": cols * cell * 0.5,
        "y": -margin * 0.4,
        "angle": 90,
        "type": 1,
        "skill1": True,
        "skill2": True,
        "skill3": True,
        "skill4": True,
        "skill5": True,
        "single": True,
        "coop": True,
        "dm": True,
    }

    parts = ['namespace = "zdoom";', ""]
    for x, y in verts:
        parts.append(emit_block("vertex", {"x": x, "y": y}))
        parts.append("")
    for sec in sectors:
        parts.append(emit_block("sector", sec))
        parts.append("")
    for sd in sides:
        parts.append(emit_block("sidedef", sd))
        parts.append("")
    for ld in lines:
        parts.append(emit_block("linedef", ld))
        parts.append("")
    parts.append(emit_block("thing", thing))
    parts.append("")
    parts.append(
        f"// D64RT empty gallery twin: {cols}x{rows} footprint, 0 pillars "
        f"(cell={cell}, size={width:.0f}x{height:.0f})"
    )
    return "\n".join(parts)


def main() -> None:
    if not BOOTHS.exists():
        raise SystemExit(f"missing {BOOTHS} — run build_texture_gallery.py once first")
    grid = json.loads(BOOTHS.read_text(encoding="utf-8"))["grid"]
    cols = int(grid["cols"])
    rows = int(grid["rows"])
    cell = int(grid["cell"])

    textmap = build_empty_textmap(cols, rows, cell)
    wad = write_wad(
        [
            ("MAP99", b""),
            ("TEXTMAP", textmap.encode("utf-8")),
            ("ENDMAP", b""),
        ]
    )
    OUT_WAD.write_bytes(wad)
    print(f"wrote {OUT_WAD} ({len(wad)} bytes)  {cols}x{rows} cell={cell} pillars=0")

    pkg = ROOT / r"tools\d64r-emptygallery-mapinfo"
    pkg.mkdir(parents=True, exist_ok=True)
    (pkg / "MAPINFO").write_text(
        'map MAP99 "Empty Gallery Hall (no pillars)"\n{\n'
        "\tlevelnum = 99\n"
        '\tnext = "MAP99"\n'
        '\tsecretnext = "MAP99"\n'
        '\tsky1 = "RSKY1"\n'
        "\tcluster = 1\n"
        '\tmusic = ""\n'
        "}\n",
        encoding="utf-8",
    )
    if OUT_MAPINFO.exists():
        OUT_MAPINFO.unlink()
    with zipfile.ZipFile(OUT_MAPINFO, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.write(pkg / "MAPINFO", arcname="MAPINFO")
    print(f"wrote {OUT_MAPINFO}")

    empty = {"version": 0, "array": []}
    for d in (SCENE_DIR, OVERLAY_SCENE):
        d.mkdir(parents=True, exist_ok=True)
        (d / "textures.json").write_text(
            json.dumps(empty, indent=2) + "\n", encoding="utf-8"
        )
    print(f"scene -> {SCENE_DIR}")


if __name__ == "__main__":
    main()
