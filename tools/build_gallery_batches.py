"""Split the texture gallery into 8 MAP99 halls of 100 pillars (last = remainder).

Reads texture order from tools/_gallery/booths.json (same as full gallery).
Outputs:
  Doom64-Retribution/d64rtexg01.wad … d64rtexg08.wad
  Doom64-Retribution/d64r-texgallery-batch-mapinfo.pk3  (MAP91–MAP98 aliases optional)
  Actually: each wad provides MAP99; launch one wad at a time.
  tools/_gallery/batches/batch_XX.json
  rt/data/scenes/d64rtexg0N_map99/textures.json (empty stub; meta from global/overlays)
"""
from __future__ import annotations

import json
import struct
import zipfile
from pathlib import Path

from build_texture_gallery import (
    GALLERY_MAP,
    build_gallery_textmap,
    write_wad,
)
import build_texture_gallery as btg

ROOT = Path(r"G:\AI\Doom64-RT")
BOOTHS = ROOT / r"tools\_gallery\booths.json"
INV = ROOT / r"tools\_gallery\texture_inventory.json"
OUT_DIR = ROOT / r"Doom64-Retribution"
BATCH_DIR = ROOT / r"tools\_gallery\batches"
MAPINFO_PK3 = OUT_DIR / "d64r-texgallery-batches-mapinfo.pk3"
ENGINE_SCENES = ROOT / r"sourcecode\gzdoom-rt\build\RelWithDebInfo\rt\data\scenes"
OVERLAY_SCENES = (
    ROOT / r"Doom64-Retribution\Retribution-RT-Materials\rt\data\scenes"
)

BATCH_SIZE = 100
NUM_BATCHES = 8  # 7×100 + remainder in #8

# Match base gallery (build_texture_gallery.py) — dense small pillars, wide view.
# Do not override CELL/PILLAR; apply_batch_scale is a no-op kept for clarity.


def apply_batch_scale() -> None:
    """Use stock gallery scale so batches look like d64rtexg.wad."""
    pass

def load_textures() -> list[str]:
    if BOOTHS.exists():
        data = json.loads(BOOTHS.read_text(encoding="utf-8"))
        names = [b["texture"] for b in data.get("booths", [])]
        if names:
            return names
    if INV.exists():
        data = json.loads(INV.read_text(encoding="utf-8"))
        return list(data.get("textures", []))
    raise SystemExit(f"missing {BOOTHS} / {INV} — run build_texture_gallery.py first")


def batch_slices(textures: list[str]) -> list[tuple[int, int, list[str]]]:
    """Return list of (batch_index_1based, global_start, textures)."""
    n = len(textures)
    out: list[tuple[int, int, list[str]]] = []
    for i in range(NUM_BATCHES):
        start = i * BATCH_SIZE
        if start >= n:
            break
        # Last planned batch takes everything remaining
        if i == NUM_BATCHES - 1:
            chunk = textures[start:]
        else:
            chunk = textures[start : start + BATCH_SIZE]
        if not chunk:
            break
        out.append((i + 1, start, chunk))
    return out


def write_scene_stub(stem: str) -> None:
    """Seed scene textures.json with world emis meta so batch maps glow like MAP99."""
    world = ROOT / r"Doom64-Retribution\Retribution-RT-Materials\rt\data\textures_world_emis.json"
    if world.exists():
        data = json.loads(world.read_text(encoding="utf-8"))
    else:
        data = {"version": 0, "array": []}
    for root in (ENGINE_SCENES, OVERLAY_SCENES):
        d = root / f"{stem}_map99"
        d.mkdir(parents=True, exist_ok=True)
        (d / "textures.json").write_text(
            json.dumps(data, indent=2) + "\n", encoding="utf-8"
        )


def write_mapinfo(batches: list[tuple[int, int, list[str]]]) -> None:
    """One MAPINFO: map MAP99 title depends on which wad is loaded — keep generic.

    Per-batch titles go in a tiny MAPINFO inside each wad? UDMF wads can't easily
    ship MAPINFO without a pk3. Single shared pk3 with MAP99 is enough; launcher
    prints the batch label.
    """
    pkg = ROOT / r"tools\d64r-texgallery-batches-mapinfo"
    pkg.mkdir(parents=True, exist_ok=True)
    lines = [
        'map MAP99 "RT Texture Gallery Batch"\n{\n',
        "\tlevelnum = 99\n",
        '\tnext = "MAP99"\n',
        '\tsecretnext = "MAP99"\n',
        '\tsky1 = "RSKY1"\n',
        "\tcluster = 1\n",
        '\tmusic = ""\n',
        "}\n",
    ]
    (pkg / "MAPINFO").write_text("".join(lines), encoding="utf-8")
    if MAPINFO_PK3.exists():
        MAPINFO_PK3.unlink()
    with zipfile.ZipFile(MAPINFO_PK3, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.write(pkg / "MAPINFO", arcname="MAPINFO")
    print(f"wrote {MAPINFO_PK3}")


def main() -> None:
    apply_batch_scale()
    textures = load_textures()
    batches = batch_slices(textures)
    BATCH_DIR.mkdir(parents=True, exist_ok=True)

    manifest = {
        "batch_size": BATCH_SIZE,
        "cell": btg.CELL,
        "pillar": btg.PILLAR,
        "hall_h": btg.HALL_H,
        "total_textures": len(textures),
        "batches": [],
    }

    for idx, start, chunk in batches:
        stem = f"d64rtexg{idx:02d}"
        wad_path = OUT_DIR / f"{stem}.wad"
        textmap = build_gallery_textmap(chunk, close_spawn=False)
        booths = getattr(build_gallery_textmap, "last_booths", [])
        grid = getattr(build_gallery_textmap, "last_grid", {})
        # Re-index booths with global texture index for review notes
        for b in booths:
            b["global_index"] = start + int(b["index"])
            b["batch"] = idx

        wad_path.write_bytes(
            write_wad(
                [
                    (GALLERY_MAP, b""),
                    ("TEXTMAP", textmap.encode("utf-8")),
                    ("ENDMAP", b""),
                ]
            )
        )
        write_scene_stub(stem)

        meta = {
            "batch": idx,
            "stem": stem,
            "wad": str(wad_path),
            "global_start": start,
            "global_end": start + len(chunk) - 1,
            "count": len(chunk),
            "textures": chunk,
            "grid": grid,
            "booths": booths,
            "cols": grid.get("cols"),
            "rows": grid.get("rows"),
        }
        (BATCH_DIR / f"batch_{idx:02d}.json").write_text(
            json.dumps(meta, indent=2) + "\n", encoding="utf-8"
        )
        manifest["batches"].append(
            {
                "batch": idx,
                "stem": stem,
                "wad": wad_path.name,
                "global_start": start,
                "global_end": start + len(chunk) - 1,
                "count": len(chunk),
                "first": chunk[0],
                "last": chunk[-1],
            }
        )
        print(
            f"batch {idx:02d}: {wad_path.name}  "
            f"[{start}..{start + len(chunk) - 1}]  {len(chunk)} pillars  "
            f"grid {grid.get('cols')}x{grid.get('rows')}"
        )

    (BATCH_DIR / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    write_mapinfo(batches)
    print(f"manifest -> {BATCH_DIR / 'manifest.json'}")
    print(f"done: {len(batches)} galleries, {len(textures)} textures total")


if __name__ == "__main__":
    main()
