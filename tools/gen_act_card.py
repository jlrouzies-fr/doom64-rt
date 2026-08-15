#!/usr/bin/env python3
"""
Render the ACT title cards that RT_InjectTitleIntoDoomMap() throws up on the
first map of each act, in Doom 64's own typeface.

WHY THIS EXISTS
    The cards are not text and not WAD graphics -- rt_main.cpp registers a 1x1
    placeholder under a made-up RTGL1 texture name ("title/act1") and RTGL1
    substitutes a file from rt/mat (KTX2) or, in developerMode, rt/mat_dev
    (PNG). The stock art is DOOM II RT's, set in a generic sans that has nothing
    to do with Doom 64. So we bake our own.

THE FONT IS ALREADY IN THE GAME
    D64RTR_v15.WAD lump DBIGFONT is a self-describing FON2 binary that GZDoom
    auto-registers as BIGFONT. It is the face every "stylised" graphic in the
    game was baked from -- the CWILV* level titles, E_DOOM64, M_EPISOD, WIENTER
    are all this font pre-rendered. So no new glyph art is drawn here: we read
    the same glyphs and the same colour ramps the game itself uses.

    Two authentic ramps:
      GREY  the font's own palette. Pixel-identical to the CWILV* level-title
            cards and WIENTER.
      RED   #290000 -> #CE0000, which is what the WAD's TEXTCOLO lump redefines
            the "Red" range to, precisely so live-drawn BIGFONT colour-matches
            the baked E_* episode plates.

Usage:  py -3 tools/gen_act_card.py            # gallery + contact sheet
        py -3 tools/gen_act_card.py --variant plate --install
"""

import argparse
import os
import re
import struct
import sys

from PIL import Image, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

WAD = os.path.join(ROOT, "Doom64-Retribution", "D64RTR_v15.WAD")
# Two real in-game frames, chosen as opposite legibility cases: a dark room with
# a blown-out floor, and a bright yellow tech level. A card that survives both
# survives the game. (Both carry a sliver of window chrome at the top, cropped.)
BACKDROPS = [
    ("dark", os.path.join(ROOT, "screen", "lavarenderbad.png"), 0.00),
    ("bright", os.path.join(ROOT, "screen", "yellowdoor.png"), 0.02),
]
OUTDIR = os.path.join(ROOT, "screen", "act-gallery")

# Loader order matters: RTGL1 tries mat/<name>.ktx2 FIRST and only falls back to
# mat_dev/<name>.png when RTGL1.json has developerMode:true. We install under the
# new names act1/act2/act3, which have no .ktx2, so the PNGs win by default --
# and the stock DOOM II ep2/ep3.ktx2 are left untouched so real Doom II keeps its
# own cards.
#
# Written to all four trees, exactly as tools/gen_lava_material.py does: the
# materials tree is the source of truth and survives a re-stage of build/rt,
# the build dir is what the launcher actually reads, and mat_dev is not a
# scratch folder -- a stale copy there is a bug waiting to happen.
ENGINE_RT = os.path.join(ROOT, "sourcecode", "gzdoom-rt", "build",
                         "RelWithDebInfo", "rt")
MAT_DIRS = [
    os.path.join(ROOT, "Doom64-Retribution", "Retribution-RT-Materials", "rt", "mat"),
    os.path.join(ROOT, "Doom64-Retribution", "Retribution-RT-Materials", "rt", "mat_dev"),
    os.path.join(ENGINE_RT, "mat"),
    os.path.join(ENGINE_RT, "mat_dev"),
]

# The engine uploads the card as a fullscreen quad; the stock art is 3840x2160.
CARD_W, CARD_H = 3840, 2160

# RT_DrawTitle() draws the card over a black wash of alpha*0.3 (rt_main.cpp).
# The previews reproduce that, otherwise everything looks too bright here.
SCENE_DIM = 0.3

# The three acts, deduced from texture families across the 25 campaign maps:
# MAP01-08 are 99-100% SPACE/SFLAT tech with zero stone and zero hell; MAP09-19
# are stone-dominant; hell takes over at MAP20 and stays. MAP08 -> INTER03 is
# also the campaign's only authored story intermission, which corroborates the
# first seam.
ACTS = [
    ("act1", "ACT I", "INCURSION"),
    ("act2", "ACT II", "CITADEL"),
    ("act3", "ACT III", "HELL"),
]

RED_RAMP = ((0x29, 0x00, 0x00), (0xCE, 0x00, 0x00))

# "plate" is the shipping look: a big letterspaced title in the red ramp under a
# small grey kicker. The title scale is NOT per-card -- it is derived once from
# the longest of the three titles so every act card is set at the same size and
# the three read as a series. Width is the binding constraint: "INCURSION" is
# nine glyphs, so the scale that lets it span TITLE_WIDTH_FRAC of the frame is
# the scale all three get.
TITLE_WIDTH_FRAC = 0.86
TITLE_TRACKING = 1
KICKER_SCALE = 8
KICKER_TRACKING = 8

# Vertical centres, as a fraction of frame height. The gap between the two lines
# is the point: at 0.435/0.565 the kicker's descender sat ~35 px off the title's
# cap, which reads as one crowded block rather than a kicker over a title.
KICKER_CY = 0.390
TITLE_CY = 0.605


# --------------------------------------------------------------------------
# FON2
# --------------------------------------------------------------------------

def read_lump(wadpath, name):
    d = open(wadpath, "rb").read()
    sig, count, diroff = struct.unpack_from("<4sii", d, 0)
    if sig not in (b"PWAD", b"IWAD"):
        raise SystemExit(f"{wadpath} is not a WAD")
    for i in range(count):
        fo, sz, nm = struct.unpack_from("<ii8s", d, diroff + i * 16)
        if nm.rstrip(b"\0").decode("latin1") == name:
            return d[fo:fo + sz]
    raise SystemExit(f"lump {name} not found in {wadpath}")


class Fon2:
    """Minimal FON2 reader: header, width table, palette, RLE glyph bitmaps."""

    def __init__(self, blob):
        if blob[:4] != b"FON2":
            raise SystemExit("not a FON2 lump")
        (self.height, self.first, self.last,
         constant_width, _shading, active_colors, _flags) = struct.unpack_from(
            "<HBBBBBB", blob, 4)
        p = 12
        n = self.last - self.first + 1

        if constant_width:
            width, = struct.unpack_from("<H", blob, p)
            p += 2
            self.widths = [width] * n
        else:
            self.widths = list(struct.unpack_from("<%dH" % n, blob, p))
            p += 2 * n

        # active_colors is "count - 1"; index 0 is the transparent entry.
        self.palette = []
        for _ in range(active_colors + 1):
            self.palette.append(tuple(blob[p:p + 3]))
            p += 3

        # Glyphs follow in order, RLE'd, row-major, one byte per pixel
        # (palette index). Zero-width chars carry no data at all.
        self.glyphs = {}
        for i, w in enumerate(self.widths):
            ch = chr(self.first + i)
            if w == 0:
                self.glyphs[ch] = None
                continue
            need = w * self.height
            out = bytearray()
            while len(out) < need:
                code = blob[p]
                p += 1
                if code < 0x80:                       # literal run of code+1
                    out += blob[p:p + code + 1]
                    p += code + 1
                elif code > 0x80:                     # repeat next byte
                    out += bytes([blob[p]]) * (257 - code)
                    p += 1
                else:                                 # 0x80 terminates
                    break
            self.glyphs[ch] = (w, bytes(out[:need]))

    def ink_indices(self):
        """Palette indices actually used by glyphs, excluding 0 (transparent)."""
        used = set()
        for g in self.glyphs.values():
            if g:
                used.update(g[1])
        used.discard(0)
        return sorted(used)


def ramp_palette(font, ramp):
    """Remap the font's grey ramp onto a two-stop colour ramp, in place order.

    The font palette is already a monotonic dark->light ramp, so mapping by
    index preserves the gradient and the baked drop shadow exactly.
    """
    if ramp is None:
        return list(font.palette)
    lo, hi = ramp
    n = len(font.palette) - 1
    out = [font.palette[0]]
    for i in range(1, len(font.palette)):
        t = (i - 1) / max(1, n - 1)
        out.append(tuple(int(round(lo[c] + (hi[c] - lo[c]) * t)) for c in range(3)))
    return out


def render_line(font, text, scale, ramp=None, tracking=0):
    """Render one line at an integer scale. Nearest-neighbour: the pixel grid is
    the point, and the engine's own sampler will soften it at draw time."""
    pal = ramp_palette(font, ramp)
    glyphs = []
    for ch in text.upper():
        g = font.glyphs.get(ch)
        if g is None and ch == " ":
            glyphs.append(None)
            continue
        if g is None:
            raise SystemExit(f"DBIGFONT has no glyph for {ch!r}")
        glyphs.append(g)

    space_w = font.widths[ord(" ") - font.first] if font.first <= 32 else 5
    total = 0
    for g in glyphs:
        total += (space_w if g is None else g[0]) + tracking
    total = max(1, total - tracking)

    img = Image.new("RGBA", (total, font.height), (0, 0, 0, 0))
    px = img.load()
    x = 0
    for g in glyphs:
        if g is None:
            x += space_w + tracking
            continue
        w, data = g
        for row in range(font.height):
            base = row * w
            for col in range(w):
                idx = data[base + col]
                if idx:
                    r, gg, b = pal[idx] if idx < len(pal) else pal[-1]
                    px[x + col, row] = (r, gg, b, 255)
        x += w + tracking

    return img.resize((total * scale, font.height * scale), Image.NEAREST)


# --------------------------------------------------------------------------
# variants
# --------------------------------------------------------------------------

def line_width(font, text, tracking):
    """Unscaled pixel width of a line, so a scale can be solved for."""
    space_w = font.widths[ord(" ") - font.first]
    total = 0
    for ch in text.upper():
        g = font.glyphs.get(ch)
        total += (space_w if (g is None and ch == " ") else g[0]) + tracking
    return max(1, total - tracking)


def shared_title_scale(font):
    """One integer scale for all three acts, set by the widest title."""
    widest = max(line_width(font, t, TITLE_TRACKING) for _, _, t in ACTS)
    return max(1, int(CARD_W * TITLE_WIDTH_FRAC) // widest)


def paste_centred(canvas, img, cy):
    canvas.alpha_composite(img, ((canvas.width - img.width) // 2,
                                 int(cy - img.height / 2)))


def build(font, kicker, title, variant):
    """Return a 3840x2160 RGBA card.

    Vertical placement matters: the mod's own ACS level-name card is on screen
    at the same time, at y=80 and y=95 of a 520x400 virtual HUD -- i.e. the band
    from 19% to 27% of screen height is already occupied. Everything here stays
    clear of it.
    """
    card = Image.new("RGBA", (CARD_W, CARD_H), (0, 0, 0, 0))

    if variant == "engraved":
        k = render_line(font, kicker, 5, None, tracking=3)
        t = render_line(font, title, 15, None, tracking=1)
        paste_centred(card, k, CARD_H * 0.50)
        paste_centred(card, t, CARD_H * 0.60)

    elif variant == "plate":
        k = render_line(font, kicker, KICKER_SCALE, None, tracking=KICKER_TRACKING)
        t = render_line(font, title, shared_title_scale(font), RED_RAMP,
                        tracking=TITLE_TRACKING)
        paste_centred(card, k, CARD_H * KICKER_CY)
        paste_centred(card, t, CARD_H * TITLE_CY)

    elif variant == "rule":
        k = render_line(font, kicker, 5, None, tracking=3)
        t = render_line(font, title, 15, RED_RAMP, tracking=1)
        paste_centred(card, k, CARD_H * 0.485)
        rule = Image.new("RGBA", (t.width, 4), (0x9C, 0x9C, 0x9C, 255))
        paste_centred(card, rule, CARD_H * 0.535)
        paste_centred(card, t, CARD_H * 0.61)

    elif variant == "bold":
        k = render_line(font, kicker, 4, None, tracking=3)
        t = render_line(font, title, 20, RED_RAMP, tracking=1)
        paste_centred(card, k, CARD_H * 0.47)
        paste_centred(card, t, CARD_H * 0.60)

    elif variant == "glow":
        k = render_line(font, kicker, 5, None, tracking=3)
        t = render_line(font, title, 15, RED_RAMP, tracking=1)
        # Dark-red bloom behind the word, in the register of TITLEPIC.
        bloom = Image.new("RGBA", card.size, (0, 0, 0, 0))
        paste_centred(bloom, t, CARD_H * 0.60)
        bloom = bloom.filter(ImageFilter.GaussianBlur(40))
        tint = Image.new("RGBA", card.size, (0xCE, 0x10, 0x00, 0))
        tint.putalpha(bloom.getchannel("A").point(lambda a: int(a * 0.75)))
        card.alpha_composite(tint)
        paste_centred(card, k, CARD_H * 0.50)
        paste_centred(card, t, CARD_H * 0.60)

    elif variant == "kicker":
        line = render_line(font, f"{kicker} - {title}", 6, RED_RAMP, tracking=2)
        paste_centred(card, line, CARD_H * 0.115)

    else:
        raise SystemExit(f"unknown variant {variant}")

    return card


VARIANTS = ["plate", "engraved", "rule", "bold", "glow", "kicker"]


# --------------------------------------------------------------------------
# output
# --------------------------------------------------------------------------

def preview(card, backdrop):
    """Composite as the engine does: dim the scene, then draw the card."""
    scene = backdrop.convert("RGBA").copy()
    wash = Image.new("RGBA", scene.size, (0, 0, 0, int(255 * SCENE_DIM)))
    scene.alpha_composite(wash)
    scene.alpha_composite(card.resize(scene.size, Image.LANCZOS))
    return scene


def alpha_bbox(card):
    bb = card.getchannel("A").getbbox()
    if not bb:
        return "empty"
    x0, y0, x1, y1 = bb
    return (f"x {x0/CARD_W:.1%}..{x1/CARD_W:.1%}  "
            f"y {y0/CARD_H:.1%}..{y1/CARD_H:.1%}")


def install(variant):
    """Write all three act cards where RTGL1 will find them."""
    import json

    cfg = os.path.join(ENGINE_RT, "RTGL1.json")
    if os.path.exists(cfg):
        devmode = json.load(open(cfg)).get("developerMode", False)
        if not devmode:
            print(f"REFUSING: {cfg} has developerMode:false, so RTGL1 will not\n"
                  f"read mat_dev PNGs and the cards would silently not appear.")
            return 1

    font = Fon2(read_lump(WAD, "DBIGFONT"))

    for slug, kicker, title in ACTS:
        card = build(font, kicker, title, variant)
        print(f"  {slug}  {card.width}x{card.height}  ink {alpha_bbox(card)}")
        for d in MAT_DIRS:
            dst = os.path.join(d, "title")
            os.makedirs(dst, exist_ok=True)
            card.save(os.path.join(dst, f"{slug}.png"))
            print(f"      -> {os.path.join(dst, slug + '.png')}")

    # A KTX2 of the same name would win the loader race and silently mask these.
    for slug, _, _ in ACTS:
        clash = os.path.join(ENGINE_RT, "mat", "title", f"{slug}.ktx2")
        if os.path.exists(clash):
            print(f"WARNING: {clash} exists and takes priority over the PNG")
    print("\nstock DOOM II ep2/ep3.ktx2 left untouched")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", help="render just this one")
    ap.add_argument("--act", default="act3", help="act1|act2|act3 for the gallery")
    ap.add_argument("--install", action="store_true",
                    help="write all three cards into the live engine's rt/mat_dev/title/")
    args = ap.parse_args()

    if args.install:
        return install(args.variant or "plate")

    font = Fon2(read_lump(WAD, "DBIGFONT"))
    print(f"DBIGFONT: height {font.height}, chars {font.first}..{font.last}, "
          f"palette {len(font.palette)}, ink indices {font.ink_indices()}")

    os.makedirs(OUTDIR, exist_ok=True)
    which = [args.variant] if args.variant else VARIANTS
    slug, kicker, title = next(a for a in ACTS if a[0] == args.act)

    cards = []
    for v in which:
        card = build(font, kicker, title, v)
        card.save(os.path.join(OUTDIR, f"{slug}_{v}.png"))
        cards.append((v, card))
        print(f"  {v:9} ink {alpha_bbox(card)}")

    for bdname, bdpath, croptop in BACKDROPS:
        bd = Image.open(bdpath).convert("RGB")
        if croptop:
            bd = bd.crop((0, int(bd.height * croptop), bd.width, bd.height))
        shots = [(v, preview(c, bd)) for v, c in cards]

        for v, p in shots:
            p.convert("RGB").save(
                os.path.join(OUTDIR, f"preview_{v}_{bdname}.png"), quality=95)

        if len(shots) > 1:
            tw, th = shots[0][1].size[0] // 2, shots[0][1].size[1] // 2
            cols, rows = 2, (len(shots) + 1) // 2
            sheet = Image.new("RGB", (cols * tw, rows * th), (10, 10, 10))
            for i, (v, p) in enumerate(shots):
                sheet.paste(p.convert("RGB").resize((tw, th), Image.LANCZOS),
                            ((i % cols) * tw, (i // cols) * th))
            out = os.path.join(OUTDIR, f"contact-sheet-{bdname}.png")
            sheet.save(out)
            print(f"contact sheet ({bdname}) -> {out}  {sheet.width}x{sheet.height}")


if __name__ == "__main__":
    main()
