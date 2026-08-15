"""
Build MOONSKY: Retribution's night sky with an actual moon in it.

Why this exists
---------------
MAP13's west and north halls were lit by *painted* light shafts -- wedge sectors
at lightlevel 255 inside rooms at 170/180, identical to those rooms in every
other respect, fanning out of real F_SKY1 windows. Under RT that stopped being
paint: rt_sector_emis turns any sector over the per-map threshold into a surface
emitter, so the wedges radiated from both floor and ceiling with nothing casting
them (screen/level13fakeoutside light streaks.png). They read as moonlight from a
moon that did not exist.

tools/make_seqlight_fix.py drops the wedges to their host rooms' lightlevel. That
alone would leave the halls with windows and no light through them, so the other
half of the repair is to make the moon real: a visible disc in the sky, and a
directional light (rt_sun_*) coming from the same bearing, which casts genuine
shafts through the genuine windows.

Two things about the RT sky make this work at all:

- Under RT the sky is `RG_SKY_TYPE_RASTERIZED_GEOMETRY`: gzdoom rasterises the
  sky dome into a cubemap that RTGL1 then samples by ray direction. So whatever
  is painted here is a real environment map, not a backdrop.
- It is *not*, however, importance-sampled. A bright disc in the cubemap is only
  found by rays that happen to point at it, which at 1 spp is far too noisy to
  light a room. Hence the analytic directional light alongside it: the disc is
  what you see, rt_sun_* is what casts the shafts. They have to agree, and
  keeping them agreeing is what --azimuth is for.

Why 1024 wide
-------------
hw_skydome.cpp picks `xscale = texw < 1024 ? floor(1024 / texw) : 1`. The WAD's
SPACE flat is 256 wide, so today's sky is tiled **four times** around the
horizon. Painting a moon into a 256-wide texture would put four moons in the sky.

So MOONSKY is exactly four copies of SPACE side by side -- 1024x128, xscale 1,
one wrap -- which is pixel-for-pixel the starfield already on screen, with a
single moon painted over one of the copies. Height stays 128 so the `texh <= 128
&& tiled` branch of SetupMatrices still applies and the vertical mapping is
unchanged too. The only difference from the current sky is the moon.

Where the moon goes
-------------------
Horizontal, from SkyVertexDoom + SetupMatrices: a dome column at texture u sits
at world azimuth `-360 * u` degrees, so `u = -azimuth / 360` (mod 1). That is a
derivation off the vertex/matrix code, not something measured in game, and the
one thing it can plausibly get wrong is the *sign* -- the dome mirrors in x and
negates u, and two sign errors would cancel.

That only matters with --bake-disc now. The shipping moon is MOONDISC, drawn as
GEOMETRY along the rt_sun direction (RT_DrawMoonQuad, hw_skyportal.cpp), so it is
placed by the light itself: no texture column to derive, no sign to settle, and
no altitude ceiling from the sky dome's 60 degrees.

Vertical is cruder still. The dome spans +/-60 degrees of altitude over the
texture's height, but SetupMatrices then translates and scales v by
skyoffsetfactor and 240/texh for short tiled textures. `--altitude` uses the
plain dome mapping (v = 1 - alt/60) and `--v` overrides it outright.

    python tools/gen_moon_sky.py                 # defaults: az 135, alt 25
    python tools/gen_moon_sky.py --preview       # + a brightened PNG to eyeball
    python tools/pack_rt_sky.py                  # build the pk3 around it
"""

from __future__ import annotations

import argparse
import io
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parent))

from make_map_3dfloor_rtfix import WAD, read_wad_lumps

# Repo root, derived from this file so a clone can live anywhere.
PROJ_ROOT = Path(__file__).resolve().parents[1]

HERE = Path(__file__).resolve().parent
SKYDIR = HERE / "d64r-rt-sky"
OUTPNG = SKYDIR / "textures" / "MOONSKY.png"

# The flat the current night sky already uses. Read out of the IWAD rather than
# checked in, so the starfield can never drift from what the game ships.
SOURCE_FLAT = "SPACE"

# hw_skydome.cpp: xscale = texw < 1024 ? floor(1024/texw) : 1. Anything narrower
# than this repeats around the horizon, and every repeat gets its own moon.
SKY_WIDTH = 1024

# maxSideAngle in SkyVertexDoom. The dome covers +/-60 degrees, not a hemisphere.
DOME_MAX_ALTITUDE = 60.0

# The moon's own angular size, in degrees, mapped through the same 360-degree
# wrap as its position. 0.5 is the real moon and is far too small to read as
# anything but a bright star at this texture resolution; 4 is about as small as
# stays recognisably a disc.
DEFAULT_DIAMETER_DEG = 12.0

# Painted moon art, if present. Its ALPHA channel is the disc mask (opaque to
# about r=476 in a 1536x1024 image, feathered to nothing by r=500), and its RGB
# carries a halo out beyond that -- so the disc composites through alpha and the
# halo screens on, each doing the job it was drawn for. Falls back to the
# procedural disc below if the file is missing, so the sky always builds.
MOON_ART = PROJ_ROOT / "tools" / "_assets" / "moontexture.png"


def load_moon_art() -> tuple[Image.Image, Image.Image, float] | None:
    """(rgb, alpha, disc radius in px) for the painted moon, or None."""
    if not MOON_ART.is_file():
        return None
    im = Image.open(MOON_ART)
    if im.mode != "RGBA":
        im = im.convert("RGBA")
    rgb = im.convert("RGB")
    alpha = im.getchannel("A")

    # Disc radius straight off the alpha falloff rather than a hardcoded number,
    # so replacing the art with a differently framed moon still works.
    import numpy as np

    a = np.asarray(alpha).astype(float)
    cy, cx = a.shape[0] / 2.0, a.shape[1] / 2.0
    yy, xx = np.mgrid[0:a.shape[0], 0:a.shape[1]]
    r = np.hypot(xx - cx, yy - cy).astype(int)
    prof = np.bincount(r.ravel(), a.ravel()) / np.maximum(np.bincount(r.ravel()), 1)
    peak = prof[: max(4, len(prof) // 8)].mean()
    radius = next((i for i, v in enumerate(prof) if v < peak * 0.5), len(prof) // 2)
    return rgb, alpha, float(radius)


def load_source_flat() -> Image.Image:
    for name, blob in read_wad_lumps(WAD):
        if name.upper() == SOURCE_FLAT:
            return Image.open(io.BytesIO(blob)).convert("RGB")
    raise SystemExit(f"{WAD}: no {SOURCE_FLAT} lump — cannot build the night sky")


def tile_to_width(src: Image.Image, width: int) -> Image.Image:
    if width % src.width:
        raise SystemExit(
            f"{SOURCE_FLAT} is {src.width}px wide, which does not divide {width} — "
            f"tiling would seam. Pick a --width that is a multiple of it."
        )
    out = Image.new("RGB", (width, src.height))
    for i in range(width // src.width):
        out.paste(src, (i * src.width, 0))
    return out


def _wrapped(layer: Image.Image, width: int) -> list[Image.Image]:
    """The layer plus its two horizontal shifts, so a moon drawn near u=0 or u=1
    comes out whole instead of clipped at the seam the sky wraps on."""
    out = [layer]
    for dx in (-width, width):
        shifted = Image.new(layer.mode, layer.size, 0 if layer.mode == "L" else (0, 0, 0))
        shifted.paste(layer, (dx, 0))
        out.append(shifted)
    return out


def paste_moon_art(sky: Image.Image, art: tuple[Image.Image, Image.Image, float],
                   cx: float, cy: float, rx: float, ry: float, halo: float) -> None:
    """Composite the painted moon: screen its halo, then paste its disc.

    Scaled so the art's DISC (not its canvas, which is mostly halo and black)
    lands on rx by ry. Two passes for the same reason the procedural moon uses
    two: the halo has to let stars through, the disc has to occlude them.
    """
    from PIL import ImageChops

    rgb, alpha, disc_r = art
    # Scale the whole canvas by the ratio the disc needs, so the halo scales with it.
    sx, sy = rx / disc_r, ry / disc_r
    w = max(4, int(round(rgb.width * sx)))
    h = max(4, int(round(rgb.height * sy)))
    rgb_s = rgb.resize((w, h), Image.LANCZOS)
    a_s = alpha.resize((w, h), Image.LANCZOS)

    ox, oy = int(round(cx - w / 2)), int(round(cy - h / 2))

    # 1. halo: the art's RGB screened on, so the starfield shows through it.
    if halo > 0:
        glow = Image.new("RGB", sky.size, (0, 0, 0))
        glow.paste(rgb_s, (ox, oy))
        if halo != 1.0:
            glow = glow.point(lambda v: min(255, int(v * halo)))
        for layer in _wrapped(glow, sky.width):
            sky.paste(ImageChops.screen(sky, layer), (0, 0))

    # 2. disc: pasted through the art's own alpha, so the moon is solid.
    disc = Image.new("RGB", sky.size, (0, 0, 0))
    disc.paste(rgb_s, (ox, oy))
    mask = Image.new("L", sky.size, 0)
    mask.paste(a_s, (ox, oy))
    for layer, m in zip(_wrapped(disc, sky.width), _wrapped(mask, sky.width)):
        sky.paste(layer, (0, 0), m)


def draw_moon(sky: Image.Image, cx: float, cy: float, radius: float,
              color: tuple[int, int, int], halo: float) -> None:
    """Paint one moon: a soft halo screened onto the starfield, then an opaque
    disc composited over it.

    The two have to be separate passes. Screening the disc as well would let the
    halo underneath it wash the maria back out to flat white, which is exactly
    what turns a moon into an anonymous blob of glow.
    """
    from PIL import ImageChops

    # 1. Halo. Screened, so stars stay visible through it rather than being
    #    painted over -- it is atmosphere around the moon, not a lens flare.
    if halo > 0:
        hr = radius * 2.6
        glow = Image.new("RGB", sky.size, (0, 0, 0))
        ImageDraw.Draw(glow).ellipse(
            [cx - hr, cy - hr, cx + hr, cy + hr],
            fill=tuple(int(c * 0.16 * min(halo, 1.0)) for c in color))
        glow = glow.filter(ImageFilter.GaussianBlur(radius * 1.1))
        for layer in _wrapped(glow, sky.width):
            sky.paste(ImageChops.screen(sky, layer), (0, 0))

    # 2. The disc itself, with maria, composited through its own mask so it is
    #    solid: a moon occludes the stars behind it.
    disc = Image.new("RGB", sky.size, (0, 0, 0))
    mask = Image.new("L", sky.size, 0)
    dd, dm = ImageDraw.Draw(disc), ImageDraw.Draw(mask)
    box = [cx - radius, cy - radius, cx + radius, cy + radius]
    dd.ellipse(box, fill=color)
    dm.ellipse(box, fill=255)

    # Maria: fixed positions, never random -- a sky texture that comes out
    # different on every rebuild makes two A/B screenshots incomparable.
    for mx, my, mr in [(-0.36, -0.30, 0.26), (0.26, -0.34, 0.17),
                       (0.04, 0.10, 0.21), (0.44, 0.26, 0.15),
                       (-0.30, 0.42, 0.12)]:
        r = radius * mr
        px, py = cx + radius * mx, cy + radius * my
        dd.ellipse([px - r, py - r, px + r, py + r],
                   fill=tuple(int(c * 0.62) for c in color))

    # A sub-pixel softening on the mask only, so the limb is not a hard
    # staircase at 1024px-per-360-degrees but the maria stay crisp.
    mask = mask.filter(ImageFilter.GaussianBlur(max(0.5, radius * 0.05)))
    for layer, m in zip(_wrapped(disc, sky.width), _wrapped(mask, sky.width)):
        sky.paste(layer, (0, 0), m)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--azimuth", type=float, default=135.0,
                   help="world azimuth of the moon in degrees, matching rt_sun_b. "
                        "135 puts it north-west, which is the one bearing that "
                        "serves both of MAP13's window walls at once (default: 135)")
    p.add_argument("--altitude", type=float, default=25.0,
                   help="degrees above the horizon, matching rt_sun_a (default: 25)")
    p.add_argument("--diameter", type=float, default=DEFAULT_DIAMETER_DEG,
                   help=f"apparent diameter in degrees (default: {DEFAULT_DIAMETER_DEG})")
    p.add_argument("--color", default="D8E4FF",
                   help="moon disc colour, hex (default: D8E4FF, cold moonlight)")
    p.add_argument("--halo", type=float, default=1.0,
                   help="0 disables the halo, 1 is the default glow")
    p.add_argument("--flip-u", action="store_true",
                   help="mirror the horizontal placement. The one knob to try if "
                        "the moon appears mirrored about north relative to where "
                        "the shafts come from")
    p.add_argument("--v", type=float, default=None,
                   help="override the vertical texture coordinate outright, 0..1")
    p.add_argument("--width", type=int, default=SKY_WIDTH,
                   help=f"output width (default: {SKY_WIDTH}; below 1024 the sky "
                        f"tiles and you get one moon per repeat)")
    p.add_argument("--aspect", type=float, default=1.0,
                   help="extra vertical squash on top of the automatic dome "
                        "correction. The texture is anisotropic in angle (360 deg "
                        "across its width, 60 down its height), which is corrected "
                        "for; this is the residual fudge if the moon still reads "
                        "as an ellipse in game, because SetupMatrices rescales v "
                        "again for short tiled textures (default: 1.0)")
    p.add_argument("--bake-disc", action="store_true",
                   help="ALSO paint the moon into the sky texture. Off by default: "
                        "the moon is drawn as geometry now, and baking it too would "
                        "put two moons in the sky. Only for falling back to the old "
                        "texture-only moon, which cannot go above the dome's 60 deg.")
    p.add_argument("--no-art", action="store_true",
                   help=f"ignore {MOON_ART.name} and draw the procedural disc instead")
    p.add_argument("--debug", action="store_true",
                   help="DIAGNOSTIC SKY: replace the starfield with flat magenta "
                        "and a green grid. Every sky surface in the game then "
                        "identifies itself on sight -- ceiling openings, the "
                        "decorative slots punched in walls, and the invisible "
                        "sky-hack bands above wall tops all light up in a colour "
                        "Doom 64 does not otherwise use. Stand in a leaking room "
                        "and the opening feeding it is the magenta one. The "
                        "magenta also tints the light the sky DOME casts, so "
                        "magenta light = sky, blue-white = the moon (rt_sun), "
                        "which separates the two contributions at a glance. Run "
                        "without --debug to put the real sky back.")
    p.add_argument("--preview", action="store_true",
                   help="also write MOONSKY_preview.png, brightened, since the "
                        "real thing is nearly black and unreadable on screen")
    args = p.parse_args()

    src = load_source_flat()
    sky = tile_to_width(src, args.width)

    if args.debug:
        # Flat magenta with a green grid. Magenta because Doom 64's palette
        # barely uses it, so nothing else on screen can be mistaken for a sky
        # surface; the grid because a flat colour gives no sense of which way a
        # surface faces, and telling a ceiling opening from a slot in a wall is
        # the whole point of looking.
        sky = Image.new("RGB", sky.size, (255, 0, 200))
        dr = ImageDraw.Draw(sky)
        for x in range(0, sky.width, 32):
            dr.line([(x, 0), (x, sky.height)], fill=(0, 255, 80), width=1)
        for y in range(0, sky.height, 32):
            dr.line([(0, y), (sky.width, y)], fill=(0, 255, 80), width=1)
        OUTPNG.parent.mkdir(parents=True, exist_ok=True)
        sky.save(OUTPNG)
        print(f"wrote {OUTPNG} {sky.width}x{sky.height} -- DIAGNOSTIC SKY, not the real one")
        print("  every sky surface now renders magenta: ceiling openings, the")
        print("  decorative slots punched in walls, and the sky-hack bands above")
        print("  wall tops. In a leaking room, the opening feeding it is the one")
        print("  you can see. Magenta light = the sky dome; blue-white = the moon.")
        print("  next: python tools/pack_rt_sky.py")
        print("  restore: python tools/gen_moon_sky.py && python tools/pack_rt_sky.py")
        return

    u = (-args.azimuth / 360.0) % 1.0
    if args.flip_u:
        u = (1.0 - u) % 1.0
    v = args.v if args.v is not None else 1.0 - args.altitude / DOME_MAX_ALTITUDE
    if not 0.0 <= v <= 1.0:
        raise SystemExit(
            f"altitude {args.altitude} maps to v={v:.3f}, outside the dome's "
            f"0..{DOME_MAX_ALTITUDE} degrees. Lower --altitude or pass --v."
        )

    cx = u * sky.width
    cy = v * sky.height

    # The sky texture is ANISOTROPIC in angle: width covers 360 degrees, height
    # covers only the dome's 60. So a degree is width/360 px across and
    # height/60 px down, and a moon drawn with one radius comes out an ellipse
    # in the sky. rx/ry below is that correction -- for 1024x128 it makes the
    # moon 0.75x as tall as it is wide, which is round once the dome maps it.
    rx = 0.5 * args.diameter * sky.width / 360.0
    ry = 0.5 * args.diameter * sky.height / DOME_MAX_ALTITUDE * args.aspect
    color = tuple(int(args.color.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))

    art = None if args.no_art else load_moon_art()

    # The moon is GEOMETRY now, not paint. rt_main submits a quad along the
    # rt_sun direction and textures it with MOONDISC, which is drawn over the
    # dome and its cap -- so it can sit anywhere, including straight overhead,
    # where the sky texture simply has no pixels (see the 60-degree dome limit).
    # Baking it into the sky as well would show TWO moons, so --bake-disc is off
    # by default and exists only to fall back to the old behaviour.
    if art is not None:
        rgba = Image.merge("RGBA", (*art[0].split(), art[1]))
        side = int(round(art[2] * 2.4))  # disc plus a little halo
        cx0, cy0 = rgba.width // 2, rgba.height // 2
        disc = rgba.crop((cx0 - side // 2, cy0 - side // 2,
                          cx0 + side // 2, cy0 + side // 2))
        disc = disc.resize((256, 256), Image.LANCZOS)
        discout = OUTPNG.with_name("MOONDISC.png")
        disc.save(discout)
        print(f"wrote {discout} 256x256 (disc crop of {MOON_ART.name}, alpha kept)")

    if args.bake_disc:
        if art is not None:
            paste_moon_art(sky, art, cx, cy, rx, ry, args.halo)
        else:
            draw_moon(sky, cx, cy, rx, color, args.halo)

    OUTPNG.parent.mkdir(parents=True, exist_ok=True)
    sky.save(OUTPNG)
    print(f"wrote {OUTPNG} {sky.width}x{sky.height} "
          f"(from {SOURCE_FLAT} {src.width}x{src.height} x{sky.width // src.width})")
    print(f"  moon azimuth {args.azimuth:g} deg -> u={u:.4f} (x={cx:.0f}px)"
          f"{' [flipped]' if args.flip_u else ''}")
    print(f"  moon altitude {args.altitude:g} deg -> v={v:.4f} (y={cy:.0f}px)")
    print(f"  disc {args.diameter:g} deg -> {rx * 2:.0f} x {ry * 2:.0f} px "
          f"({'painted art ' + MOON_ART.name if art is not None else 'procedural disc'})"
          f" -- not square on purpose: the texture spans 360 deg across and only "
          f"{DOME_MAX_ALTITUDE:g} down")
    print(f"  aim in game with: moon {args.azimuth:g} {args.altitude:g}")
    print("  --azimuth/--altitude only matter with --bake-disc. The shipping moon")
    print("  is MOONDISC drawn as geometry along the rt_sun direction, so it is")
    print("  placed by the light itself and needs no reference values here.")

    if args.preview:
        from PIL import ImageEnhance

        # Brightened but NOT rescaled: stretching the preview would make a round
        # moon look elliptical and send you chasing an aspect bug that is not there.
        prev = ImageEnhance.Brightness(sky).enhance(3.0)
        out = OUTPNG.with_name("MOONSKY_preview.png")
        prev.save(out)
        print(f"wrote {out} (brightened x3, the real texture is near-black)")


if __name__ == "__main__":
    main()
