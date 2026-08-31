"""
Repaint the Cacodemon fireball (BAL2) so its fringe cools to blue.

Ships as `Doom64-Retribution\\d64r-caco-ball-recolor.pk3`, which the launcher
passes ONLY when the "Classic recoloured Cacodemon / Pain Elemental" box is
ticked -- see docs\\classic-recolored-addon.md. D64ClassicRecolored repaints the
monster and stops there (71 lumps, not one of them BAL2), so with the add-on on,
a classic-hued Cacodemon was still throwing Doom 64's own orange ball. This is
the projectile catching up with it, and it is derived from RETRIBUTION's sprite
-- none of the add-on's pixels are read, copied or redistributed.

The look: the core stays the fire it already was, the midtones pass through the
violet the classic Doom BAL2 has around its rim, and the extremities -- the dark
maroon fringe and the speckles that fly off the explosion -- land on blue.

Three things this has to get right:

  * `grAb`. Every BAL2 lump is a PNG with a grAb chunk, and PIL silently drops
    it on save: the ball would render sunk and off-centre. The chunk is copied
    from the source bytes and re-injected after tRNS.

  * The gradient runs on the SILHOUETTE, not on the palette. A palette-only
    remap is tempting (the ramp really is a luminance ramp, and it would keep
    the IDAT byte-identical) but it has no idea where a pixel sits: the dark
    maroon inside the explosion's gaps would turn into blue confetti scattered
    through the fire. The distance to the transparent edge is what "extremity"
    actually means, so that is what drives it, with luminance only as a second
    term.

  * Luminance is preserved. Each recoloured pixel is scaled back to the source
    pixel's luma (x1.05 violet, x1.15 blue, so the fringe still reads as a
    halo). Swap the hue, keep the drawing -- the value structure is the art.

Usage:
    py -3 tools/gen_caco_ball_recolor.py            # pk3 + gallery
    py -3 tools/gen_caco_ball_recolor.py --gallery-only
"""

from __future__ import annotations

import argparse
import io
import re
import math
import struct
import zipfile
from pathlib import Path

from PIL import Image, ImageDraw

# Repo root, derived from this file so a clone can live anywhere.
PROJ_ROOT = Path(__file__).resolve().parents[1]

WAD = PROJ_ROOT / r"Doom64-Retribution\D64RTR_v15.WAD"
OUT_PK3 = PROJ_ROOT / r"Doom64-Retribution\d64r-caco-ball-recolor.pk3"
GALLERY_DIR = PROJ_ROOT / r"tools\_caco_recolor"

# BAL2 ABC is the flight loop, D-J the burst -- 64CacodemonBall in Retribution's
# DECORATE. All ten get the same treatment so the ball and its explosion agree.
FRAMES = "ABCDEFGHIJ"

# The one tuning block. Picked off a four-preset contact sheet; the reason each
# value is where it is:
#   depth_frac  how deep "the edge" reaches, as a fraction of sqrt(area) -- so a
#               32px ball and an 80px burst get a proportionate fringe
#   we/ge       edge term: weight and falloff of the distance-to-silhouette
#   wl/gl       luminance term: how much a dark pixel cools on its own
#   core_lo/hi  above core_lo the recolour fades out, above core_hi nothing
#               moves at all -- this is what keeps the centre fire
#   gain_*      luma gain on the two cool stops, so the fringe reads as a halo
TUNE = dict(depth_frac=0.17, we=0.82, ge=1.7, wl=0.36, gl=2.2,
            core_lo=0.24, core_hi=0.54, gain_mid=1.05, gain_cold=1.15)


# --- wad ------------------------------------------------------------------

def wad_lumps(path: Path) -> dict[str, bytes]:
    d = path.read_bytes()
    _, n, off = struct.unpack_from("<4sii", d, 0)
    out: dict[str, bytes] = {}
    for i in range(n):
        o, s, name = struct.unpack_from("<ii8s", d, off + 16 * i)
        nm = name.rstrip(b"\0").decode("latin1")
        out.setdefault(nm, d[o:o + s])
    return out


def png_chunk(raw: bytes, want: str) -> bytes | None:
    """The whole 12+len chunk, ready to splice back into another PNG."""
    i = 8
    while i < len(raw):
        ln = struct.unpack_from(">I", raw, i)[0]
        if raw[i + 4:i + 8].decode("latin1") == want:
            return raw[i:i + 12 + ln]
        i += 12 + ln
    return None


def inject_before_idat(raw: bytes, chunk: bytes) -> bytes:
    i = 8
    while i < len(raw):
        ln = struct.unpack_from(">I", raw, i)[0]
        if raw[i + 4:i + 8] == b"IDAT":
            return raw[:i] + chunk + raw[i:]
        i += 12 + ln
    raise SystemExit("no IDAT in PNG")


# --- colour ---------------------------------------------------------------

def smoothstep(e0: float, e1: float, x: float) -> float:
    if e1 <= e0:
        return 0.0 if x < e0 else 1.0
    t = min(1.0, max(0.0, (x - e0) / (e1 - e0)))
    return t * t * (3 - 2 * t)


def luma(c) -> float:
    return 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]


def mid_twin(r, g, b):
    """The violet stop: red survives, green is cut, blue is pushed up."""
    return (0.85 * r + 0.10 * g,
            0.18 * r + 0.35 * g,
            0.95 * r + 0.35 * g + 0.30 * b + 20)


def cold_twin(r, g, b):
    """The blue stop: the fire's red energy is spent on the blue channel."""
    return (0.16 * r + 0.08 * g,
            0.26 * r + 0.50 * g + 0.22 * b,
            1.15 * r + 0.50 * g + 0.30 * b + 30)


def match_luma(c, target: float, gain: float):
    l = luma(c)
    if l < 1e-3:
        return c
    k = (target * gain) / l
    return tuple(min(255.0, v * k) for v in c)


def inner_distance(mask: list[bool], w: int, h: int) -> list[float]:
    """Chamfer distance to the transparent edge: 0 just inside it, up inward."""
    INF = 1e9
    d = [INF if mask[i] else 0.0 for i in range(w * h)]

    def at(x, y):
        if x < 0 or y < 0 or x >= w or y >= h:
            return 0.0
        return d[y * w + x]

    for y in range(h):
        for x in range(w):
            if not mask[y * w + x]:
                continue
            d[y * w + x] = min(d[y * w + x], at(x - 1, y) + 1, at(x, y - 1) + 1,
                               at(x - 1, y - 1) + 1.41421, at(x + 1, y - 1) + 1.41421)
    for y in range(h - 1, -1, -1):
        for x in range(w - 1, -1, -1):
            if not mask[y * w + x]:
                continue
            d[y * w + x] = min(d[y * w + x], at(x + 1, y) + 1, at(x, y + 1) + 1,
                               at(x + 1, y + 1) + 1.41421, at(x - 1, y + 1) + 1.41421)
    return d


def recolor(im: Image.Image, P: dict) -> Image.Image:
    im = im.convert("RGBA")
    w, h = im.size
    raw = im.tobytes()
    px = [tuple(raw[i:i + 4]) for i in range(0, len(raw), 4)]
    mask = [p[3] > 0 for p in px]
    dist = inner_distance(mask, w, h)
    depth = max(2.5, P["depth_frac"] * math.sqrt(w * h))

    out = []
    for i, p in enumerate(px):
        r, g, b, a = p
        if a == 0:
            out.append((0, 0, 0, 0))
            continue
        L = luma((r, g, b))
        v = L / 255.0
        dn = min(1.0, dist[i] / depth)
        t = P["we"] * (1.0 - dn) ** P["ge"] + P["wl"] * (1.0 - v) ** P["gl"]
        t = min(1.0, max(0.0, t))
        t *= 1.0 - smoothstep(P["core_lo"], P["core_hi"], v)
        if t <= 0.0:
            out.append((r, g, b, 255))
            continue
        mid = match_luma(mid_twin(r, g, b), L, P["gain_mid"])
        cold = match_luma(cold_twin(r, g, b), L, P["gain_cold"])
        src = (r, g, b)
        if t < 0.5:
            k = t * 2.0
            c = tuple(src[j] + (mid[j] - src[j]) * k for j in range(3))
        else:
            k = (t - 0.5) * 2.0
            c = tuple(mid[j] + (cold[j] - mid[j]) * k for j in range(3))
        out.append(tuple(int(round(min(255.0, max(0.0, x)))) for x in c) + (255,))

    o = Image.new("RGBA", (w, h))
    o.putdata(out)
    return o


# --- png ------------------------------------------------------------------

def to_indexed_png(rgba: Image.Image, grab: bytes | None) -> bytes:
    """Same shape as the source lump: palette + tRNS index 0 + grAb.

    Index 0 is transparent, exactly as Retribution stores it, so anything that
    reads these back (the RT material pipeline, a future generator) sees the
    format it already knows.
    """
    w, h = rgba.size
    raw = rgba.tobytes()
    px = [tuple(raw[i:i + 4]) for i in range(0, len(raw), 4)]

    # A continuous gradient over a 13-entry ramp can run past 255 distinct
    # colours (BAL2I0 hits 279). Round the channels onto a coarser lattice until
    # it fits -- at the step this settles on, the difference is under a quarter
    # of one of the source ramp's own steps.
    for q in (1, 2, 3, 4, 6, 8, 12):
        snap = [p if p[3] == 0 else
                (tuple(min(255, (c + q // 2) // q * q) for c in p[:3]) + (255,))
                for p in px]
        if len({p[:3] for p in snap if p[3]}) <= 255:
            break
    else:
        raise SystemExit("cannot fit the recolour into a palette PNG")
    px = snap

    uniq: dict[tuple, int] = {}
    idx = []
    for p in px:
        if p[3] == 0:
            idx.append(0)
            continue
        key = p[:3]
        if key not in uniq:
            uniq[key] = len(uniq) + 1          # 0 is reserved for transparent
        idx.append(uniq[key])

    im = Image.new("P", (w, h))
    im.putdata(idx)
    pal = [0, 0, 0]
    for c, _ in sorted(uniq.items(), key=lambda kv: kv[1]):
        pal += list(c)
    pal += [0] * (768 - len(pal))
    im.putpalette(pal)

    buf = io.BytesIO()
    im.save(buf, "PNG", transparency=0, optimize=True)
    raw = buf.getvalue()
    if grab:
        raw = inject_before_idat(raw, grab)
    return raw


# --- gallery --------------------------------------------------------------

def build_gallery(pairs, path: Path, scale: int = 8, per_row: int = 5) -> None:
    """Original above, recoloured below, on the dark the fireball is seen against.

    Five frames to a band so the sheet stays readable at 100%: the flight loop
    (ABC) and the first burst frames on top, the rest of the burst below.
    """
    BG = (20, 20, 24)
    CELL_PAD, GAP, LEFT, TOP, BAND_GAP = 12, 8, 118, 62, 30
    cw = max(a.width for _, a, _ in pairs) * scale + CELL_PAD * 2
    ih = max(a.height for _, a, _ in pairs) * scale
    band_h = 22 + ih + GAP + ih + CELL_PAD
    bands = [pairs[i:i + per_row] for i in range(0, len(pairs), per_row)]
    W = LEFT + cw * per_row + CELL_PAD
    H = TOP + len(bands) * (band_h + BAND_GAP) + 78
    sheet = Image.new("RGB", (W, H), BG)
    dr = ImageDraw.Draw(sheet)

    dr.text((18, 16), "BAL2 -- Cacodemon fireball", fill=(232, 228, 220))
    dr.text((18, 34),
            "core keeps its fire, midtones pass through violet, the fringe and "
            "the flying speckles land on blue",
            fill=(158, 156, 152))

    for bi, band in enumerate(bands):
        by = TOP + bi * (band_h + BAND_GAP)
        dr.text((18, by + 22 + ih // 2 - 6), "Retribution", fill=(172, 168, 162))
        dr.text((18, by + 22 + ih + GAP + ih // 2 - 6), "recoloured", fill=(172, 168, 162))
        for ci, (name, orig, new_im) in enumerate(band):
            x = LEFT + ci * cw + CELL_PAD
            kind = "flight loop" if name[4] in "ABC" else "burst"
            dr.text((x, by), f"{name}   {kind}", fill=(140, 138, 136))
            for ri, im in enumerate((orig, new_im)):
                b = im.convert("RGBA").resize(
                    (im.width * scale, im.height * scale), Image.NEAREST)
                bg = Image.new("RGBA", b.size, BG + (255,))
                bg.alpha_composite(b)
                # bottom-align: the frames differ in height and a common
                # baseline is what makes the two rows comparable
                sheet.paste(bg.convert("RGB"),
                            (x, by + 22 + ri * (ih + GAP) + ih - b.height))

    # The mapping itself, as a strip: what a source colour becomes at t=0/0.5/1.
    ly = H - 56
    dr.text((18, ly - 20), "fringe gradient  (t = 0 core .. 1 extremity)",
            fill=(158, 156, 152))
    ramp = [(200, 88, 32), (160, 48, 16), (96, 16, 0), (56, 0, 0)]
    x = 18
    for src in ramp:
        for k in range(13):
            t = k / 12.0
            L = luma(src)
            mid = match_luma(mid_twin(*src), L, TUNE["gain_mid"])
            cold = match_luma(cold_twin(*src), L, TUNE["gain_cold"])
            if t < 0.5:
                c = tuple(src[j] + (mid[j] - src[j]) * (t * 2) for j in range(3))
            else:
                c = tuple(mid[j] + (cold[j] - mid[j]) * ((t - 0.5) * 2) for j in range(3))
            dr.rectangle([x, ly, x + 15, ly + 26],
                         fill=tuple(int(round(min(255.0, max(0.0, v)))) for v in c))
            x += 16
        x += 14

    path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(path)
    print(f"gallery  {path}  {sheet.size[0]}x{sheet.size[1]}")


def build_readme_pair(pairs, out_dir: Path, scale: int = 4) -> None:
    """The two before/after strips the README's Art changes table shows.

    Only the flight loop: it is the ball the player actually watches come at
    them, and the burst is over in 17 tics.
    """
    BG = (20, 20, 24)
    flight = [p for p in pairs if p[0][4] in "ABC"]
    W = sum(a.width for _, a, _ in flight) * scale + 10 * (len(flight) + 1)
    H = max(a.height for _, a, _ in flight) * scale + 20
    for which, path in ((1, "caco-ball-before.png"), (2, "caco-ball-after.png")):
        sheet = Image.new("RGB", (W, H), BG)
        x = 10
        for entry in flight:
            im = entry[which]
            b = im.convert("RGBA").resize(
                (im.width * scale, im.height * scale), Image.NEAREST)
            bg = Image.new("RGBA", b.size, BG + (255,))
            bg.alpha_composite(b)
            sheet.paste(bg.convert("RGB"), (x, H - 10 - b.height))
            x += b.width + 10
        out_dir.mkdir(parents=True, exist_ok=True)
        sheet.save(out_dir / path)
        print(f"readme   {out_dir / path}  {W}x{H}")


# --- the impact ramp ---------------------------------------------------------
#
# The blue half of the fireball's impact fire, as a C++ table. The four shipping
# fire ramps are read off each projectile's own death frames by
# tools/gen_fire_impact_art.py --ramps; this one is DERIVED, and the difference
# is worth stating because the house rule is the other way round.
#
# Reading it off the recoloured burst was tried first and it is wrong here. The
# cool pixels of this art are a TWO-DIMENSIONAL family -- source ramp entry
# crossed with fringe position -- so ordering them by luminance and taking ten
# quantiles walks in and out of violet (A037A7, 5E37CA, 812AA1, 4432C1 ...).
# On a five-frame spark nobody would see it; on a mark held on a wall for
# seconds it reads as the fire changing its mind.
#
# What the fringe actually IS, is the ball's own ramp run through `cold_twin` at
# full strength -- the same transform, the same luma match, the same gain the
# art uses. Applying it to the RED ramp therefore gives the same hues with a
# monotone ladder, and ties the two halves of the fire to the two halves of the
# sprite by construction: re-tune the recolour and the flames follow.
#
# The red half is NOT generated here. It stays BAL8's ramp -- the one deliberate
# exception the impact-FX plan records, because Doom 64 lights the caco ball and
# the baron ball with the same GLDEFS red -- so with the add-on off, nothing
# about the caco's fire has moved.

# rt_sparks_internal.h RT_FIRE_RED_RAMP, which is BAL8 C0-H0. Duplicated rather
# than parsed out of the header: this is an INPUT, and if the two ever disagree
# the check below says so instead of silently drifting.
RT_FIRE_RED_RAMP = [
    0xF83000, 0xF82800, 0xC82800, 0xB82000, 0xA02000,
    0x901800, 0x601000, 0x500800, 0x280800, 0x180000,
]

HEADER = (PROJ_ROOT / "sourcecode" / "gzdoom-rt" / "src" / "common" / "rendering"
          / "rt" / "rt_sparks_internal.h")


def check_red_ramp_still_matches() -> None:
    """The header is the authority; fail rather than emit a stale blue half."""
    try:
        text = HEADER.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        print("// (rt_sparks_internal.h not readable -- red ramp unverified)")
        return
    i = text.find("RT_FIRE_RED_RAMP[]")
    if i < 0:
        print("// (RT_FIRE_RED_RAMP not found in the header -- unverified)")
        return
    body = text[text.index("{", i) + 1:text.index("}", i)]
    got = [int(v, 16) for v in re.findall(r"0x([0-9A-Fa-f]{6})", body)]
    if got != RT_FIRE_RED_RAMP:
        raise SystemExit(
            "RT_FIRE_RED_RAMP in rt_sparks_internal.h no longer matches the copy "
            "in this file -- update RT_FIRE_RED_RAMP here and re-run.")


def blue_ramp() -> list:
    out = []
    for v in RT_FIRE_RED_RAMP:
        r, g, b = (v >> 16) & 0xFF, (v >> 8) & 0xFF, v & 0xFF
        L = luma((r, g, b))
        c = match_luma(cold_twin(r, g, b), L, TUNE["gain_cold"])
        c = tuple(int(round(min(255.0, max(0.0, x)))) for x in c)
        out.append((c[0] << 16) | (c[1] << 8) | c[2])
    return out


def print_ramp() -> None:
    check_red_ramp_still_matches()
    vals = blue_ramp()
    print()
    print("// GENERATED by `py -3 tools/gen_caco_ball_recolor.py --ramp`. Do not")
    print("// hand-edit; re-run it if the recolour is retuned.")
    print("//")
    print("// THE BLUE HALF of 64CacodemonBall's impact fire, and it is RT_FIRE_RED_RAMP")
    print("// above run through the recolour's own cold twin at full strength -- the")
    print("// same transform that put the blue on the sprite's fringe, so the two halves")
    print("// of the fire are the two halves of the ball. Derived rather than read off")
    print("// the art because the recoloured burst's cool pixels are a two-dimensional")
    print("// family and ten luminance quantiles through them walk in and out of violet;")
    print("// the generator's docstring has the numbers.")
    print("constexpr uint32_t RT_FIRE_CACO_BLUE_RAMP[] = {")
    for i in range(0, len(vals), 5):
        print("    " + ", ".join(f"0x{v:06X}" for v in vals[i:i + 5]) + ",")
    print("};")
    print("constexpr int RT_FIRE_CACO_BLUE_RAMP_N = "
          "int( std::size( RT_FIRE_CACO_BLUE_RAMP ) );")


FIRE_SHEET = (PROJ_ROOT / "sourcecode" / "gzdoom-rt" / "build" / "RelWithDebInfo"
              / "rt" / "mat" / "d64rt" / "fire" / "fire.png")


def build_fire_gallery(path: Path) -> None:
    """What the IMPACT looks like: the two ramps, the mix, and the mark itself.

    The flames are drawn with the GAME'S OWN sheet -- rt/mat/d64rt/fire/fire.png,
    the five-cell strip gen_fire_impact_art.py lifts out of 64BigFire -- tinted
    and added exactly the way the renderer does it: the sheet is a white-hot
    luminance with alpha, the colour is per vertex, and the blend is additive.
    A hand-drawn triangle would have shown the palette and lied about the shape.

    Life runs left to right, because what decides whether this reads is how the
    two halves sit next to each other OVER the mark's life, and no screenshot of
    one moment shows that.
    """
    BG = (20, 20, 24)
    W, H = 1180, 560
    sheet = Image.new("RGB", (W, H), BG)
    dr = ImageDraw.Draw(sheet)
    blue = blue_ramp()
    red = RT_FIRE_RED_RAMP

    def rgb(v):
        return ((v >> 16) & 0xFF, (v >> 8) & 0xFF, v & 0xFF)

    def at(ramp, t):
        f = t * (len(ramp) - 1)
        i0 = min(int(f), len(ramp) - 1)
        i1 = min(i0 + 1, len(ramp) - 1)
        fr = f - i0
        a, b = rgb(ramp[i0]), rgb(ramp[i1])
        return tuple(int(round(a[j] + (b[j] - a[j]) * fr)) for j in range(3))

    dr.text((22, 18), "BAL2 impact fire -- half red, half blue", fill=(232, 228, 220))
    dr.text((22, 36),
            "seven flames (rt_fire_count), alternating by index, over rt_fire_life 3.5 s. "
            "Only with the classic-recolour add-on -- rt_fire_caco_blue.",
            fill=(158, 156, 152))

    LEFT, TOP, CW, RH, GAP = 150, 92, 128, 30, 6
    STEPS = 8
    rows = (("red half", lambda t: at(red, t)),
            ("blue half", lambda t: at(blue, t)),
            ("the mark's light",
             lambda t: tuple((at(red, t)[j] + at(blue, t)[j]) // 2 for j in range(3))))
    for ri, (label, fn) in enumerate(rows):
        y = TOP + ri * (RH + GAP)
        dr.text((22, y + RH // 2 - 6), label, fill=(176, 172, 166))
        for k in range(STEPS):
            t = k / (STEPS - 1)
            dr.rectangle([LEFT + k * CW, y, LEFT + (k + 1) * CW - 2, y + RH], fill=fn(t))
    for k in range(STEPS):
        dr.text((LEFT + k * CW, TOP - 18), f"{k / (STEPS - 1) * 3.5:.1f}s",
                fill=(140, 138, 136))
    y = TOP + 3 * (RH + GAP)
    dr.text((LEFT, y + 2),
            "one light per mark, so it is the average of the two -- the violet the "
            "ball's own midtones pass through",
            fill=(140, 138, 136))

    # --- the mark, drawn with the real sheet -------------------------------
    try:
        strip = Image.open(FIRE_SHEET).convert("RGBA")
    except OSError:
        dr.text((22, y + 34), f"(flame sheet not built: {FIRE_SHEET})", fill=(200, 120, 120))
        path.parent.mkdir(parents=True, exist_ok=True)
        sheet.save(path)
        print(f"gallery  {path}  {sheet.size[0]}x{sheet.size[1]}  (no sheet)")
        return
    cells = max(1, round(strip.width / strip.height))
    cell = strip.height

    import random as _r
    MTOP = y + 40
    dr.text((22, MTOP), "the mark, at three ages -- the game's own flame sheet, tinted "
                        "and added", fill=(176, 172, 166))
    for ci, t in enumerate((0.10, 0.35, 0.65)):
        ox, oy = 40 + ci * 380, MTOP + 30
        panel = Image.new("RGB", (340, 210), (26, 23, 25))
        # the scorch the flames stand in
        scorch = Image.new("RGBA", panel.size, (0, 0, 0, 0))
        ImageDraw.Draw(scorch).ellipse([40, 120, 300, 190], fill=(12, 8, 8, 210))
        panel = Image.alpha_composite(panel.convert("RGBA"), scorch).convert("RGB")
        acc = [list(px) for px in [panel.getpixel((x, yy)) for yy in range(panel.height)
                                   for x in range(panel.width)]]
        rnd = _r.Random(11 + ci)
        spots = [(rnd.uniform(70, 270), rnd.uniform(150, 178), rnd.randrange(cells))
                 for _ in range(7)]
        fade = (1.0 - t) * (1.0 - t)
        for e, (fx, fy, ph) in sorted(enumerate(spots), key=lambda kv: kv[1][1]):
            col = at(blue if (e & 1) else red, t)
            f = strip.crop((ph * cell, 0, (ph + 1) * cell, cell))
            sz = int(cell * (1.05 - 0.35 * t))
            f = f.resize((sz, sz), Image.BILINEAR)
            fpx = f.load()
            bx, by = int(fx - sz / 2), int(fy - sz)
            for yy in range(sz):
                for xx in range(sz):
                    r, g, b, a = fpx[xx, yy]
                    if a == 0:
                        continue
                    px, py = bx + xx, by + yy
                    if not (0 <= px < panel.width and 0 <= py < panel.height):
                        continue
                    # additive, tinted per vertex, brightness = alpha -- the
                    # renderer's own three facts about this quad
                    k = (a / 255.0) * (r / 255.0) * min(1.0, 1.6 * fade)
                    i = py * panel.width + px
                    for m in range(3):
                        acc[i][m] = min(255, int(acc[i][m] + col[m] * k))
        out = Image.new("RGB", panel.size)
        out.putdata([tuple(v) for v in acc])
        sheet.paste(out, (ox, oy))
        dr.text((ox + 4, oy + 214), f"t = {t * 3.5:.1f}s", fill=(140, 138, 136))

    path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(path)
    print(f"gallery  {path}  {sheet.size[0]}x{sheet.size[1]}")


# --- main -----------------------------------------------------------------

def verify(name: str, src: bytes, out: bytes) -> None:
    """Nothing but the colours may have moved.

    Size, grAb and the silhouette are what a recolour must not touch, and all
    three fail quietly: a dropped grAb sinks the ball into the floor, and a
    silhouette that shifted by one pixel is invisible next to a hue change.
    """
    a, b = Image.open(io.BytesIO(src)), Image.open(io.BytesIO(out))
    a.load(); b.load()
    if a.size != b.size:
        raise SystemExit(f"{name}: size {b.size} != source {a.size}")
    if png_chunk(src, "grAb") != png_chunk(out, "grAb"):
        raise SystemExit(f"{name}: grAb lost or changed")
    sa = a.convert("RGBA").tobytes()[3::4]
    sb = b.convert("RGBA").tobytes()[3::4]
    if bytes(bool(v) for v in sa) != bytes(bool(v) for v in sb):
        raise SystemExit(f"{name}: silhouette changed")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gallery-only", action="store_true",
                    help="render the comparison sheet, leave the pk3 alone")
    ap.add_argument("--ramp", action="store_true",
                    help="print the C++ blue impact ramp and exit")
    args = ap.parse_args()

    lumps = wad_lumps(WAD)
    pairs, entries = [], []
    for f in FRAMES:
        name = f"BAL2{f}0"
        raw = lumps[name]
        orig = Image.open(io.BytesIO(raw))
        orig.load()
        new = recolor(orig, TUNE)
        grab = png_chunk(raw, "grAb")
        if grab is None:
            print(f"  ! {name} has no grAb")
        out = to_indexed_png(new, grab)
        verify(name, raw, out)
        entries.append((name, out))
        pairs.append((name, orig, new))
        gx, gy = struct.unpack(">ii", grab[8:16]) if grab else (0, 0)
        print(f"  {name}  {orig.size[0]}x{orig.size[1]}  grAb {gx},{gy}  {len(out)} B  ok")

    if args.ramp:
        print_ramp()
        return

    build_gallery(pairs, GALLERY_DIR / "bal2-blue-fringe.png")
    build_fire_gallery(GALLERY_DIR / "bal2-impact-fire.png")
    build_readme_pair(pairs, PROJ_ROOT / "docs" / "img" / "features")

    if args.gallery_only:
        return

    with zipfile.ZipFile(OUT_PK3, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in entries:
            z.writestr(f"sprites/{name}.png", data)
        z.writestr("README.txt",
                   "d64r-caco-ball-recolor.pk3 -- generated by "
                   "tools/gen_caco_ball_recolor.py.\n"
                   "Retribution's BAL2 with a violet/blue fringe, loaded only "
                   "when the classic\nrecolour add-on is ticked. Do not edit by "
                   "hand; re-run the generator.\n")
    print(f"wrote    {OUT_PK3}  {OUT_PK3.stat().st_size} B")


if __name__ == "__main__":
    main()
