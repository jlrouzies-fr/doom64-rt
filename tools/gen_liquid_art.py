"""Liquid flats from reference art: blood (with relief + flow map), poison, sludge.

    tools\\.venv-ai\\Scripts\\python.exe tools/gen_liquid_art.py            # report + preview
    tools\\.venv-ai\\Scripts\\python.exe tools/gen_liquid_art.py --apply
    tools\\.venv-ai\\Scripts\\python.exe tools/gen_liquid_art.py --revert

    reads   screen/bloodtexture_coag.png    coagulated blood: dark plates, liquid veins
            screen/poison_texture.png       nukage: marbled swirl, bright rivers
            screen/sludge_texture.png       sludge: brown crust, rust-gold seams
    writes  Doom64-Retribution/d64r-liquid-art.wad
              TX_ patches D64BCOAG, D64NCOAG, D64SCOAG + one TEXTURES lump
              redefining all 384 D64B1_/B2_/N1_/N2_/S1_/S2_ frames
            <4 material dirs>/D64B{1,2}_{01..64}_{n,h,orm}.png   BLOOD ONLY
            screen/liquid_art_preview.png

Poison and sludge get the ART and nothing else: no relief, no flow. Their only
other change is engine-side -- rt_nukage_caustics / rt_sludge_caustics 0,
because an opaque fluid refracts nothing and so focuses nothing.

WHY THE ANIMATION HAS TO DIE FIRST.

Each of the 64 frames is a 64x64 composite of TWO offset copies of the patch,
the second at 50% alpha, with the offsets shifting one unit per frame (TEXTURES
lump in D64RTR_v15.WAD). That is the drift you see in the stock game. On the
stock art -- soft blobs -- the doubled copy reads as churn. On a crisp cell
mosaic it reads as a ghosted double image, and for blood it also makes a static
_n/_h impossible: the relief could only ever match ONE frame, which is exactly
why set_water_meta.py quarantined the frame-01-only overlays for every liquid.

So the TEXTURES lump redefines every frame as ONE unshifted copy of a single
patch. The ANIMDEFS sequence still runs and is simply invisible. The stylized
water shader's own wave shimmer still animates on top for poison; for blood the
motion is the flow map below.

WHAT THE BLOOD MAPS CARRY, AND THE ONE THAT IS NOT WHAT IT LOOKS LIKE.

  _n     relief from the height. Veins are channels, plates stand proud.
         RTGL reads .xy only and rebuilds z from the tangent frame.

  _h.r   HEIGHT, for parallax. sampleHeightMap() reads .r and nothing else.
  _h.g   flow DIRECTION x, in texture space, * 0.5 + 0.5      <-- NOT height
  _h.b   flow DIRECTION y                                       <-- see below

  _orm   occlusion / roughness / metallic. Inert on the surface itself (the
         stylized branch writes roughness explicitly) but it is what reflections
         OF the pool use. Safe to ship: water primitives get GEOM_INST_FLAG_REFRACT
         unconditionally (GeomInfoManager.cpp:151), so no roughness value can
         gate the stylized path off.

THE FLOW MAP, AND WHY IT IS A DIRECTION AND NOT A PHASE.

The first version baked a PHASE -- geodesic distance along the vein -- and slid
a brightness band along it. It was rejected on sight, and correctly: a band of
brightness moving along a static vein is still just brightness changing in
place. Nothing in the picture moves. The eye reads it as the bright parts
flickering.

What reads as flow is TEXTURE moving: a detail pattern advected along the
channel, so blobs of liquid physically slide down each vein. That is a flow map
(the Portal 2 water technique): bake the vein's tangent direction per texel,
and in the shader scroll a detail texture along it with a two-phase ping-pong
blend so the distortion never accumulates. The shader half lives in
HitInfo.inl (the advection, where the texcoords are) and RaygenPrimary.inl (the
modulation, where the liquid is shaded).

The direction is the vein's TANGENT from a structure tensor -- the eigenvector
of the smaller eigenvalue of the blurred gradient outer product, i.e. "along the
ridge" -- signed so that it points roughly along FLOW_DIR. One global downstream
direction, on purpose: the alternative (radiating out of source nodes) gives the
flow a different heading every few cells, and at pool-viewing distance that
reads as pulsing from points rather than as a pool drifting one way. Where a
vein runs perpendicular to FLOW_DIR the sign is ambiguous; the tensor's
coherence goes into the vector's LENGTH, so those texels and the cells bake to
~zero length and the shader treats them as still.

Stored as a vector, so bilinear filtering between two disagreeing texels shrinks
toward zero and the flow FADES there rather than snapping. Two properties of
the height slot make that safe, both checked rather than assumed: _h is loaded
LINEAR (TextureManager.cpp:1142 marks only albedo and emissive sRGB), and
sampleHeightMap uses LOD 0 -- no mips, so only bilinear ever happens.

THE TILE IS EXPOSED, AND THAT IS NOT A LOOK DECISION. The stylized shader's
vein mask is luminance / rt_water_veinref with veinref pinned at 0.1, and both
references are far brighter at the top end than the flats they replace (blood
p99 0.30 vs 0.095; poison p50 alone is 0.18). Shipped as drawn, two thirds of
the blood read as "vein" and the mask stopped picking out the network. The
tile is scaled so its VEIN_PCT percentile lands on VEIN_REF. Exposing the ART
rather than retuning rt_water_veinref keeps this per liquid; the stylized path
only ever uses this texture's LUMINANCE for the mask and takes its colour from
rt_*_tint / _crest, so only the shape survives either way.

TILING: MIN-CUT, NOT CROSS-FADE. Neither reference tiles. A feathered cross-fade
over the wrap seam ghosts every vein it crosses and leaves a visibly lighter
band. The seam is routed by a minimum-error boundary cut (image quilting),
which follows the dark interiors where the two sides agree.

SCALE. Crop to half, resample to 128 px, declare 128x128 with XScale/YScale 2.0
-> the tile is 64 MAP UNITS. Retribution's own TEXTURES already uses XScale 2.0
this way (see AZTEC02C).
"""

from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gen_lava_looks import blur, relief  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent

WAD = ROOT / "Doom64-Retribution/d64r-liquid-art.wad"
PREVIEW = ROOT / "screen/liquid_art_preview.png"

# mat_dev is NOT a scratch folder: TextureOverrides.cpp looks there too
# (TEXTURES_FOLDER_DEV) and rt/RTGL1.json sets developerMode, so mat_dev WINS.
# Four dirs or the change is a ghost.
MAT_DIRS = [
    ROOT / "Doom64-Retribution/Retribution-RT-Materials/rt/mat",
    ROOT / "Doom64-Retribution/Retribution-RT-Materials/rt/mat_dev",
    ROOT / "sourcecode/gzdoom-rt/build/RelWithDebInfo/rt/mat",
    ROOT / "sourcecode/gzdoom-rt/build/RelWithDebInfo/rt/mat_dev",
]

# One entry per liquid. New PATCH names on purpose: D64BLOD*/D64NUKG* stay live
# for the warp2 stills and the BFALL/SFALL wall sheets.
LIQUIDS = {
    "blood": dict(
        src=ROOT / "screen/bloodtexture_coag.png",
        patch="D64BCOAG",
        families=("D64B1_", "D64B2_"),
        relief=True,
        height_src="mask",      # the vein network IS the structure
        relief_strength=0.045,
        relief_depth=0.85,
        rough=(0.10, 0.55),     # wet vein / dried crust
        relief_hf=1.0,          # relief() already blurs the mask; nothing to shelve
        flow=True,
    ),
    "poison": dict(
        src=ROOT / "screen/poison_texture.png",
        patch="D64NCOAG",
        families=("D64N1_", "D64N2_"),
        relief=False,
    ),
    "sludge": dict(
        src=ROOT / "screen/sludge_texture.png",
        patch="D64SCOAG",
        families=("D64S1_", "D64S2_"),
        relief=True,
        # NOT the vein mask. Sludge's exposed art puts 90% of its texels above
        # the mask's clip point, so a mask-derived height is a flat plateau with
        # a few dents -- the opposite of what mud wants. Its structure is in the
        # full luminance range: lumps, rims, pits, all of it.
        height_src="luma",
        # Nearly twice blood's, and deliberately: depth IS the effect here.
        relief_strength=0.085,
        relief_depth=1.15,
        relief_smooth=1,        # barely: the fine speckle IS the texture...
        parallax_smooth=4,      # ...but NOT in the height map. See below.
        # ...and the top octave of it is turned down, because at full strength
        # it destabilised the lighting under a moving flashlight. Only the
        # RESIDUAL is scaled -- the lumps and rims stay at full depth.
        relief_hf=0.35,
        # Rough everywhere -- mud is not a mirror. Wetter in the pits, where
        # the water pools, than on the humps.
        rough=(0.55, 0.90),
        flow=False,
    ),
}
FRAMES = 64

TILE_PX = 128               # patch pixels...
TILE_SCALE = 2.0            # ...declared with XScale/YScale 2.0 -> 64 map units
CROP_FRAC = 0.5             # how much of the reference becomes one tile
SEAM_FRAC = 0.18            # width of the min-cut overlap band, as a fraction

VEIN_REF = 0.10             # matches rt_water_veinref: luminance that saturates the mask
VEIN_PCT = 98.0             # the tile is EXPOSED so this percentile lands on VEIN_REF

# relief_strength / relief_depth / rough now live per liquid in LIQUIDS: blood
# is a thin skin with channels cut in it, sludge is a thick lumpy bed, and one
# pair of numbers cannot be both.

HEIGHT_PCT = (2.0, 98.0)    # luma height source: percentiles the range stretches to

# The normal map's high-frequency BUDGET, as (laplacian RMS) / (relief strength).
#
# A normal that swings hard from texel to texel makes N.L swing hard for a tiny
# change in light direction, so a moving flashlight lands on a different answer
# every frame. The denoiser cannot accumulate that; it arrives as noise that
# reads as unstable shadows and then averages away the moment the player stops.
# Bisected to here: rt_heightmap_stren 0 changed nothing (not parallax),
# rt_upscale_dlss 0 changed nothing (not the upscaler), rt_normalmap_stren 0
# fixed it completely and 0.4 halved it -- so it is the normal map's amplitude.
#
# Blood shipped at 0.0200 / 0.045 = 0.444 and is stable under the same light.
# Anything above this warns; fix it with relief_hf, NOT by dropping
# relief_strength, which takes the depth away with the speckle.
HF_BUDGET = 0.45

FLOW_DIR = np.array([1.0, 1.0]) / np.sqrt(2.0)   # global downstream, image space
FLOW_TENSOR_RADIUS = 3      # structure-tensor window; ~ a vein width
FLOW_MASK_MIN = 0.20        # below this vein-mask value a texel carries no flow

SUFFIXES = ("_n.png", "_h.png", "_orm.png")


# --- tiling -------------------------------------------------------------------


def _min_cut_path(err: np.ndarray) -> np.ndarray:
    """Minimum-cost monotone cut through an (R, B) error field. Returns path[R]."""
    R, B = err.shape
    cost = err.astype(np.float64).copy()
    back = np.zeros((R, B), np.int32)
    for i in range(1, R):
        p = cost[i - 1]
        left = np.concatenate(([np.inf], p[:-1]))
        right = np.concatenate((p[1:], [np.inf]))
        stack = np.stack([left, p, right])
        k = np.argmin(stack, 0)
        back[i] = k - 1
        cost[i] += stack[k, np.arange(B)]
    path = np.zeros(R, np.int32)
    j = int(np.argmin(cost[-1]))
    for i in range(R - 1, -1, -1):
        path[i] = j
        j = int(min(max(j + back[i, j], 0), B - 1))
    return path


def _wrap_seam(img: np.ndarray, size: int, band: int, axis: int) -> np.ndarray:
    """Cut `img` down to `size` along `axis` so that it wraps without a seam.

    `img` must carry `band` extra samples: the ones that FOLLOW the tile, which
    are what the tile's own head has to continue from. The overlap is resolved
    by a minimum-error cut rather than a blend, so no vein is ever ghosted.
    """
    a = np.moveaxis(img, axis, 0)
    body = a[band : band + size].copy()
    tail = a[size : size + band]  # continues past the tile
    head = a[0:band]              # precedes it, i.e. what the tile wraps onto
    err = ((tail - head) ** 2).sum(-1)
    path = _min_cut_path(np.moveaxis(err, 0, 1))
    take_head = np.arange(band)[:, None] >= path[None, :]
    body[size - band :] = np.where(take_head[..., None], head, tail)
    return np.moveaxis(body, 0, axis)


def expose(tile: np.ndarray) -> np.ndarray:
    """Scale the tile so its vein network saturates at VEIN_REF, and no wider."""
    lum = 0.2126 * tile[..., 0] + 0.7152 * tile[..., 1] + 0.0722 * tile[..., 2]
    ref = float(np.percentile(lum, VEIN_PCT))
    return np.clip(tile * (VEIN_REF / max(ref, 1e-6)), 0.0, 1.0)


def build_tile(src: Path) -> np.ndarray:
    """The reference, cropped, made to wrap, resampled to TILE_PX and exposed."""
    if not src.exists():
        raise SystemExit(f"ERROR: reference art not found: {src}")
    a = np.asarray(Image.open(src).convert("RGB"), np.float32) / 255.0
    n = min(a.shape[0], a.shape[1])
    size = int(n * CROP_FRAC)
    band = int(size * SEAM_FRAC)
    off = (n - (size + band)) // 2
    reg = a[off : off + size + band, off : off + size + band]

    t = _wrap_seam(reg, size, band, 0)
    t = _wrap_seam(t, size, band, 1)

    small = Image.fromarray((np.clip(t, 0, 1) * 255).astype(np.uint8))
    small = small.resize((TILE_PX, TILE_PX), Image.LANCZOS)
    return expose(np.asarray(small, np.float32) / 255.0)


# --- the vein network ---------------------------------------------------------


def vein_mask(tile: np.ndarray) -> np.ndarray:
    """0..1 mask of the liquid veins, normalised the way the shader will.

    getStylizedWaterAlbedo builds its mask as luminance / stylizedWaterVeinRef,
    so the mask baked here has to use the same reference or the relief and the
    caustic veins land on different pixels.
    """
    lum = 0.2126 * tile[..., 0] + 0.7152 * tile[..., 1] + 0.0722 * tile[..., 2]
    return np.clip(lum / VEIN_REF, 0.0, 1.0)


def _wrap_gradient(a: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Central differences that WRAP, because the flat tiles."""
    gx = (np.roll(a, -1, 1) - np.roll(a, 1, 1)) * 0.5
    gy = (np.roll(a, -1, 0) - np.roll(a, 1, 0)) * 0.5
    return gx, gy


def flow_field(mask: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Per-texel flow direction along the veins, as (dir[y,x,2], coherence).

    Structure tensor of the blurred mask. Its dominant eigenvector is the
    gradient direction -- ACROSS the vein -- so the tangent is that rotated 90
    degrees. The tensor is orientation-only (theta and theta+180 are the same
    ridge), and the sign is chosen to agree with FLOW_DIR. Coherence is 1 for a
    clean line and 0 where the neighbourhood is isotropic (a junction, a blob,
    a cell interior); it scales the vector's length so those texels fade to
    still instead of pointing somewhere random.
    """
    g = blur(mask, 1, passes=2)
    gx, gy = _wrap_gradient(g)
    jxx = blur(gx * gx, FLOW_TENSOR_RADIUS, passes=2)
    jyy = blur(gy * gy, FLOW_TENSOR_RADIUS, passes=2)
    jxy = blur(gx * gy, FLOW_TENSOR_RADIUS, passes=2)

    theta = 0.5 * np.arctan2(2.0 * jxy, jxx - jyy)      # gradient orientation
    tx, ty = -np.sin(theta), np.cos(theta)               # tangent: +90 degrees
    sign = np.where(tx * FLOW_DIR[0] + ty * FLOW_DIR[1] < 0.0, -1.0, 1.0)
    tx, ty = tx * sign, ty * sign

    trace = jxx + jyy
    coherence = np.sqrt((jxx - jyy) ** 2 + 4.0 * jxy * jxy) / (trace + 1e-7)
    coherence = np.where(trace > 1e-6, coherence, 0.0)
    # only where the texel IS a vein -- direction over a cell is meaningless
    strength = np.clip(coherence, 0, 1) * np.clip((mask - FLOW_MASK_MIN) / 0.3, 0, 1)
    # a little smoothing so the sign flip along a perpendicular vein is a fade
    # over a few texels rather than a wall
    dx = blur(tx * strength, 1, passes=1)
    dy = blur(ty * strength, 1, passes=1)
    return np.stack([dx, dy], -1), strength


# --- the maps -----------------------------------------------------------------


def luma_height(tile: np.ndarray) -> np.ndarray:
    """Height straight from the tile's own luminance, range-stretched.

    For an art style whose structure is CONTINUOUS -- mud: lumps, rims, pits,
    all of it -- rather than a binary network of channels cut into plates. The
    vein mask cannot serve here: expose() puts sludge's p98 on the mask's clip
    point, so 90% of the tile saturates and a mask-derived height is a plateau.

    Bright is high. These references are painted with implied top-light, so
    luminance IS the photometric height approximation, and the alternative --
    reading the dark lumps as high -- turns every raised rim into a trench.
    """
    lum = 0.2126 * tile[..., 0] + 0.7152 * tile[..., 1] + 0.0722 * tile[..., 2]
    lo, hi = (float(np.percentile(lum, q)) for q in HEIGHT_PCT)
    return np.clip((lum - lo) / max(hi - lo, 1e-6), 0.0, 1.0)


def hf_shelf(h: np.ndarray, gain: float, radius: int = 3) -> np.ndarray:
    """Attenuate only the TOP octave of a height field, keeping the shape.

    A blanket blur (or turning rt_normalmap_stren down) removes the lumps and
    rims along with the speckle, and the lumps are the depth. What actually
    destabilises the lighting is the highest frequency alone: a normal that
    swings hard from texel to texel makes N.L swing hard for a tiny change in
    light direction, so a moving flashlight produces a different answer every
    frame. The denoiser cannot accumulate that, and it arrives as noise that
    reads as unstable shadows -- then averages away the moment you stand still.

    So split the field, keep the low band at FULL strength, and scale only the
    residual. Measured as the RMS of the wrapping laplacian (gen_liquid_art
    prints it), blood sits at 0.0200 per 0.045 of relief strength and is
    known-stable; that ratio is the budget.
    """
    if gain >= 1.0:
        return h
    low = blur(h, radius, passes=2)
    return low + (h - low) * gain


def relief_from_height(h: np.ndarray, strength: float, depth: float, smooth: int):
    """gen_lava_looks.relief(), but from a height that is already built.

    Two differences from the mask version, both of which matter here:

    WRAPPING gradient. np.gradient does not wrap, which leaves a ridge down the
    tile seam -- invisible at blood's 0.045, not at sludge's 0.085.

    Far less blur. relief() smooths at radius 2 twice because it is fed a
    CLIPPED MASK, which is effectively binary and would otherwise give stepped
    normals. A luminance height is already a continuous image, and the same
    blur throws away exactly the fine crust speckle that is the point of using
    it -- the surface comes back as soft rolling humps with no texture on them.
    """
    hh = blur(h, smooth, passes=1) ** (1.0 / max(depth, 0.05)) if smooth > 0 else h ** (
        1.0 / max(depth, 0.05)
    )
    gx, gy = _wrap_gradient(hh)
    return hh, -gx * strength * 64.0, -gy * strength * 64.0


def build_maps(tile: np.ndarray, liq: dict):
    """(_n, _h, _orm) as uint8 arrays, plus the intermediates for the preview."""
    mask = vein_mask(tile)

    if liq["height_src"] == "luma":
        base = luma_height(tile)
        height, nx, ny = relief_from_height(
            hf_shelf(base, liq["relief_hf"]),
            liq["relief_strength"],
            liq["relief_depth"],
            liq["relief_smooth"],
        )
        # THE FINE DETAIL GOES IN THE NORMAL MAP AND NOWHERE ELSE.
        #
        # The two maps are sampled by completely different machinery:
        #
        #   _n  getTextureSampleGrad(normalTexture, uv, dTdx, dTdy)  -- ray-cone
        #       derivatives, so it picks a MIP and filters. Stable at any range.
        #   _h  textureLod(heightTexture, uv, 0)                     -- LOD 0.
        #       Always. No mips, no derivatives, and parallaxTexCoords marches
        #       it ten times plus four binary-search steps.
        #
        # So high-frequency content in the HEIGHT map is sampled unfiltered at
        # full resolution however far away the surface is: once a screen pixel
        # covers more than a texel, each pixel's march lands on uncorrelated
        # texels and the parallax offset becomes per-pixel noise. In motion that
        # flickers as unstable pseudo-shadows; standing still, the upscaler's
        # jittered accumulation averages it back to flat. Which is exactly the
        # bug this caused -- shadows under the flashlight that appear when you
        # walk and vanish when you stop.
        #
        # Blood never showed it because relief() blurs its mask at radius 2
        # twice, leaving almost no high frequency to alias.
        #
        # Hence: the normal map keeps every bit of crust speckle, and the height
        # map carries ONLY what parallax can actually resolve -- the big lumps
        # and hollows.
        parallax = blur(base, liq["parallax_smooth"], passes=2) ** (
            1.0 / max(liq["relief_depth"], 0.05)
        )
        # wetness drives roughness: the PITS hold the water, the humps drain
        wet = 1.0 - height
    else:
        height, nx, ny = relief(mask, liq["relief_strength"], liq["relief_depth"])
        parallax = height   # already blurred at radius 2 twice by relief()
        wet = mask          # the veins are the liquid

    inv = 1.0 / np.sqrt(nx * nx + ny * ny + 1.0)
    nrm = np.stack([nx * inv, ny * inv, inv], -1)
    n_img = np.clip(nrm * 0.5 + 0.5, 0, 1)

    if liq["flow"]:
        flow, strength = flow_field(mask)
    else:
        # a zero vector is "no flow here", and 0.5/0.5 is how the shader reads
        # it. Baked flat rather than left to stylizedLiquidFlow[id] == 0, so
        # HitInfo.inl's advection is dead at the SOURCE for this liquid.
        flow = np.zeros(mask.shape + (2,), np.float32)
        strength = np.zeros_like(mask)

    h_img = np.stack(
        [np.clip(parallax, 0, 1), flow[..., 0] * 0.5 + 0.5, flow[..., 1] * 0.5 + 0.5], -1
    )

    occl = np.clip(blur(height, 3, passes=2) * 0.55 + 0.45, 0, 1)
    r_wet, r_dry = liq["rough"]
    rough = r_dry + (r_wet - r_dry) * wet
    orm_img = np.stack([occl, np.clip(rough, 0, 1), np.zeros_like(rough)], -1)

    def u8(a):
        return (np.clip(a, 0, 1) * 255.0 + 0.5).astype(np.uint8)

    return (
        u8(n_img), u8(h_img), u8(orm_img),
        dict(mask=mask, height=height, parallax=parallax, flow=flow, strength=strength),
    )


# --- output -------------------------------------------------------------------


def png_bytes(im: Image.Image) -> bytes:
    import io

    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


def write_wad(items) -> bytes:
    body, directory, offset = b"", b"", 12
    for name, data in items:
        directory += struct.pack(
            "<II8s", offset, len(data), name.encode("ascii")[:8].ljust(8, b"\0")
        )
        body += data
        offset += len(data)
    return struct.pack("<4sII", b"PWAD", len(items), 12 + len(body)) + body + directory


def textures_lump() -> bytes:
    """Every frame of every family as ONE unshifted copy of its patch.

    No second layer and no Alpha: the stock definition composites two offset
    copies at 50%, and that per-frame shift is precisely what makes authored
    relief impossible and turns a crisp mosaic into a double image.
    """
    out = [
        "// d64r-liquid-art: blood, poison and sludge flats from reference art.",
        "// Every frame is the same image -- see tools/gen_liquid_art.py for why.",
        "",
    ]
    for liq in LIQUIDS.values():
        for fam in liq["families"]:
            for i in range(1, FRAMES + 1):
                out.append(f"Texture {fam}{i:02d}, {TILE_PX}, {TILE_PX}")
                out.append("{")
                out.append(f"\tXScale {TILE_SCALE}")
                out.append(f"\tYScale {TILE_SCALE}")
                out.append(f"\tPatch {liq['patch']}, 0, 0")
                out.append("}")
    return ("\n".join(out) + "\n").encode("ascii")


def frame_names(liq: dict) -> list[str]:
    return [f"{fam}{i:02d}" for fam in liq["families"] for i in range(1, FRAMES + 1)]


def deploy(liq: dict, n_u8, h_u8, orm_u8) -> int:
    blobs = {
        "_n.png": png_bytes(Image.fromarray(n_u8, "RGB")),
        "_h.png": png_bytes(Image.fromarray(h_u8, "RGB")),
        "_orm.png": png_bytes(Image.fromarray(orm_u8, "RGB")),
    }
    written = 0
    for d in MAT_DIRS:
        if not d.exists():
            print(f"  skip (missing): {d}")
            continue
        for name in frame_names(liq):
            for suf, data in blobs.items():
                (d / (name + suf)).write_bytes(data)
                written += 1
    return written


def revert() -> None:
    removed = 0
    for d in MAT_DIRS:
        if not d.exists():
            continue
        for liq in LIQUIDS.values():
            for name in frame_names(liq):
                for suf in SUFFIXES:
                    p = d / (name + suf)
                    if p.exists():
                        p.unlink()
                        removed += 1
    print(f"  removed {removed} material file(s)")
    for old in (WAD, ROOT / "Doom64-Retribution/d64r-blood-coag.wad"):
        if old.exists():
            old.unlink()
            print(f"  removed {old}")
    print("  NOTE: the stock overlays are still in the *_quarantine_water dirs;")
    print("        run tools/set_water_meta.py --revert if you want them back.")


def write_preview(rows) -> None:
    """One row per liquid: tile 2x2 (so the wrap shows), then height / normal / flow."""

    def cell(a):
        return Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8)).resize(
            (256, 256), Image.NEAREST
        )

    sheet = Image.new("RGB", (256 * 5, 256 * len(rows)))
    for r, (tile, dbg) in enumerate(rows):
        cells = [cell(np.tile(tile, (2, 2, 1)))]
        if dbg is not None:
            flow = dbg["flow"]
            cells += [
                cell(np.repeat(dbg["height"][..., None], 3, -1)),
                cell(np.repeat(dbg["parallax"][..., None], 3, -1)),
                cell(np.stack([flow[..., 0] * 0.5 + 0.5, flow[..., 1] * 0.5 + 0.5,
                               dbg["strength"]], -1)),
                cell(np.repeat(dbg["mask"][..., None], 3, -1)),
            ]
        for i, c in enumerate(cells):
            sheet.paste(c, (256 * i, 256 * r))
    PREVIEW.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(PREVIEW)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--revert", action="store_true")
    args = ap.parse_args()

    if args.revert:
        revert()
        return

    print(f"tile        {TILE_PX}x{TILE_PX} px, XScale {TILE_SCALE} -> "
          f"{int(TILE_PX / TILE_SCALE)} map units")

    built = {}
    rows = []
    for name, liq in LIQUIDS.items():
        tile = build_tile(liq["src"])
        mask = vein_mask(tile)
        print(f"{name:8}    vein mask {float((mask > 0.25).mean()) * 100:.1f}% of texels "
              f"above 0.25, mean {mask.mean():.3f}")
        maps = dbg = None
        if liq["relief"]:
            n_u8, h_u8, orm_u8, dbg = build_maps(tile, liq)
            maps = (n_u8, h_u8, orm_u8)
            h, px = dbg["height"], dbg["parallax"]
            def _hf(a):
                """RMS of the wrapping laplacian: how much high frequency is in
                a map. The height map's must stay LOW -- it is sampled at LOD 0."""
                lap = 4 * a - sum(np.roll(a, s, ax) for ax in (0, 1) for s in (-1, 1))
                return float(np.sqrt((lap ** 2).mean()))
            print(f"            height p10 {np.percentile(h, 10):.2f} "
                  f"p90 {np.percentile(h, 90):.2f} (src {liq['height_src']}), "
                  f"relief strength {liq['relief_strength']}")
            hf_n = _hf(h)
            ratio = hf_n / max(liq["relief_strength"], 1e-6)
            print(f"            high-freq: normal src {hf_n:.4f}, "
                  f"PARALLAX map {_hf(px):.4f} (must stay low: _h is LOD 0)")
            flag = "OVER BUDGET" if ratio > HF_BUDGET else "ok"
            print(f"            hf/strength {ratio:.3f} vs budget {HF_BUDGET} -- {flag}")
            if ratio > HF_BUDGET:
                print(f"            !! {name}'s normal map will destabilise the "
                      f"lighting under a moving light.")
                print(f"            !! Lower relief_hf (currently "
                      f"{liq['relief_hf']}), not relief_strength.")
            if liq["flow"]:
                flowing = float((dbg["strength"] > 0.2).mean())
                print(f"            flow on {flowing * 100:.1f}% of texels, "
                      f"downstream ({FLOW_DIR[0]:.2f}, {FLOW_DIR[1]:.2f}) in texture space")
        built[name] = (tile, maps)
        rows.append((tile, dbg))

    write_preview(rows)
    print(f"preview     {PREVIEW}")

    if not args.apply:
        print("\n(report only -- pass --apply to write the wad and the materials)")
        return

    lumps = [("TX_START", b"")]
    for name, liq in LIQUIDS.items():
        tile = built[name][0]
        lumps.append((liq["patch"],
                      png_bytes(Image.fromarray((np.clip(tile, 0, 1) * 255).astype(np.uint8), "RGB"))))
    lumps += [("TX_END", b""), ("TEXTURES", textures_lump())]
    WAD.write_bytes(write_wad(lumps))
    print(f"\nwrote       {WAD}  ({WAD.stat().st_size / 1024:.0f} KB)")

    # the old single-liquid wad must not stay on disk: the launcher would still
    # find it, and two TEXTURES lumps defining the same frames is a coin toss
    old = ROOT / "Doom64-Retribution/d64r-blood-coag.wad"
    if old.exists():
        old.unlink()
        print(f"removed     {old} (superseded)")

    for name, liq in LIQUIDS.items():
        if built[name][1] is None:
            continue
        n = deploy(liq, *built[name][1])
        print(f"wrote       {n} {name} material file(s) across "
              f"{sum(1 for d in MAT_DIRS if d.exists())} dir(s)")


if __name__ == "__main__":
    main()
