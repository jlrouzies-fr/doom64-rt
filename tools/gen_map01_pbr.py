"""
Auto-generate Phase-3/4 PBR meta + simple ORM/emissive PNGs for Retribution MAP01.

Outputs (into gzdoom-rt build rt/ tree):
  rt/data/scenes/d64rtr_v15_map01/textures.json
  rt/mat/<TEX>_orm.png   (dev-mode PNG; enable developerMode in RTGL1.json)
  rt/mat/<TEX>_e.png     (from brightmaps when available, else heuristic glow)
  rt/data/textures_retribution_map01.json  (copy of scene meta for packaging)

Also writes overlay package under Doom64-Retribution/Retribution-RT-Materials/
for later packaging as pk3-equivalent loose rt/ overlay instructions.
"""
from __future__ import annotations

import json
import re
import struct
import zlib
from collections import Counter
from pathlib import Path

ROOT = Path(r"G:\AI\Doom64-RT")
TEXTMAP = ROOT / r"tools\_map_cmp\MAP01_TEXTMAP.txt"
WAD = ROOT / r"Doom64-Retribution\D64RTR_v15.WAD"
BM_PK3 = ROOT / r"Doom64-Retribution\D64RTR_BRIGHTMAPS.PK3"
RT = ROOT / r"sourcecode\gzdoom-rt\build\RelWithDebInfo\rt"
SCENE = "d64rtr_v15_map01"
OVERLAY = ROOT / r"Doom64-Retribution\Retribution-RT-Materials"


def map_textures(text: str) -> list[str]:
    tex = Counter()
    for m in re.finditer(
        r'texture(?:floor|ceiling|middle|top|bottom)\s*=\s*"([^"]+)"', text
    ):
        name = m.group(1)
        if name not in ("-", "F_SKY1"):
            tex[name] += 1
    return [n for n, _ in tex.most_common()]


def classify(name: str) -> dict:
    u = name.upper()
    meta: dict = {"textureName": name, "roughnessDefault": 0.85, "metallicDefault": 0.0}

    # liquids / mirrors
    if any(x in u for x in ("WATER", "NUKE", "SLIME", "BLOOD", "LAVA")):
        if "LAVA" in u or "NUKE" in u or "FIRE" in u:
            meta["emissiveMult"] = 1.5
            meta["roughnessDefault"] = 0.35
            meta["isAcid"] = "NUKE" in u or "SLIME" in u
        else:
            meta["isMirror"] = True
            meta["isWater"] = "WATER" in u
            meta["metallicDefault"] = 1.0
            meta["roughnessDefault"] = 0.05
        return meta

    # space / metal panels (Doom 64 look)
    if u.startswith("SPACE") or u.startswith("METAL") or u.startswith("STEEL"):
        meta["metallicDefault"] = 0.75
        meta["roughnessDefault"] = 0.35
        meta["isMirrorIfSmooth"] = True
        return meta

    # monitors / computers / lights
    if any(x in u for x in ("COMP", "MONIT", "TECH", "PANEL", "LIGHT", "LITE", "GLOW", "SWITCH")):
        meta["metallicDefault"] = 0.55
        meta["roughnessDefault"] = 0.4
        meta["emissiveMult"] = 0.6
        meta["lightIntensity"] = 20.0
        meta["lightColor"] = [180, 220, 255]
        return meta

    # floors / flats
    if u.startswith("SFLAT") or u.startswith("FLAT") or u.startswith("FLOOR"):
        meta["roughnessDefault"] = 0.9
        meta["metallicDefault"] = 0.05
        return meta

    # ceilings
    if u.startswith("CEIL") or u.startswith("SDFLT"):
        meta["roughnessDefault"] = 0.8
        meta["metallicDefault"] = 0.15
        return meta

    # doors / gates
    if "DOOR" in u or "GATE" in u:
        meta["metallicDefault"] = 0.65
        meta["roughnessDefault"] = 0.45
        if "GATE" in u:
            meta["emissiveMult"] = 0.15
        return meta

    # default industrial
    meta["metallicDefault"] = 0.25
    meta["roughnessDefault"] = 0.7
    return meta


def write_png_rgba(path: Path, w: int, h: int, rgba: bytes) -> None:
    """Minimal PNG writer (no deps)."""

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    raw = b"".join(b"\x00" + rgba[y * w * 4 : (y + 1) * w * 4] for y in range(h))
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b"")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(png)


def solid_orm(roughness: float, metallic: float, size: int = 64) -> bytes:
    # ORM: R=AO, G=Roughness, B=Metallic (matches RG_TEXTURE_SWIZZLING_NULL_ROUGHNESS_METALLIC
    # used by gzdoom-rt — R ignored / null AO)
    g = max(0, min(255, int(roughness * 255)))
    b = max(0, min(255, int(metallic * 255)))
    pix = bytes([255, g, b, 255])
    return pix * (size * size)


def solid_emissive(rgb: tuple[int, int, int], size: int = 64) -> bytes:
    r, g, b = rgb
    pix = bytes([r, g, b, 255])
    return pix * (size * size)


def load_brightmap_names() -> set[str]:
    """Best-effort: zip entry basenames without extension."""
    if not BM_PK3.exists():
        return set()
    data = BM_PK3.read_bytes()
    # zip local headers
    names = set()
    i = 0
    while True:
        p = data.find(b"PK\x03\x04", i)
        if p < 0:
            break
        if p + 30 > len(data):
            break
        fnlen, = struct.unpack_from("<H", data, p + 26)
        name = data[p + 30 : p + 30 + fnlen].decode("latin1", "replace")
        base = Path(name).stem.upper()
        if base:
            names.add(base)
        i = p + 4
    return names


def main():
    names = map_textures(TEXTMAP.read_text(encoding="utf-8", errors="replace"))
    bright = load_brightmap_names()
    print(f"MAP01 textures: {len(names)}; brightmap-ish names: {len(bright)}")

    array = []
    for name in names:
        meta = classify(name)
        # boost emissive if brightmap exists for this texture
        if name.upper() in bright or f"BRT{name.upper()}" in bright:
            meta["emissiveMult"] = max(float(meta.get("emissiveMult", 0)), 0.8)
        array.append(meta)

    doc = {"version": 0, "array": array}

    scene_dir = RT / "data" / "scenes" / SCENE
    scene_dir.mkdir(parents=True, exist_ok=True)
    scene_json = scene_dir / "textures.json"
    # JSON with comments not allowed — write strict JSON
    scene_json.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    print("wrote", scene_json)

    # Overlay mirror for packaging
    ov_scene = OVERLAY / "rt" / "data" / "scenes" / SCENE
    ov_mat = OVERLAY / "rt" / "mat"
    ov_scene.mkdir(parents=True, exist_ok=True)
    ov_mat.mkdir(parents=True, exist_ok=True)
    (ov_scene / "textures.json").write_text(json.dumps(doc, indent=2), encoding="utf-8")

    mat_dir = RT / "mat"
    mat_dir.mkdir(parents=True, exist_ok=True)

    orm_n = emis_n = 0
    for meta in array:
        name = meta["textureName"]
        rough = float(meta.get("roughnessDefault", 0.85))
        metal = float(meta.get("metallicDefault", 0.0))
        emis = float(meta.get("emissiveMult", 0.0))

        orm = solid_orm(rough, metal)
        for dest in (mat_dir / f"{name}_orm.png", ov_mat / f"{name}_orm.png"):
            write_png_rgba(dest, 64, 64, orm)
        orm_n += 1

        if emis > 0.05:
            # mild cyan/amber glow tint for tech; lava hotter
            u = name.upper()
            if "LAVA" in u or "FIRE" in u:
                rgb = (255, 90, 20)
            elif "NUKE" in u or "SLIME" in u:
                rgb = (40, 255, 40)
            else:
                rgb = (120, 180, 255)
            # scale by emissiveMult
            scale = min(1.0, emis)
            rgb = tuple(max(0, min(255, int(c * scale))) for c in rgb)
            e = solid_emissive(rgb)  # type: ignore
            for dest in (mat_dir / f"{name}_e.png", ov_mat / f"{name}_e.png"):
                write_png_rgba(dest, 64, 64, e)
            emis_n += 1

    # Enable PNG overrides in RTGL1
    cfg = RT / "RTGL1.json"
    cfg.write_text(
        json.dumps(
            {
                "version": 0,
                "developerMode": True,
                "vulkanValidation": False,
                "dx12Validation": False,
                "dlssValidation": False,
                "fpsMonitor": False,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print("wrote", cfg, "(developerMode=true for PNG mat overrides)")
    print(f"orm pngs: {orm_n}; emissive pngs: {emis_n}")
    print("overlay:", OVERLAY)


if __name__ == "__main__":
    main()
