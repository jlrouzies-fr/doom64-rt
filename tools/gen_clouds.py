"""
Build the storm sky: a sliced volumetric cloud deck and four lightning bolts.

Why this exists
---------------
MAP11 ("Terror Core") is the game's one storm level. It is authored as three
separate pieces that only add up in the original renderer:

  * MAPINFO gives it the Hexen `lightning` keyword, so the engine's
    DLightningThinker flashes every F_SKY1 sector and plays `world/thunder`;
  * `script 670 OPEN` scrolls a two-layer CLOUDPRP *skybox room* (sectors with
    id 1 and 2, at the far corner of the map) at 4/4 and 15/15 for parallax;
  * `script 671 LIGHTNING` brightens those two skybox sectors 180 -> 255 -> 180
    on every strike.

Under RT the middle piece is gone: sector skybox rooms are ignored (the
white/black box bug -- see hw_walls.cpp and the d64r-rt-sky ZSCRIPT), and
rt_sky_always fills every F_SKY1 opening with the flat night sky instead. So the
map's clouds never render and the parallax scroll animates a room nobody sees.

Volumetric, and why it is *slices*
----------------------------------
The clouds are a real 3D density field, generated here and stored as NSLICES
horizontal cuts through it. The engine draws each slice on its own horizontal
disc at its own altitude (RT_DrawCloudDeck, hw_skyportal.cpp), so the stack you
look up at is a genuine volume: the slices parallax against each other as you
walk, they occlude each other correctly, and the deck converges on the horizon
with real perspective.

This replaced a pair of textures scrolled around the sky *dome*, which is the
one thing a cloud layer must not do. A dome layer rotates about the viewer, so
the clouds visibly orbit -- they come round again, and every cloud moves in a
circle no matter where you stand. A horizontal deck has neither problem: the
texture translates along a fixed wind vector, so cloud motion is linear and
unbounded, and perspective makes distant clouds crowd toward the horizon by
itself.

Slices are horizontal cuts, so the field only has to be tileable in X and Y --
never in Z, which is the cloud's own vertical axis and has hard limits (clear
air below the base, clear air above the tops).

Lighting is baked
-----------------
The engine draws these with a fixed textured shader -- RTGL1 rasterises sky
geometry into a cubemap with RsSky.frag, so no gzdoom material shader runs on
the sky and there is nowhere to compute lighting at draw time. So it is done
here, once: transmittance from the top down through the density field
(Beer-Lambert), which is a single-scattering approximation of moonlight
arriving from above. That is what gives the deck lit tops and dark undersides,
and it is most of what makes a stack of flat discs read as cloud rather than as
a stack of flat discs.

The engine still ramps brightness per shell on top of this (rt_clouds_dark) and
lights the stack from BELOW during a lightning strike, which is the one lighting
direction that cannot be baked because it does not exist most of the time.

Dependencies
------------
numpy, for the 3D noise. The only generator in tools/ that needs it, so run it
with the venv rather than the bare 3.13 that the Pillow-only scripts use:

  tools\.venv-ai\Scripts\python.exe tools/gen_clouds.py
  tools\.venv-ai\Scripts\python.exe tools/gen_clouds.py --preview

`--preview` also writes CLOUDV_preview.png, a contact sheet of every slice over
a dark backdrop, and BOLTS_preview.png. Neither is packed -- see pack_rt_sky.py.

Then repack: python tools/pack_rt_sky.py
"""

from __future__ import annotations

import argparse
import random
from pathlib import Path

import numpy as np
from PIL import Image

OUT_DIR = Path(r"G:\AI\Doom64-RT\tools\d64r-rt-sky\textures")

# Slice resolution.
#
# 1024, not 512. The deck stretches one tile across a large solid angle near the
# zenith -- that is MAGNIFICATION, not minification, so the usual "the far tiles
# compress to nothing anyway" argument does not apply where the player actually
# looks. 512 read as soft and low-detail overhead.
#
# (The other half of that fix is in the engine: these slices are uploaded with an
# explicit RG_SAMPLER_FILTER_LINEAR, because rt_smoothtextures is off globally --
# correct for 64x64 Doom wall art, badly wrong for a magnified cloud, where
# NEAREST turns a soft edge into visible square blocks.)
RES = 1024

# Number of horizontal cuts through the volume. The engine picks how many of
# these to actually draw (rt_clouds_shells) and spaces its picks evenly through
# the stack, so this is the ceiling on vertical detail, not the cost.
NSLICES = 8

# Bolts: full resolution with a soft halo, no pixel-art upscale.
BOLT_W, BOLT_H = 192, 384


def _smooth(t: np.ndarray) -> np.ndarray:
    return t * t * (3.0 - 2.0 * t)


# --------------------------------------------------------------------------
# tileable 3D value noise
# --------------------------------------------------------------------------
def _vnoise3(rng: np.random.Generator, nz: int, ny: int, nx: int,
             fz: int, fy: int, fx: int) -> np.ndarray:
    """Trilinear value noise on (nz, ny, nx), wrapping in Y and X only.

    Z deliberately does not wrap: it is the cloud's vertical axis, and a field
    that tiles vertically would put cloud tops directly under cloud bases.
    """
    lat = rng.random((fz + 1, fy, fx)).astype(np.float32)

    def axis(n: int, f: int, wrap: bool):
        s = np.linspace(0.0, f, n, endpoint=False, dtype=np.float32)
        i0 = np.floor(s).astype(np.int64)
        t = _smooth(s - i0)
        i1 = (i0 + 1) % f if wrap else np.minimum(i0 + 1, f)
        return (i0 % f if wrap else np.minimum(i0, f)), i1, t

    z0, z1, tz = axis(nz, fz, False)
    y0, y1, ty = axis(ny, fy, True)
    x0, x1, tx = axis(nx, fx, True)

    def g(zi, yi, xi):
        return lat[zi[:, None, None], yi[None, :, None], xi[None, None, :]]

    tzb, tyb, txb = tz[:, None, None], ty[None, :, None], tx[None, None, :]

    c00 = g(z0, y0, x0) * (1 - txb) + g(z0, y0, x1) * txb
    c01 = g(z0, y1, x0) * (1 - txb) + g(z0, y1, x1) * txb
    c10 = g(z1, y0, x0) * (1 - txb) + g(z1, y0, x1) * txb
    c11 = g(z1, y1, x0) * (1 - txb) + g(z1, y1, x1) * txb

    c0 = c00 * (1 - tyb) + c01 * tyb
    c1 = c10 * (1 - tyb) + c11 * tyb
    return c0 * (1 - tzb) + c1 * tzb


def _fbm3(rng: np.random.Generator, nz: int, ny: int, nx: int,
          fz: int, fy: int, fx: int, octaves: int) -> np.ndarray:
    acc = np.zeros((nz, ny, nx), dtype=np.float32)
    amp, total = 1.0, 0.0
    for _ in range(octaves):
        acc += _vnoise3(rng, nz, ny, nx, fz, fy, fx) * amp
        total += amp
        amp *= 0.5
        # X and Y double every octave. Z is capped at nz: there are only NSLICES
        # cuts, and detail finer than the slice spacing is invisible by
        # construction -- it would only add per-slice noise that does not
        # correspond to anything between the slices.
        fx, fy = fx * 2, fy * 2
        fz = min(fz * 2, nz)
    return acc / total


# --------------------------------------------------------------------------
# the cloud volume
# --------------------------------------------------------------------------
def _build_volume(seed: int, coverage: float, sharpness: float) -> np.ndarray:
    """Density in [0,1], shape (NSLICES, RES, RES). Index 0 is the cloud BASE."""
    rng = np.random.default_rng(seed)

    # fy/fx of 3 over 1024px, six octaves. The low base is deliberate: a cloud
    # deck seen from underneath is a small number of large objects, not a
    # texture, and starting higher gave wispy fog with no masses in it. The
    # octave count is what puts detail back on top of those masses.
    #
    # fz 3, not 2. This is the one that decides whether the stack reads as a
    # VOLUME. At 2, consecutive slices were near-identical silhouettes at
    # different scales, so the shells parallaxed into a blurry doubling of the
    # same shape rather than into structure -- the clouds had depth in the
    # geometry and none in the art. At 3 a mass genuinely changes outline as it
    # rises, which is what the eye reads as three-dimensional.
    n = _fbm3(rng, NSLICES, RES, RES, fz=3, fy=3, fx=3, octaves=6)

    # Vertical shape. h = 0 at the base, 1 at the top.
    #
    # The profile is what turns a 3D noise blob into something cloud-shaped: it
    # narrows the field with height, so a given cloud is widest at its base and
    # tapers to a smaller top. Every slice shares the same noise, so this taper
    # is the ONLY reason a mass looks like one object seen at eight heights
    # rather than eight unrelated sheets stacked up.
    #
    # Base-heavy, not centre-heavy. The first attempt ramped in over the bottom
    # 18% and peaked mid-stack, which put the widest cut in the MIDDLE of the
    # deck -- so the underside you actually look at was the thin end of the
    # cloud and the deck read as a flat grey slab with no bottom to it.
    h = (np.arange(NSLICES, dtype=np.float32) + 0.5) / NSLICES
    rise = np.clip(h / 0.06, 0.0, 1.0)              # base is full almost at once
    fall = np.clip((1.0 - h) / 0.85, 0.0, 1.0) ** 0.75
    shape = (rise * fall)[:, None, None]

    # Threshold by PERCENTILE, not by an absolute level.
    #
    # The textbook remap -- (n - thresh) / (1 - thresh) -- was tried first and
    # cannot work on this field. FBM's values cluster near 0.5 and essentially
    # never reach 1, so dividing by (1 - thresh) rescales a narrow band that
    # tops out well below full density: cloud interiors come out translucent
    # grey, the whole deck reads as haze, and turning `coverage` down to fix the
    # haze deletes the clouds instead of solidifying them. Both failure modes
    # are the same bug.
    #
    # A percentile says directly what is wanted -- "this fraction of the sky is
    # cloud" -- independently of how the noise happens to be distributed. The
    # soft edge then comes from smoothstep over a narrow band above it, which is
    # what gives solid middles AND feathered rims at the same time.
    lo, hi = np.quantile(n, 0.02), np.quantile(n, 0.98)
    n = np.clip((n - lo) / max(1e-4, hi - lo), 0.0, 1.0)

    base_t = float(np.quantile(n[0], 1.0 - coverage))
    # Higher slices get a higher threshold, so a mass shrinks with height. `edge`
    # is the width of the feathered rim in normalised-noise units.
    thresh = (base_t + (1.0 - base_t) * (1.0 - shape)).astype(np.float32)
    edge = 0.20

    t = np.clip((n - thresh) / edge, 0.0, 1.0)
    d = t * t * (3.0 - 2.0 * t)

    # Edge erosion. A second, much higher-frequency field carved out of the
    # first, remapping the low end so it bites hardest where the density is
    # already thin.
    #
    # This is what makes the silhouettes look like cloud instead of like
    # threshold contours. Grid-sampled value noise cannot be domain-warped (the
    # whole lattice is evaluated at once, there is nowhere to displace the
    # sample point), and without either warping or erosion a smoothstepped FBM
    # gives smooth blobby outlines that read as an oil slick. Erosion is the
    # version of that trick that works on a regular grid: the fringes end up
    # billowy and torn, the cores stay solid.
    er = _fbm3(rng, NSLICES, RES, RES, fz=3, fy=14, fx=14, octaves=3)
    lo2, hi2 = np.quantile(er, 0.05), np.quantile(er, 0.95)
    er = np.clip((er - lo2) / max(1e-4, hi2 - lo2), 0.0, 1.0)

    # Scaled by height: tops get torn apart, bases stay solid. Applying it evenly
    # was the first try and it ate the cloud BASE, which is the one cut the
    # player is directly underneath and the one that has to read as substantial.
    # It is also simply what clouds do -- the wispy end is the top.
    cut = er * 0.5 * (0.35 + 0.65 * h)[:, None, None]
    d = np.clip((d - cut) / np.maximum(1e-4, 1.0 - cut), 0.0, 1.0)

    return np.clip(d * sharpness, 0.0, 1.0).astype(np.float32)


def _light_volume(dens: np.ndarray, extinction: float, ambient: float) -> np.ndarray:
    """Beer-Lambert transmittance for light arriving from directly above.

    Slice index NSLICES-1 is the top and sees the sky unobstructed; each slice
    below it is dimmed by everything stacked over it. This is the single
    approximation that makes flat discs read as a volume, so it is worth being
    explicit about what it is NOT: no multiple scattering, no sun angle, and no
    horizontal transport. A cloud lit from the side would need the real thing.
    """
    above = np.cumsum(dens[::-1], axis=0)[::-1] - dens  # exclusive, from the top
    return (ambient + (1.0 - ambient) * np.exp(-extinction * above)).astype(np.float32)


def _slice_to_image(dens: np.ndarray, light: np.ndarray,
                    lit: tuple[int, int, int], shadow: tuple[int, int, int],
                    alpha_scale: float) -> Image.Image:
    lit_a = np.array(lit, dtype=np.float32)
    sh_a = np.array(shadow, dtype=np.float32)
    rgb = sh_a[None, None, :] + (lit_a - sh_a)[None, None, :] * light[:, :, None]

    out = np.empty((dens.shape[0], dens.shape[1], 4), dtype=np.uint8)
    out[..., :3] = np.clip(rgb, 0, 255).astype(np.uint8)
    out[..., 3] = np.clip(dens * alpha_scale * 255.0, 0, 255).astype(np.uint8)
    return Image.fromarray(out, "RGBA")


# --------------------------------------------------------------------------
# bolts
# --------------------------------------------------------------------------
def _make_bolt(seed: int) -> Image.Image:
    """One forked bolt: straight runs between jittered waypoints, soft halo.

    A per-pixel random walk was the obvious first try and it does not work --
    stepping x by a random amount every row produces a frayed rope, not a bolt,
    because real lightning is a chain of *straight* runs that change direction
    at a handful of kinks.

    Lateral drift is a FRACTION of each segment's own height rather than an
    absolute pixel budget. That distinction matters: with a fixed budget a short
    run -- a fork near the bottom, with little height left -- zigzags sideways
    across the whole texture instead of descending.
    """
    rng = random.Random(seed)
    w, h = BOLT_W, BOLT_H

    core = np.zeros((h, w), dtype=np.float32)

    def line(x0: int, y0: int, x1: int, y1: int) -> list[tuple[int, int]]:
        pts = []
        dx, dy = abs(x1 - x0), -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        while True:
            pts.append((x0, y0))
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy
        return pts

    def channel(x, y, y_end, segs, slant, depth) -> list[tuple[int, int]]:
        pts: list[tuple[int, int]] = []
        step = (y_end - y) / max(1, segs)
        for _ in range(segs):
            ny = min(h - 1.0, y + step * rng.uniform(0.75, 1.25))
            nx = min(w - 1.0, max(0.0, x + rng.uniform(-1.0, 1.0) * (ny - y) * slant))
            pts += line(int(x), int(y), int(nx), int(ny))
            x, y = nx, ny
            if y >= h - 1:
                break
            remaining = y_end - y
            # Fork at a kink, and only while there is enough height left below
            # for the branch to actually descend.
            if depth < 2 and remaining > h * 0.2 and rng.random() < 0.6:
                pts += channel(x, y, y + remaining * rng.uniform(0.4, 0.8),
                               rng.randint(2, 3), slant * 1.5, depth + 1)
        return pts

    # slant 0.6 keeps every segment within ~31 degrees of vertical: a bolt reads
    # as falling, not as wandering.
    for (x, y) in channel(rng.uniform(w * 0.3, w * 0.7), 0.0, float(h - 1),
                          rng.randint(5, 8), 0.6, 0):
        core[y, x] = 1.0

    # Halo by successive box blurs of the channel mask. Soft, unlike the rest of
    # the storm art used to be -- a lightning channel is the one thing in the
    # sky that genuinely is a bloom around a hot line.
    def blur(a: np.ndarray, r: int) -> np.ndarray:
        k = 2 * r + 1
        p = np.pad(a, r, mode="constant")
        c = np.cumsum(np.cumsum(p, axis=0), axis=1)
        c = np.pad(c, ((1, 0), (1, 0)), mode="constant")
        s = (c[k:, k:] - c[:-k, k:] - c[k:, :-k] + c[:-k, :-k])
        return s[: a.shape[0], : a.shape[1]] / (k * k)

    thick = np.clip(blur(core, 1) * 4.0, 0.0, 1.0)
    glow = np.clip(blur(core, 5) * 9.0, 0.0, 1.0)

    CORE = np.array([255, 255, 255], dtype=np.float32)
    GLOW = np.array([120, 160, 255], dtype=np.float32)

    rgb = GLOW[None, None, :] + (CORE - GLOW)[None, None, :] * thick[:, :, None]
    a = np.clip(thick + glow * 0.45, 0.0, 1.0)

    out = np.empty((h, w, 4), dtype=np.uint8)
    out[..., :3] = np.clip(rgb, 0, 255).astype(np.uint8)
    out[..., 3] = np.clip(a * 255.0, 0, 255).astype(np.uint8)
    return Image.fromarray(out, "RGBA")


# --------------------------------------------------------------------------
def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--preview", action="store_true",
                    help="also write *_preview.png contact sheets (never packed)")
    ap.add_argument("--seed", type=int, default=64)
    ap.add_argument("--coverage", type=float, default=0.46,
                    help="how much of the sky is cloud, 0..1. Above ~0.75 the deck "
                         "closes over and the moon never shows through.")
    ap.add_argument("--extinction", type=float, default=3.2,
                    help="how fast light is absorbed downward through the deck. "
                         "Higher = darker undersides, more contrast.")
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    dens = _build_volume(args.seed, coverage=args.coverage, sharpness=1.0)
    light = _light_volume(dens, extinction=args.extinction, ambient=0.10)

    # NEUTRAL, on purpose. The art carries shape and LUMINANCE; hue is the
    # engine's job (rt_clouds_tint, overridable per map in RT_CLOUD_PRESETS).
    #
    # These used to be baked cool-blue, and that was wrong the moment the deck
    # had to serve a map with a dark purple skybox: SetObjectColor is a
    # multiply, so tinting blue art purple gives a muddy grey-violet rather than
    # purple, and there is no tint that can undo a hue already in the texture.
    # Keeping the slices near-achromatic means any tint reproduces cleanly --
    # including the old blue, which is now just the default cvar value.
    LIT = (216, 220, 228)
    SHADOW = (32, 33, 40)

    written = []
    imgs = []
    for k in range(NSLICES):
        img = _slice_to_image(dens[k], light[k], LIT, SHADOW, alpha_scale=0.88)
        imgs.append(img)
        p = OUT_DIR / f"CLOUDV{k + 1}.png"
        img.save(p)
        written.append(p)

    bolts = []
    for i in range(1, 5):
        b = _make_bolt(args.seed * 31 + i)
        bolts.append(b)
        p = OUT_DIR / f"BOLT{i}.png"
        b.save(p)
        written.append(p)

    if args.preview:
        # Deliberately NOT packed: a copy under a resolvable name would be an
        # extra, wrong texture in the archive. Same rule as MOONSKY_preview.png.
        cols = 4
        rows = (NSLICES + cols - 1) // cols
        sheet = Image.new("RGBA", (cols * 256, rows * 256), (10, 10, 20, 255))
        for k, img in enumerate(imgs):
            sheet.alpha_composite(img.resize((256, 256), Image.LANCZOS),
                                  ((k % cols) * 256, (k // cols) * 256))
        sheet.save(OUT_DIR / "CLOUDV_preview.png")

        # And the stack composited top-down, which is what you actually look at.
        stack = Image.new("RGBA", (512, 512), (10, 10, 20, 255))
        for img in reversed(imgs):
            stack.alpha_composite(img)
        stack.save(OUT_DIR / "CLOUDSTACK_preview.png")

        bs = Image.new("RGBA", (4 * BOLT_W, BOLT_H), (10, 10, 20, 255))
        for i, b in enumerate(bolts):
            bs.alpha_composite(b, (i * BOLT_W, 0))
        bs.save(OUT_DIR / "BOLTS_preview.png")

    for p in written:
        print(f"wrote {p} ({p.stat().st_size} bytes)")
    print("now repack: python tools/pack_rt_sky.py")


if __name__ == "__main__":
    main()
