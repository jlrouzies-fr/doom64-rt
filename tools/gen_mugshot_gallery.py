"""
Render contact sheets of mugshot treatments as PNGs, for picking a look without
launching the game.

Two axes, kept deliberately separate:

  * within one sheet, each row is a STYLING variation - band count, dithering,
    silhouette outline, sharpness. Tone is pinned (--tone source, one --punch)
    so every row on a sheet carries the same contrast and only the styling
    differs.
  * across sheets, --pixels sweeps the texel grid. 1.0 is vanilla density
    (30x31); below that is chunkier, above is finer. Every sheet is drawn at
    the same on-screen size, so coarser really does mean bigger pixels rather
    than a smaller face.

Columns are the idle trio the engine rotates through every 17 tics (boxed,
because that rotation is what usually looks wrong) followed by the reactions.

Usage:
    py -3 tools/gen_mugshot_gallery.py --sheet screen/doomguy_grittry.png \
        --outdir screen --pixels 0.5,0.67,1.0,1.5,2.0
"""

import argparse
import os
import shutil
import tempfile
import types

import numpy as np
from PIL import Image, ImageDraw

import gen_mugshot as G

# Styling only. Tone/punch/idle are fixed by --tone/--punch/--idle below so the
# contrast is identical down the sheet.
TREATMENTS = [
    ("A  4 bands",              dict(colors=4)),
    ("B  6 bands",              dict(colors=6)),
    ("C  8 bands",              dict(colors=8)),
    ("D  12 bands",             dict(colors=12)),
    ("E  full palette",         dict(colors=0)),
    ("F  6 bands + dither",     dict(colors=6, dither=True)),
    ("G  8 bands + dither",     dict(colors=8, dither=True)),
    ("H  6 bands + outline",    dict(colors=6, outline=0.40)),
    ("I  8 bands, outline+dth", dict(colors=8, dither=True, outline=0.40)),
    ("J  6 bands, sharp",       dict(colors=6, sharpen=130)),
    ("K  6 bands, soft",        dict(colors=6, sharpen=0)),
]

IDLE = ["STFST00", "STFST01", "STFST02"]
REACT = ["STFEVL0", "STFKILL0", "STFOUCH2", "STFST41", "STFGOD0"]
COLS = IDLE + REACT

SCREEN = 3  # HUD units -> screen pixels at 1280x720


def opts(scale, punch, tone, idle, **over):
    o = dict(grain=5, sharpen=55, punch=punch, scale=scale, colors=0,
             flatten="levels", tone=tone, dither=False, outline=0.0, idle=idle)
    o.update(over)
    return types.SimpleNamespace(**o)


def render_sheet(sheet, heads, faces, pal, scale, args, work):
    px = SCREEN * args.zoom
    cellw, cellh = int(30 * px) + 10, int(31 * px) + 10
    labw, headh, gap = 200, 28, 20
    width = labw + len(IDLE) * cellw + gap + len(REACT) * cellw + 16
    height = headh + len(TREATMENTS) * cellh + 16

    img = Image.new("RGB", (width, height), (28, 27, 32))
    d = ImageDraw.Draw(img)

    def colx(i):
        return labw + i * cellw + (gap if i >= len(IDLE) else 0)

    for i, n in enumerate(COLS):
        d.text((colx(i) + 2, 10), n.replace("STF", ""), fill=(185, 185, 195))
    d.text((labw + 2, 0), "idle rotation", fill=(120, 200, 200))

    texels = None
    for ri, (label, over) in enumerate(TREATMENTS):
        o = opts(scale, args.punch, args.tone, args.idle, **over)
        out = tempfile.mkdtemp(dir=work)
        G.generate(sheet, heads, faces, pal, out, o, want=set(COLS))
        y = headh + ri * cellh
        d.text((8, y + cellh // 2 - 6), label, fill=(205, 205, 215))
        d.rectangle([colx(0) - 5, y - 3, colx(len(IDLE) - 1) + cellw - 8, y + cellh - 9],
                    outline=(60, 110, 110))
        for ci, n in enumerate(COLS):
            fp = os.path.join(out, n + ".png")
            if not os.path.exists(fp):
                continue
            im = Image.open(fp)
            texels = im.size
            # texels -> HUD units (what TEXTURES XScale does) -> screen -> zoom
            hud = (max(1, round(im.size[0] / scale)), max(1, round(im.size[1] / scale)))
            im = im.resize(hud, Image.BOX) if hud != im.size else im
            im = im.resize((im.size[0] * px, im.size[1] * px), Image.NEAREST)
            img.paste(im, (colx(ci) + 2, y + 2), im)
    return img, texels


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sheet", required=True)
    ap.add_argument("--outdir", default="screen")
    ap.add_argument("--pixels", default="0.5,0.67,1.0,1.5,2.0")
    ap.add_argument("--zoom", type=int, default=2)
    ap.add_argument("--punch", type=float, default=0.15)
    ap.add_argument("--tone", default="source")
    ap.add_argument("--idle", default="glance")
    args = ap.parse_args()

    pal, faces = G.read_iwad()
    src = np.array(Image.open(args.sheet).convert("RGB")).astype(int)
    heads = {r: G.row_heads(src, r, expect=8 if r < 5 else 2) for r in range(6)}

    work = tempfile.mkdtemp()
    made = []
    try:
        for s in [float(x) for x in args.pixels.split(",")]:
            img, texels = render_sheet(src, heads, faces, pal, s, args, work)
            name = f"mugshot_style_p{int(round(s * 100)):03d}.png"
            path = os.path.join(args.outdir, name)
            img.save(path)
            made.append((s, texels, path))
            print(f"  {s:>4}x  {texels[0]}x{texels[1]} texels  ->  {path}")
    finally:
        shutil.rmtree(work, ignore_errors=True)
    print(f"\n{len(made)} galleries written")


if __name__ == "__main__":
    main()
