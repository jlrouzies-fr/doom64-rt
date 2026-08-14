"""Rebuild SFLATAS as a SINGLE CENTRED BULB, from its own painted pixels.

    python tools/make_single_bulb_flat.py

    -> Doom64-Retribution/d64r-single-bulb.wad      TX_ override for SFLATAS
    -> rt/mat, rt/mat_dev, Retribution-RT-Materials  matching SFLATAS_e.png
    -> docs/img/features/sflatas-before.png, sflatas-after.png   for the README

WHY THIS EXISTS -- the short version, with the measurement behind it.

A grating casts a legible shadow only when its light comes from ONE compact
source. Measured in the shadow lab (MAP93, tools/build_shadow_lab.py), same
fixture alone in a dark room:

    1 light,  radius 0.02   crisp diamond shadows on floor, walls and ceiling
    4 lights, radius 0.02   shadows once the intensity beats the bounce fill
    16 lights, any radius   nothing at all

SFLATAS paints 2x2 bulbs per 64-unit tile, so the lattice places one light per
painted bulb -- bulbs 32 units apart, which is ONE METRE. The grating's openings
are ~16 units. Once the lights are further apart than the occluder's features,
each one lays down an offset copy of the mesh shadow that fills in the previous
one's gaps, and the pattern cancels. That is not a tuning failure; a real ceiling
with sixteen metre-spaced bulbs behind a half-metre mesh washes out too.

SFLATCH -- the game's existing single-bulb flat -- proved the fix works, but its
bulb sits in a 64-unit tile with little margin, and flats anchor to the WORLD
ORIGIN rather than to the sector. So a wall lands wherever it lands and cuts a
bulb in half. Padding is what fixes that: a bulb small and central enough that a
tile boundary falls on blank plate, where the seam is invisible.

HOW THE ART IS MADE, and what it deliberately does NOT do.

It does not draw a new bulb. It takes SFLATAS's own bulb and its own plate:

  1. the authored _e mask says exactly which texels are bulb;
  2. those texels are inpainted away with surrounding plate, wrapping at the
     edges because flats tile -- leaving a clean plate tile;
  3. ONE of the original bulbs is cropped with that mask and pasted at (32,32).

So every pixel in the result is Doom 64's, rearranged. That is the standing rule
in this repo -- keep the art, never replace a painted albedo with something
generated (docs/rt-lighting-practices.md, and the "keep the art" memory).

THE _e MASK IS REBUILT TOO, and it has to be. It is what makes the bulbs glow;
leaving the four-blob mask against a one-bulb albedo would light three bulbs that
are no longer painted. `_n`/`_orm`/`_h` are NOT regenerated -- they carry plate
relief that still matches, and the bulb's own relief is a small local error.
"""

import struct
from pathlib import Path

from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
MODS = ROOT / "Doom64-Retribution"
IWAD = MODS / "D64RTR_v15.WAD"
OUT_WAD = MODS / "d64r-single-bulb.wad"
DOCS = ROOT / "docs" / "img" / "features"

TEX = "SFLATAS"
TILE = 64
# The authored bulb centres, from BulbLatticeAS in rt_lights_fixtures.cpp -- the
# _e mask's blob centroids, detected by gen_bulb_flat_masks.py, not assumed.
BULBS = [(15.5, 15.5), (47.5, 15.5), (15.5, 47.5), (47.5, 47.5)]

# Where the runtime looks. mat_dev is the one that matters under developerMode
# (mat/ is KTX2-only there), and Retribution-RT-Materials is the tracked copy --
# writing only the build tree is how 427 masks went missing from a fresh clone.
MAT_DIRS = [
    ROOT / "sourcecode/gzdoom-rt/build/RelWithDebInfo/rt/mat",
    ROOT / "sourcecode/gzdoom-rt/build/RelWithDebInfo/rt/mat_dev",
    MODS / "Retribution-RT-Materials/rt/mat",
]


def wad_lumps(path: Path):
    d = path.read_bytes()
    n, off = struct.unpack("<II", d[4:12])
    out = {}
    for i in range(n):
        o, sz, nm = struct.unpack("<II8s", d[off + i * 16 : off + i * 16 + 16])
        out.setdefault(nm.rstrip(b"\0").decode("latin1"), d[o : o + sz])
    return out


def write_wad(items):
    body, directory, offset = b"", b"", 12
    for name, data in items:
        directory += struct.pack(
            "<II8s", offset, len(data), name.encode("ascii")[:8].ljust(8, b"\0")
        )
        body += data
        offset += len(data)
    return struct.pack("<4sII", b"PWAD", len(items), 12 + len(body)) + body + directory


# A pristine copy of the authored 4-blob mask, kept beside this script.
#
# It exists because the first version read the mask from MAT_DIRS -- the same
# directories it WRITES the new one-blob mask into. Run it twice and the second
# run rebuilt the art from its own output, producing a bulb 16 units off centre
# and a "0 units of padding" report that looked like a geometry bug. A generator
# whose input is its own output is not idempotent; it is a ratchet.
SRC_MASK = ROOT / "tools" / "_sflatas_e_authored.png"


def find_mask() -> Image.Image:
    """The AUTHORED four-blob mask, never this script's own output."""
    if SRC_MASK.exists():
        return Image.open(SRC_MASK).convert("L")
    # First run: snapshot it from the tracked material tree, which git restores
    # and which therefore still holds the authored version.
    src = MODS / "Retribution-RT-Materials/rt/mat" / f"{TEX}_e.png"
    if not src.exists():
        raise SystemExit(f"{src} missing - run tools/gen_bulb_flat_masks.py first")
    im = Image.open(src).convert("L")
    if len(_blob_boxes(im)) != len(BULBS):
        raise SystemExit(
            f"{src} has {len(_blob_boxes(im))} blob(s), expected {len(BULBS)} -- "
            "it is probably already this script's output. Restore it with: "
            f"git checkout -- {src.relative_to(ROOT)}")
    im.save(SRC_MASK)
    print(f"  snapshotted authored mask -> {SRC_MASK.relative_to(ROOT)}")
    return im


def _blob_boxes(mask: Image.Image):
    """Connected lit components, so 'is this the authored mask' is checkable."""
    w, h = mask.size
    px = mask.load()
    seen, boxes = set(), []
    for y in range(h):
        for x in range(w):
            if px[x, y] <= 8 or (x, y) in seen:
                continue
            stack, comp = [(x, y)], []
            seen.add((x, y))
            while stack:
                cx, cy = stack.pop()
                comp.append((cx, cy))
                for nx, ny in ((cx+1, cy), (cx-1, cy), (cx, cy+1), (cx, cy-1)):
                    if 0 <= nx < w and 0 <= ny < h and (nx, ny) not in seen and px[nx, ny] > 8:
                        seen.add((nx, ny))
                        stack.append((nx, ny))
            if len(comp) >= 12:
                boxes.append(comp)
    return boxes


def inpaint(img: Image.Image, mask: Image.Image) -> Image.Image:
    """Replace masked texels by COPYING real plate from elsewhere in the tile.

    Not a blur. Blurring was tried first and is wrong here: a bulb is a bright
    dome inside a DARK ring, so diffusing the hole just spreads the ring outward
    and leaves three grey ghosts where the removed bulbs were -- visible in the
    first render of this texture.

    Instead, for each masked texel take the same texel offset by half a bulb
    pitch, wrapping, and accept the first candidate that is itself unmasked. The
    bulbs sit on a 32-unit lattice, so a 16-unit shift always lands between them.
    The plate is fine noise, so a copied patch is seamless, and every pixel in
    the result is still one Doom 64 painted.
    """
    w, h = img.size
    src, msk = img.load(), mask.load()
    out = img.copy()
    dst = out.load()
    # Half the 32-unit bulb pitch, in eight directions, nearest first.
    cands = [(16, 16), (-16, -16), (16, -16), (-16, 16),
             (0, 16), (16, 0), (0, -16), (-16, 0)]
    holes = 0
    for y in range(h):
        for x in range(w):
            if msk[x, y] <= 8:
                continue
            for ox, oy in cands:
                sx, sy = (x + ox) % w, (y + oy) % h
                if msk[sx, sy] <= 8:
                    dst[x, y] = src[sx, sy]
                    break
            else:
                holes += 1
    if holes:
        print(f"  WARNING: {holes} masked texel(s) had no unmasked source")
    return out


def main() -> None:
    lumps = wad_lumps(IWAD)
    if TEX not in lumps:
        raise SystemExit(f"{TEX} not in {IWAD.name}")

    import io

    before = Image.open(io.BytesIO(lumps[TEX])).convert("RGB")
    if before.size != (TILE, TILE):
        raise SystemExit(f"{TEX} is {before.size}, expected {TILE}x{TILE}")

    mask = find_mask().resize((TILE, TILE), Image.NEAREST)
    # Grow the mask so the bulb's rim and its little cast shadow come with it --
    # a mask tight to the lit texels leaves a dark halo behind when the bulb moves.
    grown = mask.filter(ImageFilter.MaxFilter(7)).point(lambda p: 255 if p > 8 else 0)

    plate = inpaint(before, grown)

    # Take ONE bulb and stamp it dead centre. Crop a quadrant-sized window around
    # the chosen bulb first: pasting the whole shifted mask brings all FOUR blobs
    # with it, which lands the others on the tile edge and defeats the padding
    # this whole change is for.
    bx, by = BULBS[0]
    half = TILE // 2
    win = (0, 0, half, half)            # contains the (15.5, 15.5) bulb and no other
    cx, cy = (win[0] + win[2]) / 2.0, (win[1] + win[3]) / 2.0
    dx, dy = int(round(TILE / 2 - cx)), int(round(TILE / 2 - cy))

    bulb_rgb = Image.new("RGB", (TILE, TILE))
    bulb_a = Image.new("L", (TILE, TILE), 0)
    bulb_rgb.paste(before.crop(win), (dx, dy))
    bulb_a.paste(grown.crop(win), (dx, dy))
    after = Image.composite(bulb_rgb, plate, bulb_a)

    # The new _e: the same single blob, so the glow matches what is painted.
    e_new = Image.new("L", (TILE, TILE), 0)
    e_new.paste(mask.crop(win), (dx, dy))

    # Padding is the whole point of the exercise, so report it rather than assume.
    box = e_new.getbbox()
    pad = min(box[0], box[1], TILE - box[2], TILE - box[3])

    OUT_WAD.write_bytes(write_wad([
        ("TX_START", b""),
        (TEX, png_bytes(after)),
        ("TX_END", b""),
    ]))

    for d in MAT_DIRS:
        if d.exists():
            e_new.save(d / f"{TEX}_e.png")

    DOCS.mkdir(parents=True, exist_ok=True)
    before.resize((256, 256), Image.NEAREST).save(DOCS / "sflatas-before.png")
    after.resize((256, 256), Image.NEAREST).save(DOCS / "sflatas-after.png")

    print(f"wrote {OUT_WAD.name}  ({OUT_WAD.stat().st_size} bytes)")
    print(f"  {TEX}: 4 bulbs -> 1 bulb at ({TILE//2}, {TILE//2})")
    print(f"  bulb spans {box}, so {pad} units of plate to the nearest tile edge")
    print(f"  _e rebuilt in {sum(1 for d in MAT_DIRS if d.exists())} material dir(s)")
    print(f"  README pngs -> docs/img/features/sflatas-before.png, -after.png")


def png_bytes(im: Image.Image) -> bytes:
    import io

    b = io.BytesIO()
    im.save(b, "PNG")
    return b.getvalue()


if __name__ == "__main__":
    main()
