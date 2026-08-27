"""
Export every wall/flat texture Doom 64: Unseen Evil actually SHOWS, as a single
browsable HTML page.

This is the Unseen Evil counterpart to tools/export_all_textures_gallery.py, but
the two mods answer the question differently and the difference is the whole
point of this script.

Retribution ships its own maps: read a MAPxx, read its sidedefs and sectors, and
the texture names in them are the textures you see.  Unseen Evil ships almost no
maps at all.  It is an overhaul of DOOM / DOOM II, and its
`D64UE_Terraformer_Event` retextures the IWAD's own maps at WorldLoaded by
walking `resources/d64ue_textures.*` and calling `level.ReplaceTextures`.  So a
sidedef that says STARTAN2 in doom2.wad is a Doom 64 texture on screen, and the
name in the map lump tells you nothing about what you are looking at.

Therefore this script REPLAYS the Terraformer.  It loads the IWAD maps, loads the
mapping tables in the exact order the ZScript loads them, applies each rule in
sequence the way ReplaceTextures does (including the conditional `if fitWidth`,
`if hasSpecial`, `if lessOrEqualHeight` and `if isGame` blocks and the
D64T_NOTWALL / D64T_NOTFLAT flags), and only then counts what is on the walls.

Pixels come from the pk3: plain PNG texture files read as-is, and the composite
definitions in the `TEXTURES.*` lumps rendered from their patch lists
(FlipX / FlipY / Rotate / Blend / Style Overlay / UseOffsets).  Anything the
Terraformer leaves alone still renders -- from the IWAD, through PLAYPAL, so the
stock DOOM walls that survive are visible next to the replacements.

Usage:  py -3 tools\\export_unseenevil_textures_gallery.py
        py -3 tools\\export_unseenevil_textures_gallery.py --doom2-only
Output: tools\\_gallery\\unseenevil_texture_export.html
        tools\\_gallery\\unseenevil_texture_export.json   (raw data, no pixels)
"""
from __future__ import annotations

import argparse
import base64
import io
import os
import re
import struct
import sys
import zipfile
from collections import defaultdict
from pathlib import Path

from PIL import Image

PROJ_ROOT = Path(__file__).resolve().parents[1]

PK3 = PROJ_ROOT / "Doom64-UnseenEvil" / "D64UnseenEvil-v1.0.3.pk3"
OUT_HTML = PROJ_ROOT / "tools" / "_gallery" / "unseenevil_texture_export.html"
OUT_JSON = PROJ_ROOT / "tools" / "_gallery" / "unseenevil_texture_export.json"

MAX_PX = 168  # matches the Retribution export's preview scale

# Where the launcher looks for an IWAD, minus the rerelease copies it refuses on
# purpose (different bytes, same name -- see launch-unseenevil-rt.cmd).
IWAD_SEARCH = [
    r"D:\Games\GZDoom",
    r"G:\SteamLibrary\steamapps\common\Ultimate Doom\base",
    r"G:\SteamLibrary\steamapps\common\Ultimate Doom\base\doom2",
    os.path.expandvars(r"%ProgramFiles(x86)%\Steam\steamapps\common\Doom 2\base"),
    os.path.expandvars(r"%ProgramFiles(x86)%\Steam\steamapps\common\Ultimate Doom\base"),
    os.path.expandvars(r"%USERPROFILE%\Documents\GZDoom"),
    str(PROJ_ROOT),
]

# The Terraformer's own include order: the .txt body runs first (its #include
# lines only queue the others), then the queue in the order it was pushed.
TABLE_ORDER = [
    "resources/d64ue_textures.txt",
    "resources/d64ue_textures.bricks",
    "resources/d64ue_textures.floors",
    "resources/d64ue_textures.metal",
    "resources/d64ue_textures.doors",
    "resources/d64ue_textures.stone",
    "resources/d64ue_textures.flesh",
    "resources/d64ue_textures.wood",
    "resources/d64ue_textures.switches",
]

SKIP_NAMES = {"-", "", "F_SKY1", "P_SKY1"}

WALL_SLOTS = ("top", "bot", "mid")
FLAT_SLOTS = ("flr", "ceil")


# =========================================================================== #
# WAD reading
# =========================================================================== #

class Wad:
    def __init__(self, data: bytes):
        self.data = data
        n, off = struct.unpack_from("<II", data, 4)
        self.entries: list[tuple[str, int, int]] = []
        for i in range(n):
            lo, sz, nm = struct.unpack_from("<II8s", data, off + i * 16)
            self.entries.append((nm.split(b"\0")[0].decode("ascii", "replace").upper(), lo, sz))
        self.index: dict[str, int] = {}
        for i, (nm, _, _) in enumerate(self.entries):
            self.index.setdefault(nm, i)

    def lump(self, name: str) -> bytes | None:
        i = self.index.get(name.upper())
        if i is None:
            return None
        _, off, sz = self.entries[i]
        return self.data[off : off + sz]

    def at(self, i: int) -> bytes:
        _, off, sz = self.entries[i]
        return self.data[off : off + sz]

    def between(self, start: str, end: str) -> list[tuple[str, int]]:
        """Lump names between two markers, as (name, entry index)."""
        out = []
        inside = False
        for i, (nm, _, _) in enumerate(self.entries):
            if nm == start.upper() or (nm.endswith(start.upper()) and nm[1:] == start.upper()):
                inside = True
                continue
            if nm == end.upper() or (nm.endswith(end.upper()) and nm[1:] == end.upper()):
                inside = False
                continue
            if inside:
                out.append((nm, i))
        return out


def read_pal(wad: Wad) -> list[tuple[int, int, int]]:
    raw = wad.lump("PLAYPAL")
    return [tuple(raw[i * 3 : i * 3 + 3]) for i in range(256)]


def decode_picture(raw: bytes, pal) -> Image.Image | None:
    """Doom column-based picture format -> RGBA."""
    if len(raw) < 8:
        return None
    w, h, lo, to = struct.unpack_from("<hhhh", raw, 0)
    if not (0 < w <= 4096 and 0 < h <= 4096) or len(raw) < 8 + w * 4:
        return None
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    px = im.load()
    offs = struct.unpack_from("<%dI" % w, raw, 8)
    for x in range(w):
        p = offs[x]
        if p >= len(raw):
            continue
        prev_delta = -1
        base = 0
        while p < len(raw):
            top = raw[p]
            if top == 0xFF:
                break
            cnt = raw[p + 1]
            # tall-patch convention: a non-increasing offset continues the column
            if top <= prev_delta:
                base += prev_delta
            prev_delta = top
            p += 3  # skip the unused pad byte
            for k in range(cnt):
                y = base + top + k
                if 0 <= y < h and p + k < len(raw):
                    px[x, y] = pal[raw[p + k]] + (255,)
            p += cnt + 1
    im.info["grab"] = (lo, to)
    return im


def decode_flat(raw: bytes, pal) -> Image.Image | None:
    n = len(raw)
    side = {64 * 64: 64, 128 * 128: 128, 32 * 32: 32, 8 * 8: 8, 16 * 16: 16, 256 * 256: 256}.get(n)
    if side is None:
        return None
    im = Image.new("RGBA", (side, side))
    im.putdata([pal[b] + (255,) for b in raw])
    return im


def png_grab(raw: bytes) -> tuple[int, int]:
    """PNG grAb offsets, which Pillow drops."""
    i = 8
    while i + 8 <= len(raw):
        ln = struct.unpack_from(">I", raw, i)[0]
        typ = raw[i + 4 : i + 8]
        if typ == b"grAb" and ln >= 8:
            x, y = struct.unpack_from(">ii", raw, i + 8)
            return x, y
        if typ == b"IDAT":
            break
        i += 12 + ln
    return 0, 0


# =========================================================================== #
# IWAD texture set (TEXTURE1/2 + PNAMES + flats)
# =========================================================================== #

class IwadTextures:
    def __init__(self, wad: Wad, tag: str):
        self.wad = wad
        self.tag = tag
        self.pal = read_pal(wad)
        self.patch_names: list[str] = []
        pn = wad.lump("PNAMES")
        if pn:
            cnt = struct.unpack_from("<I", pn, 0)[0]
            for i in range(cnt):
                self.patch_names.append(
                    pn[4 + i * 8 : 12 + i * 8].split(b"\0")[0].decode("ascii", "replace").upper()
                )
        self.walls: dict[str, dict] = {}
        for ln in ("TEXTURE1", "TEXTURE2"):
            raw = wad.lump(ln)
            if raw:
                self._parse_texture_lump(raw)
        self.flats: dict[str, int] = {}
        for nm, i in wad.between("F_START", "F_END"):
            if nm not in self.flats:
                self.flats[nm] = i
        self._cache: dict[str, Image.Image | None] = {}

    def _parse_texture_lump(self, raw: bytes) -> None:
        n = struct.unpack_from("<I", raw, 0)[0]
        offs = struct.unpack_from("<%di" % n, raw, 4)
        for o in offs:
            name = raw[o : o + 8].split(b"\0")[0].decode("ascii", "replace").upper()
            w, h, pc = struct.unpack_from("<hhxxxxh", raw, o + 12)
            patches = []
            for k in range(pc):
                px, py, pi = struct.unpack_from("<hhh", raw, o + 22 + k * 10)
                patches.append((px, py, pi))
            self.walls.setdefault(name, {"w": w, "h": h, "patches": patches})

    def has(self, name: str, kind: str = "any") -> bool:
        u = name.upper()
        if kind in ("any", "wall") and u in self.walls:
            return True
        if kind in ("any", "flat") and u in self.flats:
            return True
        return False

    def render_wall(self, name: str) -> Image.Image | None:
        key = "W:" + name.upper()
        if key in self._cache:
            return self._cache[key]
        d = self.walls.get(name.upper())
        im = None
        if d:
            im = Image.new("RGBA", (max(d["w"], 1), max(d["h"], 1)), (0, 0, 0, 0))
            for px, py, pi in d["patches"]:
                if not (0 <= pi < len(self.patch_names)):
                    continue
                praw = self.wad.lump(self.patch_names[pi])
                if not praw:
                    continue
                pim = decode_picture(praw, self.pal)
                if pim is None:
                    continue
                im.paste(pim, (px, py), pim)
        self._cache[key] = im
        return im

    def render_flat(self, name: str) -> Image.Image | None:
        key = "F:" + name.upper()
        if key in self._cache:
            return self._cache[key]
        i = self.flats.get(name.upper())
        im = decode_flat(self.wad.at(i), self.pal) if i is not None else None
        self._cache[key] = im
        return im


# =========================================================================== #
# Unseen Evil pk3 texture set
# =========================================================================== #

TEXDEF_RE = re.compile(
    r'^\s*(Texture|WallTexture|Flat|Graphic|Sprite)\s+"?([^",]+)"?\s*,\s*(-?\d+)\s*,\s*(-?\d+)',
    re.I | re.M,
)
PATCH_RE = re.compile(r'\b(Patch|Graphic|Sprite)\s+"?([^",]+)"?\s*,\s*(-?\d+)\s*,\s*(-?\d+)', re.I)


def strip_comments(t: str) -> str:
    t = re.sub(r"/\*.*?\*/", "", t, flags=re.S)
    return re.sub(r"//[^\n]*", "", t)


class UeTextures:
    """Resolves a name the way TexMan.CheckForTexture would for this pk3."""

    def __init__(self, path: Path, iwad_pal):
        self.zip = zipfile.ZipFile(path)
        self.pal = iwad_pal
        names = [n for n in self.zip.namelist() if not n.endswith("/")]

        self.by_path: dict[str, str] = {}      # lowercase full path -> entry
        self.by_stem: dict[str, str] = {}      # lowercase basename-no-ext -> entry
        # Short-name lookup must respect GZDoom's namespaces, and the priority
        # order here is load-bearing: brightmaps/ is NOT a texture namespace, and
        # letting brightmaps/d64/CASFL98.png win the stem over
        # textures/d64/CASFL98.png silently kills every rule that targets it.
        NS_RANK = {"textures/": 0, "flats/": 1, "patches/": 2, "graphics/": 3, "sprites/": 4}
        best: dict[str, tuple[int, str]] = {}
        for n in names:
            self.by_path[n.lower()] = n
            low = n.lower()
            rank = next((r for p, r in NS_RANK.items() if low.startswith(p)), None)
            if rank is None:
                continue
            stem = n.rsplit("/", 1)[-1]
            stem = stem.rsplit(".", 1)[0] if "." in stem else stem
            stem = stem.lower()
            if stem not in best or rank < best[stem][0]:
                best[stem] = (rank, n)
        self.by_stem = {k: v[1] for k, v in best.items()}

        # composite defs from every TEXTURES.* lump
        self.defs: dict[str, dict] = {}
        self.def_key: dict[str, str] = {}      # lowercase name / stem -> canonical def name
        for n in names:
            if n.upper().startswith("TEXTURES"):
                self._parse_textures(self.zip.read(n).decode("utf-8", "replace"))
        self._cache: dict[str, Image.Image | None] = {}

    def _parse_textures(self, text: str) -> None:
        text = strip_comments(text)
        for m in TEXDEF_RE.finditer(text):
            kind, name, w, h = m.group(1), m.group(2).strip(), int(m.group(3)), int(m.group(4))
            brace = text.find("{", m.end())
            if brace < 0:
                continue
            depth, i, end = 0, brace, -1
            while i < len(text):
                if text[i] == "{":
                    depth += 1
                elif text[i] == "}":
                    depth -= 1
                    if depth == 0:
                        end = i
                        break
                i += 1
            if end < 0:
                continue
            body = text[brace + 1 : end]
            patches = []
            for pm in PATCH_RE.finditer(body):
                src, px, py = pm.group(2).strip(), int(pm.group(3)), int(pm.group(4))
                # the patch's own optional { ... } block
                rest = body[pm.end() :]
                fb = ""
                lead = rest[: len(rest) - len(rest.lstrip())]
                if "\n" not in lead and rest.lstrip().startswith("{"):
                    s = rest.lstrip()
                    d, j = 0, 0
                    while j < len(s):
                        if s[j] == "{":
                            d += 1
                        elif s[j] == "}":
                            d -= 1
                            if d == 0:
                                break
                        j += 1
                    fb = s[: j + 1]
                patches.append({"src": src, "x": px, "y": py, "flags": self._flags(fb)})
            self.defs[name] = {"kind": kind, "w": w, "h": h, "patches": patches}
            self.def_key.setdefault(name.lower(), name)
            stem = name.rsplit("/", 1)[-1]
            self.def_key.setdefault(stem.lower(), name)

    @staticmethod
    def _flags(fb: str) -> dict:
        f: dict = {}
        if not fb:
            return f
        if re.search(r"\bFlipX\b", fb, re.I):
            f["flipx"] = True
        if re.search(r"\bFlipY\b", fb, re.I):
            f["flipy"] = True
        m = re.search(r"\bRotate\s+(-?\d+)", fb, re.I)
        if m:
            f["rotate"] = int(m.group(1))
        m = re.search(r"\bBlend\s+\"?(#?[0-9A-Fa-f]{6}|[A-Za-z ]+)\"?\s*(?:,\s*([0-9.]+))?", fb, re.I)
        if m:
            f["blend"] = (m.group(1), float(m.group(2)) if m.group(2) else None)
        m = re.search(r"\bStyle\s+(\w+)", fb, re.I)
        if m:
            f["style"] = m.group(1).lower()
        m = re.search(r"\bAlpha\s+([0-9.]+)", fb, re.I)
        if m:
            f["alpha"] = float(m.group(1))
        if re.search(r"\bUseOffsets\b", fb, re.I):
            f["useoffsets"] = True
        return f

    # ---- resolution -------------------------------------------------------

    def resolve(self, name: str) -> str | None:
        """Canonical key for a UE-provided texture, or None."""
        n = name.strip().strip('"')
        low = n.lower()
        if low in self.def_key:
            return "def:" + self.def_key[low]
        if low in self.by_path:
            return "file:" + self.by_path[low]
        for ext in (".png", ".jpg", ".lmp"):
            if low + ext in self.by_path:
                return "file:" + self.by_path[low + ext]
        stem = low.rsplit("/", 1)[-1]
        stem = stem.rsplit(".", 1)[0] if "." in stem else stem
        if stem in self.def_key:
            return "def:" + self.def_key[stem]
        e = self.by_stem.get(stem)
        if e:
            return "file:" + e
        return None

    # ---- rendering --------------------------------------------------------

    def render(self, key: str, depth: int = 0) -> Image.Image | None:
        if key in self._cache:
            return self._cache[key]
        if depth > 6:
            return None
        im = None
        if key.startswith("file:"):
            raw = self.zip.read(key[5:])
            if raw[:8] == b"\x89PNG\r\n\x1a\n":
                im = Image.open(io.BytesIO(raw)).convert("RGBA")
                im.info["grab"] = png_grab(raw)
            else:
                im = decode_picture(raw, self.pal)
        elif key.startswith("def:"):
            im = self._render_def(self.defs[key[4:]], depth)
        self._cache[key] = im
        return im

    def _render_def(self, d: dict, depth: int) -> Image.Image | None:
        canvas = Image.new("RGBA", (max(d["w"], 1), max(d["h"], 1)), (0, 0, 0, 0))
        for p in d["patches"]:
            k = self.resolve(p["src"])
            pim = self.render(k, depth + 1) if k else None
            if pim is None:
                pim = IWAD_FALLBACK(p["src"])
            if pim is None:
                continue
            pim = pim.copy()
            f = p["flags"]
            ox, oy = pim.info.get("grab", (0, 0)) if f.get("useoffsets") else (0, 0)
            if f.get("flipx"):
                pim = pim.transpose(Image.FLIP_LEFT_RIGHT)
            if f.get("flipy"):
                pim = pim.transpose(Image.FLIP_TOP_BOTTOM)
            if f.get("rotate"):
                pim = pim.rotate(-f["rotate"], expand=True)
            bl = f.get("blend")
            if bl:
                pim = apply_blend(pim, bl)
            a = f.get("alpha")
            if a is not None and a < 1.0:
                al = pim.getchannel("A").point(lambda v, a=a: int(v * a))
                pim.putalpha(al)
            dest = (p["x"] - ox, p["y"] - oy)
            style = f.get("style", "copy")
            if style in ("overlay", "translucent", "add", "normal") or a is not None:
                layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
                layer.paste(pim, dest)
                canvas = Image.alpha_composite(canvas, layer)
            else:
                # Style Copy still SKIPS fully-transparent source texels -- see
                # iCopyColors in common/textures/bitmap.cpp, where the copy blend's
                # ProcessAlpha0() is false and an alpha-0 pixel is never written.
                # Pasting without the mask instead wipes whatever is underneath,
                # which turned d64_bronzewall_lit (a bronze wall plus a
                # transparent "justlight" overlay) into a blank white plate.
                canvas.paste(pim, dest, pim)
        return canvas


NAMED_COLORS = {"white": (255, 255, 255), "black": (0, 0, 0), "red": (255, 0, 0)}


def apply_blend(im: Image.Image, bl) -> Image.Image:
    """GZDoom TEXTURES Blend: no alpha -> per-channel multiply (BLEND_MODULATE);
    with alpha -> lerp toward the colour.  See multipatchtexture.cpp GetBlendMap."""
    spec, alpha = bl
    s = spec.strip().lstrip("#")
    if re.fullmatch(r"[0-9A-Fa-f]{6}", s):
        cr, cg, cb = int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)
    else:
        cr, cg, cb = NAMED_COLORS.get(spec.strip().lower(), (255, 255, 255))
    r, g, b, a = im.split()
    if alpha is None:
        r = r.point(lambda v: v * cr // 255)
        g = g.point(lambda v: v * cg // 255)
        b = b.point(lambda v: v * cb // 255)
    else:
        t = max(0.0, min(1.0, alpha))
        r = r.point(lambda v: int(cr * t + v * (1 - t)))
        g = g.point(lambda v: int(cg * t + v * (1 - t)))
        b = b.point(lambda v: int(cb * t + v * (1 - t)))
    return Image.merge("RGBA", (r, g, b, a))


IWAD_FALLBACK = lambda name: None  # rebound in main() once the IWADs are open


# =========================================================================== #
# Mapping tables
# =========================================================================== #

class Rule:
    __slots__ = ("old", "new", "check", "value", "not_wall", "not_flat")

    def __init__(self, old, new, check, value, not_wall, not_flat):
        self.old, self.new = old, new
        self.check, self.value = check, value
        self.not_wall, self.not_flat = not_wall, not_flat


def parse_tables(ue: UeTextures) -> list[Rule]:
    rules: list[Rule] = []
    for fn in TABLE_ORDER:
        text = ue.zip.read(fn).decode("utf-8", "replace")
        check, value = None, None
        for raw in text.splitlines():
            s = raw.strip()
            if not s or s.startswith("//") or s.startswith("#"):
                continue
            if s.startswith("{"):
                continue
            if s.startswith("}"):
                check, value = None, None
                continue
            low = s.lower()
            if low.startswith("if"):
                body = s[2:].strip().rstrip(")")
                if "(" in body:
                    fname, arg = body.split("(", 1)
                else:
                    fname, arg = body, ""
                fname = fname.strip().lower()
                if fname == "fitwidth":
                    check, value = "fitwidth", int(arg)
                elif fname == "isgame":
                    check, value = "isgame", arg.strip().upper()
                elif fname == "hasspecial":
                    check, value = "hasspecial", None
                elif fname == "lessorequalheight":
                    check, value = "loeheight", int(arg)
                elif fname == "greaterorequalheight":
                    check, value = "goeheight", int(arg)
                else:
                    check, value = None, None
                continue
            parts = s.split(":")
            if len(parts) < 2:
                continue
            flag = parts[2].strip().upper() if len(parts) > 2 else ""
            rules.append(
                Rule(
                    parts[0].strip(),
                    parts[1].strip(),
                    check,
                    value,
                    not_wall=(flag == "D64T_NOTWALL"),
                    not_flat=(flag == "D64T_NOTFLAT"),
                )
            )
    return rules


# =========================================================================== #
# Map reading + Terraformer replay
# =========================================================================== #

def read_binary_map(wad: Wad, start: int):
    """(sides, sectors, lines) from the lumps following a map marker."""
    lumps = {}
    i = start + 1
    while i < len(wad.entries):
        nm = wad.entries[i][0]
        if nm in ("THINGS", "LINEDEFS", "SIDEDEFS", "VERTEXES", "SEGS", "SSECTORS",
                  "NODES", "SECTORS", "REJECT", "BLOCKMAP", "BEHAVIOR", "SCRIPTS",
                  "TEXTMAP", "ZNODES", "DIALOGUE", "ENDMAP"):
            lumps[nm] = wad.at(i)
            i += 1
            continue
        break

    if "TEXTMAP" in lumps:
        return read_udmf_map(lumps["TEXTMAP"].decode("utf-8", "replace"))

    def nm8(b):
        return b.split(b"\0")[0].decode("ascii", "replace").upper()

    verts = []
    vraw = lumps.get("VERTEXES", b"")
    for k in range(len(vraw) // 4):
        verts.append(struct.unpack_from("<hh", vraw, k * 4))

    secs = []
    sraw = lumps.get("SECTORS", b"")
    for k in range(len(sraw) // 26):
        fh, ch, fp, cp, li, sp, tg = struct.unpack_from("<hh8s8shhh", sraw, k * 26)
        secs.append({"flr": nm8(fp), "ceil": nm8(cp), "light": li, "h": abs(ch - fh)})

    sides = []
    draw = lumps.get("SIDEDEFS", b"")
    for k in range(len(draw) // 30):
        xo, yo, up, lo_, mid, sec = struct.unpack_from("<hh8s8s8sh", draw, k * 30)
        sides.append({"top": nm8(up), "bot": nm8(lo_), "mid": nm8(mid), "sector": sec,
                      "special": 0, "len": 0.0})

    lraw = lumps.get("LINEDEFS", b"")
    for k in range(len(lraw) // 14):
        v1, v2, fl, sp, tg, sr, sl = struct.unpack_from("<HHhhhHH", lraw, k * 14)
        ln = 0.0
        if v1 < len(verts) and v2 < len(verts):
            dx = verts[v1][0] - verts[v2][0]
            dy = verts[v1][1] - verts[v2][1]
            ln = (dx * dx + dy * dy) ** 0.5
        for s in (sr, sl):
            if s != 0xFFFF and s < len(sides):
                sides[s]["special"] = sp
                sides[s]["len"] = ln
    return sides, secs


UDMF_BLOCK = re.compile(r"([A-Za-z]+)\s*\{([^{}]*)\}", re.S)
UDMF_FIELD = re.compile(r'([A-Za-z0-9_]+)\s*=\s*("(?:[^"\\]|\\.)*"|[-+]?[0-9.]+|true|false)\s*;')


def read_udmf_map(text: str):
    verts, secs, sides, lines = [], [], [], []
    for bm in UDMF_BLOCK.finditer(text):
        kind = bm.group(1).lower()
        f = {}
        for fm in UDMF_FIELD.finditer(bm.group(2)):
            v = fm.group(2)
            f[fm.group(1).lower()] = v[1:-1] if v.startswith('"') else v
        if kind == "vertex":
            verts.append((float(f.get("x", 0)), float(f.get("y", 0))))
        elif kind == "sector":
            secs.append({
                "flr": f.get("texturefloor", "-").upper(),
                "ceil": f.get("textureceiling", "-").upper(),
                "light": int(float(f.get("lightlevel", 160))),
                "h": abs(float(f.get("heightceiling", 0)) - float(f.get("heightfloor", 0))),
            })
        elif kind == "sidedef":
            sides.append({
                "top": f.get("texturetop", "-").upper(),
                "bot": f.get("texturebottom", "-").upper(),
                "mid": f.get("texturemiddle", "-").upper(),
                "sector": int(f.get("sector", 0)),
                "special": 0, "len": 0.0,
            })
        elif kind == "linedef":
            lines.append(f)
    for f in lines:
        try:
            v1 = verts[int(f.get("v1", 0))]
            v2 = verts[int(f.get("v2", 0))]
            ln = ((v1[0] - v2[0]) ** 2 + (v1[1] - v2[1]) ** 2) ** 0.5
        except (IndexError, ValueError):
            ln = 0.0
        sp = int(float(f.get("special", 0)))
        for key in ("sidefront", "sideback"):
            if key in f:
                si = int(f[key])
                if 0 <= si < len(sides):
                    sides[si]["special"] = sp
                    sides[si]["len"] = ln
    return sides, secs


def terraform(sides, secs, rules, game: str, resolve):
    """Replay level.ReplaceTextures over one map's sides and sectors.

    Slots hold canonical keys, so a chained rule (a rule whose `old` is the
    output of an earlier rule) matches, exactly as it does in the engine where
    ReplaceTextures compares texture indices.
    """
    for s in sides:
        for slot in WALL_SLOTS:
            s[slot] = resolve(s[slot], "wall")
    for c in secs:
        for slot in FLAT_SLOTS:
            c[slot] = resolve(c[slot], "flat")

    for r in rules:
        if r.check == "isgame" and r.value != game:
            continue
        old_w = resolve(r.old, "wall")
        old_f = resolve(r.old, "flat")
        new_w = resolve(r.new, "wall")
        new_f = resolve(r.new, "flat")
        if (old_w is None and old_f is None) or (new_w is None and new_f is None):
            continue  # CheckForTexture said invalid -> the engine skips the line

        if not r.not_wall and old_w is not None and new_w is not None:
            for s in sides:
                if r.check == "fitwidth" and (round(s["len"]) % r.value) != 0:
                    continue
                if r.check == "hasspecial" and s["special"] == 0:
                    continue
                if r.check == "loeheight" and not (s["_h"] <= r.value):
                    continue
                if r.check == "goeheight" and not (s["_h"] >= r.value):
                    continue
                for slot in WALL_SLOTS:
                    if s[slot] == old_w:
                        s[slot] = new_w

        # conditional blocks only walk level.Sides -- flats are untouched there
        if r.check is None or r.check == "isgame":
            if not r.not_flat and old_f is not None and new_f is not None:
                for c in secs:
                    for slot in FLAT_SLOTS:
                        if c[slot] == old_f:
                            c[slot] = new_f
    return sides, secs


# =========================================================================== #
# main
# =========================================================================== #

def find_iwad(want: str) -> Path | None:
    env = os.environ.get("D64RT_UE_IWAD")
    if env and Path(env).name.lower() == want and Path(env).exists():
        return Path(env)
    for d in IWAD_SEARCH:
        p = Path(d) / want
        if p.exists():
            return p
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--doom2-only", action="store_true", help="skip the Ultimate Doom side")
    ap.add_argument("--webp", action="store_true", help="encode previews as lossless WebP")
    args = ap.parse_args()

    d2p = find_iwad("doom2.wad")
    d1p = None if args.doom2_only else find_iwad("doom.wad")
    if d2p is None:
        sys.exit("no doom2.wad found -- set D64RT_UE_IWAD or see launch-unseenevil-rt.cmd")
    print("doom2.wad:", d2p)
    if d1p:
        print("doom.wad :", d1p)

    d2 = IwadTextures(Wad(d2p.read_bytes()), "DOOM2")
    d1 = IwadTextures(Wad(d1p.read_bytes()), "DOOM") if d1p else None

    ue = UeTextures(PK3, d2.pal)
    print(f"UE composite defs: {len(ue.defs)}   UE files: {len(ue.by_path)}")

    global IWAD_FALLBACK
    IWAD_FALLBACK = lambda name: (
        d2.render_wall(name) if d2.has(name, "wall")
        else d2.render_flat(name) if d2.has(name, "flat")
        else None
    )

    rules = parse_tables(ue)
    print(f"terraformer rules: {len(rules)}")

    # A name resolves to UE first (it loads after the IWAD), then the IWAD.
    def make_resolver(iw: IwadTextures):
        cache: dict[tuple[str, str], str | None] = {}

        def resolve(name: str, kind: str) -> str | None:
            if not name or name.upper() in SKIP_NAMES:
                return None
            k = (name, kind)
            if k in cache:
                return cache[k]
            r = ue.resolve(name)
            if r is None:
                u = name.upper()
                if kind == "wall" and iw.has(u, "wall"):
                    r = "iwad:wall:" + u
                elif kind == "flat" and iw.has(u, "flat"):
                    r = "iwad:flat:" + u
                elif iw.has(u, "wall"):
                    r = "iwad:wall:" + u
                elif iw.has(u, "flat"):
                    r = "iwad:flat:" + u
            cache[k] = r
            return r

        return resolve

    # ---- collect maps ----
    jobs: list[tuple[str, str, IwadTextures, Wad, int]] = []  # (map, game, texset, wad, idx)
    for iw, game, pat in ((d2, "DOOM2", r"MAP\d\d"), (d1, "DOOM1", r"E\dM\d")):
        if iw is None:
            continue
        for i, (nm, _, _) in enumerate(iw.wad.entries):
            if re.fullmatch(pat, nm) and i + 1 < len(iw.wad.entries) and \
                    iw.wad.entries[i + 1][0] in ("THINGS", "TEXTMAP"):
                jobs.append((nm, game, iw, iw.wad, i))

    # Unseen Evil's own two maps, from inside the pk3
    for entry, game in (("maps/64UE_SIN.wad", "DOOM2"), ("maps/64UE_DIS.wad", "DOOM1")):
        try:
            w = Wad(ue.zip.read(entry))
        except KeyError:
            continue
        iw = d2 if game == "DOOM2" else (d1 or d2)
        for i, (nm, _, _) in enumerate(w.entries):
            if i + 1 < len(w.entries) and w.entries[i + 1][0] in ("THINGS", "TEXTMAP"):
                jobs.append((entry.split("/")[-1].replace(".wad", ""), game, iw, w, i))
                break

    print(f"maps: {len(jobs)}")

    usage: dict[str, dict] = defaultdict(
        lambda: {"per_map": defaultdict(int), "placements": set(), "stock": set(),
                 "light_min": None, "light_max": None, "games": set()}
    )
    map_list: list[tuple[str, str]] = []

    for mname, game, iw, wad, idx in jobs:
        resolve = make_resolver(iw)
        sides, secs = read_binary_map(wad, idx)
        if not sides and not secs:
            continue
        map_list.append((mname, game))

        # stock names, kept for the "replaces" line before terraforming eats them
        stock = []
        for s in sides:
            stock.append({slot: s[slot] for slot in WALL_SLOTS})
        stock_f = [{slot: c[slot] for slot in FLAT_SLOTS} for c in secs]

        for s in sides:
            si = s["sector"]
            s["_h"] = secs[si]["h"] if 0 <= si < len(secs) else 0
        terraform(sides, secs, rules, game, resolve)

        for k, s in enumerate(sides):
            si = s["sector"]
            light = secs[si]["light"] if 0 <= si < len(secs) else 160
            for slot in WALL_SLOTS:
                key = s[slot]
                if key is None:
                    continue
                u = usage[key]
                u["per_map"][mname] += 1
                u["placements"].add(slot)
                u["games"].add(game)
                orig = stock[k][slot]
                if orig and orig not in SKIP_NAMES:
                    u["stock"].add(orig)
                u["light_min"] = light if u["light_min"] is None else min(u["light_min"], light)
                u["light_max"] = light if u["light_max"] is None else max(u["light_max"], light)

        for k, c in enumerate(secs):
            light = c["light"]
            for slot in FLAT_SLOTS:
                key = c[slot]
                if key is None:
                    continue
                u = usage[key]
                u["per_map"][mname] += 1
                u["placements"].add(slot)
                u["games"].add(game)
                orig = stock_f[k][slot]
                if orig and orig not in SKIP_NAMES:
                    u["stock"].add(orig)
                u["light_min"] = light if u["light_min"] is None else min(u["light_min"], light)
                u["light_max"] = light if u["light_max"] is None else max(u["light_max"], light)

    print(f"distinct textures on screen: {len(usage)}")

    # ---- render ----
    records, missing = [], []
    for key in sorted(usage.keys()):
        u = usage[key]
        if key.startswith("iwad:wall:"):
            im = d2.render_wall(key[10:]) or (d1.render_wall(key[10:]) if d1 else None)
            src, disp = "stock", key[10:]
        elif key.startswith("iwad:flat:"):
            im = d2.render_flat(key[10:]) or (d1.render_flat(key[10:]) if d1 else None)
            src, disp = "stock", key[10:]
        elif key.startswith("def:"):
            im = ue.render(key)
            src, disp = "composite", key[4:].rsplit("/", 1)[-1]
        else:
            im = ue.render(key)
            src, disp = "file", key[5:].rsplit("/", 1)[-1].rsplit(".", 1)[0]
        if im is None or im.size[0] == 0 or im.size[1] == 0:
            missing.append(key)
            continue

        w, h = im.size
        prev = im
        if max(w, h) > MAX_PX * 2:
            sc = (MAX_PX * 2) / max(w, h)
            prev = im.resize((max(1, round(w * sc)), max(1, round(h * sc))), Image.BOX)
        buf = io.BytesIO()
        if args.webp:
            prev.save(buf, "WEBP", lossless=True)
            mime = "image/webp"
        else:
            prev.save(buf, "PNG", optimize=True)
            mime = "image/png"

        per_map = dict(u["per_map"])
        origin = key.split(":", 1)[1] if ":" in key else key
        records.append({
            "key": key, "name": disp, "src": src, "origin": origin,
            "w": w, "h": h,
            "uses": sum(per_map.values()),
            "maps": sorted(per_map.keys()),
            "per_map": per_map,
            "placements": sorted(u["placements"]),
            "stock": sorted(u["stock"]),
            "games": sorted(u["games"]),
            "light_min": u["light_min"], "light_max": u["light_max"],
            "mime": mime,
            "b64": base64.b64encode(buf.getvalue()).decode("ascii"),
        })

    print(f"rendered: {len(records)}   no pixels: {len(missing)}")
    if missing:
        print("  missing sample:", missing[:15])

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    import json
    OUT_JSON.write_text(json.dumps({
        "generated_from": str(PK3),
        "iwads": [str(d2p)] + ([str(d1p)] if d1p else []),
        "map_count": len(map_list),
        "texture_count": len(records),
        "rules": len(rules),
        "textures": [{k: v for k, v in r.items() if k != "b64"} for r in records],
    }, indent=2), encoding="utf-8")

    write_html(records, map_list, len(rules), d2p, d1p)
    size = OUT_HTML.stat().st_size
    print(f"wrote {OUT_HTML}  ({size / 1048576:.2f} MB)")
    if size > 15 * 1048576:
        print("  WARNING: over the 16 MB artifact budget -- rerun with --webp")


def write_html(records, map_list, rule_count, d2p, d1p) -> None:
    import json

    games = sorted({g for _, g in map_list})
    opts = ['<option value="all">all maps</option>']
    for g in games:
        label = "DOOM II" if g == "DOOM2" else "Ultimate DOOM"
        opts.append(f'<optgroup label="{label}">')
        for m, mg in map_list:
            if mg == g:
                opts.append(f'<option value="{m}">{m}</option>')
        opts.append("</optgroup>")
    map_options = "".join(opts)

    SRC_LABEL = {"file": "pk3 art", "composite": "composite", "stock": "stock DOOM"}

    figs = []
    for r in records:
        w, h = r["w"], r["h"]
        scale = MAX_PX / max(w, h) if max(w, h) > 0 else 1
        dw, dh = max(1, round(w * scale)), max(1, round(h * scale))
        badges = "".join(f'<span class="m">{m}</span>' for m in r["maps"][:8])
        more = f'<span class="m">+{len(r["maps"]) - 8}</span>' if len(r["maps"]) > 8 else ""
        light = ""
        if r["light_min"] is not None:
            light = f' &middot; light {r["light_min"]}&ndash;{r["light_max"]}'
        placement = "+".join(r["placements"])
        stock = ""
        if r["src"] != "stock" and r["stock"]:
            shown = ", ".join(r["stock"][:8])
            if len(r["stock"]) > 8:
                shown += f", +{len(r['stock']) - 8}"
            stock = f'<p class="note">stands in for {shown}</p>'
        elif r["src"] == "stock":
            stock = '<p class="note warn">not replaced &mdash; stock DOOM art still on screen</p>'
        path = f'<p class="note path">{r["origin"]}</p>' if r["src"] != "stock" else ""
        pm = json.dumps(r["per_map"]).replace('"', "&quot;")
        figs.append(
            f'''<figure class="tx" data-name="{r["name"].upper()}" data-uses="{r["uses"]}"
  data-maps="{" ".join(r["maps"])}" data-src="{r["src"]}" data-permap="{pm}">
  <div class="px"><img style="--w:{dw}px;--h:{dh}px" src="data:{r["mime"]};base64,{r["b64"]}"
    alt="{r["name"]}" loading="lazy" width="{dw}" height="{dh}"></div>
  <figcaption>
    <div class="hd"><b>{r["name"]}</b><span class="maps">{badges}{more}</span></div>
    <dl>
      <div><dt>game</dt><dd class="n">{r["uses"]}</dd></div>
      <div><dt>here</dt><dd class="n here-val">{r["uses"]}</dd></div>
      <div><dt>px</dt><dd class="n">{w}&times;{h}</dd></div>
      <div><dt>src</dt><dd class="tag t-{r["src"]}">{SRC_LABEL[r["src"]]}</dd></div>
    </dl>
    <p class="meta">{placement}{light}</p>
    {stock}{path}
  </figcaption>
</figure>'''
        )

    n_file = sum(1 for r in records if r["src"] == "file")
    n_comp = sum(1 for r in records if r["src"] == "composite")
    n_stock = sum(1 for r in records if r["src"] == "stock")
    iwad_line = d2p.name + (" + " + d1p.name if d1p else "")
    stock_uses = sum(r["uses"] for r in records if r["src"] == "stock")
    all_uses = sum(r["uses"] for r in records)

    html = f'''<title>Every texture Unseen Evil puts on screen</title>
<style>
:root {{
  --paper:#E9ECEF; --card:#F7F8FA; --edge:#C6CDD4; --edge-soft:#DCE2E7;
  --ink:#131A20; --ink-2:#495660; --ink-3:#6B7883;
  --lamp-line:#B0741F; --lamp-ink:#7A4A0C; --lamp-bg:#F4E4C9;
  --warn-ink:#8A2C1E; --warn-bg:#F6DCD6;
  --well:#171D23; --field:#FFFFFF;
}}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{
    --paper:#0E1317; --card:#171E24; --edge:#2C363E; --edge-soft:#232C33;
    --ink:#E4EAEF; --ink-2:#9DAAB4; --ink-3:#75838D;
    --lamp-line:#8A6A3B; --lamp-ink:#F0BC6E; --lamp-bg:#33260F;
    --warn-ink:#F0A08C; --warn-bg:#3A1A13;
    --well:#080B0E; --field:#0C1115;
  }}
}}
:root[data-theme="dark"] {{
  --paper:#0E1317; --card:#171E24; --edge:#2C363E; --edge-soft:#232C33;
  --ink:#E4EAEF; --ink-2:#9DAAB4; --ink-3:#75838D;
  --lamp-line:#8A6A3B; --lamp-ink:#F0BC6E; --lamp-bg:#33260F;
  --warn-ink:#F0A08C; --warn-bg:#3A1A13;
  --well:#080B0E; --field:#0C1115;
}}
* {{ box-sizing:border-box; }}
body {{
  background:var(--paper); color:var(--ink);
  font:16px/1.6 system-ui,-apple-system,"Segoe UI",sans-serif;
  margin:0; padding:clamp(18px,3.4vw,44px);
}}
.wrap {{ max-width:1320px; margin:0 auto; display:flex; flex-direction:column; gap:28px; }}
.mono, code, dl, .hd b, h1, .eyebrow, button, input, select, .m, .tag, .path
  {{ font-family:ui-monospace,"Cascadia Mono",Consolas,"SF Mono",monospace; }}
code {{ font-size:.88em; background:var(--edge-soft); padding:.1em .34em; border-radius:3px; }}

header {{ display:flex; flex-direction:column; gap:13px; max-width:72ch; }}
.eyebrow {{ font-size:12px; letter-spacing:.14em; text-transform:uppercase; color:var(--ink-3); }}
h1 {{ font-weight:600; font-size:clamp(23px,3.2vw,32px); line-height:1.22;
  letter-spacing:-.01em; text-wrap:balance; margin:0; }}
header p {{ margin:0; color:var(--ink-2); }}

.bar {{ position:sticky; top:0; z-index:5; background:var(--paper);
  border-bottom:1px solid var(--edge); padding:12px 0;
  display:flex; gap:10px; align-items:center; flex-wrap:wrap; }}
.bar input, .bar select {{ background:var(--field); color:var(--ink); border:1px solid var(--edge);
  border-radius:4px; padding:7px 10px; font-size:13.5px; min-width:120px; }}
.grp {{ display:flex; border:1px solid var(--edge); border-radius:4px; overflow:hidden; }}
.grp button {{ background:var(--card); color:var(--ink-2); border:0; cursor:pointer;
  padding:7px 12px; font-size:12.5px; letter-spacing:.03em; }}
.grp button + button {{ border-left:1px solid var(--edge); }}
.grp button[aria-pressed="true"] {{ background:var(--lamp-bg); color:var(--lamp-ink); }}
button:focus-visible, input:focus-visible, select:focus-visible
  {{ outline:2px solid var(--lamp-line); outline-offset:1px; }}
.count {{ color:var(--ink-3); font-size:13px; margin-left:auto; font-variant-numeric:tabular-nums; }}

.band {{ display:grid; gap:1px; background:var(--edge); border:1px solid var(--edge);
  border-radius:5px; overflow:hidden; grid-template-columns:repeat(auto-fit,minmax(168px,1fr)); }}
.stat {{ background:var(--card); padding:14px 16px; display:flex; flex-direction:column; gap:3px; }}
.stat b {{ font-family:ui-monospace,"Cascadia Mono",Consolas,monospace; font-size:26px;
  font-weight:600; line-height:1; font-variant-numeric:tabular-nums; letter-spacing:-.02em; }}
.stat span {{ font-size:11.5px; letter-spacing:.05em; text-transform:uppercase; color:var(--ink-3); }}
.stat.miss {{ background:var(--warn-bg); }}
.stat.miss b, .stat.miss span {{ color:var(--warn-ink); }}

.grid {{ display:grid; gap:14px; grid-template-columns:repeat(auto-fill,minmax(224px,1fr)); }}
.tx {{ margin:0; background:var(--card); border:1px solid var(--edge); border-radius:5px;
  overflow:hidden; display:flex; flex-direction:column; }}
.tx.matched {{ border-color:var(--lamp-line); }}
.tx[hidden] {{ display:none; }}
.px {{ background:var(--well); display:grid; place-items:center; padding:16px 0;
  border-bottom:1px solid var(--edge-soft); }}
.px img {{ width:var(--w); height:var(--h); image-rendering:pixelated; display:block;
  outline:1px solid rgba(140,150,160,.35); outline-offset:2px; }}
figcaption {{ padding:11px 13px 13px; display:flex; flex-direction:column; gap:7px; }}
.hd {{ display:flex; align-items:baseline; justify-content:space-between; gap:8px; }}
.hd b {{ font-size:13px; letter-spacing:.02em; overflow-wrap:anywhere; }}
.maps {{ display:flex; gap:3px; flex-wrap:wrap; justify-content:flex-end; }}
.m {{ font-size:10px; letter-spacing:.04em; padding:2px 5px; border-radius:3px;
  background:var(--edge-soft); color:var(--ink-3); }}
.matched .m {{ background:var(--lamp-bg); color:var(--lamp-ink); }}
dl {{ margin:0; display:flex; gap:12px; font-size:11.5px; flex-wrap:wrap; }}
dl div {{ display:flex; gap:5px; }}
dt {{ color:var(--ink-3); margin:0; }}
dd {{ margin:0; color:var(--ink); }}
.n {{ font-variant-numeric:tabular-nums; }}
.tag {{ font-size:10.5px; padding:1px 5px; border-radius:3px; background:var(--edge-soft);
  color:var(--ink-2); }}
.t-stock {{ background:var(--warn-bg); color:var(--warn-ink); }}
.t-composite {{ background:var(--lamp-bg); color:var(--lamp-ink); }}
.meta {{ margin:0; font-size:12px; color:var(--ink-2); }}
.note {{ margin:0; font-size:11.5px; color:var(--ink-3); overflow-wrap:anywhere; }}
.note.warn {{ color:var(--warn-ink); }}
.path {{ font-size:10.5px; color:var(--ink-3); opacity:.75; }}
footer {{ color:var(--ink-3); font-size:13.5px; border-top:1px solid var(--edge);
  padding-top:16px; max-width:76ch; display:flex; flex-direction:column; gap:10px; }}
</style>

<div class="wrap">
<header>
  <div class="eyebrow">{len(map_list)} maps &middot; D64UnseenEvil-v1.0.3.pk3 + {iwad_line}</div>
  <h1>Every texture Unseen Evil puts on screen</h1>
  <p>Unseen Evil ships almost no maps. It is an overhaul of DOOM&nbsp;II and Ultimate DOOM,
  and its <span class="mono">Terraformer</span> retextures the IWAD's own levels at load
  time from <span class="mono">resources/d64ue_textures.*</span>. So the name in a map lump
  tells you nothing about what you see &mdash; a sidedef that says
  <span class="mono">STARTAN2</span> is a Doom&nbsp;64 wall on screen.</p>
  <p>This page replays that. All {rule_count} Terraformer rules are applied in the engine's
  own order, including the conditional <span class="mono">fitWidth</span> /
  <span class="mono">hasSpecial</span> / <span class="mono">lessOrEqualHeight</span> /
  <span class="mono">isGame</span> blocks, and only then is the wall counted. Pixels come
  from the pk3 &mdash; {n_file} plain art files and {n_comp} composites rendered from their
  <span class="mono">TEXTURES</span> patch lists. The {n_stock} marked
  <b class="mono">stock DOOM</b> are what the Terraformer <i>misses</i>: original id art
  still showing through, decoded from the IWAD.</p>
  <p><b>here</b> counts uses inside the map the filter is scoped to; <b>game</b> is the
  total across all {len(map_list)}. <b>light</b> is the sector light-level range every use
  was found at. Ordered rarest first.</p>
</header>

<div class="band">
  <div class="stat"><b>{len(records)}</b><span>textures on screen</span></div>
  <div class="stat"><b>{all_uses}</b><span>wall &amp; flat placements</span></div>
  <div class="stat"><b>{rule_count}</b><span>Terraformer rules</span></div>
  <div class="stat"><b>{len(map_list)}</b><span>maps retextured</span></div>
  <div class="stat miss"><b>{n_stock}</b><span>never replaced &middot; {stock_uses} placements</span></div>
</div>

<div class="bar">
  <input id="q" type="search" placeholder="filter by name&hellip;" aria-label="Filter by name">
  <select id="mapSel" aria-label="Map">{map_options}</select>
  <select id="srcSel" aria-label="Source">
    <option value="all">any source</option>
    <option value="file">pk3 art</option>
    <option value="composite">composite</option>
    <option value="stock">stock DOOM (not replaced)</option>
  </select>
  <div class="grp" role="group" aria-label="Sort">
    <button data-sort="uses" aria-pressed="true">rarest first</button>
    <button data-sort="name" aria-pressed="false">A&ndash;Z</button>
    <button data-sort="here" aria-pressed="false">most used here</button>
  </div>
  <span class="count" id="count"></span>
</div>

<div class="grid" id="grid">
{"".join(figs)}
</div>

<footer>
  <p>Generated by <code>tools/export_unseenevil_textures_gallery.py</code> from
  <code>D64UnseenEvil-v1.0.3.pk3</code> and <code>{iwad_line}</code>.</p>
  <p>Composites are rendered the way GZDoom builds them: <code>Blend</code> without an alpha
  is a per-channel multiply (<code>BLEND_MODULATE</code>), <code>Style Overlay</code> is
  alpha-over, plain patches copy. Sky flats and <code>-</code> are excluded.</p>
</footer>
</div>

<script>
(function() {{
  const grid = document.getElementById('grid');
  const items = Array.from(grid.querySelectorAll('.tx'));
  const q = document.getElementById('q');
  const mapSel = document.getElementById('mapSel');
  const srcSel = document.getElementById('srcSel');
  const sortGrp = document.querySelector('.grp[aria-label="Sort"]');
  const countEl = document.getElementById('count');
  let sortKey = 'uses';

  function hereCount(it, map) {{
    if (map === 'all') return +it.dataset.uses;
    try {{ return JSON.parse(it.dataset.permap)[map] || 0; }} catch (e) {{ return 0; }}
  }}

  function apply() {{
    const term = q.value.trim().toUpperCase();
    const map = mapSel.value;
    const src = srcSel.value;
    let visible = 0;
    items.forEach(it => {{
      const maps = it.dataset.maps.split(' ');
      const nameOk = !term || it.dataset.name.includes(term);
      const mapOk = map === 'all' || maps.includes(map);
      const srcOk = src === 'all' || it.dataset.src === src;
      const here = hereCount(it, map);
      it.querySelector('.here-val').textContent = here;
      it.classList.toggle('matched', map !== 'all' && mapOk);
      const show = nameOk && mapOk && srcOk;
      it.hidden = !show;
      it._here = here;
      if (show) visible++;
    }});
    const shown = items.filter(it => !it.hidden);
    shown.sort((a, b) => {{
      if (sortKey === 'name') return a.dataset.name.localeCompare(b.dataset.name);
      if (sortKey === 'here') return b._here - a._here;
      return (+a.dataset.uses) - (+b.dataset.uses);
    }});
    shown.forEach(it => grid.appendChild(it));
    countEl.textContent = visible + ' / ' + items.length;
  }}

  q.addEventListener('input', apply);
  mapSel.addEventListener('change', apply);
  srcSel.addEventListener('change', apply);
  sortGrp.addEventListener('click', e => {{
    const btn = e.target.closest('button[data-sort]');
    if (!btn) return;
    sortGrp.querySelectorAll('button').forEach(b => b.setAttribute('aria-pressed', 'false'));
    btn.setAttribute('aria-pressed', 'true');
    sortKey = btn.dataset.sort;
    apply();
  }});
  apply();
}})();
</script>
'''
    OUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    OUT_HTML.write_text(html, encoding="utf-8")


if __name__ == "__main__":
    main()
