"""
Generate content-aware ORM (+ optional normal) from Retribution albedo PNGs in the WAD.

RTGL1 ORM swizzle NULL_ROUGHNESS_METALLIC:
  R = AO (approx), G = roughness, B = metallic

Hardware heuristic: small bright/dark local contrast (rivets/screws) →
higher metallic, lower roughness. Panel body stays near category defaults.
"""
from __future__ import annotations

import argparse
import io
import json
import re
import struct
import sys
from pathlib import Path

from PIL import Image, ImageFilter, ImageOps

ROOT = Path(r"G:\AI\Doom64-RT")
sys.path.insert(0, str(ROOT / "tools"))
from apply_all_category_pbr import classify  # noqa: E402

WAD = ROOT / r"Doom64-Retribution\D64RTR_v15.WAD"
MAT = ROOT / r"sourcecode\gzdoom-rt\build\RelWithDebInfo\rt\mat"
MAT_DEV = ROOT / r"sourcecode\gzdoom-rt\build\RelWithDebInfo\rt\mat_dev"
OMAT = ROOT / r"Doom64-Retribution\Retribution-RT-Materials\rt\mat"
BOOTHS = ROOT / r"tools\_gallery\booths.json"


def _wad_index() -> dict[str, bytes]:
    data = WAD.read_bytes()
    n, o = struct.unpack_from("<II", data, 4)
    out: dict[str, bytes] = {}
    for i in range(n):
        off, sz, raw = struct.unpack_from("<II8s", data, o + i * 16)
        nm = raw.split(b"\0")[0].decode("ascii", "replace").upper()
        if sz > 0:
            out[nm] = data[off : off + sz]
    return out


def _png_lump(lumps: dict[str, bytes], name: str) -> Image.Image:
    blob = lumps[name.upper()]
    if blob[:4] != b"\x89PNG":
        raise RuntimeError(f"{name}: lump is not PNG")
    return Image.open(io.BytesIO(blob)).convert("RGBA")


def _compose_from_textures(lumps: dict[str, bytes], name: str) -> Image.Image | None:
    """Resolve ZDoom TEXTURES lump: Texture NAME, w, h + Patch ..."""
    tex = lumps.get("TEXTURES")
    if not tex:
        return None
    text = tex.decode("latin1", "replace")
    key = name.upper()
    # Texture NAME, W, H  ... until next Texture/Sprite/WallTexture/Flat
    pat = re.compile(
        rf"(?im)^\s*(?:Texture|WallTexture|Flat)\s+{re.escape(key)}\s*,\s*(\d+)\s*,\s*(\d+)\s*(.*?)(?=^\s*(?:Texture|WallTexture|Flat|Sprite)\s+|\Z)",
        re.S,
    )
    m = pat.search(text)
    if not m:
        return None
    w, h = int(m.group(1)), int(m.group(2))
    body = m.group(3)
    canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    for pm in re.finditer(
        r"(?im)(?:^|[\{;])\s*Patch\s+([A-Za-z0-9_]+)\s*,\s*(-?\d+)\s*,\s*(-?\d+)",
        body,
    ):
        pname, px, py = pm.group(1).upper(), int(pm.group(2)), int(pm.group(3))
        if pname not in lumps:
            continue
        try:
            patch = _png_lump(lumps, pname)
        except Exception:
            continue
        canvas.paste(patch, (px, py), patch)
    if canvas.getbbox() is None:
        return None
    return canvas


def wad_png(name: str) -> Image.Image:
    lumps = _wad_index()
    key = name.upper()
    if key in lumps and lumps[key][:4] == b"\x89PNG":
        return _png_lump(lumps, key)
    composed = _compose_from_textures(lumps, key)
    if composed is not None:
        return composed
    raise KeyError(name)


def category_base(name: str) -> tuple[float, float]:
    m = classify(name)
    return float(m.get("roughnessDefault", 0.75)), float(m.get("metallicDefault", 0.2))


def detail_masks(albedo: Image.Image) -> tuple[Image.Image, Image.Image, Image.Image]:
    """Return (luma, highpass abs, hardware weight) as L mode 0..255.

    Hardware = small bright heads / dark pits that also sit on local contrast.
    Lone panel seams (high-pass only) stay dull so metal_frac stays sparse.
    """
    rgb = albedo.convert("RGB")
    luma = ImageOps.grayscale(rgb)
    blur = luma.filter(ImageFilter.GaussianBlur(radius=1.4))
    w, h = luma.size
    lp = luma.load()
    bp = blur.load()
    hp = Image.new("L", (w, h))
    hpp = hp.load()
    for y in range(h):
        for x in range(w):
            hpp[x, y] = min(255, abs(lp[x, y] - bp[x, y]) * 4)

    # Small bright spots (screw heads) + dark recesses — stricter thresholds
    bright = luma.point(lambda v: 255 if v >= 190 else 0)
    dark = luma.point(lambda v: 255 if v <= 40 else 0)
    bright = bright.filter(ImageFilter.MaxFilter(3))
    dark = dark.filter(ImageFilter.MaxFilter(3))
    # Strong local contrast only (skip soft panel gradients)
    hp_bin = hp.point(lambda v: 255 if v >= 55 else 0)

    hw = Image.new("L", (w, h))
    hwp = hw.load()
    br = bright.load()
    dk = dark.load()
    hb = hp_bin.load()
    for y in range(h):
        for x in range(w):
            # Require contrast + polarity; ignore seam-only edges
            if hb[x, y] and br[x, y]:
                score = 220
            elif hb[x, y] and dk[x, y]:
                score = 180
            elif br[x, y] and lp[x, y] >= 210:
                # tiny specular speck without strong HP
                score = 140
            else:
                score = 0
            hwp[x, y] = score
    # Tiny soft falloff so rivet highlights aren't 1px hard
    hw = hw.filter(ImageFilter.GaussianBlur(radius=0.5))
    return luma, hp, hw


def make_orm(name: str, albedo: Image.Image) -> Image.Image:
    base_r, base_m = category_base(name)
    luma, _hp, hw = detail_masks(albedo)
    w, h = albedo.size
    lp = luma.load()
    hwp = hw.load()
    out = Image.new("RGBA", (w, h))
    op = out.load()

    for y in range(h):
        for x in range(w):
            a = albedo.getpixel((x, y))[3] if albedo.mode == "RGBA" else 255
            if a < 8:
                op[x, y] = (255, int(base_r * 255), 0, 0)
                continue

            t = hwp[x, y] / 255.0  # 0..1 hardware weight
            shade = lp[x, y] / 255.0

            # Dull panel/rock body vs sparse shiny rivets (avoid chrome walls)
            body_r = min(0.82, max(0.55, base_r + 0.20))
            body_m = min(0.10, base_m * 0.12)
            hw_r, hw_m = 0.16, 0.92
            rough = body_r * (1.0 - t) + hw_r * t
            metal = body_m * (1.0 - t) + hw_m * t

            if t < 0.12:
                rough = min(1.0, rough + (1.0 - shade) * 0.10)

            ao = int(max(40, min(255, 40 + shade * 215)))
            op[x, y] = (
                ao,
                max(0, min(255, int(rough * 255))),
                max(0, min(255, int(metal * 255))),
                255,
            )
    return out


def make_normal(albedo: Image.Image, strength: float = 1.6) -> Image.Image:
    """Sobel-ish normal from luma (OpenGL-style: +X right, +Y up)."""
    luma = ImageOps.grayscale(albedo.convert("RGB"))
    w, h = luma.size
    lp = luma.load()
    out = Image.new("RGB", (w, h))
    op = out.load()
    for y in range(h):
        for x in range(w):
            l = lp[max(0, x - 1), y]
            r = lp[min(w - 1, x + 1), y]
            u = lp[x, max(0, y - 1)]
            d = lp[x, min(h - 1, y + 1)]
            dx = (r - l) / 255.0 * strength
            dy = (u - d) / 255.0 * strength  # invert y for typical GL
            # n = normalize(-dx, -dy, 1)
            nx, ny, nz = -dx, -dy, 1.0
            inv = (nx * nx + ny * ny + nz * nz) ** 0.5 or 1.0
            nx, ny, nz = nx / inv, ny / inv, nz / inv
            op[x, y] = (
                int((nx * 0.5 + 0.5) * 255),
                int((ny * 0.5 + 0.5) * 255),
                int((nz * 0.5 + 0.5) * 255),
            )
    return out


def solid_orm_image(name: str, size: tuple[int, int] | None = None) -> Image.Image:
    if size is None:
        size = wad_png(name).size
    rough, metal = category_base(name)
    g = max(0, min(255, int(rough * 255)))
    b = max(0, min(255, int(metal * 255)))
    return Image.new("RGBA", size, (255, g, b, 255))


def process(name: str, mode: str = "detail", write_normal: bool = True) -> dict:
    albedo = wad_png(name)
    if mode == "solid":
        orm = solid_orm_image(name, albedo.size)
        for mat in (MAT_DEV, OMAT, MAT):
            mat.mkdir(parents=True, exist_ok=True)
            orm.save(mat / f"{name}_orm.png")
            # remove detail normal so before pass is fair
            p = mat / f"{name}_n.png"
            if p.exists():
                p.unlink()
        return {"texture": name, "size": list(albedo.size), "mode": "solid", "metal_frac": category_base(name)[1]}

    orm = make_orm(name, albedo)
    stats = {"texture": name, "size": list(albedo.size), "mode": "detail"}
    # hardware metal (B high); body is deliberately ~0.28
    metals = sum(1 for p in orm.getdata() if p[2] > 150)
    stats["metal_frac"] = round(metals / max(1, orm.size[0] * orm.size[1]), 3)

    for mat in (MAT_DEV, OMAT, MAT):
        mat.mkdir(parents=True, exist_ok=True)
        orm.save(mat / f"{name}_orm.png")
        if write_normal:
            make_normal(albedo).save(mat / f"{name}_n.png")
    return stats


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--names", nargs="*", help="Texture names")
    ap.add_argument("--indices", default="", help="Comma gallery indices, e.g. 0,2,5,6,8")
    ap.add_argument("--mode", choices=("detail", "solid"), default="detail")
    ap.add_argument("--no-normal", action="store_true")
    args = ap.parse_args()

    names = list(args.names or [])
    if args.indices.strip():
        booths = json.loads(BOOTHS.read_text(encoding="utf-8"))["booths"]
        for part in args.indices.split(","):
            names.append(booths[int(part.strip())]["texture"])
    if not names:
        raise SystemExit("Provide --names or --indices")

    seen = set()
    uniq = []
    for n in names:
        u = n.upper()
        if u not in seen:
            seen.add(u)
            uniq.append(n)

    report = []
    for n in uniq:
        st = process(n, mode=args.mode, write_normal=not args.no_normal)
        report.append(st)
        print(
            f"{st['texture']}: {st['size'][0]}x{st['size'][1]} "
            f"mode={st['mode']} metal_frac={st['metal_frac']}"
        )

    out = ROOT / r"tools\_gallery\detail_orm_report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("wrote", out)


if __name__ == "__main__":
    main()
