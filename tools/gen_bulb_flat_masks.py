"""Author the `_e` masks for the Doom 64 bulb-array textures.

Why this exists. `emissiveMult` with no `_e.png` on disk is not "a weaker glow"
-- RsWorld.inl falls back to `ldrEmis = ldrColor.rgb` when
`emissiveTextureIndex == MATERIAL_NO_TEXTURE`, so the ENTIRE albedo emits, tan
brick and all. That is what baked MAP07's ceiling panel into a white slab
(open-issues 1.6f). The masks for SFLATAS/SFLATAQ were deleted in e0fe5ef as
collateral in a generic SFLAT* blob cleanup, and 1.6f then removed the mult that
had been left dangling -- correct as far as it went, but it left the bulbs
emitting nothing at all.

The fix is the mask, not the absence of the mult. Run this, then
`set_bulb_emissive.py <mult>`.

SPACEAZ never had a mask in any commit, so its blobs are detected here from the
albedo with the same threshold the other two were authored with
(`_e_ceiling_blobs_from_albedo`, thresh 130) rather than recovered from git.

NOT SFLATAP: recessed grille, no bulbs in the art, no analytic fixture -- it
stays in `LAMP_FLAT_NO_EMIS`.

Writes <TEX>_e.png to all three trees the loader can read from:
    build/.../rt/mat        build/.../rt/mat_dev        Retribution-RT-Materials/rt/mat

Usage:
    python tools/gen_bulb_flat_masks.py
"""
from __future__ import annotations

import subprocess
import sys
from io import BytesIO
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gen_world_emissives import (  # noqa: E402
    MAT,
    MAT_DEV,
    OMAT,
    ROOT,
    WAD,
    _e_ceiling_blobs_from_albedo,
    resolve_albedo,
    wad_lumps,
)

# The commit that deleted the masks; its parent still has them.
PRE_DELETE = "e0fe5ef^"
GIT_MASK_PATH = "Doom64-Retribution/Retribution-RT-Materials/rt/mat/{}_e.png"

# Recovered from git where an authored mask existed, generated from the albedo
# where it never did.
RECOVER = ("SFLATAS", "SFLATAQ")
GENERATE = ("SPACEAZ",)


def from_git(name: str) -> Image.Image | None:
    try:
        blob = subprocess.run(
            ["git", "show", f"{PRE_DELETE}:{GIT_MASK_PATH.format(name)}"],
            cwd=ROOT,
            capture_output=True,
            check=True,
        ).stdout
    except subprocess.CalledProcessError:
        return None
    return Image.open(BytesIO(blob)).convert("RGBA")


def _bulb_lattice_mask(img: Image.Image, period: int = 16, radius: float = 4.5) -> Image.Image:
    """Per-tile local-max mask for bulb grids the art does not paint bright.

    `_e_ceiling_blobs_from_albedo`'s absolute threshold (130) works on
    SFLATAS/SFLATAQ because those bulbs are near-white. SPACEAZ's are dull grey
    -- peak luma 184, most of the socket at 128, on brick that runs 96-136. An
    absolute cut at that level selects brick speckle and misses the bulbs
    entirely (verified: 3.1% of pixels lit, none of them on a socket).

    So work per lattice tile and relative to that tile's own peak. Doom flats and
    walls are anchored at the world origin and SPACEAZ's grid is 4x4 over 64px,
    i.e. one bulb per 16-unit tile.

    Painted at full white, deliberately not sampled from the albedo: the shader
    already multiplies emission by baseColor, so an albedo-sampled mask squares
    it and the dull sockets would stay dull.
    """
    w, h = img.size
    ip = img.convert("RGBA").load()
    out = Image.new("RGBA", img.size, (0, 0, 0, 0))
    op = out.load()

    for ty in range(0, h, period):
        for tx in range(0, w, period):
            cells = [
                (x, y, max(ip[x, y][:3]))
                for y in range(ty, min(ty + period, h))
                for x in range(tx, min(tx + period, w))
                if ip[x, y][3] >= 40
            ]
            if not cells:
                continue
            peak = max(c[2] for c in cells)
            cut = peak * 0.68
            hot = [(x, y) for x, y, v in cells if v >= cut]
            if not hot:
                continue
            # Centroid of the hot set, so the disc follows the socket rather than
            # the tile's geometric middle.
            cx = sum(x for x, _ in hot) / len(hot)
            cy = sum(y for _, y in hot) / len(hot)
            for x, y in hot:
                if (x - cx) ** 2 + (y - cy) ** 2 <= radius * radius:
                    op[x, y] = (255, 255, 255, 255)
    return out


def from_albedo(name: str, lumps: dict[str, bytes]) -> Image.Image | None:
    img = resolve_albedo(lumps, name)
    if img is None:
        return None
    return _bulb_lattice_mask(img.convert("RGBA"))


def despeckle(mask: Image.Image, min_area: int = 12) -> tuple[Image.Image, int]:
    """Drop lit components too small to be a bulb.

    The authored SFLATAS/SFLATAQ masks carry a scatter of single stray brick
    pixels that the absolute threshold picked up. At the mult they shipped with
    (3) those were invisible; at 30 every speck is its own emitter smeared across
    the brick, which is a diffuse version of the whole-albedo bug. Wrapping is
    intentional -- flats tile, so a blob crossing the edge is one blob.
    """
    w, h = mask.size
    px = mask.load()
    lit = [[px[x, y][3] >= 40 and max(px[x, y][:3]) > 0 for x in range(w)] for y in range(h)]
    seen = [[False] * w for _ in range(h)]
    removed = 0
    for y0 in range(h):
        for x0 in range(w):
            if not lit[y0][x0] or seen[y0][x0]:
                continue
            stack = [(x0, y0)]
            seen[y0][x0] = True
            comp = []
            while stack:
                x, y = stack.pop()
                comp.append((x, y))
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nx, ny = (x + dx) % w, (y + dy) % h
                    if lit[ny][nx] and not seen[ny][nx]:
                        seen[ny][nx] = True
                        stack.append((nx, ny))
            if len(comp) < min_area:
                for x, y in comp:
                    px[x, y] = (0, 0, 0, 0)
                removed += len(comp)
    return mask, removed


def lit_stats(mask: Image.Image) -> tuple[int, int]:
    """(lit pixels, peak channel) -- a mask that lights everything is the bug."""
    px = mask.load()
    w, h = mask.size
    lit = 0
    peak = 0
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a >= 40 and max(r, g, b) > 0:
                lit += 1
                peak = max(peak, r, g, b)
    return lit, peak


def main() -> int:
    lumps = wad_lumps(WAD)
    out_dirs = [d for d in (MAT, MAT_DEV, OMAT) if d.exists()]
    if not out_dirs:
        print("ERROR: no material output dir found -- build gzdoom first")
        return 1

    rc = 0
    for name in RECOVER + GENERATE:
        mask = from_git(name) if name in RECOVER else from_albedo(name, lumps)
        if mask is None:
            print(f"  {name:10} FAILED to obtain a mask")
            rc = 1
            continue

        mask, specks = despeckle(mask)
        lit, peak = lit_stats(mask)
        total = mask.size[0] * mask.size[1]
        frac = lit / total
        # A blob mask that covers most of the texture is indistinguishable from
        # having no mask at all -- which is the exact failure this file exists to
        # prevent, so refuse to write it rather than ship a subtler version of it.
        if frac > 0.35:
            print(f"  {name:10} REFUSED: {frac:.0%} of pixels lit -- not a blob mask")
            rc = 1
            continue

        for d in out_dirs:
            mask.save(d / f"{name}_e.png")
        src = "git" if name in RECOVER else "albedo"
        print(f"  {name:10} {mask.size[0]}x{mask.size[1]} from {src}: "
              f"{lit} lit px ({frac:.1%}), peak {peak}, {specks} speck px dropped "
              f"-> {len(out_dirs)} dirs")

    print("\nnow run: python tools/set_bulb_emissive.py <mult>")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
