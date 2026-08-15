"""
Convert an AI-painted mugshot sheet into game-ready STF* face lumps.

The source sheets (tools/mugshot-art/doomguy_grittry.png) follow the vanilla mugshot layout:
8 columns of expressions across, 5 health tiers down, then DEAD/GOD on row 6.

    col  0     1     2     3     4     5     6     7
         EVL   KILL  OUCH  ST0   ST1   ST2   TL    TR
    row  0..4 = health tier (0 = healthiest), row 5 = DEAD, GOD

Each frame is fitted to the footprint of the vanilla lump it replaces, so the
head does not jitter between frames and lands where the HUD expects it. The
painted art is ~130px tall and very dark; getting it to read at 24x29 needs, in
order: grain removal BEFORE downscaling (a median, so edges survive), a
white-balance onto the vanilla skin tone (per-channel gain, which keeps red
warpaint red), a luminance stretch onto the vanilla range, and only then the
box downscale and PLAYPAL quantize.

Usage:
    py -3 tools/gen_mugshot.py --sheet tools/mugshot-art/doomguy_grittry.png --out <dir>
    py -3 tools/gen_mugshot.py ... --only STFST01,STFEVL0,STFST41
"""

import argparse
import os
import struct
from collections import deque

import numpy as np
from PIL import Image, ImageFilter

IWAD = r"D:\Games\GZDoom\doom2.wad"

# Column -> lump-name builder. `t` is the health tier digit.
COLUMNS = [
    lambda t: f"STFEVL{t}",
    lambda t: f"STFKILL{t}",
    lambda t: f"STFOUCH{t}",
    lambda t: f"STFST{t}0",
    lambda t: f"STFST{t}1",
    lambda t: f"STFST{t}2",
    lambda t: f"STFTL{t}0",
    lambda t: f"STFTR{t}0",
]
LAST_ROW = ["STFDEAD0", "STFGOD0"]


def wad_lumps(path):
    f = open(path, "rb")
    _, n, off = struct.unpack("<4sii", f.read(12))
    f.seek(off)
    d = f.read(n * 16)
    table = {}
    for i in range(n):
        fp, sz, nm = struct.unpack("<ii8s", d[i * 16:i * 16 + 16])
        table.setdefault(nm.decode("latin1").rstrip("\0").upper(), (fp, sz))
    return f, table


def read_iwad():
    """Return (PLAYPAL, {name: (rgba array, (xoff, yoff))}) for every STF* lump."""
    f, table = wad_lumps(IWAD)

    def rd(nm):
        fp, sz = table[nm]
        f.seek(fp)
        return f.read(sz)

    pal = np.frombuffer(rd("PLAYPAL")[:768], dtype=np.uint8).reshape(256, 3).astype(int)

    def decode(nm):
        b = rd(nm)
        w, h, lo, to = struct.unpack("<hhhh", b[:8])
        cols = struct.unpack("<%di" % w, b[8:8 + 4 * w])
        img = np.zeros((h, w, 4), np.uint8)
        for x in range(w):
            p = cols[x]
            while b[p] != 0xFF:
                top, ln = b[p], b[p + 1]
                p += 3
                for y in range(ln):
                    yy = top + y
                    if 0 <= yy < h:
                        img[yy, x, :3] = pal[b[p + y]]
                        img[yy, x, 3] = 255
                p += ln + 1
        return img, (lo, to)

    faces = {nm: decode(nm) for nm in table if nm.startswith("STF") and not nm.startswith("STFB")}
    return pal, faces


def components(m, min_area=1):
    """All connected blobs in `m`, largest first, as boolean masks."""
    h, w = m.shape
    seen = np.zeros((h, w), bool)
    found = []
    for sy in range(h):
        for sx in range(w):
            if not m[sy, sx] or seen[sy, sx]:
                continue
            comp = []
            q = deque([(sy, sx)])
            seen[sy, sx] = True
            while q:
                y, x = q.popleft()
                comp.append((y, x))
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < h and 0 <= nx < w and m[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        q.append((ny, nx))
            if len(comp) >= min_area:
                out = np.zeros((h, w), bool)
                ys, xs = zip(*comp)
                out[list(ys), list(xs)] = True
                found.append((len(comp), out))
    found.sort(key=lambda t: -t[0])
    return [f[1] for f in found]


def row_heads(sheet_rgb, row, rows=6, expect=8, dark=10, min_area=1500, alpha=None):
    """Locate the heads in one row of the sheet as (mask, bbox) pairs, left to
    right. A uniform grid does not work: the painted rows drift by up to half a
    head, which slices a face down the middle and stitches in its neighbour."""
    H = sheet_rgb.shape[0]
    rh = H / rows
    y0, y1 = int(round(row * rh)), int(round((row + 1) * rh))
    if alpha is not None:
        # A background-removed sheet already carries the silhouette; trust it
        # rather than re-thresholding dark paint against a dark background.
        head = alpha[y0:y1] > 128
    else:
        head = sheet_rgb[y0:y1].sum(2) > dark
    hi = Image.fromarray((head * 255).astype(np.uint8))
    hi = hi.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.MinFilter(5))
    head = np.array(hi) > 127
    blobs = [b for b in components(head, min_area)][:expect]
    if len(blobs) != expect:
        print(f"  WARNING: row {row} found {len(blobs)} heads, expected {expect}")
    out = []
    for b in blobs:
        ys, xs = np.where(b)
        by0, by1, bx0, bx1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
        out.append((b[by0:by1, bx0:bx1], (bx0, y0 + by0, bx1, y0 + by1)))
    out.sort(key=lambda t: t[1][0])
    return out


def split_blob(mask, k):
    """Cut a blob holding k touching heads into k pieces at its narrowest
    columns, searching near each evenly-spaced guess."""
    # Work in the blob's own column range; the mask spans the whole row band,
    # so using its full width would place every cut outside the blob.
    xs = np.where(mask.any(0))[0]
    x0, x1 = int(xs.min()), int(xs.max()) + 1
    w = x1 - x0
    colsum = mask.sum(0)
    cuts = []
    for i in range(1, k):
        guess = x0 + round(i * w / k)
        win = max(2, round(w / (4 * k)))
        lo, hi = max(x0 + 1, guess - win), min(x1 - 1, guess + win)
        cuts.append(lo + int(np.argmin(colsum[lo:hi])) if hi > lo else guess)
    bounds = [x0] + sorted(cuts) + [x1]
    out = []
    for a, b in zip(bounds, bounds[1:]):
        if b - a < 2:
            continue
        piece = np.zeros_like(mask)
        piece[:, a:b] = mask[:, a:b]
        if piece.any():
            out.append(piece)
    return out


def grow_hair(blob, alpha, strict, soft=100, iters=3):
    """Hysteresis: extend a head into adjacent SOFTER alpha, upper half only.

    The strict threshold is what keeps neighbouring heads apart, but it also
    shaves the top of the hair, because that is exactly where the cut-out went
    semi-transparent. Two frames showed it plainly: STFEVL0's crown sits at
    alpha ~124 and was simply excluded, and STFGOD0's is opaque (248) but
    DETACHED, so the largest-component pick dropped it. Both rendered with a
    flat, chopped skull.

    Growth is limited to rows above the blob's vertical midpoint so it cannot
    reach the removebg drop shadow, which sits under the chin and is the reason
    the strict threshold exists in the first place."""
    ys, xs = np.where(blob)
    mid = (ys.min() + ys.max()) // 2
    soft_px = (alpha > soft)
    cur = blob.copy()
    h, w = blob.shape
    for _ in range(iters):
        # UPWARD only. Growing sideways as well sprouted stray nubs off the
        # ears, and every extra row of mask height makes the aspect-preserving
        # fit scale the whole head down - so this stays as small as it can be
        # while still rounding the crown.
        # up[y] must be true where the mask exists at y+1, i.e. the row ABOVE
        # the current edge. Writing up[1:] = cur[:-1] marks the row BELOW and
        # silently does nothing here, since growth is capped to the upper half.
        up = np.zeros_like(cur)
        up[:-1] = cur[1:]
        band = np.zeros_like(cur)
        band[:mid] = True
        add = up & soft_px & band & ~cur
        if not add.any():
            break
        cur |= add
    return cur


def segment_sheet(sheet_rgb, alpha=None, rows=6, dark=10, min_area=400, alpha_thr=200):
    """Locate every head in the sheet as its own connected blob.

    Deliberately does NOT slice the sheet into six equal bands first. The rows
    drift vertically, so a band edge cuts through heads: the chin gets sliced
    off one face while the top of the head below leaks into its neighbour's
    crop. Segmenting the whole sheet at once avoids both.

    `alpha_thr` matters. The cut-out sheet keeps a semi-transparent drop shadow
    under many heads; at >128 the shadow joins the head (and two heads merge
    through it), at >200 the sheet resolves into exactly 42 clean blobs and the
    shadow is excluded for free.

    Rows are then recovered from the blob centroids by cutting at the five
    largest vertical gaps, rather than assumed from geometry."""
    if alpha is not None:
        mask = alpha > alpha_thr
    else:
        mask = sheet_rgb.sum(2) > dark
        mi = Image.fromarray((mask * 255).astype(np.uint8))
        mi = mi.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.MinFilter(5))
        mask = np.array(mi) > 127

    blobs = components(mask, min_area)
    if not blobs:
        raise SystemExit("no heads found in sheet")

    if alpha is not None:
        blobs = [grow_hair(b, alpha, alpha_thr) for b in blobs]

    info = []
    for b in blobs:
        ys, xs = np.where(b)
        info.append((float(ys.mean()), float(xs.mean()), b,
                     (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)))
    info.sort(key=lambda t: t[0])

    gaps = sorted(range(1, len(info)), key=lambda i: info[i][0] - info[i - 1][0], reverse=True)
    cuts = sorted(gaps[:rows - 1])
    bounds = [0] + cuts + [len(info)]

    out = {}
    for r, (a, b_) in enumerate(zip(bounds, bounds[1:])):
        band = sorted(info[a:b_], key=lambda t: t[1])
        expect = 8 if r < 5 else 2
        if len(band) != expect:
            print(f"  WARNING: row {r} found {len(band)} heads, expected {expect}")
        heads = []
        for _, _, blob, box in band:
            x0, y0, x1, y1 = box
            heads.append((blob[y0:y1, x0:x1], box))
        out[r] = heads
    return out


def background_mask(rgb, dark=10):
    """True where the cell is head. Flood-fills the dark background in from the
    border, so shadowed cheeks and hair stay part of the head. `dark` is the
    RGB *sum* - the painted art is dark enough that a per-channel threshold
    swallows the cheeks and the fill eats the whole face."""
    h, w, _ = rgb.shape
    dark_px = rgb.sum(2) <= dark
    bg = np.zeros((h, w), bool)
    q = deque()
    for x in range(w):
        for y in (0, h - 1):
            if dark_px[y, x] and not bg[y, x]:
                bg[y, x] = True
                q.append((y, x))
    for y in range(h):
        for x in (0, w - 1):
            if dark_px[y, x] and not bg[y, x]:
                bg[y, x] = True
                q.append((y, x))
    while q:
        y, x = q.popleft()
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w and dark_px[ny, nx] and not bg[ny, nx]:
                bg[ny, nx] = True
                q.append((ny, nx))
    m = Image.fromarray((~bg * 255).astype(np.uint8))
    # close pinholes, then shave the 1px dark halo the painter left around each head
    m = m.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.MinFilter(5))
    return largest_component(np.array(m) > 127)


def bleed_outward(a, m, iters=6):
    """Push head colour into the background before downscaling. Without this the
    box filter averages edge pixels against the near-black background and every
    frame picks up a dark fringe that reads as a bad cut-out at 24x29."""
    a = a.copy()
    m = m.copy()
    for _ in range(iters):
        if m.all():
            break
        pad = np.pad(a, ((1, 1), (1, 1), (0, 0)), mode="edge")
        padm = np.pad(m, 1, mode="constant", constant_values=False).astype(float)
        acc = np.zeros_like(a)
        cnt = np.zeros(m.shape, float)
        for dy, dx in ((1, 1), (1, 0), (1, 2), (0, 1), (2, 1)):
            acc += pad[dy:dy + m.shape[0], dx:dx + m.shape[1]] * padm[dy:dy + m.shape[0], dx:dx + m.shape[1], None]
            cnt += padm[dy:dy + m.shape[0], dx:dx + m.shape[1]]
        grow = (~m) & (cnt > 0)
        a[grow] = (acc[grow] / cnt[grow][:, None])
        m = m | grow
    return a


def common_canvas(faces, pad=0):
    """Vanilla keeps frames of different sizes aligned through their grAb
    offsets, but SBARINFO's DrawGraphic treats x,y as the top-left and ignores
    offsets unless CENTER is set. So every frame is composited onto one shared
    canvas whose geometry reproduces the offset alignment, and the HUD can then
    draw all 42 at a single fixed position.

    Returns (canvas_w, canvas_h, {name: (paste_x, paste_y)})."""
    rects = {}
    for nm, (rgba, (lo, to)) in faces.items():
        # STFB0..3 are the 35x31 multiplayer background, not mugshot frames -
        # letting them into the union inflates the canvas by 7px of dead space
        if nm.startswith("STFB"):
            continue
        h, w = rgba.shape[:2]
        rects[nm] = (-lo, -to, -lo + w, -to + h)
    x0 = min(r[0] for r in rects.values())
    y0 = min(r[1] for r in rects.values())
    x1 = max(r[2] for r in rects.values())
    y1 = max(r[3] for r in rects.values())
    # `pad` adds a transparent border on every side. The heads otherwise sit
    # flush against the canvas edge (the union is sized by OUCH, which is
    # full-height), and the renderer shaves the outermost row or two off the
    # destination rect - which cuts the hair and the chin instead of nothing.
    origins = {nm: (r[0] - x0 + pad, r[1] - y0 + pad) for nm, r in rects.items()}
    return x1 - x0 + 2 * pad, y1 - y0 + 2 * pad, origins


def convert_cell(head_rgb, head_mask, vanilla, pal, canvas, origin,
                 grain=5, sharpen=55, punch=0.30, scale=1, colors=0,
                 flatten="levels", tone="source", dither=False, outline=0.0, raw=False,
                 soft_alpha=False, lift=0.0):
    van_rgba, _ = vanilla
    vin = van_rgba[..., 3] > 0
    vrgb = van_rgba[..., :3].astype(float)
    ys, xs = np.where(vin)
    # where the head sits inside the shared canvas, at output resolution
    vbox = (xs.min() + origin[0], ys.min() + origin[1],
            xs.max() + 1 + origin[0], ys.max() + 1 + origin[1])
    vw, vh = canvas
    # Texels per HUD unit. Above 1 the frame carries more detail than the HUD
    # grid, below 1 it carries less and reads chunkier; a TEXTURES `Scale N`
    # (fractional is fine) puts either back on the same 30x31 footprint.
    if scale != 1:
        vh, vw = max(1, round(vh * scale)), max(1, round(vw * scale))
        vbox = tuple(max(0, round(v * scale)) for v in vbox)

    m = head_mask
    src = Image.fromarray(head_rgb.astype(np.uint8))

    if grain > 1:
        src = src.filter(ImageFilter.MedianFilter(grain if scale >= 1 else max(3, grain - 2)))
    a = np.array(src).astype(float)

    if raw:
        # Take the painting as it is: no white balance, no tone remap, no
        # S-curve. Only the edge bleed survives, because without it the box
        # filter averages the silhouette against nothing and leaves a fringe.
        a = bleed_outward(a, m)
    else:
        smed = np.array([np.median(a[..., c][m]) for c in range(3)])
        vmed = np.array([np.median(vrgb[..., c][vin]) for c in range(3)])
        a *= (vmed / np.maximum(smed, 1e-3))[None, None, :]

        lum = a.sum(2) / 3.0
        lo, hi = np.percentile(lum[m], 1), np.percentile(lum[m], 99)
        vlum = (vrgb.sum(2) / 3.0)[vin]
        vlo, vhi = np.percentile(vlum, 1), np.percentile(vlum, 99)
        if tone == "vanilla":
            # Map the source range onto vanilla's. Matches the original faces,
            # but it lifts the black point and costs the painting its shadows.
            a = np.clip((a - lo) * ((vhi - vlo) / max(hi - lo, 1e-3)) + vlo, 0, 255)
        else:
            # Exposure-only lift: scale so the highlights reach vanilla's,
            # leaving the black point alone so the painted contrast survives.
            a = np.clip(a * (vhi / max(hi, 1e-3)), 0, 255)

        # The painted art is low-contrast next to vanilla, which at this size
        # reads as mud. An S-curve about the vanilla midpoint restores the hard
        # light/shadow split the original faces have.
        if punch > 0:
            mid = (vlo + vhi) / 2.0
            half = max(vhi - vlo, 1e-3) / 2.0
            old = np.clip(a.sum(2) / 3.0, 1e-3, None)
            t = np.clip((old - mid) / half, -1, 1)
            new = mid + (t + punch * t * (1 - np.abs(t))) * half
            # scale RGB by the luminance ratio so chroma rides along; applying
            # the curve per channel instead detonates the saturation
            a = np.clip(a * (np.clip(new, 0, 255) / old)[..., None], 0, 255)
        a = bleed_outward(a, m)

    bw, bh = vbox[2] - vbox[0], vbox[3] - vbox[1]
    sw, sh = src.size
    s = min(bw / sw, bh / sh)
    tw, th = max(1, round(sw * s)), max(1, round(sh * s))

    small = Image.fromarray(a.astype(np.uint8)).resize((tw, th), Image.BOX)
    if sharpen:
        small = small.filter(ImageFilter.UnsharpMask(radius=1, percent=sharpen, threshold=0))
    ma = Image.fromarray((m * 255).astype(np.uint8)).resize((tw, th), Image.BOX)
    if raw and lift:
        # Highlight-preserving brightness lift: 1-(1-x)^(1+lift). The painting is
        # much darker than the rest of the HUD art (~63% of a key icon's mean),
        # and a dark low-contrast sprite over a busy floor reads as translucent
        # even at alpha 1.0. This lifts the shadows without clipping highlights,
        # so the palette and mood survive.
        arr = np.array(small).astype(float) / 255.0
        small = Image.fromarray(
            np.clip((1.0 - (1.0 - arr) ** (1.0 + lift)) * 255.0, 0, 255).astype(np.uint8))

    if raw:
        if soft_alpha:
            # Resampled coverage as real alpha: smoothest silhouette, but the
            # feathered rim reads as translucency next to the rest of the HUD,
            # which is all binary-alpha paletted art.
            alpha = np.array(ma)
        else:
            alpha = np.where(np.array(ma) > 110, 255, 0).astype(np.uint8)
        rgba = np.dstack([np.array(small), alpha])
        if outline:
            # A rim OUTSIDE the silhouette, one pixel wide. The head has no
            # defined boundary against a busy floor, and an edgeless dark shape
            # reads as see-through no matter what its alpha is; a hard rim is
            # what makes it read as a solid object sitting on top.
            av = alpha > 0
            dil = np.array(Image.fromarray((av * 255).astype(np.uint8))
                           .filter(ImageFilter.MaxFilter(3))) > 127
            rim = dil & ~av
            rgba[rim] = (0, 0, 0, 255)
        out = np.zeros((vh, vw, 4), np.uint8)
        ox = vbox[0] + (bw - tw) // 2
        oy = vbox[1] + (bh - th)
        out[oy:oy + th, ox:ox + tw] = rgba
        return Image.fromarray(out)
    alpha = (np.array(ma) > 120).astype(np.uint8) * 255

    # PLAYPAL 248..255 are the gold "special" entries; letting the nearest-match
    # reach them speckles the face, so quantize against 0..247 only.
    palq = pal[:248]
    px = np.array(small)
    if dither and colors:
        # Ordered 4x4 Bayer, amplitude tied to one band's width, applied before
        # posterizing. Breaks the band boundaries into a stipple without moving
        # the black or white point, so contrast is untouched.
        bayer = np.array([[0, 8, 2, 10], [12, 4, 14, 6],
                          [3, 11, 1, 9], [15, 7, 13, 5]], float) / 16.0 - 0.5
        h, w = px.shape[:2]
        tile = np.tile(bayer, (h // 4 + 1, w // 4 + 1))[:h, :w]
        px = np.clip(px.astype(float) + tile[..., None] * (255.0 / max(colors - 1, 1)), 0, 255).astype(np.uint8)
    if colors and flatten == "median":
        # Adaptive palette. Allocates colours by population, so on a face that
        # is mostly mid-tone skin the shadows get merged into the midtones and
        # the result goes flat. Kept for comparison only.
        flat = Image.fromarray(px).quantize(colors=colors, method=Image.MEDIANCUT, dither=Image.NONE)
        px = np.array(flat.convert("RGB"))
    elif colors and flatten == "levels":
        # Posterize luminance into N bands spread across the frame's actual
        # range, carrying chroma along. Flat bands (the pixel-art read) without
        # losing either end of the contrast.
        f = px.astype(float)
        l = np.clip(f.sum(2) / 3.0, 1e-3, None)
        inside = l[np.array(alpha) > 0] if alpha is not None else l
        blo, bhi = inside.min(), inside.max()
        t = np.clip((l - blo) / max(bhi - blo, 1e-3), 0, 1)
        band = np.round(t * (colors - 1)) / (colors - 1)
        px = np.clip(f * ((band * (bhi - blo) + blo) / l)[..., None], 0, 255).astype(np.uint8)
    px = px.astype(int)
    idx = ((px.reshape(-1, 1, 3) - palq[None]) ** 2).sum(2).argmin(1)
    q = np.dstack([palq[idx].reshape(th, tw, 3).astype(np.uint8), alpha])

    if outline:
        # Darken the silhouette's own edge pixels. Vanilla reads as a cut-out
        # against the status bar; this restores that edge without touching the
        # interior, so the tone range is unchanged.
        av = alpha > 0
        er = np.array(Image.fromarray((av * 255).astype(np.uint8)).filter(ImageFilter.MinFilter(3))) > 127
        rim = av & ~er
        q[..., :3][rim] = (q[..., :3][rim].astype(float) * (1.0 - outline)).astype(np.uint8)

    out = np.zeros((vh, vw, 4), np.uint8)
    ox = vbox[0] + (bw - tw) // 2
    oy = vbox[1] + (bh - th)  # bottom-align: the chin lands where vanilla's does
    out[oy:oy + th, ox:ox + tw] = q
    return Image.fromarray(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sheet", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--only", default="", help="comma-separated lump names")
    ap.add_argument("--grain", type=int, default=5)
    ap.add_argument("--sharpen", type=int, default=55)
    ap.add_argument("--punch", type=float, default=0.30)
    ap.add_argument("--scale", type=float, default=1.0,
                    help="texels per HUD unit; <1 is chunkier, >1 finer (needs TEXTURES Scale N)")
    ap.add_argument("--colors", type=int, default=0, help="flatten to N levels/colours before PLAYPAL (0 = off)")
    ap.add_argument("--flatten", choices=("levels", "median"), default="levels",
                    help="levels = luminance bands (keeps contrast); median = adaptive palette (flattens)")
    ap.add_argument("--pad", type=int, default=2,
                    help="transparent border in HUD px on every side; keeps the renderer's "
                         "edge shave off the head. Pass the same value to build_mugshot_pk3.")
    ap.add_argument("--align", choices=("centroid", "vanilla"), default="centroid",
                    help="centroid = all heads share one axis; vanilla = keep each frame's own bbox")
    ap.add_argument("--lift", type=float, default=0.0,
                    help="raw mode: highlight-preserving brightness lift so the dark painting "
                         "reads as solid next to the rest of the HUD (0.5 is a good start)")
    ap.add_argument("--soft-alpha", action="store_true",
                    help="keep the feathered silhouette; default is a hard cut so the face "
                         "matches the binary-alpha HUD art around it")
    ap.add_argument("--raw", action="store_true",
                    help="take the art as-is: no white balance, tone remap, punch, banding or PLAYPAL snap")
    ap.add_argument("--dither", action="store_true", help="ordered Bayer stipple across the bands")
    ap.add_argument("--outline", type=float, default=0.0, help="darken silhouette edge by this fraction")
    ap.add_argument("--tone", choices=("source", "vanilla"), default="source",
                    help="source = keep the painting's contrast; vanilla = remap onto the original faces' range")
    ap.add_argument("--idle", choices=("sheet", "single", "glance", "brow"), default="sheet",
                    help="sheet = three painted idle faces; single = all three from the centre one; brow = centre head with only the brow band swapped in")
    args = ap.parse_args()

    pal, faces = read_iwad()
    raw_img = Image.open(args.sheet)
    salpha = np.array(raw_img.getchannel("A")) if "A" in raw_img.getbands() else None
    sheet = np.array(raw_img.convert("RGB")).astype(int)
    want = set(n.strip().upper() for n in args.only.split(",") if n.strip())
    os.makedirs(args.out, exist_ok=True)
    heads_by_row = segment_sheet(sheet, salpha)
    cw, chh = generate(sheet, heads_by_row, faces, pal, args.out, args, want, verbose=True)
    return cw, chh


def brow_blend(sheet, alpha, base, variant, lo=0.20, hi=0.55, feather=0.06):
    """Build an idle variant that differs from the base head ONLY in the brows.

    The sheet's three idle faces are the same head painted three times: neutral,
    left brow raised, right brow raised. Using the three paintings directly
    swaps in a whole separate painting, which reads as the head twitching. This
    keeps the base head and its silhouette and lifts in just the brow band from
    the variant, so the brow moves and nothing else does.

    lo/hi are fractions of head height; feather softens both seams."""
    mb, (bx0, by0, bx1, by1) = base
    mv, (vx0, vy0, vx1, vy1) = variant
    base_rgb = sheet[by0:by1, bx0:bx1].astype(float)
    h, w = base_rgb.shape[:2]

    var_rgb = sheet[vy0:vy1, vx0:vx1].astype(np.uint8)
    # Same character at the same scale, so matching the bounding boxes aligns
    # the features closely enough for a band swap.
    var_rgb = np.array(Image.fromarray(var_rgb).resize((w, h), Image.BICUBIC)).astype(float)

    ys = np.arange(h)[:, None]
    f = max(1.0, feather * h)
    wgt = np.clip((ys - lo * h) / f, 0, 1) * np.clip((hi * h - ys) / f, 0, 1)
    out = base_rgb * (1 - wgt[..., None]) + var_rgb * wgt[..., None]
    return np.clip(out, 0, 255), mb


def recentre(frames, verbose=False):
    """Shift every frame horizontally so all the heads share one centre.

    Each frame is fitted to its own vanilla counterpart's bbox, and the painted
    heads differ in width too, so the head's centre of mass drifts a pixel or
    two between expressions. On screen that reads as the face sliding sideways
    whenever the state changes. The idle frame is the anchor, so the face the
    player looks at most never moves. A shift is skipped if it would push
    opaque pixels off the canvas."""
    def cx(img):
        al = np.array(img)[..., 3].astype(float)
        if al.sum() <= 0:
            return None
        return float((al.sum(0) * np.arange(al.shape[1])).sum() / al.sum())

    anchor = frames.get("STFST01") or next(iter(frames.values()))
    target = cx(anchor)
    if target is None:
        return frames
    out, moved = {}, 0
    for nm, img in frames.items():
        c = cx(img)
        dx = 0 if c is None else int(round(target - c))
        a = np.array(img)
        if dx and (a[:, 0, 3].any() if dx > 0 else a[:, -1, 3].any()):
            dx = 0  # would clip the silhouette
        if dx:
            a = np.roll(a, dx, axis=1)
            if dx > 0:
                a[:, :dx] = 0
            else:
                a[:, dx:] = 0
            moved += 1
        out[nm] = Image.fromarray(a)
    if verbose and moved:
        print(f"  recentred {moved} frame(s) onto the idle frame's axis")
    return out


def generate(sheet, heads_by_row, faces, pal, out_dir, opt, want=(), verbose=False):
    """Write one full set of frames. `heads_by_row` and `faces` are passed in so
    a caller sweeping many treatments pays for the IWAD decode and the sheet
    segmentation once instead of once per treatment."""
    os.makedirs(out_dir, exist_ok=True)
    cw, chh, origins = common_canvas(faces, getattr(opt, "pad", 0))
    if verbose:
        print(f"shared canvas {cw}x{chh} logical"
              + (f" ({round(cw * opt.scale)}x{round(chh * opt.scale)} at {opt.scale}x)" if opt.scale != 1 else ""))

    done = 0
    made = {}
    for r in range(6):
        names = [COLUMNS[c](r) for c in range(8)] if r < 5 else LAST_ROW
        heads = heads_by_row[r]
        if opt.idle in ("single", "glance") and r < 5 and len(heads) == 8:
            # Columns 3/4/5 are three separately painted faces, so the engine's
            # 17-tic idle rotation reads as the head swapping identity rather
            # than glancing around (they differ by ~50% of pixels; vanilla's
            # trio differ by 5%). Drive all three from the centre painting.
            heads = list(heads)
            heads[3] = heads[4]
            heads[5] = heads[4]
        for c, (mask, box) in enumerate(heads):
            if c >= len(names):
                break
            nm = names[c]
            if want and nm not in want:
                continue
            if nm not in faces:
                continue
            x0, y0, x1, y1 = box
            sub = sheet[y0:y1, x0:x1]
            ref = nm
            if opt.idle == "brow" and r < 5 and nm.startswith("STFST") and nm[-1] in "02" and len(heads) == 8:
                # ST0/ST2 = the base head with one brow lifted in.
                sub, mask = brow_blend(sheet, None, heads[4], heads[3 if nm[-1] == "0" else 5])
                ref = nm[:-1] + "1"
            if opt.idle in ("single", "glance", "brow") and r < 5 and nm.startswith("STFST") and nm[-1] in "02":
                # Also borrow the centre frame's target geometry. Sharing only
                # the source head is not enough: each vanilla frame has its own
                # alpha bbox, and fitting to those shifts the result by a pixel,
                # which at this size changes half the pixels in the image.
                ref = nm[:-1] + "1"
            img = convert_cell(sub, mask, faces[ref], pal, (cw, chh), origins[ref],
                               opt.grain, opt.sharpen, opt.punch, opt.scale, opt.colors,
                               opt.flatten, opt.tone, opt.dither, opt.outline, getattr(opt, "raw", False),
                               getattr(opt, "soft_alpha", False), getattr(opt, "lift", 0.0))
            if opt.idle == "glance" and r < 5 and nm.startswith("STFST") and nm[-1] in "02":
                # Nudge the two outer idle frames one pixel sideways so the
                # rotation reads as a glance rather than as nothing at all.
                dx = -1 if nm[-1] == "0" else 1
                img = Image.fromarray(np.roll(np.array(img), dx, axis=1))
            made[nm] = img
            if verbose:
                print(f"  {nm}  {img.size[0]}x{img.size[1]}  <- row {r} head {c} at x={x0}")
            done += 1

    if getattr(opt, "align", "centroid") == "centroid" and made:
        made = recentre(made, verbose)
    for nm, img in made.items():
        img.save(os.path.join(out_dir, nm + ".png"))
    if verbose:
        print(f"{done} frames written to {out_dir}")
    return cw, chh


if __name__ == "__main__":
    main()
