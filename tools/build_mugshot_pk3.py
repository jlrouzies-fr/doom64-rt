"""
Package the generated STF* frames into d64r-mugshot.pk3.

The pk3 carries three things:

  mugface/STF*.png  the frames (a non-namespace folder, so the PNGs do not
                    themselves claim the lump name the TEXTURES entry defines)
  TEXTURES          one Graphic per frame; at --scale N this is where the
                    XScale/YScale put the art back on a 30x31 HUD footprint
  SBARINFO          Retribution's own HUD, copied verbatim with a DrawMugShot
                    added - SBARINFO replaces wholesale rather than merging, so
                    a partial copy would drop the whole Doom 64 HUD

Usage:
    py -3 tools/build_mugshot_pk3.py --frames <dir> --scale 2
"""

import argparse
import os
import re
import struct
import zipfile

from PIL import Image
from pathlib import Path

# Repo root, derived from this file so a clone can live anywhere.
PROJ_ROOT = Path(__file__).resolve().parents[1]

WAD = str(PROJ_ROOT / r"Doom64-Retribution\D64RTR_v15.WAD")
OUT = str(PROJ_ROOT / r"Doom64-Retribution\d64r-mugshot.pk3")

# Where the face sits in the 320x240 HUD: the gap between the key icons
# (which end at x=88) and the centred 3-digit ammo counter (which starts
# around x=137). y=207 lines the frame's top up with the HEALTH/ARMOR labels.
FACE_X, FACE_Y = 105, -35


def read_sbarinfo():
    f = open(WAD, "rb")
    _, n, off = struct.unpack("<4sii", f.read(12))
    f.seek(off)
    d = f.read(n * 16)
    for i in range(n):
        fp, sz, nm = struct.unpack("<ii8s", d[i * 16:i * 16 + 16])
        if nm.decode("latin1").rstrip("\0").upper() == "SBARINFO":
            f.seek(fp)
            return f.read(sz).decode("latin1")
    raise SystemExit("SBARINFO not found in " + WAD)


def inject_mugshot(sbar, pad=0):
    """Add the DrawMugShot to the Normal and FullScreen blocks, after the keys.

    The frames carry a `pad`-wide transparent border, so the draw position moves
    up and left by the same amount: the head then keeps both its size and its
    place on screen, and the border is what the renderer's edge shave eats."""
    anchor = 'DrawSwitchableImage KeySlot 4, "NULL", "STKEYS5", 78, 220; // Red skull'
    if sbar.count(anchor) != 2:
        raise SystemExit(f"expected 2 key blocks to anchor to, found {sbar.count(anchor)}")
    x, y = FACE_X - pad, FACE_Y - pad
    added = anchor + f"\n\t\t\n\t\tDrawMugShot 5, {x}, {y};"
    return sbar.replace(anchor, added)


# --- HUD layout -------------------------------------------------------------
# Retribution ships: HEALTH at 24, keys 58..88, ammo centred at 160 with no
# label, ARMOR at 296. That puts the keys in the left block where the mugshot
# wants to be, and leaves the ammo stranded mid-screen.
#
# New layout, left to right:
#   HEALTH 24 | face 52 | AMMO 200 | keys 236..256 | ARMOR 296
#
# Widths that constrain it: a 3-digit BIGFONT number centred on x spans roughly
# x+-22, the key icons are 8px wide on a 10px pitch, and the face is 36 wide
# drawn from its left edge. So ARMOR's number occupies ~274..318 and the keys
# have to finish before 274.
# SCREEN-ANCHORED coordinates (the StatusBar blocks carry FullScreenOffsets).
#
# Retribution's HUD was ForceScaled only, which maps 320x240 into a CENTRED 4:3
# box. On an ultrawide that box stops well short of the screen edges, so "put
# AMMO on the right" could never reach the right of the monitor - x=298 was
# already the right edge of the box. With FullScreenOffsets (sbarinfo.cpp:1284)
# a negative x anchors from the RIGHT edge of the real screen and a negative y
# from the BOTTOM, so the group splits properly across any aspect ratio.
#
#   positive x = units from the left edge, negative x = units from the right
#   negative y = units up from the bottom
LABEL_Y, VALUE_Y = -32, -23   # were 208 / 217 in the 240-tall box
HEALTH_X = 84                 # left group, packed. Measured in game: this balances the
                              # gaps either side (BATTERY->HEALTH ~10u, HEALTH->face ~11u).
AMMO_X = -24                  # right group, rightmost
ARMOR_X = -70
KEY_X = (-134, -120, -106)    # red | blue | yellow
KEY_Y = -22                   # single row, on the value baseline
# The battery is drawn by d64r-rt-flashlight.pk3's ZScript, which places itself
# a fixed gap to the left of HEALTH. It only needs to know where HEALTH went.


def relayout(sbar, face_x, face_y):
    """Move the HUD elements into the new arrangement.

    Left group:  BATTERY | HEALTH | face      (battery comes from the flashlight pk3)
    Centre:      left clear for the weapon sprite
    Right group: keys | ARMOR | AMMO

    Every 3-digit BIGFONT value spans about +-21 from its centre, so the right
    group is the tight one: keys end at 222, ARMOR occupies ~229..271 and AMMO
    ~275..317, just inside the 320-wide HUD.
    """
    subs = [
        # HEALTH shifts right to clear the BATTERY column (the flashlight pk3
        # now anchors that at a fixed x=4 instead of deriving it from HEALTH).
        (r'DrawString D64HUDFONT, UNTRANSLATED, "HEALTH", 24, 208, 0, Alignment\(center\);',
         f'DrawString D64HUDFONT, UNTRANSLATED, "HEALTH", {HEALTH_X}, {LABEL_Y}, 0, Alignment(center);'),
        (r'DrawNumber 3, BIGFONT, RED, Health, Alignment\(center\), 24, 217;',
         f'DrawNumber 3, BIGFONT, RED, Health, Alignment(center), {HEALTH_X}, {VALUE_Y};'),
        # ARMOR shifts left to leave the far right for AMMO.
        (r'DrawString D64HUDFONT, UNTRANSLATED, "ARMOR", 296, 208, 0, Alignment\(center\);',
         f'DrawString D64HUDFONT, UNTRANSLATED, "ARMOR", {ARMOR_X}, {LABEL_Y}, 0, Alignment(center);'),
        (r'DrawNumber 3, BIGFONT, RED, Armor, Alignment\(center\), 296, 217;',
         f'DrawNumber 3, BIGFONT, RED, Armor, Alignment(center), {ARMOR_X}, {VALUE_Y};'),
        # ammo: off the centre line to the far right, and give it a header
        (r'DrawNumber 3, BIGFONT, RED, Ammo1, Alignment\(center\), 160, 217;',
         f'DrawString D64HUDFONT, UNTRANSLATED, "AMMO", {AMMO_X}, {LABEL_Y}, 0, Alignment(center);\n'
         f'\t\tDrawNumber 3, BIGFONT, RED, Ammo1, Alignment(center), {AMMO_X}, {VALUE_Y};'),
    ]
    # Keys: one slot PER COLOUR in a single row, not a 2x3 card/skull grid.
    # Each slot draws that colour's card and its skull at the same spot - a map
    # gives you one or the other, so they never actually collide.
    #   red 190 | blue 204 | yellow 218,  all on one baseline
    old_keys = [(2, 58, 208, "blue card"), (3, 68, 208, "yellow card"),
                (1, 78, 208, "red card"), (5, 58, 220, "blue skull"),
                (6, 68, 220, "yellow skull"), (4, 78, 220, "red skull")]
    colour_x = {"red": KEY_X[0], "blue": KEY_X[1], "yellow": KEY_X[2]}
    for slot, ox, oy, what in old_keys:
        nx = colour_x[what.split()[0]]
        subs.append((rf'(DrawSwitchableImage KeySlot {slot}, "NULL", "STKEYS\d", ){ox}, {oy};',
                     rf'\g<1>{nx}, {KEY_Y};'))
    out = sbar
    for pat, rep in subs:
        out, n = re.subn(pat, rep, out)
        if n == 0:
            raise SystemExit(f"relayout: pattern never matched: {pat}")
    print(f"  layout: BATTERY(auto) | HEALTH {HEALTH_X} | face {face_x} | "
          f"[weapon] | keys {KEY_X[0]},{KEY_X[1]},{KEY_X[2]}@{KEY_Y} | ARMOR {ARMOR_X} | AMMO {AMMO_X}")
    return out


# --- D64HUDFONT: the two glyphs Retribution never needed ---------------------
# The mod's HUD font defines exactly eight characters - A E H L M O R T - which
# is precisely what HEALTH, ARMOR and AMMO require and nothing more. "BATTERY"
# therefore rendered as " ATTER ": B and Y simply do not exist in the font and
# drew as blanks. Not a length limit.
#
# Each glyph is 6 rows tall with one fixed grey per row (a vertical gradient,
# dark at top) and binary alpha, so new letters can be drawn to match exactly.
FONT_ROW_GREY = [64, 88, 104, 128, 152, 176]
NEW_GLYPHS = {
    # name       char, 6 rows of "#" = ink, "." = transparent
    "D64HF066": ("B", ["#####..",
                       "##..##.",
                       "#####..",
                       "##..##.",
                       "##..##.",
                       "#####.."]),
    "D64HF089": ("Y", ["##..##.",
                       "##..##.",
                       ".####..",
                       "..##...",
                       "..##...",
                       "..##..."]),
}
FONT_CHARS = "A B E H L M O R T Y".split()
FONT_LUMPS = {"A": "D64HF065", "B": "D64HF066", "E": "D64HF069", "H": "D64HF072",
              "L": "D64HF076", "M": "D64HF077", "O": "D64HF079", "R": "D64HF082",
              "T": "D64HF084", "Y": "D64HF089"}


def build_font_glyphs():
    """Render the missing glyphs and the FONTDEFS that installs them."""
    import io as _io
    out = {}
    for lump, (ch, rows) in NEW_GLYPHS.items():
        h = len(rows)
        w = max(len(r) for r in rows)
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        px = img.load()
        for y, row in enumerate(rows):
            g = FONT_ROW_GREY[y]
            for x, c in enumerate(row):
                if c == "#":
                    px[x, y] = (g, g, g, 255)
        buf = _io.BytesIO()
        img.save(buf, "PNG")
        out[f"graphics/{lump}.png"] = buf.getvalue()
    # Redefining the font wholesale; this pk3 loads after the mod, so it wins.
    defs = ["// Generated by tools/build_mugshot_pk3.py - adds B and Y so the\n"
            "// flashlight's BATTERY label can render in the Doom 64 HUD font.\n",
            "D64HUDFONT\n{\n"]
    for ch in FONT_CHARS:
        defs.append(f"\t{ch} {FONT_LUMPS[ch]}\n")
    defs.append("}\n")
    out["FONTDEFS"] = "".join(defs).encode("latin1")
    return out


CLASSIC_STYLE_CVAR = "d64_hud_style"   # 0 = Classic, 1 = Modern


def classicise(sbar):
    """Re-express Retribution's ORIGINAL layout in centre-relative coordinates.

    Classic has to look exactly like the stock Doom 64 HUD, but the StatusBar
    blocks now carry FullScreenOffsets (block-level, not switchable per branch),
    where a bare x means "from the left edge of the monitor". SBARINFO's
    `<int> + center` form (sbarinfo.cpp:164, adjustRelCenter) offsets from the
    screen CENTRE instead, so the original 320-wide arrangement is reproduced by
    subtracting 160 from every x. y is already bottom-relative in both styles.

    No mugshot here - Classic is the untouched HUD.
    """
    def cx(x):
        v = x - 160
        return f"{v} + center"
    subs = [
        (r'("HEALTH", )24(, )208', rf'\g<1>{cx(24)}\g<2>-32'),
        (r'(Health, Alignment\(center\), )24, 217', rf'\g<1>{cx(24)}, -23'),
        (r'("ARMOR", )296(, )208', rf'\g<1>{cx(296)}\g<2>-32'),
        (r'(Armor, Alignment\(center\), )296, 217', rf'\g<1>{cx(296)}, -23'),
        (r'(Ammo1, Alignment\(center\), )160, 217', rf'\g<1>{cx(160)}, -23'),
    ]
    for slot, ox, oy in [(2,58,208),(3,68,208),(1,78,208),(5,58,220),(6,68,220),(4,78,220)]:
        ny = oy - 240
        subs.append((rf'(KeySlot {slot}, "NULL", "STKEYS\d", ){ox}, {oy};',
                     rf'\g<1>{cx(ox)}, {ny};'))
    out = sbar
    for pat, rep in subs:
        out, n = re.subn(pat, rep, out)
        if n == 0:
            raise SystemExit(f"classicise: pattern never matched: {pat}")
    return out


def debug_grid(sbar, frames, fw, fh):
    """Replace the HUD body with every frame drawn at once, in a grid.

    For eyeballing all 42 faces in one screenshot instead of playing until each
    state happens to trigger. DrawImage takes a literal lump name, so the grid
    is just 42 draws at computed positions in the 320x240 HUD space."""
    cols = 8
    sx, sy = 12, 6
    lines = []
    for i, fn in enumerate(sorted(frames)):
        name = os.path.splitext(fn)[0].upper()
        x = sx + (i % cols) * (fw + 1)
        y = sy + (i // cols) * (fh + 1)
        lines.append(f'\t\tDrawImage "{name}", {x}, {y};')
    body = "\n".join(lines)
    # Keep the same StatusBar headers/conditions, swap what they draw.
    out, n = re.subn(r'(InInventory "IsPlaying"\s*\{)(.*?)(\n\t\})',
                     lambda m: m.group(1) + "\n" + body + m.group(3),
                     sbar, flags=re.S)
    print(f"  DEBUG GRID: {len(lines)} frames into {n} block(s)")
    return out


HUD_ALPHA_CVAR = "d64_hud_alpha"
# One branch per slider notch. Level 0 gets no branch at all: drawing nothing is
# the same as drawing at alpha 0, and it is cheaper.
HUD_ALPHA_LEVELS = [100, 90, 80, 70, 60, 50, 40, 30, 20, 10]


def split_statusbar_blocks(sbar):
    """Yield (start, end, header_line, body_lines) for each top-level StatusBar.

    `end` is the index of the closing '}' line. Brace counting, not a regex,
    because the bodies contain nested flow-control blocks."""
    lines = sbar.split("\n")
    i = 0
    while i < len(lines):
        if re.match(r"\s*StatusBar\b", lines[i]):
            header = i
            depth = 0
            j = i
            while j < len(lines):
                depth += lines[j].count("{") - lines[j].count("}")
                if depth == 0 and j > header:
                    break
                j += 1
            else:
                raise SystemExit("unterminated StatusBar block")
            yield header, j, lines[header], lines[header + 2:j]
            i = j
        i += 1


def set_hud_alpha(sbar, alpha, face_gamma=0.5, classic_sbar=None):
    """Make the whole-HUD alpha a runtime setting driven by d64_hud_alpha.

    `StatusBar Normal, ForceScaled, 0.55` - that 0.55 is the whole HUD's ALPHA,
    not a scale (sbarinfo.cpp parses the trailing float straight into `alpha`).
    The parser demands a float LITERAL there (MustGetToken(TK_FloatConst)), so a
    cvar name cannot be put in the header. What SBARINFO *does* have is the
    `alpha <float> { ... }` block command and the `ifcvarint <cvar>, <n>` flow
    control, and nested alpha blocks multiply (CommandAlpha::Draw passes the
    parent block's Alpha()). So the header is pinned to `alpha` and the body is
    emitted once per notch of d64_hud_alpha, each inside its own alpha block.

    The 100 branch uses the default >= comparison so any stray higher value
    still draws; the rest use `equal`, so exactly one branch ever runs. A value
    that is not a multiple of 10 draws nothing - which is why RT_HudMenu's
    slider is 0..100 step 10.
    """
    lines = sbar.split("\n")
    blocks = list(split_statusbar_blocks(sbar))
    classic_blocks = list(split_statusbar_blocks(classic_sbar)) if classic_sbar else None
    if classic_blocks is not None and len(classic_blocks) != len(blocks):
        raise SystemExit("classic/modern StatusBar block count differs")
    out = []
    prev = 0
    for bi, (header, close, header_line, body) in enumerate(blocks):
        out.extend(lines[prev:header])
        # Must keep a decimal point: MustGetToken(TK_FloatConst) rejects "1".
        # FullScreenOffsets makes the coordinates screen-anchored so the HUD
        # spans an ultrawide instead of being boxed into a centred 4:3 area.
        hl = re.sub(r"(,\s*ForceScaled\s*,\s*)[0-9.]+",
                    lambda m: m.group(1) + f"{alpha:.2f}", header_line)
        if "FullScreenOffsets" not in hl:
            hl = hl.replace("ForceScaled", "ForceScaled|FullScreenOffsets", 1)
        out.append(hl)
        out.append("{")
        for lvl in HUD_ALPHA_LEVELS:
            cmp = "" if lvl == max(HUD_ALPHA_LEVELS) else ", equal"
            out.append(f"\tifcvarint {HUD_ALPHA_CVAR}, {lvl}{cmp}")
            out.append("\t{")
            body_a = lvl / 100.0
            # The mugshot is pulled into its own sibling alpha block at a
            # COMPENSATED value. It gets the same alpha as everything else
            # otherwise, but it does not read that way: the face is much darker
            # than the world behind it (~34 vs ~103), so blending drags it
            # toward the background hard - at 0.9 the face shifts +21% in
            # luminance while a bright ammo digit shifts -3%. Raising its alpha
            # on a gamma curve keeps it looking like it belongs to the same HUD.
            # It has to be a SIBLING block, not nested: nested alphas multiply,
            # so from inside the body block the face could only go darker.
            face_a = round(body_a ** face_gamma, 2) if face_gamma else body_a
            face_lines = [b for b in body if "DrawMugShot" in b]
            rest = [b for b in body if "DrawMugShot" not in b]
            out.append(f"\t\talpha {body_a:.2f}")
            out.append("\t\t{")
            if classic_blocks is None:
                out.extend(("\t\t" + b if b.strip() else b) for b in rest)
            else:
                # The style cannot be a block flag (FullScreenOffsets is set on
                # the StatusBar header), so both layouts are emitted and the
                # cvar picks one. Modern is >=1, Classic is ==0.
                out.append(f"\t\t\tifcvarint {CLASSIC_STYLE_CVAR}, 1")
                out.append("\t\t\t{")
                out.extend(("\t\t\t" + b if b.strip() else b) for b in rest)
                out.append("\t\t\t}")
                out.append(f"\t\t\tifcvarint {CLASSIC_STYLE_CVAR}, 0, equal")
                out.append("\t\t\t{")
                out.extend(("\t\t\t" + b if b.strip() else b)
                           for b in classic_blocks[bi][3])
                out.append("\t\t\t}")
            out.append("\t\t}")
            if face_lines:
                # Re-wrap in the same condition the body carries; lifting the
                # draw out of the body would otherwise drop its InInventory
                # guard and paint the face over the menu and intermission.
                # The mugshot belongs to Modern only.
                out.append(f"\t\talpha {face_a:.2f}")
                out.append("\t\t{")
                if classic_blocks is not None:
                    out.append(f"\t\t\tifcvarint {CLASSIC_STYLE_CVAR}, 1")
                    out.append("\t\t\t{")
                out.append('\t\t\t\tInInventory "IsPlaying"')
                out.append("\t\t\t\t{")
                out.extend("\t\t\t\t\t" + b.strip() for b in face_lines)
                out.append("\t\t\t\t}")
                if classic_blocks is not None:
                    out.append("\t\t\t}")
                out.append("\t\t}")
            out.append("\t}")
        out.append("}")
        prev = close + 1
    out.extend(lines[prev:])
    print(f"  HUD alpha -> {alpha:.2f} x {HUD_ALPHA_CVAR}/100 "
          f"({len(blocks)} status bar blocks, {len(HUD_ALPHA_LEVELS)} notches)")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", required=True, help="dir of generated STF*.png")
    ap.add_argument("--scale", type=int, default=2)
    ap.add_argument("--pad", type=int, default=2,
                    help="the --pad gen_mugshot used; the draw position shifts by -pad so the "
                         "head keeps its size and its place on screen")
    ap.add_argument("--debug-grid", action="store_true",
                    help="draw ALL frames at once instead of the mugshot, to check them in one screenshot")
    ap.add_argument("--face-gamma", type=float, default=0.35,
                    help="mugshot alpha = hud_alpha ** gamma. <1 keeps the dark face from "
                         "washing out faster than the bright HUD text. 1.0 = no compensation")
    ap.add_argument("--hud-alpha", type=float, default=1.0,
                    help="whole-HUD alpha; Retribution ships 0.55 (semi-transparent)")
    ap.add_argument("--out", default=OUT)
    args = ap.parse_args()

    frames = sorted(n for n in os.listdir(args.frames) if n.upper().endswith(".PNG")
                    and n.upper().startswith("STF"))
    if not frames:
        raise SystemExit("no STF*.png in " + args.frames)

    tex = ["// Generated by tools/build_mugshot_pk3.py - do not hand-edit.\n"]
    for fn in frames:
        name = os.path.splitext(fn)[0].upper()
        w, h = Image.open(os.path.join(args.frames, fn)).size
        tex.append(f'Graphic "{name}", {w}, {h}\n{{\n')
        if args.scale != 1:
            tex.append(f"\tXScale {args.scale}.0\n\tYScale {args.scale}.0\n")
        tex.append(f'\tPatch "mugface/{fn}", 0, 0\n}}\n\n')

    disp = Image.open(os.path.join(args.frames, frames[0])).size
    sbar = read_sbarinfo()
    classic = None
    if args.debug_grid:
        sbar = debug_grid(sbar, frames, disp[0] // args.scale, disp[1] // args.scale)
    else:
        # inject first: relayout moves the keys, and the injection anchors on
        # the red-skull key at its ORIGINAL coordinates.
        classic = classicise(read_sbarinfo())
        sbar = inject_mugshot(sbar, args.pad)
        sbar = relayout(sbar, FACE_X - args.pad, FACE_Y - args.pad)
    sbar = set_hud_alpha(sbar, args.hud_alpha, args.face_gamma, classic)

    with zipfile.ZipFile(args.out, "w", zipfile.ZIP_DEFLATED) as z:
        for fn in frames:
            z.write(os.path.join(args.frames, fn), "mugface/" + fn)
        z.writestr("TEXTURES", "".join(tex))
        z.writestr("SBARINFO", sbar)
        for name, data in build_font_glyphs().items():
            z.writestr(name, data)

    print(f"{args.out}")
    print(f"  {len(frames)} frames, {disp[0]}x{disp[1]} texels "
          f"-> {disp[0] // args.scale}x{disp[1] // args.scale} on the HUD")
    print(f"  DrawMugShot at {FACE_X - args.pad},{FACE_Y - args.pad}  (pad {args.pad})")


if __name__ == "__main__":
    main()
