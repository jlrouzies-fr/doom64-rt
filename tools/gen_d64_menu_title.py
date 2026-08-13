"""
Render a Doom 64 menu title patch from the mod's own big font.

Why this works
--------------
Retribution's menu patches are not hand-drawn art: they are straight renders of
its `DBIGFONT` lump (FON2), at zero tracking, with the font's 8-level grey ramp
translated to the menu's 8-level red ramp. That was verified by reconstruction -
`--verify` rebuilds M_NGAME / M_LOADG / M_SAVEG / M_OPTION / M_QUITG from the
font and compares them pixel by pixel against the wad; all five come back with
zero mismatching pixels.

So any word we need in the Doom 64 menu face can be generated rather than drawn,
and it is indistinguishable from the shipped patches.

What it is for
--------------
gzdoom-rt mounts `rt/wad` AFTER every `-file` PWAD (d_main.cpp:1963), and ships
its own menu graphics in the plain Doom font. Where the mod already has D64 art
for a lump, `tools/extract_d64_menu_gfx.py` copies it into the overlay. Where it
does NOT - RT's `M_DISOPT` / `M_DISP` read "GRAPHICS", a word Doom 64 never had -
this script synthesises it.

Output goes to `rt-wad-overlay/graphics/`; `tools/sync-rt-wad.py` mirrors it into
the real rt/wad trees.

Usage:
    py -3 tools/gen_d64_menu_title.py                     # write the TITLES below
    py -3 tools/gen_d64_menu_title.py --verify            # self-test against the wad
    py -3 tools/gen_d64_menu_title.py --text "Graphics" --lump M_DISOPT
"""

import argparse
import os
import struct

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WAD = os.path.join(ROOT, "Doom64-Retribution", "D64RTR_v15.WAD")
OUTDIR = os.path.join(ROOT, "rt-wad-overlay", "graphics")

# lump name -> the word it should read, in the font's own casing convention
# (leading capital + small caps, exactly as "Options" / "Load Game" are drawn).
TITLES = {
    "M_DISOPT": "Graphics",   # RT_OptionsMenu / RT_OptionsMenuRemix header
    "M_DISP": "Graphics",     # RT's other copy of the same title
}

# DBIGFONT palette index -> the colour the shipped patches use for it. Read off
# the art itself, not guessed: every one of these pairings is confirmed by the
# --verify reconstruction below. Index 0 is transparent. Index 9 and 10 both
# land on the same red - the translation clamps at the top of the ramp. Index 11
# (a brown) appears in no glyph any menu word uses, so it has no known pairing
# and rendering asks you rather than inventing one.
RED_BY_INDEX = {
    1: (24, 0, 0),
    2: (41, 0, 0),
    3: (66, 0, 0),
    4: (90, 0, 0),
    5: (107, 0, 0),
    6: (132, 0, 0),
    7: (156, 0, 0),
    8: (181, 0, 0),
    9: (206, 28, 28),
    10: (206, 28, 28),
}

TRANSPARENT = (255, 255, 255, 0)  # what the shipped patches use

# lumps that are pure font renders, for --verify
KNOWN_RENDERS = {
    "M_NGAME": "New Game",
    "M_NEWG": "New Game",
    "M_LOADG": "Load Game",
    "M_SAVEG": "Save Game",
    "M_OPTION": "Options",
    "M_OPTTTL": "Options",
    "M_QUITG": "Quit Game",
}


def read_wad_lumps(path, wanted):
    with open(path, "rb") as f:
        data = f.read()
    magic, numlumps, infotableofs = struct.unpack_from("<4sii", data, 0)
    if magic not in (b"IWAD", b"PWAD"):
        raise SystemExit(f"{path}: not a wad (magic {magic!r})")
    found = {}
    for i in range(numlumps):
        filepos, size, raw = struct.unpack_from("<ii8s", data, infotableofs + i * 16)
        name = raw.split(b"\0")[0].decode("ascii", "replace").upper()
        if name in wanted:
            found[name] = data[filepos:filepos + size]
    return found


class Fon2:
    """Minimal FON2 reader - enough for DBIGFONT. See FSingleLumpFont::LoadFON2."""

    def __init__(self, blob):
        if blob[:4] != b"FON2":
            raise SystemExit("DBIGFONT is not FON2")
        self.height = struct.unpack_from("<H", blob, 4)[0]
        first, last, constant, shading, palsize, flags = struct.unpack_from("<6B", blob, 6)
        count = last - first + 1
        p = 12
        widths = list(struct.unpack_from("<%dH" % count, blob, p))
        p += 2 * count
        self.palette = [tuple(blob[p + 3 * i:p + 3 * i + 3]) for i in range(palsize + 1)]
        p += 3 * (palsize + 1)

        data = blob[p:]
        pos = 0
        self.glyphs = {}
        for i, w in enumerate(widths):
            if w == 0:
                continue
            px, pos = self._unrle(w * self.height, data, pos)
            self.glyphs[chr(first + i)] = (w, px)

    @staticmethod
    def _unrle(need, src, pos):
        out = bytearray()
        while len(out) < need:
            code = src[pos]
            pos += 1
            code = code - 256 if code > 127 else code
            if code >= 0:                      # literal run of code+1 bytes
                out += src[pos:pos + code + 1]
                pos += code + 1
            elif code != -128:                 # repeat next byte 1-code times
                out += bytes([src[pos]]) * (1 - code)
                pos += 1
        return out[:need], pos

    def missing(self, text):
        return sorted({c for c in text if c not in self.glyphs})

    def render(self, text):
        """Render at zero tracking, cropped to the ink's own height - which is how
        the shipped patches are cut (13 rows normally, 14 when a Q descends)."""
        missing = self.missing(text)
        if missing:
            raise SystemExit(f"DBIGFONT has no glyph for: {missing}")

        width = sum(self.glyphs[c][0] for c in text)
        rows = 0
        for c in text:
            w, px = self.glyphs[c]
            for y in range(self.height):
                if any(px[y * w + x] for x in range(w)):
                    rows = max(rows, y + 1)

        im = Image.new("RGBA", (width, rows), TRANSPARENT)
        put = im.load()
        x = 0
        for c in text:
            w, px = self.glyphs[c]
            for y in range(rows):
                for xx in range(w):
                    v = px[y * w + xx]
                    if not v:            # index 0 is the transparent one
                        continue
                    if v not in RED_BY_INDEX:
                        raise SystemExit(
                            f"'{c}' uses DBIGFONT palette index {v} {self.palette[v]}, "
                            "which no shipped patch pairs with a red - extend RED_BY_INDEX "
                            "from real art before rendering this word")
                    put[x + xx, y] = RED_BY_INDEX[v] + (255,)
            x += w
        return im


def load_font():
    if not os.path.isfile(WAD):
        raise SystemExit(f"missing wad: {WAD}")
    found = read_wad_lumps(WAD, {"DBIGFONT"})
    if "DBIGFONT" not in found:
        raise SystemExit(f"{WAD}: no DBIGFONT lump")
    return Fon2(found["DBIGFONT"])


def verify(font):
    """Prove the renderer is faithful before trusting anything it generates."""
    import io

    found = read_wad_lumps(WAD, set(KNOWN_RENDERS))
    bad = 0
    for lump, text in sorted(KNOWN_RENDERS.items()):
        if lump not in found:
            print(f"  SKIP  {lump}  (not in wad)")
            continue
        want = Image.open(io.BytesIO(found[lump])).convert("RGBA")
        got = font.render(text)
        if got.size != want.size:
            print(f"  FAIL  {lump}  size {got.size} != {want.size}")
            bad += 1
            continue
        a, b = list(got.getdata()), list(want.getdata())
        diff = sum(
            1 for x, y in zip(a, b)
            if (x[3] == 0) != (y[3] == 0) or (x[3] and x[:3] != y[:3])
        )
        print(f"  {'ok  ' if not diff else 'FAIL'}  {lump:9s} \"{text}\"  {got.size[0]}x{got.size[1]}  "
              f"{diff} mismatching px")
        bad += bool(diff)
    print(f"\n{bad} lump(s) failed to reproduce")
    raise SystemExit(1 if bad else 0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true",
                    help="reconstruct the shipped D64 patches and compare, write nothing")
    ap.add_argument("--text", help="render this string instead of the TITLES table")
    ap.add_argument("--lump", help="lump name to write --text as")
    args = ap.parse_args()

    font = load_font()
    if args.verify:
        verify(font)

    if bool(args.text) != bool(args.lump):
        raise SystemExit("--text and --lump go together")
    titles = {args.lump.upper(): args.text} if args.text else TITLES

    os.makedirs(OUTDIR, exist_ok=True)
    for lump, text in sorted(titles.items()):
        im = font.render(text)
        dst = os.path.join(OUTDIR, lump + ".png")
        im.save(dst)
        print(f"  WROTE {lump}.png  \"{text}\"  {im.size[0]}x{im.size[1]}  -> {dst}")

    print(f"\nnow run:  py -3 tools/sync-rt-wad.py")


if __name__ == "__main__":
    main()
