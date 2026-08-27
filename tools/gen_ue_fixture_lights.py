"""
Measure Unseen Evil's lit wall art and emit the light table the renderer casts
real light from.

WHY THIS EXISTS. tools/launch-unseenevil-rt.cmd says it plainly: "the engine's
fixture walk keys off Doom 64 texture names this content does not use". Every RT
fixture classifier -- SFLATAS, SFLATAQ, SPACEAZ, the CMPSW* switch table -- was
built against Retribution's own art. Unseen Evil's Terraformer swaps DOOM's walls
for ITS art, so its door indicators, light strips and switch lamps all reach the
renderer under names no classifier knows, and every one of them is dark. This
measures where the light actually is in each texture and writes the rows out.

THREE FAMILIES, ONE MECHANISM. They differ only in what makes the texture change:

  doors     a 4-frame ANIMDEFS ping-pong (_0 _1 _2 _1, 7 tics) -- it pulses
  switches  a SWITCHES pair, off -> on, thrown by the player
  strips    no change at all; a light strip is just always on

and none of that has to be modelled, because the renderer asks
TexMan.GetGameTexture(id, /*animate=*/true) -- the texture being drawn RIGHT NOW.
So the table is keyed on the frame's OWN name, and a frame with no row emits no
light. The door blink, the switch coming on when thrown and only when thrown, and
the strip's steady burn are all the same lookup. No phase arithmetic, no
line-special inspection, no state.

WHERE THE MASK COMES FROM, in order of trust:
  1. The mod's OWN brightmap, from `material texture "X" { brightmap "Y" }` in
     its GLDEFS.* lumps -- the artist saying "these texels are self-lit", which
     is the exact question being asked. A brightmap may itself be a TEXTURES
     composite, so it is resolved the same way any other texture is.
  2. Failing that, a colour heuristic over the albedo. Every row records which
     was used; a heuristic row is worth a second look.

TWO TRAPS THE MEASUREMENT CATCHES, either of which inverts a blink if assumed:

  d64_bigdoor's frames are NOT ordered by brightness. Its ANIMDEFS is keyed on _0
  and runs _0 -> _2 -> _1 -> _2; _0 is its BRIGHTEST frame and _1 is dark. Taking
  "_2 = full" would have run its blink backwards.

  An EMPTY or ABSENT brightmap is an answer, not a miss. d64_beigedoor_0 ships an
  all-black one and d64_bigdoor_1 ships none, because both are the off frame.
  Falling through to a colour guess there invents a light on the one frame whose
  entire job is to be dark.

A SWITCH EARNS ITS ROW BY GETTING BRIGHTER. Only the `on` texture of a SWITCHES
pair is measured, and only if its lit energy actually beats the `off` frame's --
a plain lever with no lamp changes pose, not light, and gets nothing.

Usage:  py -3 tools\\gen_ue_fixture_lights.py --report   # measure and explain
        py -3 tools\\gen_ue_fixture_lights.py --write    # write the engine header
Output: sourcecode/gzdoom-rt/src/common/rendering/rt/rt_ue_fixture_lights.h
"""
from __future__ import annotations

import argparse
import colorsys
import re
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import export_unseenevil_textures_gallery as X  # WAD/pk3/composite decoding

PROJ_ROOT = Path(__file__).resolve().parents[1]
OUT = PROJ_ROOT / "sourcecode/gzdoom-rt/src/common/rendering/rt/rt_ue_fixture_lights.h"

# Animated door faces. The base name only; _0/_1/_2 are found and measured.
DOOR_FAMILIES = [
    "d64_greydoor",
    "d64_beigedoor",
    "d64_widedoor",
    "d64_talldoor",
    "d64_talldooralpha",
    "d64_exitdoor",
    "d64_bigdoor",
]

# Steady wall light strips.
STRIP_TEXTURES = [
    "d64_metal7",
    "d64_lite_thin",
    "d64_lite_wide",
    "d64_d1_lite4",
    "d64_d1liteblu1",
    "d64_d1litesuperthin",
    "d64_lite_blue",
    "d64_bronzewall_lit",
    "d64_silver2",
    "d64_d1_lite2",
    "d64_d1liteblu2",
    "d64_d1_lite96",
    "d64_d1_litemet",
    "d64_d1_litestone",
]

# Lit regions UE's own brightmaps omit, added by hand and only by hand:
# (texture, x0, x1, y0, y1) in texels, inclusive.
#
# d64_exitdoor's right-hand edge is a vertical stack of ten cream panels, lit,
# and none of it is in brightmaps/comp/d64_exitdoor_*. It is steady -- identical
# in _0, _1 and _2 -- so it is measured on _0, the frame the green gem is dark
# in, which makes it the light an exit door still gives off between blinks.
MANUAL_BANDS = [
    ("d64_exitdoor_0", 112, 126, 2, 70),
]

# A band under this share of the texture's lit texels is dropped: a stray
# highlight is not a fixture, and every extra row is a light in every room the
# texture appears in. 0.20 is what separates d64_bronzewall_lit's real bottom
# pair (0.55) from the two single-row specular glints on the bronze above it
# (0.14 each); every genuine multi-band texture here sits at 0.35 or more.
BAND_MIN_SHARE = 0.20
# Texel rows this far apart start a new band. 4 keeps a two-row strip together
# and still separates a door's gem from the bar below it.
BAND_GAP = 4
# The narrowest column gap worth cutting a band at -- see _split_band, which
# cuts only when a centroid lands off the paint, and then only at the widest gap
# available. d64_brickwarn's two wedges are 3 columns apart, so anything above 3
# would leave their shared centroid on the dark plate between them.
X_GAP = 2
# Separate lamps kept per texture. Raised from 3 when bands began splitting
# horizontally as well: a lever switch is legitimately a bar plus two wedges.
BAND_MAX = 6
# A horizontal cluster must be this share of its OWN band to count. Splitting a
# band into two halves each of them, so this is deliberately well below
# BAND_MIN_SHARE, which is measured against the whole texture.
CLUSTER_MIN_SHARE = 0.15

# Saturation handling for a measured light colour -- see hue_hex. SAT_GAIN
# multiplies HSV saturation (hue and value untouched, so a hue can never move);
# SAT_LIFT_MIN is the saturation a fixture must already show before any of it is
# applied, so white fixtures stay white. 0.25 sits above d64_lite_thin (0.15) and
# d64_silver2 (0.11), which are warm whites, and below d64_greydoor and
# d64_lite_blue, both around 0.51.
SAT_GAIN = 1.5
SAT_LIFT_MIN = 0.25


# ----------------------------------------------------------------- resources

def build_ue():
    d2p = X.find_iwad("doom2.wad")
    if d2p is None:
        sys.exit("no doom2.wad found -- see launch-unseenevil-rt.cmd")
    d2 = X.IwadTextures(X.Wad(d2p.read_bytes()), "DOOM2")
    ue = X.UeTextures(X.PK3, d2.pal)
    X.IWAD_FALLBACK = lambda n: (
        d2.render_wall(n) if d2.has(n, "wall")
        else d2.render_flat(n) if d2.has(n, "flat") else None
    )
    return ue


MATERIAL_RE = re.compile(r'material\s+texture\s+"([^"]+)"\s*\{([^}]*)\}', re.I | re.S)
BRIGHTMAP_RE = re.compile(r'brightmap\s+"([^"]+)"', re.I)
SWITCH_RE = re.compile(r"^\s*switch\s+(\S+)\s+on\s+pic\s+(\S+)", re.I | re.M)


def base(name: str) -> str:
    n = name.rsplit("/", 1)[-1]
    return (n.rsplit(".", 1)[0] if "." in n else n).lower()


def read_brightmaps(ue) -> dict[str, str]:
    out: dict[str, str] = {}
    for n in ue.zip.namelist():
        if not n.upper().startswith("GLDEFS"):
            continue
        text = X.strip_comments(ue.zip.read(n).decode("utf-8", "replace"))
        for m in MATERIAL_RE.finditer(text):
            bm = BRIGHTMAP_RE.search(m.group(2))
            if bm:
                out.setdefault(base(m.group(1)), bm.group(1))
    return out


def read_switches(ue) -> list[tuple[str, str]]:
    """(off, on) names from every ANIMDEFS.* lump."""
    pairs = []
    for n in ue.zip.namelist():
        if not n.upper().startswith("ANIMDEFS"):
            continue
        text = X.strip_comments(ue.zip.read(n).decode("utf-8", "replace"))
        for m in SWITCH_RE.finditer(text):
            pairs.append((m.group(1).strip('"'), m.group(2).strip('"')))
    return pairs


def render(ue, name: str) -> Image.Image | None:
    key = ue.resolve(name)
    return ue.render(key) if key else None


def full_path(ue, name: str) -> str:
    """The name as the pk3 stores it -- what GetName() may hand the engine."""
    k = ue.resolve(name)
    if not k:
        return name
    return k[4:] if k.startswith("def:") else k[5:]


# -------------------------------------------------------------- measurement

def lit_mask(ue, albedo: Image.Image, bmpath: str | None, force: str | None = None):
    """(mask, source) for the self-lit texels of one texture.

    `force` pins the method so every frame of an animated family is measured the
    same way. Without it, one frame finding a brightmap and the next falling
    through to a colour guess makes their energies incomparable, and the blink
    amplitudes derived from them are nonsense.
    """
    a = np.asarray(albedo)
    if force == "brightmap" and not bmpath:
        # No brightmap on a family measured from brightmaps = the artist saying
        # this frame is dark. See the module docstring's second trap.
        return np.zeros(a.shape[:2], dtype=bool), "brightmap"
    if bmpath and force in (None, "brightmap"):
        bm = render(ue, bmpath)
        if bm is not None:
            if bm.size != albedo.size:
                bm = bm.resize(albedo.size, Image.NEAREST)
            b = np.asarray(bm)
            # A brightmap marks lit texels by being non-black; its own colour is
            # a mask, not a hue, so only its level is read here.
            m = (b[..., 3] > 0) & (b[..., :3].max(axis=2) > 24)
            if m.sum() or force == "brightmap":
                return m, "brightmap"
    r, g, bl = (a[..., i].astype(int) for i in range(3))
    al = a[..., 3]
    green = (al > 0) & (g > 90) & (g > r + 30) & (g > bl + 30)
    if green.sum() and force in (None, "green"):
        return green, "green"
    # Last resort. Relative to the texture's OWN peak, not an absolute level: an
    # absolute threshold picks up pale metal on a light wall and misses a dim
    # lamp on a dark one.
    lum = a[..., :3].mean(axis=2)
    peak = float(lum.max()) if lum.size else 0.0
    bright = (al > 0) & (lum >= max(0.82 * peak, 150.0))
    return bright, "bright"


def energy(mask, albedo: Image.Image) -> float:
    a = np.asarray(albedo).astype(float)
    ys, xs = np.nonzero(mask)
    return float(a[ys, xs, :3].sum()) if len(ys) else 0.0


def hue_hex(albedo: Image.Image, mask) -> str:
    """The colour of the light, taken from the SATURATED part of the lamp.

    A flat average over the lit mask is the trap RT_KeyTrimHue already documents
    for the key doors: "the trim art is mostly dark metal around a coloured inlay,
    so an averaged colour comes out grey and defeats the entire purpose". A lamp
    has the same problem from the other end -- an LED is painted as a blown-out
    near-WHITE core inside a saturated rim, so averaging the two gives a pale
    wash. Normalising that to max=1 does not rescue it: #7eff7e still carries 50%
    white, and at any intensity a path tracer will render it as a white light.
    That is exactly the report this replaced: "the lights on that door are white,
    not green".

    So texels are weighted by their own saturation before averaging, which lets
    the rim decide the hue and the core contribute almost nothing. A genuinely
    colourless fixture -- d64_exitdoor's cream panel stack, every white strip --
    has no saturated texels to find, so the weights collapse and it falls back to
    the plain average and stays white, which is correct for it.
    """
    a = np.asarray(albedo).astype(float)
    ys, xs = np.nonzero(mask)
    if not len(ys):
        return "ffffff"
    px = a[ys, xs, :3]
    mx = px.max(axis=1)
    mn = px.min(axis=1)
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1.0), 0.0)
    # Squared, so a rim texel at 0.8 saturation outvotes a core texel at 0.1 by
    # 64:1 rather than 8:1.
    w = sat ** 2
    if w.sum() > 1e-3:
        r, g, b = (px * w[:, None]).sum(axis=0) / w.sum()
    else:
        r, g, b = px.mean(axis=0)
    m = max(r, g, b)
    if m <= 0:
        return "ffffff"
    c = [v / m for v in (r, g, b)]

    # THEN RAISE THE SATURATION, because a light's colour is not the paint's
    # colour. Saturation weighting alone moved d64_greydoor from #7eff7e only as
    # far as #76ff76 -- the whole indicator is painted pale, there is no saturated
    # rim to find, and a colour that is 46% white renders as a white light at any
    # intensity. The paint is pale because the lamp is drawn blown out on screen,
    # not because it emits white. RT_KeyTrimHue reaches the same conclusion by
    # hand: "an averaged colour comes out grey and defeats the entire purpose."
    #
    # IN HSV, AND THAT MATTERS. The first version subtracted a share of the
    # achromatic component per channel, which does not just saturate a colour --
    # it SHIFTS ITS HUE. d64_lite_blue's pale sky blue (124,174,255) came out
    # (24,106,255): most of its green gone and the hue dragged toward pure blue.
    # The report was "too blue not enough green", and it was exactly right.
    # Scaling S with H and V untouched cannot move a hue at all, so the blue
    # strip keeps its cyan cast and the door indicators still go green.
    #
    # GATED ON THE MEASURED SATURATION so it cannot invent a colour: below the
    # threshold a fixture is genuinely white and is left as measured, or the same
    # maths turns d64_lite_thin's warm white (0.15) into orange.
    hh, ss, vv = colorsys.rgb_to_hsv(*c)
    if ss >= SAT_LIFT_MIN:
        ss = min(1.0, ss * SAT_GAIN)
        c = list(colorsys.hsv_to_rgb(hh, ss, vv))
    return "%02x%02x%02x" % tuple(int(round(min(255.0, max(0.0, v) * 255.0))) for v in c)


def _runs(indices, gap: int) -> list[list[int]]:
    """Group sorted indices into runs separated by more than `gap`."""
    if not len(indices):
        return []
    out: list[list[int]] = [[int(indices[0])]]
    for v in indices[1:]:
        if int(v) - out[-1][-1] <= gap:
            out[-1].append(int(v))
        else:
            out.append([int(v)])
    return out


def _split_band(band, w: int, depth: int = 0) -> list[tuple[int, int]]:
    """Column ranges for one row band, split ONLY where a centroid would lie.

    Splitting a band at every column gap is the obvious approach and it is
    wrong: d64_beigedoor's indicator is two groups of three small ticks, and
    cutting between every tick turned one indicator into five lights, which then
    hit the per-texture cap and dropped one of them at random.

    A lamp group only needs splitting when its centroid does not land on it --
    that is the entire defect, and it is directly testable. So: measure the
    centroid; if it sits on lit paint the group is one lamp and stays whole; if
    it sits in a gap, cut at the WIDEST gap and re-ask of each half. Bounded at
    two cuts, so a band yields at most four lamps and a pathological texture
    cannot explode into a light per texel.
    """
    xs = np.nonzero(band.any(axis=0))[0]
    if not len(xs):
        return []
    lo, hi = int(xs[0]), int(xs[-1])
    if depth >= 2:
        return [(lo, hi)]

    ys2, xs2 = np.nonzero(band)
    cx = int(round(float(xs2.mean())))
    cy = int(round(float(ys2.mean())))
    # THE SAME TEST THE REPORT USES, at the centroid POINT rather than anywhere
    # in its column. Testing the whole column let a lamp elsewhere in the band
    # vouch for a centroid sitting in a gap -- d64_brickwarn has a small centre
    # element a few rows above its two wedges, which was enough to answer "on
    # paint" for a point that plainly was not, so the band never split and the
    # check downstream flagged it. Two tests of the same property must not be
    # allowed to disagree.
    if band[max(0, cy - 1): cy + 2, max(0, cx - 1): cx + 2].any():
        return [(lo, hi)]

    runs = _runs(xs, 1)
    if len(runs) < 2:
        return [(lo, hi)]
    widest, at = -1, None
    for a, b in zip(runs, runs[1:]):
        gap = b[0] - a[-1]
        if gap > widest:
            widest, at = gap, (a[-1], b[0])
    if at is None or widest < X_GAP:
        return [(lo, hi)]

    left = band.copy()
    left[:, at[0] + 1:] = False
    right = band.copy()
    right[:, : at[1]] = False
    return _split_band(left, w, depth + 1) + _split_band(right, w, depth + 1)


def bands(mask, albedo: Image.Image, split_x: bool = True):
    """Split a mask into the separate LAMPS it contains.

    Rows first, then -- for anything that is not a tiling strip -- columns
    WITHIN each row band, because a centroid is only a light position when the
    thing it averages is one lamp.

    THE HORIZONTAL SPLIT IS NOT COSMETIC. Every lever switch here paints its
    lower element as TWO small wedges, one at each side of the housing. Averaged
    together they give a centroid in the dark gap between them -- so the light
    was placed below the visible green bar, on unpainted plate, which is exactly
    the "white light lower than the green square" this fixed. It is the same
    failure the ceiling lattice already documents for SFLATC: "perimeter lights
    land between bulbs, in the middle of blank plate, and read as light coming
    from nowhere."

    A tiling strip is exempt (`split_x=False`): its light is a chain along the
    whole sidedef, so where in the texture it starts does not matter, and
    splitting one would only multiply identical chains.
    """
    h, w = mask.shape
    total = float(mask.sum())
    if total == 0:
        return []

    out = []
    for grp in _runs(np.nonzero(mask.any(axis=1))[0], BAND_GAP):
        band = np.zeros_like(mask)
        band[grp[0]: grp[-1] + 1, :] = mask[grp[0]: grp[-1] + 1, :]
        bandn = float(band.sum())
        if bandn == 0 or bandn / total < BAND_MIN_SHARE:
            continue

        cols = _split_band(band, w) if split_x else [(0, w - 1)]

        for cg in cols:
            sub = np.zeros_like(band)
            sub[:, cg[0]: cg[1] + 1] = band[:, cg[0]: cg[1] + 1]
            n = float(sub.sum())
            # Measured against its OWN band, not the whole texture: splitting a
            # band in two halves the share of each, and a threshold applied to
            # the texture total would throw both away.
            if n == 0 or n / bandn < CLUSTER_MIN_SHARE:
                continue
            ys, xs = np.nonzero(sub)
            cx, cy = float(xs.mean()) + 0.5, float(ys.mean()) + 0.5
            # LAST RESORT: SNAP ONTO THE LAMP.
            #
            # Splitting fixes a group whose halves sit either side of one gap.
            # It cannot fix a REGULAR ROW -- d64_exitdoor's lower strip is a row
            # of evenly spaced cells, every gap the same width, so cutting at
            # "the widest" is arbitrary and each half has the same shape as the
            # whole. That row is one bar of light and should stay one lamp, so
            # the centroid is simply moved to the nearest lit texel in the
            # cluster. It shifts the light by a texel or two along a fixture it
            # was already on, which is the smallest correction available and
            # keeps the invariant absolute: every light sits on painted lamp.
            snapped = False
            if split_x and not sub[max(0, int(cy) - 1): int(cy) + 2,
                                   max(0, int(cx) - 1): int(cx) + 2].any():
                d = (xs - (cx - 0.5)) ** 2 + (ys - (cy - 0.5)) ** 2
                k = int(np.argmin(d))
                cx, cy = float(xs[k]) + 0.5, float(ys[k]) + 0.5
                snapped = True
            # A CENTROID IS ONLY A LIGHT POSITION IF IT LANDS ON THE LAMP.
            # Averaging two lamps that sit either side of a gap puts the light
            # in the gap, on unpainted plate, which is what the horizontal split
            # above exists to prevent. This is the assertion that it worked, and
            # the one that will catch the next texture the splitter cannot
            # separate -- checked within one texel, since a centroid can sit on
            # the boundary of a lamp that is an even number of texels wide.
            # Only meaningful where cx is actually used to place the light. A
            # tiling strip is a chain stepped along the sidedef at a fixed
            # interval and never consults cx, so a band whose horizontal centre
            # falls between two lit runs is not a defect there.
            on = ( not split_x ) or bool(
                sub[max(0, int(cy) - 1): int(cy) + 2,
                    max(0, int(cx) - 1): int(cx) + 2].any() )
            _ = snapped
            out.append({
                "cx": cx, "cy": cy,
                "w": w, "h": h, "lit": int(n), "share": n / total,
                "rgb": hue_hex(albedo, sub),
                # The lamp's extent. For a point fixture it is informational; for
                # a strip it is the whole answer -- the engine lights a strip
                # along its LONG axis, so a 16x128 vertical tube gets a column of
                # lights up the wall and a 64x7 bar gets a row along it.
                "x0": int(xs.min()), "x1": int(xs.max()),
                "y0": int(ys.min()), "y1": int(ys.max()),
                "on_paint": bool(on), "snapped": snapped,
            })

    out.sort(key=lambda b: -b["share"])
    out = out[:BAND_MAX]
    out.sort(key=lambda b: (b["cy"], b["cx"]))
    return out


def row(ue, tex, band, scale, src, kind):
    return {"tex": tex, "path": full_path(ue, tex), "kind": kind, "src": src,
            "scale": scale, **band}


# --------------------------------------------------------------------- main

def measure(ue, bmaps):
    rows: list[dict] = []

    # ---- doors: one row per LIT frame, keyed on that frame's own name
    for fam in DOOR_FAMILIES:
        imgs = {f: render(ue, f"{fam}_{f}") for f in (0, 1, 2)}
        imgs = {f: im for f, im in imgs.items() if im is not None}
        if not imgs:
            print(f"WARNING: {fam} resolved no frames", file=sys.stderr)
            continue
        method = None
        for f in sorted(imgs, reverse=True):
            _, method = lit_mask(ue, imgs[f], bmaps.get(f"{fam}_{f}"))
            if method == "brightmap":
                break
        frames = {}
        for f, im in sorted(imgs.items()):
            m, src = lit_mask(ue, im, bmaps.get(f"{fam}_{f}"), method)
            frames[f] = (im, m, src, energy(m, im))
        peak = max(e for _, _, _, e in frames.values()) or 1.0
        for f, (im, m, src, e) in sorted(frames.items()):
            scale = e / peak
            if scale < 0.02:
                continue  # dark frame: no row, hence no light, hence the blink
            for b in bands(m, im):
                rows.append(row(ue, f"{fam}_{f}", b, scale, src, "door"))

    # ---- steady strips
    for tex in STRIP_TEXTURES:
        im = render(ue, tex)
        if im is None:
            print(f"WARNING: {tex} did not resolve", file=sys.stderr)
            continue
        m, src = lit_mask(ue, im, bmaps.get(tex))
        if not m.sum():
            print(f"WARNING: {tex} has no lit texels", file=sys.stderr)
            continue
        for b in bands(m, im, split_x=False):
            rows.append(row(ue, tex, b, 1.0, src, "strip"))

    # ---- switches: the ON frame only, and only if it actually gets brighter
    for off, on in read_switches(ue):
        onim, offim = render(ue, on), render(ue, off)
        if onim is None or offim is None:
            continue
        mon, src = lit_mask(ue, onim, bmaps.get(base(on)))
        moff, _ = lit_mask(ue, offim, bmaps.get(base(off)), src)
        if not mon.sum():
            continue
        if energy(mon, onim) <= energy(moff, offim) * 1.05:
            continue  # changes pose, not light
        for b in bands(mon, onim):
            rows.append(row(ue, base(on), b, 1.0, src, "switch"))

    # ---- hand-added regions the mod's brightmaps omit
    for tex, x0, x1, y0, y1 in MANUAL_BANDS:
        im = render(ue, tex)
        if im is None:
            continue
        a = np.asarray(im)
        m = np.zeros(a.shape[:2], dtype=bool)
        m[y0:y1 + 1, x0:x1 + 1] = True
        m &= (a[..., 3] > 0) & (a[..., :3].mean(axis=2) >= 150.0)
        if not m.sum():
            print(f"WARNING: manual band on {tex} is empty", file=sys.stderr)
            continue
        for b in bands(m, im, split_x=False):
            rows.append(row(ue, tex, b, 1.0, "manual", "strip"))

    return rows


def emit(rows) -> str:
    L: list[str] = []
    a = L.append
    a("// GENERATED by tools/gen_ue_fixture_lights.py -- do not edit by hand.")
    a("//")
    a("// One row per LIT wall face in Doom 64: Unseen Evil -- a door indicator on a")
    a("// frame it is actually lit on, a switch lamp in its ON texture, a light strip.")
    a("// The layout matches RtSwitchLight so RT_UploadSwitchLights can peg both the")
    a("// same way: position is the centroid of the lit mask in TEXEL space from the")
    a("// top-left, colour is that mask's hue at full saturation, `lit` is its texel")
    a("// count. `scale` is the one thing RtSwitchLight has no field for: a door's mid")
    a("// frame is the same lamp at part brightness, and without it a three-step pulse")
    a("// collapses into on/off.")
    a("//")
    a("// A STRIP IS LIT ALONG ITS LONG AXIS, and x0..y1 is how the engine knows")
    a("// which axis that is. d64_lite_thin is a 16x128 VERTICAL tube: a chain run")
    a("// along the wall put its lights side by side on a 16-unit line -- and, with")
    a("// the first light half a segment in, put NONE on a line shorter than that,")
    a("// which is every one of MAP01's. Lit up the wall instead, it is a column of")
    a("// three. d64_metal7's 64x7 bar is the other case and is lit along the wall.")
    a("//")
    a("// `band` SPLITS THE TWO SHAPES OF FIXTURE, and it is the family, not a")
    a("// measurement: a door indicator and a switch lamp are ONE object on one")
    a("// sidedef, while a light strip is wall art that TILES along the whole line.")
    a("// A strip lit as a single sphere reads as somebody dropping a dynamic point")
    a("// light on the wall -- which is exactly what it looked like -- so strips are")
    a("// walked as a chain of overlapping spheres instead, the way")
    a("// RT_UploadWallStripLights already does it. RTGL1 leaves no better option:")
    a("// an emissive surface casts no light at all, and RgLightPolygonalEXT is")
    a("// compiled out behind #if TRIANGLE_LIGHTS and hard-errors on upload.")
    a("//")
    a("// WHICH FRAME IS LIT IS NEVER ASSUMED. A row exists only where the art carries")
    a("// a lit mask, so a frame with no row emits nothing -- that IS the blink, and it")
    a("// is also why a switch lights only once thrown. See the generator's docstring")
    a("// for the two families this catches out.")
    a("#pragma once")
    a("")
    a("struct RtUeFixtureLight")
    a("{")
    a("    const char* tex;    // texture name as the engine sees it, UPPERCASE")
    a("    float       tw, th; // texture size in texels")
    a("    float       cx, cy; // lit centroid, texels from the TOP-left")
    a("    int         lit;    // lit texel count")
    a("    unsigned    rgb;    // 0xRRGGBB")
    a("    float       scale;  // this frame's brightness against the family's peak")
    a("    bool        band;   // a tiling wall strip, lit as a CHAIN, not a single sphere")
    a("    int         x0, x1; // lit extent in texels, inclusive -- a strip is lit along")
    a("    int         y0, y1; //   its LONG axis, and this is what says which axis that is")
    a("};")
    a("")
    a("// TWO KEYS PER FIXTURE, AND THE SECOND ONE IS NOT BELT-AND-BRACES -- it is the")
    a("// only key most of these can ever be found by.")
    a("//")
    a("// GZDoom fills FGameTexture::Name only for a pk3 texture whose basename fits")
    a("// the classic 8 characters. Unseen Evil's art mostly does not: C201 and SPACEAU")
    a("// out of textures/d64/ arrive named, while d64_metal7, d64_talldoor_2 and")
    a("// d64_greydoor_0 arrive with an EMPTY name and are reachable only through the")
    a("// file they came from. Its TEXTURES composites are a third case: their name is")
    a("// the declared path (\"textures/comp/d64_exitdoor_2\"), extension and all absent.")
    a("//")
    a("// Keyed on the name alone, this table matched exactly the composites -- every")
    a("// switch, and the exit door -- and silently missed every plain PNG, which is")
    a("// most of the doors and all fourteen light strips. It looked like the feature")
    a("// half-working rather than like a lookup failure. RT_UeFixtureLightFor falls")
    a("// back to fileSystem.GetFileFullName(), which is what the path rows below match.")
    keys: list[tuple[str, dict]] = []
    for r in rows:
        for k in sorted({r["tex"].upper(), r["path"].upper()}):
            keys.append((k, r))
    a(f"constexpr int RT_UE_FIXTURE_LIGHT_COUNT = {len(keys)};")
    a("")
    a("constexpr RtUeFixtureLight RT_UE_FIXTURE_LIGHTS[ RT_UE_FIXTURE_LIGHT_COUNT ] = {")
    last = None
    for k, r in keys:
        if r["kind"] != last:
            a(f'    // ---- {r["kind"]}')
            last = r["kind"]
        a(f'    {{ "{k}", {r["w"]}.f, {r["h"]}.f, {r["cx"]:.2f}f, {r["cy"]:.2f}f, '
          f'{r["lit"]}, 0x{r["rgb"]}u, {r["scale"]:.3f}f, '
          f'{"true" if r["kind"] == "strip" else "false"}, '
          f'{r["x0"]}, {r["x1"]}, {r["y0"]}, {r["y1"]} }},')
    a("};")
    return "\n".join(L) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    ue = build_ue()
    rows = measure(ue, read_brightmaps(ue))
    rows.sort(key=lambda r: (r["kind"], r["tex"], r["cy"]))

    floating = [r for r in rows if not r.get("on_paint", True)]
    for r in floating:
        print(f'WARNING: {r["tex"]} lamp at ({r["cx"]:.1f},{r["cy"]:.1f}) is NOT on a '
              f'lit texel -- the light will sit on unpainted wall', file=sys.stderr)
    snapped = [r for r in rows if r.get("snapped")]
    for r in snapped:
        print(f'  note: {r["tex"]} lamp snapped onto the nearest lit texel at '
              f'({r["cx"]:.1f},{r["cy"]:.1f}) -- a regular row of cells, see _split_band')

    if args.report:
        print("=== measured " + "=" * 68)
        for r in rows:
            print(f'{r["tex"]:28s} {r["kind"]:6s} {r["src"]:9s} '
                  f'{r["w"]:3d}x{r["h"]:<3d} y{r["y0"]:3d}..{r["y1"]:<3d} '
                  f'c({r["cx"]:6.2f},{r["cy"]:6.2f}) lit{r["lit"]:5d} '
                  f'share {r["share"]:.2f} scale {r["scale"]:.2f} #{r["rgb"]}')
        print()

    out = emit(rows)
    print(f"{len(rows)} lamps, {len(rows) - len(floating)} of them centred on lit paint")
    if args.write:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(out, encoding="utf-8")
        print(f"wrote {OUT}  ({len(rows)} fixtures)")
    else:
        print(out)


if __name__ == "__main__":
    main()
