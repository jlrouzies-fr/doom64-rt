"""
Convert Doom 64 CE GZDoom PBR packs → RTGL1 companion maps for Retribution.

Source (local, gitignored):
  DoomCE/DOOM64.CE.Addon.GFX.PBR.pk3
    materials/{normalmaps,roughness,metallic,ao}/auto/<tex>.png

Output (local, regenerable, gitignored):
  Doom64-Retribution/Retribution-RT-Materials-CE/rt/mat/<TEX>_n.png
  Doom64-Retribution/Retribution-RT-Materials-CE/rt/mat/<TEX>_orm.png
  Doom64-Retribution/Retribution-RT-Materials-CE/manifest.json

RTGL1 ORM swizzle NULL_ROUGHNESS_METALLIC: R=AO, G=roughness, B=metallic.

Only textures that also exist in Retribution (WAD PNG / TEXTURES / map-used)
are converted, so gallery A/B stays name-compatible.
"""
from __future__ import annotations

import argparse
import io
import json
import re
import struct
import zipfile
from pathlib import Path

from PIL import Image

ROOT = Path(r"G:\AI\Doom64-RT")
WAD = ROOT / r"Doom64-Retribution\D64RTR_v15.WAD"
CE_PBR = ROOT / r"DoomCE\DOOM64.CE.Addon.GFX.PBR.pk3"
OUT = ROOT / r"Doom64-Retribution\Retribution-RT-Materials-CE"
OUT_MAT = OUT / r"rt\mat"
MANIFEST = OUT / "manifest.json"


def wad_texture_names() -> set[str]:
    d = WAD.read_bytes()
    n, o = struct.unpack_from("<II", d, 4)
    names: set[str] = set()
    for i in range(n):
        off, sz, raw = struct.unpack_from("<II8s", d, o + i * 16)
        nm = raw.split(b"\0")[0].decode("ascii", "replace").rstrip().upper()
        if sz <= 0:
            continue
        if d[off : off + 4] == b"\x89PNG":
            names.add(nm)
        if nm == "TEXTMAP":
            t = d[off : off + sz].decode("utf-8", "replace")
            for m in re.finditer(
                r'texture(?:floor|ceiling|middle|top|bottom)\s*=\s*"([^"]+)"',
                t,
                re.I,
            ):
                names.add(m.group(1).upper())
        if nm == "TEXTURES":
            t = d[off : off + sz].decode("latin1", "replace")
            for m in re.finditer(
                r"(?im)^\s*(?:Texture|WallTexture|Flat)\s+([A-Za-z0-9_]+)", t
            ):
                names.add(m.group(1).upper())
    return names


def gray_channel(img: Image.Image) -> Image.Image:
    """CE stores grayscale as R=G=B; take R."""
    if img.mode != "RGB":
        img = img.convert("RGB")
    return img.split()[0]


def pack_orm(ao: Image.Image, rough: Image.Image, metal: Image.Image) -> Image.Image:
    a = gray_channel(ao)
    r = gray_channel(rough)
    m = gray_channel(metal)
    # Match sizes to AO
    if r.size != a.size:
        r = r.resize(a.size, Image.Resampling.BILINEAR)
    if m.size != a.size:
        m = m.resize(a.size, Image.Resampling.BILINEAR)
    out = Image.merge("RGB", (a, r, m))
    return out.convert("RGBA")


def open_png(data: bytes) -> Image.Image:
    return Image.open(io.BytesIO(data)).convert("RGBA")


def convert(force: bool = False) -> dict:
    if not CE_PBR.exists():
        raise SystemExit(f"missing CE PBR pack: {CE_PBR}")
    if not WAD.exists():
        raise SystemExit(f"missing Retribution WAD: {WAD}")

    retri = wad_texture_names()
    OUT_MAT.mkdir(parents=True, exist_ok=True)

    converted: list[str] = []
    skipped_no_retri: list[str] = []
    skipped_incomplete: list[str] = []

    with zipfile.ZipFile(CE_PBR) as z:
        # Index auto materials by stem + kind
        by: dict[str, dict[str, str]] = {}
        for n in z.namelist():
            path = n.replace("\\", "/")
            if not path.lower().startswith("materials/") or "/auto/" not in path.lower():
                continue
            if not path.lower().endswith(".png"):
                continue
            parts = path.split("/")
            # materials/<kind>/auto/<stem>.png
            if len(parts) < 4:
                continue
            kind = parts[1].lower()
            stem = Path(parts[-1]).stem.upper()
            by.setdefault(stem, {})[kind] = n

        for stem, kinds in sorted(by.items()):
            if stem not in retri:
                skipped_no_retri.append(stem)
                continue
            need = ("normalmaps", "roughness", "metallic", "ao")
            if any(k not in kinds for k in need):
                skipped_incomplete.append(stem)
                continue

            n_path = OUT_MAT / f"{stem}_n.png"
            o_path = OUT_MAT / f"{stem}_orm.png"
            if not force and n_path.exists() and o_path.exists():
                converted.append(stem)
                continue

            normal = open_png(z.read(kinds["normalmaps"])).convert("RGBA")
            # Ensure opaque alpha on normals
            if normal.mode == "RGBA":
                r, g, b, _a = normal.split()
                normal = Image.merge("RGBA", (r, g, b, Image.new("L", normal.size, 255)))

            orm = pack_orm(
                open_png(z.read(kinds["ao"])),
                open_png(z.read(kinds["roughness"])),
                open_png(z.read(kinds["metallic"])),
            )
            if orm.size != normal.size:
                orm = orm.resize(normal.size, Image.Resampling.BILINEAR)

            normal.save(n_path)
            orm.save(o_path)
            converted.append(stem)

    manifest = {
        "source": str(CE_PBR.relative_to(ROOT)).replace("\\", "/"),
        "output": str(OUT.relative_to(ROOT)).replace("\\", "/"),
        "converted": sorted(converted),
        "count": len(converted),
        "skipped_not_in_retribution": len(skipped_no_retri),
        "skipped_incomplete": sorted(skipped_incomplete),
        "note": (
            "GZDoom CE PBR (Substance) → RTGL1 _n + ORM(AO,R,M). "
            "Use tools/launch-texture-gallery-ce-pbr.cmd to A/B vs baseline gallery."
        ),
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"converted {len(converted)} textures -> {OUT_MAT}")
    print(f"  skipped not in Retribution: {len(skipped_no_retri)}")
    print(f"  skipped incomplete: {len(skipped_incomplete)}")
    print(f"manifest -> {MANIFEST}")
    return manifest


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--force",
        action="store_true",
        help="Rewrite existing converted PNGs",
    )
    args = ap.parse_args()
    convert(force=args.force)


if __name__ == "__main__":
    main()
