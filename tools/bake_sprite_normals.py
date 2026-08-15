"""Generate _n (and _h) maps for sprites, so a billboard stops reading as a flat card.

WHY THIS EXISTS — the "half the pixels are beige" report.

A sprite is one quad with ONE normal across its whole surface. Every dielectric's
reflectance climbs toward glancing angles (Fresnel), so when light arrives from
the side, EVERY texel is at the same grazing angle at once and the entire sprite
takes a uniform white sheen over the painted art. On a wall this never happens:
its _n map varies the normal per texel, so the same light makes highlights and
shadow instead of a wash.

It surfaced when the material pass gave sprites a roughness at all. POSSA1 has an
empty textures.json entry, so it previously ran at the 1.0 default -- fully matte,
no visible specular. 0.60 did not make it beige; it made the specular exist.

THE SHAPE COMES FROM THE SILHOUETTE, NOT FROM THE ALBEDO.

The usual trick -- emboss the luminance -- is wrong here on its own: it turns
PAINTED shading into geometry, so a dark trouser leg becomes a dent and the
already-painted light direction gets baked in twice. What a billboard actually
lacks is BODY. So the primary term is a distance transform inward from the alpha
outline, which domes the figure: normals tilt outward at the silhouette and face
the viewer at the core. Light from the side then sweeps a real terminator across
the body, which is precisely the wash this is meant to break up.

Albedo detail rides on top at a low weight, for folds and buckles.

NEVER WRITES THE ALBEDO. Sprite PNGs carry grAb offset chunks and Pillow drops
them -- a rewritten sprite renders sunk into the floor, or misplaced on screen for
a viewmodel. Only _n and _h companions are written, and those carry no offsets.

Usage:
    python tools\\bake_sprite_normals.py --codes POSS,SHTG
    python tools\\bake_sprite_normals.py --all [--bulge 1.0] [--detail 0.35]
    python tools\\bake_sprite_normals.py --revert
"""

from __future__ import annotations

import argparse
import io
import math
import re
import struct
import sys
from pathlib import Path

from PIL import Image

PROJ_ROOT = Path(__file__).resolve().parent.parent
WAD = PROJ_ROOT / "Doom64-Retribution" / "D64RTR_v15.WAD"

MAT_DIRS = [
    PROJ_ROOT / "sourcecode" / "gzdoom-rt" / "build" / "RelWithDebInfo" / "rt" / "mat_dev",
    PROJ_ROOT / "sourcecode" / "gzdoom-rt" / "build" / "RelWithDebInfo" / "rt" / "mat",
    PROJ_ROOT / "Doom64-Retribution" / "Retribution-RT-Materials" / "rt" / "mat_dev",
    PROJ_ROOT / "Doom64-Retribution" / "Retribution-RT-Materials" / "rt" / "mat",
]

BACKUP_SUFFIX = ".pre_sprite_normals"
NAME_RE = re.compile(r"^([A-Z0-9]{4})([A-Z\[\\\]])([0-8])(?:([A-Z\[\\\]])([0-8]))?$")


def read_lumps(data: bytes):
    n, o = struct.unpack_from("<II", data, 4)
    return [
        (
            struct.unpack_from("<II8s", data, o + i * 16)[2].split(b"\0")[0].decode("ascii", "replace"),
            struct.unpack_from("<II8s", data, o + i * 16)[0],
            struct.unpack_from("<II8s", data, o + i * 16)[1],
        )
        for i in range(n)
    ]


def sprite_frames(codes: set[str] | None):
    data = WAD.read_bytes()
    lumps = read_lumps(data)
    names = [nm for nm, _, _ in lumps]
    s0, s1 = names.index("SS_START"), names.index("SS_END")
    out = {}
    for nm, off, sz in lumps[s0 + 1 : s1]:
        if sz == 0:
            continue
        m = NAME_RE.match(nm)
        if not m:
            continue
        if codes and m.group(1) not in codes:
            continue
        raw = data[off : off + sz]
        if not raw.startswith(b"\x89PNG"):
            continue
        try:
            out[nm] = Image.open(io.BytesIO(raw)).convert("RGBA")
        except Exception:
            pass
    return out


def distance_inward(mask: list[list[bool]], w: int, h: int) -> list[list[float]]:
    """Chamfer distance from the silhouette edge, two passes.

    Written out rather than pulled from scipy: this project's Python is Pillow
    only, and a 40x80 sprite makes an exact transform pointless anyway."""
    BIG = float(w + h)
    d = [[0.0 if not mask[y][x] else BIG for x in range(w)] for y in range(h)]
    # forward
    for y in range(h):
        for x in range(w):
            if not mask[y][x]:
                continue
            best = d[y][x]
            if y > 0:
                best = min(best, d[y - 1][x] + 1.0)
                if x > 0:
                    best = min(best, d[y - 1][x - 1] + 1.41421)
                if x + 1 < w:
                    best = min(best, d[y - 1][x + 1] + 1.41421)
            if x > 0:
                best = min(best, d[y][x - 1] + 1.0)
            d[y][x] = best
    # backward
    for y in range(h - 1, -1, -1):
        for x in range(w - 1, -1, -1):
            if not mask[y][x]:
                continue
            best = d[y][x]
            if y + 1 < h:
                best = min(best, d[y + 1][x] + 1.0)
                if x > 0:
                    best = min(best, d[y + 1][x - 1] + 1.41421)
                if x + 1 < w:
                    best = min(best, d[y + 1][x + 1] + 1.41421)
            if x + 1 < w:
                best = min(best, d[y][x + 1] + 1.0)
            d[y][x] = best
    return d


def build_height(im: Image.Image, bulge: float, detail: float, radius: float):
    """Height field in [0,1]: a dome from the silhouette plus albedo detail."""
    w, h = im.size
    px = im.load()
    mask = [[px[x, y][3] > 0 for x in range(w)] for y in range(h)]
    dist = distance_inward(mask, w, h)

    # The dome. Normalised against a FIXED radius in pixels rather than against
    # the frame's own maximum: normalising per frame makes a thin arm as domed
    # as a torso, and the sprite then lights like a set of separate tubes.
    # sqrt() gives a hemisphere rather than a cone -- a cone has a constant
    # slope, which is exactly the uniform response being fixed.
    lum = [[0.0] * w for _ in range(h)]
    for y in range(h):
        for x in range(w):
            if mask[y][x]:
                r, g, b, _ = px[x, y]
                lum[y][x] = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255.0

    out = [[0.0] * w for _ in range(h)]
    for y in range(h):
        for x in range(w):
            if not mask[y][x]:
                continue
            dome = math.sqrt(min(1.0, dist[y][x] / max(1e-5, radius)))
            out[y][x] = bulge * dome + detail * lum[y][x]
    return out, mask


def normals_from_height(hgt, mask, w: int, h: int, strength: float):
    def at(x, y):
        x = min(w - 1, max(0, x))
        y = min(h - 1, max(0, y))
        return hgt[y][x]

    img = Image.new("RGB", (w, h), (128, 128, 255))
    out = img.load()
    for y in range(h):
        for x in range(w):
            if not mask[y][x]:
                continue  # flat outside, so a mip of the edge stays sane
            dx = (at(x + 1, y) - at(x - 1, y)) * 0.5
            dy = (at(x, y + 1) - at(x, y - 1)) * 0.5
            nx, ny, nz = -dx * strength, -dy * strength, 1.0
            inv = 1.0 / math.sqrt(nx * nx + ny * ny + nz * nz)
            nx, ny, nz = nx * inv, ny * inv, nz * inv
            out[x, y] = (
                int(round((nx * 0.5 + 0.5) * 255)),
                # GREEN IS +Y DOWN, matching the walls' generated maps. Get this
                # backwards and every sprite lights from the wrong vertical side
                # while looking perfectly plausible in isolation.
                int(round((-ny * 0.5 + 0.5) * 255)),
                int(round((nz * 0.5 + 0.5) * 255)),
            )
    return img


def write_all(lump: str, im: Image.Image, want_h: bool, dry: bool) -> int:
    n = 0
    for d in MAT_DIRS:
        if not d.is_dir():
            continue
        target = d / lump
        if dry:
            n += 1
            continue
        backup = target.with_suffix(target.suffix + BACKUP_SUFFIX)
        if not backup.exists():
            backup.write_bytes(target.read_bytes() if target.exists() else b"")
        im.save(target, "PNG", optimize=True)
        n += 1
    return n


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--codes", default="", help="comma-separated 4-letter codes")
    ap.add_argument("--all", action="store_true", help="every sprite in the WAD")
    ap.add_argument("--bulge", type=float, default=1.0,
                    help="weight of the silhouette dome (the body)")
    ap.add_argument("--detail", type=float, default=0.35,
                    help="weight of albedo-derived detail (folds, buckles)")
    ap.add_argument("--radius", type=float, default=10.0,
                    help="pixels from the outline at which the dome reaches full "
                         "height. FIXED, not per-frame: normalising per frame domes "
                         "a thin arm as hard as a torso.")
    ap.add_argument("--strength", type=float, default=2.2, help="normal steepness")
    ap.add_argument("--height", action="store_true", help="also write _h maps")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--revert", action="store_true")
    args = ap.parse_args()

    if args.revert:
        restored = removed = 0
        for d in MAT_DIRS:
            if not d.is_dir():
                continue
            for backup in d.glob(f"*.png{BACKUP_SUFFIX}"):
                target = backup.with_suffix("")
                if backup.stat().st_size == 0:
                    if target.exists():
                        target.unlink()
                        removed += 1
                else:
                    target.write_bytes(backup.read_bytes())
                    restored += 1
                backup.unlink()
        print(f"  restored {restored}, removed {removed} the bake had created")
        sys.exit(0)

    codes = {c.strip().upper() for c in args.codes.split(",") if c.strip()}
    if not codes and not args.all:
        ap.error("give --codes, or --all")

    frames = sprite_frames(codes or None)
    if not frames:
        sys.exit("no sprite frames matched")

    written = 0
    for lump, im in sorted(frames.items()):
        w, h = im.size
        hgt, mask = build_height(im, args.bulge, args.detail, args.radius)
        nrm = normals_from_height(hgt, mask, w, h, args.strength)
        written += write_all(f"{lump}_n.png", nrm, False, args.dry_run)
        if args.height:
            gray = Image.new("L", (w, h), 0)
            g = gray.load()
            for y in range(h):
                for x in range(w):
                    if mask[y][x]:
                        g[x, y] = int(round(min(1.0, hgt[y][x]) * 255))
            written += write_all(f"{lump}_h.png", gray.convert("RGB"), True, args.dry_run)

    verb = "would be written" if args.dry_run else "written"
    print(f"  {len(frames)} frame(s) -> {written} file(s) {verb} across {len(MAT_DIRS)} dirs")


if __name__ == "__main__":
    main()
