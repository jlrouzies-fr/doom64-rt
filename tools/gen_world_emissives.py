"""
Author targeted world-texture emissives for Retribution.

Replaces the blunt `rt_emis_mapboost 200` hammer (washed metals white) with
per-texture `_e.png` + modest `emissiveMult` for real glow sources:

  1) GLDEFS texture brightmaps in D64RTR_BRIGHTMAPS.PK3  (SMON* blink monitors, exits, …)
  2) Name heuristics (LAVA / HLAVA / *GLOW / *FALL / NUKE / …)
  3) ANIMDEFS frames of those animated textures
  4) ZDoom TEXTURES composites when the name is not a raw PNG lump (falls)

Does NOT touch monster eyes / FX / SKUL (other generators own those).

Cast light policy (path-traced room light, not “looks bright”):
  - Monitors / EXIT / CRT / face panels / logo: `_e` + `emissiveMult` only
    (no `lightIntensity` — that draws floating point lights on the face)
  - Key floors / lava / nukage: `_e` + mild `lightIntensity`
  - Liquid falls (BFALL/SFALL/WFALL): never — water/blood/slime are not lamps
  - `*GLOW` name walls: not auto-authored (glow-for-glow); use real sources

Writes:
  build/.../rt/mat/<TEX>_e.png
  build/.../rt/mat_dev/<TEX>_e.png   (required when RTGL1.json developerMode=true)
  Retribution-RT-Materials/rt/mat/<TEX>_e.png
  Retribution-RT-Materials/rt/data/textures_world_emis.json
  upserts scene overlays + patches global textures.json
"""
from __future__ import annotations

import io
import json
import re
import struct
import sys
import zipfile
from collections import defaultdict
from pathlib import Path

from PIL import Image

ROOT = Path(r"G:\AI\Doom64-RT")
WAD = ROOT / r"Doom64-Retribution\D64RTR_v15.WAD"
BM_PK3 = ROOT / r"Doom64-Retribution\D64RTR_BRIGHTMAPS.PK3"
RT_DATA = ROOT / r"sourcecode\gzdoom-rt\build\RelWithDebInfo\rt\data"
GLOBAL_JSON = RT_DATA / "textures.json"
SCENE_MAP01 = RT_DATA / r"scenes\d64rtr_v15_map01\textures.json"
SCENE_GALLERY = RT_DATA / r"scenes\d64rtexg_map99\textures.json"
MAT = ROOT / r"sourcecode\gzdoom-rt\build\RelWithDebInfo\rt\mat"
# developerMode=true loads PNG from mat_dev first; mat/ is KTX2-only.
MAT_DEV = ROOT / r"sourcecode\gzdoom-rt\build\RelWithDebInfo\rt\mat_dev"
OMAT = ROOT / r"Doom64-Retribution\Retribution-RT-Materials\rt\mat"
OVERLAY = ROOT / r"Doom64-Retribution\Retribution-RT-Materials\rt\data\textures_world_emis.json"
OVERLAY_MAP01 = (
    ROOT / r"Doom64-Retribution\Retribution-RT-Materials\rt\data\scenes\d64rtr_v15_map01\textures.json"
)
OVERLAY_GALLERY = (
    ROOT / r"Doom64-Retribution\Retribution-RT-Materials\rt\data\scenes\d64rtexg_map99\textures.json"
)

# Name tokens → (emissiveMult, lightIntensity or 0, RGB tint or None=sample)
#
# Pre–wall-wash authoring (visible screens/EXIT in gallery). HitInfo INDIR
# multiplies GI by emissiveMult when _e exists; wash debugging crushed these
# to ~0.01 — restore the working gallery values here. Optional --scrub still
# available for wash experiments.
# (emissiveMult, lightIntensity, RGB tint)
# Cast light on walls = surface _e × emissiveMult × mapboost (GI).
# Do NOT put lightIntensity on wall screens/signs — RTGL glues a floating
# point/spot light to the prim center (looks like a lamp hovering on the tex).
# Floor liquids/keys can keep mild attached lights (sit on the surface).
# INDIR mults: after RTGL Saturate→clamp fix, values >1 fully scale GI.
# Pre-fix "gallery perfect" looked like mult≈1 (clamped). Keep walls near 1;
# floors can sit a bit higher with attached lightIntensity.
NAME_RULES: list[tuple[str, float, float, tuple[int, int, int] | None]] = [
    ("HLAVA", 1.5, 140, (255, 90, 20)),
    ("D64LAVA", 1.5, 140, (255, 90, 20)),
    ("LAVA", 1.5, 140, (255, 90, 20)),
    ("NUKAGE", 1.2, 90, (60, 220, 40)),
    ("NUKE", 1.2, 90, (60, 220, 40)),
    ("SEXIT", 0.9, 0, (255, 40, 40)),
    # Dense SMON panels (B/F/LB/LC) stay ~1.0. Sparse green-text LEDs (A/C/D/E)
    # need higher INDIR mult — ~50px masks cast nothing at 1.0 (see screengreentextnolight).
    ("SMON", 1.0, 0, (120, 220, 255)),
    ("CFACE", 1.0, 0, (255, 200, 80)),
    ("CRTR", 1.0, 0, (80, 220, 120)),
    ("CRT", 1.0, 0, (80, 220, 120)),
    ("SKEYFLYL", 1.2, 0, (255, 200, 40)),
    ("SKEYFLRD", 1.2, 0, (255, 50, 40)),
    # D64 has no green keycard — blue floor albedo is dark; push cyan cast hard.
    ("SKEYFLBL", 1.3, 0, (60, 160, 255)),
    ("SKEYFL", 1.2, 0, None),
    ("C22", 1.0, 0, (255, 180, 60)),
    # The 0 here is not "we did not get round to it" — an attached light on a WALL
    # texture cannot work at all, and the reason is worth recording because it was
    # tried and reverted (2026-08-09). RTGL1 places a texture's attached light at the
    # exact centre of the primitive's quad with no normal offset
    # (VulkanDevice.cpp: center = average of the 4 quad verts, radius 0.1). On a sprite
    # billboard that lands in open air and works. On a wall face it lands COPLANAR with
    # the wall, i.e. buried in solid geometry, fully occluded — indistinguishable from
    # the light never being uploaded. rt_wall_strips exists precisely because of this:
    # it nudges its emitters 2 units off the wall first. C23 is lit there instead, via
    # rt_eye_panels.
    ("C23", 1.0, 0, (255, 180, 60)),
    ("D64LOGO", 1.0, 0, None),
    # Teleporter pads (MAP03 SPORT*) — cyan cast; mild floor lightIntensity OK.
    ("SPORT", 2.2, 110, (70, 190, 255)),
]

# Always include these even if heuristics miss them
FORCE: dict[str, tuple[float, float, tuple[int, int, int] | None]] = {
    "D64LOGO": (1.0, 0.0, None),
    "CRTRAKA": (1.0, 0.0, (80, 220, 120)),
    "C22": (1.0, 0.0, (255, 180, 60)),
    "C23": (1.0, 0.0, (255, 180, 60)),
    "SKEYFLYL": (1.2, 0.0, (255, 200, 40)),
    "SKEYFLRD": (1.2, 0.0, (255, 50, 40)),
    "SKEYFLBL": (1.3, 0.0, (60, 160, 255)),
    "SEXIT": (0.9, 0.0, (255, 40, 40)),
    # CTEL1..8 — ANIMDEFS loop (8 frames, 4 tics each) of a telemetry panel whose red
    # gems pulse. Glow only, no attached light. Used as a FLAT on 15 maps.
    #
    # emissiveMult IS the animation, and it has to be, because there is nothing else left
    # to carry it. RsWorld.inl builds screen emission as
    #
    #     ldrEmis = baseColor().rgb * emisTex.rgb * emissiveMult
    #
    # and under rt_mod_compat baseColor is forced to hue-only (forceWorldWhiteRgb), so
    # the ALBEDO IS NOT A FACTOR. A constant mask with a constant mult therefore gives a
    # constant glow: the first pass assumed the authored per-frame albedo would supply
    # the pulse, and the pulse simply vanished in game (2026-08-10). The frames are
    # separate texture names, so the per-frame value belongs here.
    #
    # Values are the measured relative gem luminance per frame, peak CTEL8 = 1.0.
    #
    # Peak 1.0 is a CEILING, not a taste call. emisTex is the saturated gem red
    # (255,65,28) = (1.0, 0.25, 0.11), so mult 1.0 puts the red channel exactly at full
    # and keeps the hue. The first pass used 2.5 -- the sparse-SMON value -- which drove
    # red to 2.5 and green to 0.64: red clipped, green and blue did not, and the gems
    # washed out to near-white. Above ~1.0 this texture desaturates instead of
    # brightening.
    "CTEL1": (0.71, 0.0, (255, 65, 28)),
    "CTEL2": (0.67, 0.0, (255, 65, 28)),
    "CTEL3": (0.55, 0.0, (255, 65, 28)),
    "CTEL4": (0.55, 0.0, (255, 65, 28)),
    "CTEL5": (0.48, 0.0, (255, 65, 28)),
    "CTEL6": (0.47, 0.0, (255, 65, 28)),
    "CTEL7": (0.45, 0.0, (255, 65, 28)),
    "CTEL8": (1.00, 0.0, (255, 65, 28)),
    "SPORT1": (2.2, 110.0, (70, 190, 255)),
    "SPORT2": (2.2, 110.0, (70, 190, 255)),
    "SPORT3": (2.2, 110.0, (70, 190, 255)),
    "SPORT4": (2.2, 110.0, (70, 190, 255)),
    "SPORT5": (2.2, 110.0, (70, 190, 255)),
}

# Textures whose attached light must survive a NON-QUAD primitive.
#
# VulkanDevice.cpp only builds an attached light when `evenOnDynamic || quad`, and its
# quad test is strict: indexCount 6 + vertexCount 4, or indexCount 0 + vertexCount 6. A
# flat drawn over a simple rectangular sector satisfies that, but the moment the sector
# is split into more subsector points it does not, and the light silently never exists.
#
# Empty on purpose. CTEL was in here and the flag did not produce a light either, so the
# gate is not the only thing in the way and nothing is served by carrying a setting that
# was never shown to do anything (2026-08-10). CTEL is glow-only now, like the monitors
# and EXIT signs, which is the policy at the top of this file for panels anyway.
EVEN_ON_DYNAMIC: set[str] = set()

# Flat saturated hue for the CTEL gems' _e mask. The gems' own peak texel is (222,57,24);
# this is that hue pushed to full range. Constant, never sampled per-texel from the
# albedo -- see _e_ctel_gems_from_albedo.
CTEL_GEM_RGB = (255, 65, 28)

# Skip non-emitters. OUTTEX classic brightmaps are NOT RT emitters.
# SWX* idle frames stay dark; ON frames (GLDEFS brightmaps) are allowlisted below.
SKIP_RE = re.compile(
    r"^(SPACE|METAL|STEEL|DOOR|GATE|FRSKY|FIRE[A-Z]|PLAY|POSS|TROO|CLOUD|"
    r"OUTTEX|SWX)",
    re.I,
)

# Script-19 / ANIMDEFS ON frames (and two GLDEFS A-frame brightmaps).
# GLDEFS BMTX* lumps are missing — LED chroma is taken from albedo RGB.
# emissiveMult only; no lightIntensity (no floating switch lamps).
SWITCH_ON_EMIS: dict[str, tuple[float, float, tuple[int, int, int] | None]] = {
    "SWXCB": (0.4, 0.0, None),
    "SWXCKB": (0.4, 0.0, None),
    "SWXCKLA": (0.4, 0.0, None),
    "SWXCLA": (0.4, 0.0, None),
    "SWXS4B": (0.4, 0.0, None),
    "SWXSAB": (0.4, 0.0, None),
    "SWXSCB": (0.4, 0.0, None),
    "SWXSDB": (0.4, 0.0, None),
    "SWXSEB": (0.4, 0.0, None),
    "SWXSFB": (0.4, 0.0, None),
    "SWXSGB": (0.4, 0.0, None),
}

# Stock / leftover false emitters — strip unless authored allowlist keeps them.
# Liquid falls are never lights; always scrub.
FALSE_PANEL_RE = re.compile(r"^(OUTTEX|SWX|BFALL|SFALL|WFALL|NUKAGE|NUKE)", re.I)
# Lamp flats/walls that are lit by ANALYTIC lights in the engine
# (RT_IsCeilingEdgeLampFlat / RT_IsWallStripTexture in rt_main.cpp), never by a
# texture mask. They must carry NO emissiveMult: their `_e.png` masks were deleted
# when generic SFLAT* blobs were found to spawn false emitters (open-issues 1.6e),
# and RsWorld.inl falls back to `ldrEmis = ldrColor.rgb` when a material has an
# emissiveMult but no emissive texture — i.e. the ENTIRE albedo emits, tan brick
# and all. That is what baked MAP07's ceiling panel white at mult 3.
LAMP_FLAT_NO_EMIS = ("SFLATAS", "SFLATAQ", "SFLATAP", "SPACEAZ")
FALL_RE = re.compile(r"^(BFALL|SFALL|WFALL)", re.I)
GLOW_RE = re.compile(r"GLOW", re.I)


def wad_lumps(path: Path) -> dict[str, bytes]:
    d = path.read_bytes()
    n, o = struct.unpack_from("<II", d, 4)
    out: dict[str, bytes] = {}
    for i in range(n):
        off, sz, name = struct.unpack_from("<II8s", d, o + i * 16)
        nm = name.split(b"\0")[0].decode("ascii", "replace").rstrip().upper()
        if sz > 0:
            out[nm] = d[off : off + sz]
    return out


def open_png(data: bytes) -> Image.Image | None:
    if data[:4] != b"\x89PNG":
        return None
    try:
        return Image.open(io.BytesIO(data)).convert("RGBA")
    except Exception:
        return None


def compose_from_textures(lumps: dict[str, bytes], name: str) -> Image.Image | None:
    tex = lumps.get("TEXTURES")
    if not tex:
        return None
    text = tex.decode("latin1", "replace")
    key = name.upper()
    pat = re.compile(
        rf"(?im)^\s*(?:Texture|WallTexture|Flat)\s+{re.escape(key)}\s*,\s*(\d+)\s*,\s*(\d+)\s*(.*?)(?=^\s*(?:Texture|WallTexture|Flat|Sprite)\s+|\Z)",
        re.S,
    )
    m = pat.search(text)
    if not m:
        return None
    w, h = int(m.group(1)), int(m.group(2))
    body = m.group(3)
    canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    for pm in re.finditer(
        r"(?im)(?:^|[\{;])\s*Patch\s+([A-Za-z0-9_]+)\s*,\s*(-?\d+)\s*,\s*(-?\d+)",
        body,
    ):
        pname, px, py = pm.group(1).upper(), int(pm.group(2)), int(pm.group(3))
        if pname not in lumps:
            continue
        patch = open_png(lumps[pname])
        if patch is None:
            continue
        # Clamp paste for tall scrolling patches (falls use y=-128 on 64 canvas)
        canvas.paste(patch, (px, py), patch)
    if canvas.getbbox() is None:
        # fallback: use first patch cropped to canvas
        for pm in re.finditer(r"(?im)Patch\s+([A-Za-z0-9_]+)", body):
            pname = pm.group(1).upper()
            if pname not in lumps:
                continue
            patch = open_png(lumps[pname])
            if patch is None:
                continue
            return patch.crop((0, 0, min(w, patch.size[0]), min(h, patch.size[1])))
        return None
    return canvas


def resolve_albedo(lumps: dict[str, bytes], name: str) -> Image.Image | None:
    key = name.upper()
    if key in lumps:
        img = open_png(lumps[key])
        if img is not None:
            return img
    return compose_from_textures(lumps, key)


def map_texture_names() -> set[str]:
    names: set[str] = set()
    d = WAD.read_bytes()
    n, o = struct.unpack_from("<II", d, 4)
    for i in range(n):
        off, sz, name = struct.unpack_from("<II8s", d, o + i * 16)
        nm = name.split(b"\0")[0].decode("ascii", "replace").rstrip()
        if nm != "TEXTMAP" or sz <= 0:
            continue
        t = d[off : off + sz].decode("utf-8", "replace")
        for m in re.finditer(
            r'texture(?:floor|ceiling|middle|top|bottom)\s*=\s*"([^"]+)"', t, re.I
        ):
            names.add(m.group(1).upper())
    return names


def animdefs_frames(lumps: dict[str, bytes]) -> dict[str, list[str]]:
    raw = lumps.get("ANIMDEFS", b"").decode("latin1", "replace")
    out: dict[str, list[str]] = {}
    cur: str | None = None
    pics: list[str] = []
    for line in raw.splitlines():
        s = line.strip()
        if not s or s.startswith("//") or s.startswith("/*"):
            continue
        m = re.match(r"texture\s+(\S+)", s, re.I)
        if m:
            if cur and pics:
                out[cur.upper()] = pics
            cur = m.group(1)
            pics = []
            continue
        m = re.match(r"pic\s+(\S+)", s, re.I)
        if m and cur:
            pics.append(m.group(1).upper())
    if cur and pics:
        out[cur.upper()] = pics
    return out


def brightmap_texture_bindings() -> tuple[dict[str, bytes], set[str]]:
    """Return (tex->png bytes, all GLDEFS texture names even if map file missing)."""
    out: dict[str, bytes] = {}
    names: set[str] = set()
    if not BM_PK3.exists():
        return out, names
    with zipfile.ZipFile(BM_PK3) as z:
        gldefs = z.read("GLDEFS").decode("latin1", "replace")
        defs = re.findall(
            r"brightmap\s+texture\s+\"?([^\"{\s]+)\"?\s*\{([^}]*)\}",
            gldefs,
            re.I | re.S,
        )
        file_index = {n.replace("\\", "/").lower(): n for n in z.namelist()}
        stem_index = {Path(n).stem.upper(): n for n in z.namelist()}
        for tex, body in defs:
            names.add(tex.upper())
            maps = re.findall(r"map\s+\"?([^\"{\s]+)\"?", body, re.I)
            if not maps:
                continue
            rel = maps[0].replace("\\", "/")
            path = file_index.get(rel.lower())
            if path is None:
                path = file_index.get(f"brightmaps/textures/{Path(rel).name}".lower())
            if path is None:
                path = stem_index.get(Path(rel).stem.upper())
            if path is None:
                continue
            out[tex.upper()] = z.read(path)
    return out, names


def is_skipped(name: str) -> bool:
    u = name.upper()
    if u in SWITCH_ON_EMIS:
        return False
    return bool(SKIP_RE.match(u))


def rule_for(name: str) -> tuple[float, float, tuple[int, int, int] | None] | None:
    u = name.upper()
    if u in SWITCH_ON_EMIS:
        return SWITCH_ON_EMIS[u]
    if SKIP_RE.match(u):
        return None
    for pref, em, li, rgb in NAME_RULES:
        if u.startswith(pref):
            return em, li, rgb
    return None


def albedo_looks_lit(img: Image.Image) -> bool:
    px = img.load()
    bright = tot = 0
    for y in range(img.size[1]):
        for x in range(img.size[0]):
            r, g, b, a = px[x, y]
            if a < 40:
                continue
            tot += 1
            if r + g + b >= 380 or max(r, g, b) >= 200:
                bright += 1
    return tot > 0 and (bright / tot) >= 0.10


def sample_bright_rgb(img: Image.Image) -> tuple[int, int, int]:
    acc = [0, 0, 0]
    n = 0
    px = img.load()
    for y in range(img.size[1]):
        for x in range(img.size[0]):
            r, g, b, a = px[x, y]
            if a < 40 or r + g + b < 220:
                continue
            acc[0] += r
            acc[1] += g
            acc[2] += b
            n += 1
    if n < 4:
        return (255, 180, 80)
    return tuple(min(255, acc[i] // n) for i in range(3))  # type: ignore[return-value]


def make_e_from_brightmap(
    bm: Image.Image, tint: tuple[int, int, int], albedo: Image.Image | None,
    *, use_albedo_color: bool = False,
) -> Image.Image:
    """Brightmap = mask. Default: tinted emit. use_albedo_color keeps carving RGB."""
    bm = bm.convert("RGBA")
    if albedo is not None and bm.size != albedo.size:
        bm = bm.resize(albedo.size, Image.Resampling.NEAREST)
    size = bm.size
    out = Image.new("RGBA", size, (0, 0, 0, 0))
    bp = bm.load()
    op = out.load()
    ap = albedo.load() if albedo is not None else None
    tr, tg, tb = tint
    for y in range(size[1]):
        for x in range(size[0]):
            r, g, b, a = bp[x, y]
            v = max(r, g, b)
            if a < 8 or v < 20:
                continue
            if ap is not None:
                ar, ag, ab, aa = ap[x, y]
                if aa < 8:
                    continue
                if use_albedo_color:
                    s = min(1.35, (v / 255.0) * 1.5)
                    op[x, y] = (
                        min(255, int(ar * s)),
                        min(255, int(ag * s)),
                        min(255, int(ab * s)),
                        255,
                    )
                    continue
            s = min(1.0, (v / 255.0) * 1.35)
            op[x, y] = (
                min(255, int(tr * s)),
                min(255, int(tg * s)),
                min(255, int(tb * s)),
                255,
            )
    return out


def _sat_e_from_albedo(
    img: Image.Image, tint: tuple[int, int, int]
) -> Image.Image:
    """Unused for keys — kept for callers; prefer _e_albedo_brightmap."""
    return _e_albedo_brightmap(img, tint)


def _e_albedo_brightmap(
    img: Image.Image,
    tint: tuple[int, int, int] | None = None,
    *,
    boost: float = 1.25,
) -> Image.Image:
    """Brightmap-style from albedo luma mask.

    If tint is set (keys), emit that color modulated by luma — albedo yellow
    carving is brownish (87,61,0) and GI reads as red/orange without a tint.
    """
    out = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ip = img.load()
    op = out.load()
    samples: list[tuple[int, int, int]] = []
    for y in range(img.size[1]):
        for x in range(img.size[0]):
            r, g, b, a = ip[x, y]
            if a < 40:
                continue
            samples.append((r + g + b, x, y))
    if not samples:
        return out
    # Only the brightest ~35% of opaque texels (raised carving / letters).
    samples.sort(reverse=True)
    cutoff = samples[max(0, int(len(samples) * 0.35))][0]
    for s, x, y in samples:
        if s < cutoff:
            break
        r, g, b, _a = ip[x, y]
        mx = max(r, g, b)
        if mx < 40:
            continue
        if tint is not None:
            w = min(1.0, 0.55 + (mx / 255.0) * 0.55)
            tr, tg, tb = tint
            op[x, y] = (
                min(255, int(tr * w * boost / 1.25)),
                min(255, int(tg * w * boost / 1.25)),
                min(255, int(tb * w * boost / 1.25)),
                255,
            )
        else:
            op[x, y] = (
                min(255, int(r * boost)),
                min(255, int(g * boost)),
                min(255, int(b * boost)),
                255,
            )
    return out


def _e_ceiling_blobs_from_albedo(
    img: Image.Image, *, thresh: int = 130
) -> Image.Image:
    """Eye-style mask: only bright round lamp blobs, albedo RGB kept (no tint slap)."""
    out = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ip = img.load()
    op = out.load()
    for y in range(img.size[1]):
        for x in range(img.size[0]):
            r, g, b, a = ip[x, y]
            if a < 40:
                continue
            if max(r, g, b) < thresh:
                continue
            # Mild boost so blobs read under mapboost without flooding walls.
            s = 1.15
            op[x, y] = (
                min(255, int(r * s)),
                min(255, int(g * s)),
                min(255, int(b * s)),
                255,
            )
    return out


def _e_teleporter_from_albedo(
    img: Image.Image, tint: tuple[int, int, int]
) -> Image.Image:
    """SPORT* teleporter pads — bright ring/dots + blue core, cyan GI tint.

    Ceiling-blob luma kept greyish whites that barely cast in dark rooms
    (map03groundelementnotemissive). Tint like keys so INDIR reads cyan.
    """
    out = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ip = img.load()
    op = out.load()
    tr, tg, tb = tint
    for y in range(img.size[1]):
        for x in range(img.size[0]):
            r, g, b, a = ip[x, y]
            if a < 40:
                continue
            mx = max(r, g, b)
            is_blue = b >= r + 20 and b >= g + 10 and b >= 55
            is_bright = mx >= 155 and (mx - min(r, g, b)) < 40  # white ring dots
            if not (is_blue or is_bright):
                continue
            # Weight by luma so the core reads hotter than the ring speckles.
            w = 0.55 + 0.55 * min(1.0, mx / 220.0)
            if is_blue:
                w = max(w, 0.90)
            op[x, y] = (
                min(255, int(tr * w)),
                min(255, int(tg * w)),
                min(255, int(tb * w)),
                255,
            )
    return out


def _e_ctel_gems_from_albedo(img: Image.Image) -> Image.Image:
    """CTEL1..CTEL8 — the red gems on the telemetry panel, and nothing else.

    Selected by RED DOMINANCE (r - max(g,b) > 15), not by luma. The generic luma
    path is wrong for this texture in the way that produced the C22/C23 mess: the
    panel is dark cracked stone whose brightest pixels are grey mortar, so a luma
    threshold picks the stone and misses the gems, which are dark-ish but strongly
    red (peak 222,57,24).

    The threshold is deliberately low enough that the SAME 45 pixels are selected
    in all 8 frames. That is the point: this is an 8-frame ANIMDEFS loop where the
    gems pulse, and the mask must not pulse with them. RsWorld.inl multiplies the
    mask by baseColor, so a constant full-strength mask lets the AUTHORED per-frame
    albedo produce the pulse by itself -- painting the mask per-frame instead would
    square the animation and blink far harder than the artist drew.

    The mask carries a flat SATURATED RED, the same construction
    gen_enemy_eye_emissives.py uses (hue from a constant, never from the albedo).

    It must not be painted white. "The shader multiplies by baseColor so paint the mask
    at full saturation" means saturate the HUE, not drop to white -- and under
    rt_mod_compat the world's baseColor is forced to hue-only (forceWorldWhiteRgb in
    rt_main.cpp), so there is no albedo red left in that factor to colour a white mask.
    A white mask therefore renders white: the gems came out as white dots on the first
    pass (2026-08-10).
    """
    out = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ip = img.load()
    op = out.load()
    for y in range(img.size[1]):
        for x in range(img.size[0]):
            px = ip[x, y]
            r, g, b = px[0], px[1], px[2]
            if len(px) > 3 and px[3] < 40:
                continue
            if r - max(g, b) > 15:
                op[x, y] = (*CTEL_GEM_RGB, 255)
    return out


def _flat_panel_frac(img: Image.Image) -> float:
    """Fraction of opaque texels that look like flat screen glass."""
    ip = img.load()
    tot = flat = 0
    for y in range(img.size[1]):
        for x in range(img.size[0]):
            r, g, b, a = ip[x, y]
            if a < 40:
                continue
            tot += 1
            mx, mn = max(r, g, b), min(r, g, b)
            if mx >= 85 and (mx - mn) < 48:
                flat += 1
    return (flat / tot) if tot else 0.0


def _panel_glass_e_from_albedo(
    img: Image.Image, tint: tuple[int, int, int]
) -> Image.Image:
    """Soft emission on large flat bright screen rectangles (not neon paint).

    Only the glass-like flat region; weight stays moderate so primary _e
    still reads as a lit panel, not a solid tint block.
    """
    out = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ip = img.load()
    op = out.load()
    tr, tg, tb = tint
    for y in range(img.size[1]):
        for x in range(img.size[0]):
            r, g, b, a = ip[x, y]
            if a < 40:
                continue
            mx, mn = max(r, g, b), min(r, g, b)
            if mx < 95 or (mx - mn) > 52:
                continue
            # Brighter glass → a bit more emit; stay well under full tint.
            w = 0.28 + 0.42 * min(1.0, mx / 220.0)
            op[x, y] = (
                min(255, int(tr * w)),
                min(255, int(tg * w)),
                min(255, int(tb * w)),
                255,
            )
    return out


def _screen_e_from_albedo(
    img: Image.Image, tint: tuple[int, int, int]
) -> Image.Image:
    """Sparse screen fill — brightest ~12% only (not whole-panel slap)."""
    out = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ip = img.load()
    op = out.load()
    tr, tg, tb = tint
    samples: list[tuple[int, int, int]] = []
    for y in range(img.size[1]):
        for x in range(img.size[0]):
            r, g, b, a = ip[x, y]
            if a < 40:
                continue
            samples.append((r + g + b, x, y))
    if not samples:
        return out
    samples.sort(reverse=True)
    cutoff = samples[max(0, int(len(samples) * 0.12))][0]
    for s, x, y in samples:
        if s < cutoff:
            break
        r, g, b, _a = ip[x, y]
        mx = max(r, g, b) / 255.0
        w = 0.55 + 0.35 * min(1.0, mx * 1.3)
        op[x, y] = (
            min(255, int(tr * w)),
            min(255, int(tg * w)),
            min(255, int(tb * w)),
            255,
        )
    return out


def _boost_e(img: Image.Image, factor: float) -> Image.Image:
    out = img.copy()
    px = out.load()
    for y in range(out.size[1]):
        for x in range(out.size[0]):
            r, g, b, a = px[x, y]
            if a < 8 or max(r, g, b) < 8:
                continue
            px[x, y] = (
                min(255, int(r * factor)),
                min(255, int(g * factor)),
                min(255, int(b * factor)),
                255,
            )
    return out


def _soft_halo_e(
    img: Image.Image, radius: int = 2, strength: float = 0.22
) -> Image.Image:
    """Dim fringe around LED cores for GI sampling — cores stay sharp.

    Hard dilate turned SMON green text into solid blocks on primary (raw _e).
    Halo only writes into empty texels at a fraction of the nearest core so
    glyphs remain readable while INDIR still gets a little area to sample.
    """
    if radius <= 0 or strength <= 0:
        return img
    src = img.convert("RGBA")
    w, h = src.size
    sp = src.load()
    out = src.copy()
    op = out.load()
    # Collect core pixels first
    cores: list[tuple[int, int, int, int, int]] = []
    for y in range(h):
        for x in range(w):
            r, g, b, a = sp[x, y]
            if a > 8 and max(r, g, b) > 8:
                cores.append((x, y, r, g, b))
    if not cores:
        return out
    for y in range(h):
        for x in range(w):
            r0, g0, b0, a0 = sp[x, y]
            if a0 > 8 and max(r0, g0, b0) > 8:
                continue  # never overwrite glyph cores
            best = 0.0
            br = bg = bb = 0
            for cx, cy, cr, cg, cb in cores:
                dx = abs(cx - x)
                dy = abs(cy - y)
                if dx > radius or dy > radius:
                    continue
                dist = max(dx, dy)  # chebyshev — square-ish CRT glow
                if dist < 1:
                    continue
                fall = strength * (1.0 - (dist - 1) / radius)
                if fall <= 0:
                    continue
                v = max(cr, cg, cb) * fall
                if v > best:
                    best = v
                    br = int(cr * fall)
                    bg = int(cg * fall)
                    bb = int(cb * fall)
            if best >= 6:
                op[x, y] = (min(255, br), min(255, bg), min(255, bb), 255)
    return out


def _e_lit_frac(img: Image.Image) -> float:
    px = img.convert("RGBA").load()
    w, h = img.size
    lit = 0
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a > 8 and max(r, g, b) > 8:
                lit += 1
    return lit / max(1, w * h)


def _is_sparse_smon_text(name: str) -> bool:
    """SMON A/C/D/E families = green LED text (not dense B/F/L panels)."""
    return bool(re.match(r"^SMON[ACDE]", name.upper()))


def _is_static_screen_smon(name: str) -> bool:
    """SMONB = CRT showing white static; brightmap is a solid screen rect.

    Unlike the sparse LED families, carving albedo RGB here copies the whole
    rusty screen *and* its dark blue bezel into the emit, so the monitor glows
    muddy brown with cyan speckle. Static is white — emit luminance instead.
    """
    return bool(re.match(r"^SMONB", name.upper()))


def make_e_static_screen(
    bm: Image.Image, albedo: Image.Image | None, gain: float = 1.6
) -> Image.Image:
    """White CRT static: brightmap = mask, albedo *luminance* = per-pixel level.

    Flat white loses the static entirely (the emit is not modulated by
    baseColor here). Keying on luminance keeps the speckle while forcing
    R==G==B, so no albedo hue — cyan bezel included — can leak into the glow.
    """
    bm = bm.convert("RGBA")
    if albedo is not None and bm.size != albedo.size:
        bm = bm.resize(albedo.size, Image.Resampling.NEAREST)
    out = Image.new("RGBA", bm.size, (0, 0, 0, 0))
    bp = bm.load()
    op = out.load()
    ap = albedo.convert("RGBA").load() if albedo is not None else None
    for y in range(bm.size[1]):
        for x in range(bm.size[0]):
            r, g, b, a = bp[x, y]
            if a < 8 or max(r, g, b) < 20:
                continue
            if ap is None:
                lum = 255
            else:
                ar, ag, ab, aa = ap[x, y]
                if aa < 8:
                    continue
                lum = int(0.299 * ar + 0.587 * ag + 0.114 * ab)
            v = min(255, int(lum * gain))
            op[x, y] = (v, v, v, 255)
    return out


def clone_anim_pbr_maps(
    anims: dict[str, list[str]], mat_dirs: list[Path]
) -> int:
    """Copy donor-frame _n/_orm/_h onto ANIMDEFS siblings (fixes flat↔bump flicker)."""
    suffixes = ("_n.png", "_orm.png", "_h.png", "_n.ktx2", "_orm.ktx2", "_h.ktx2")
    cloned = 0
    for base, frames in anims.items():
        if not base.upper().startswith("SMON"):
            continue
        seq = [base.upper()] + [f.upper() for f in frames]
        # unique order preserved
        seen: set[str] = set()
        ordered: list[str] = []
        for n in seq:
            if n not in seen:
                seen.add(n)
                ordered.append(n)
        if len(ordered) < 2:
            continue
        for d in mat_dirs:
            if not d.exists():
                continue
            # pick first frame that has any PBR companion as donor
            donor: str | None = None
            for n in ordered:
                if any((d / f"{n}{suf}").exists() for suf in suffixes):
                    donor = n
                    break
            if not donor:
                continue
            for n in ordered:
                if n == donor:
                    continue
                for suf in suffixes:
                    src = d / f"{donor}{suf}"
                    dst = d / f"{n}{suf}"
                    if not src.exists():
                        continue
                    if dst.exists() and dst.stat().st_size == src.stat().st_size:
                        continue
                    dst.write_bytes(src.read_bytes())
                    cloned += 1
    return cloned


def _e_switch_led_from_albedo(
    img: Image.Image,
    tint: tuple[int, int, int] | None = None,
) -> Image.Image:
    """ON-frame switch indicator only — saturated LED pixels, not metal.

    GLDEFS points at missing BMTX* lumps. Do not use luma / loose albedo masks
    (those paint brown metal with green tint). Keep albedo RGB so red/magenta/
    green indicators stay correct; ``tint`` is unused for color.

    After chroma filter, keep connected components that touch the upper ~45%
    so lower-corner metal false greens (e.g. SWXSFB) are dropped while full
    mid-panel LCDs that start in the upper half (SWXS4B) remain.
    """
    del tint
    w, h = img.size
    ip = img.load()
    mask = [[False] * w for _ in range(h)]

    def is_led(r: int, g: int, b: int) -> bool:
        mx = max(r, g, b)
        mn = min(r, g, b)
        sat = mx - mn
        if mx < 80 or sat < 55:
            return False
        if sat < 70 and mx < 170:
            return False
        # Green strip / LCD (reject teal bevels where g≈b).
        if g >= r + 20 and g >= b + 30:
            return True
        # Red / orange eyes and bars.
        if r >= g + 20 and r >= b + 20:
            return True
        # Magenta / purple key lights.
        if r >= 100 and b >= 100 and g <= 40:
            return True
        # Deep red with a little blue (SWXSGB).
        if r >= 180 and b >= 32 and g <= 64 and r >= b + 80:
            return True
        return False

    for y in range(h):
        for x in range(w):
            r, g, b, a = ip[x, y]
            if a >= 40 and is_led(r, g, b):
                mask[y][x] = True

    # Connected components; keep those that touch the upper ~55% (covers mid
    # skull eyes ~y=15 on 32px faces; still drops SWXSFB lower-corner greens).
    y_touch = max(1, int(h * 0.55))
    keep = [[False] * w for _ in range(h)]
    seen = [[False] * w for _ in range(h)]
    for y0 in range(h):
        for x0 in range(w):
            if not mask[y0][x0] or seen[y0][x0]:
                continue
            stack = [(x0, y0)]
            seen[y0][x0] = True
            comp: list[tuple[int, int]] = []
            touches_top = False
            while stack:
                x, y = stack.pop()
                comp.append((x, y))
                if y < y_touch:
                    touches_top = True
                for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                    if 0 <= nx < w and 0 <= ny < h and mask[ny][nx] and not seen[ny][nx]:
                        seen[ny][nx] = True
                        stack.append((nx, ny))
            if touches_top:
                for x, y in comp:
                    keep[y][x] = True

    out = Image.new("RGBA", img.size, (0, 0, 0, 0))
    op = out.load()
    for y in range(h):
        for x in range(w):
            if not keep[y][x]:
                continue
            r, g, b, _a = ip[x, y]
            s = 1.05
            op[x, y] = (
                min(255, int(r * s)),
                min(255, int(g * s)),
                min(255, int(b * s)),
                255,
            )
    return out


def make_e_from_albedo(
    img: Image.Image,
    tint: tuple[int, int, int] | None,
    *,
    loose: bool = False,
) -> Image.Image:
    """Keep bright / saturated pixels as emissive.

    loose=True: take the brightest ~25% of opaque pixels when absolute
    thresholds find nothing. Do not use for SWX* — use _e_switch_led_from_albedo.
    """
    out = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ip = img.load()
    op = out.load()
    tr, tg, tb = tint or (255, 255, 255)
    hit = 0
    for y in range(img.size[1]):
        for x in range(img.size[0]):
            r, g, b, a = ip[x, y]
            if a < 40:
                continue
            s = r + g + b
            mx = max(r, g, b)
            mn = min(r, g, b)
            if s < 280 and (mx - mn) < 40:
                continue
            if mx < 70:
                continue
            if tint:
                w = mx / 255.0
                op[x, y] = (
                    min(255, int(tr * w)),
                    min(255, int(tg * w)),
                    min(255, int(tb * w)),
                    255,
                )
            else:
                boost = 1.8
                op[x, y] = (
                    min(255, int(r * boost)),
                    min(255, int(g * boost)),
                    min(255, int(b * boost)),
                    255,
                )
            hit += 1
    if hit > 0 or not loose:
        return out

    # Relative fallback for dull switch faces
    samples: list[tuple[int, int, int]] = []
    for y in range(img.size[1]):
        for x in range(img.size[0]):
            r, g, b, a = ip[x, y]
            if a < 40:
                continue
            samples.append((r + g + b, x, y))
    if not samples:
        return out
    samples.sort(reverse=True)
    cutoff = samples[max(0, len(samples) // 4)][0]
    for s, x, y in samples:
        if s < cutoff:
            break
        r, g, b, a = ip[x, y]
        mx = max(r, g, b) / 255.0
        op[x, y] = (
            min(255, int(tr * mx)),
            min(255, int(tg * mx)),
            min(255, int(tb * mx)),
            255,
        )
    return out


def e_max(img: Image.Image) -> int:
    return max(img.getextrema()[i][1] for i in range(3))


def patch_global_inline(path: Path, entries: dict[str, dict]) -> None:
    """Overwrite or insert meta lines in the comment-y textures.json.

    RTGL keeps the *first* textureName hit and ignores duplicates — so we must
    rewrite the existing line in place (never append a second OUTTEX at 0.004
    while a stock OUTTEX at 1.25 sits earlier).
    """
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    for name, meta in entries.items():
        parts = [f'"textureName":"{name}"']
        for k, v in meta.items():
            if k == "textureName":
                continue
            if isinstance(v, bool):
                parts.append(f'"{k}":{"true" if v else "false"}')
            elif isinstance(v, float) and v == int(v):
                parts.append(f'"{k}":{int(v)}')
            elif isinstance(v, (int, float)):
                parts.append(f'"{k}":{v}')
            elif isinstance(v, list):
                parts.append(f'"{k}":{json.dumps(v)}')
            else:
                parts.append(f'"{k}":"{v}"')
        # Preserve leading comma / indent from the matched line when possible
        body = "  ,".join(parts)

        def repl(m: re.Match[str]) -> str:
            lead = m.group(1) or "    ,   "
            return f"{lead}{{ {body} }}"

        pat = re.compile(
            rf'^([ \t]*,?[ \t]*)\{{[ \t]*"textureName"[ \t]*:[ \t]*"{re.escape(name)}"[^}}\n]*\}}[ \t]*$',
            re.M,
        )
        if pat.search(text):
            text = pat.sub(repl, text, count=1)
        else:
            # Pretty-printed multiline object — replace whole first block
            # (emisMult-only edits miss new lightIntensity / lightColor).
            pat_multi = re.compile(
                rf'(\{{\s*\n\s*"textureName"\s*:\s*"{re.escape(name)}"\s*,)(.*?)(\n\s*\}})',
                re.S,
            )
            mm = pat_multi.search(text)
            if mm:
                indent = "      "
                lines = [f'{{\n{indent}"textureName": "{name}",']
                keys = [k for k in meta if k != "textureName"]
                # Keep metallicDefault/roughnessDefault from the old block if authored
                # meta doesn't set them (stock PBR companions).
                old = mm.group(0)
                for keep_k in ("metallicDefault", "roughnessDefault", "isMirror", "isWater"):
                    if keep_k in meta:
                        continue
                    km = re.search(rf'"{keep_k}"\s*:\s*([^,}}\s]+)', old)
                    if km and keep_k not in keys:
                        keys.append(keep_k)
                        meta = dict(meta)
                        raw = km.group(1)
                        if raw in ("true", "false"):
                            meta[keep_k] = raw == "true"
                        else:
                            try:
                                meta[keep_k] = float(raw) if "." in raw else int(raw)
                            except ValueError:
                                meta[keep_k] = raw
                for i, k in enumerate(keys):
                    v = meta[k]
                    comma = "," if i < len(keys) - 1 else ""
                    if isinstance(v, bool):
                        lines.append(f'{indent}"{k}": {"true" if v else "false"}{comma}')
                    elif isinstance(v, float) and v == int(v):
                        lines.append(f'{indent}"{k}": {int(v)}{comma}')
                    elif isinstance(v, (int, float)):
                        lines.append(f'{indent}"{k}": {v}{comma}')
                    elif isinstance(v, list):
                        lines.append(f'{indent}"{k}": {json.dumps(v)}{comma}')
                    else:
                        lines.append(f'{indent}"{k}": "{v}"{comma}')
                lines.append("    }")
                text = text[: mm.start()] + "\n".join(lines) + text[mm.end() :]
            else:
                line = f"    ,   {{ {body} }}"
                text = re.sub(r"\n(\s*\]\s*\}\s*)$", "\n" + line + r"\n\1", text, count=1)
        # Drop any later single-line duplicates for this name
        text = re.sub(
            rf'^\s*,\s*\{{[ \t]*"textureName"[ \t]*:[ \t]*"{re.escape(name)}"[^}}\n]*\}}\s*$\n?',
            "",
            text,
            flags=re.M,
        )
    path.write_text(text, encoding="utf-8")


def _authored_emis_keep(extra: set[str] | None = None) -> set[str]:
    """Names that may keep emissiveMult / lightIntensity in global JSON."""
    keep: set[str] = {n.upper() for n in (extra or ())}
    overlay_dir = ROOT / r"Doom64-Retribution\Retribution-RT-Materials\rt\data"
    for p in (
        OVERLAY,
        overlay_dir / "textures_enemy_eyes.json",
        overlay_dir / "textures_pinky_eyes.json",
        overlay_dir / "textures_fx.json",
        overlay_dir / "textures_explosions.json",
    ):
        if not p.exists():
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        for e in data.get("array", []):
            n = e.get("textureName")
            if n:
                keep.add(str(n).upper())
    return keep


def scrub_false_panel_emis(path: Path, keep: set[str] | None = None) -> int:
    """Strip stock OUTTEX/SWX/fall/glow/nuke emis unless in keep (authored allowlist)."""
    if not path.exists():
        return 0
    keep_u = {k.upper() for k in (keep or set())}
    text = path.read_text(encoding="utf-8")
    n = 0

    def repl(m: re.Match[str]) -> str:
        nonlocal n
        full = m.group(0)
        name_m = re.search(r'"textureName"\s*:\s*"([^"]+)"', full)
        if not name_m:
            return full
        name = name_m.group(1)
        u = name.upper()
        is_false = bool(
            FALSE_PANEL_RE.match(u) or FALL_RE.match(u) or GLOW_RE.search(u)
        )
        if not is_false:
            return full
        if u in keep_u:
            return full
        if "emissiveMult" not in full and "lightIntensity" not in full:
            return full
        keep_fields = []
        for k in (
            "metallicDefault",
            "roughnessDefault",
            "isMirror",
            "isMirrorIfSmooth",
            "isWater",
            "isGlass",
            "invertRoughness",
        ):
            km = re.search(rf'"{k}"\s*:\s*([^,\s}}]+)', full)
            if km:
                keep_fields.append(f'"{k}":{km.group(1)}')
        n += 1
        lead = m.group(1) or "    ,   "
        if keep_fields:
            body = f'"textureName":"{name_m.group(1)}", ' + ", ".join(keep_fields)
            return f"{lead}{{ {body} }}"
        return f'{lead}{{ "textureName":"{name_m.group(1)}"   }}'

    text2 = re.sub(
        r'^([ \t]*,?[ \t]*)\{[ \t]*"textureName"[ \t]*:[ \t]*"[^"]+"[^}}\n]*\}[ \t]*$',
        repl,
        text,
        flags=re.M,
    )
    if n:
        path.write_text(text2, encoding="utf-8")
    return n


def scrub_stock_world_emis(path: Path, allow: set[str]) -> int:
    """Strip stock Doom II RT emis/light meta from global textures.json.

    Keep only Retribution-authored names (world allowlist + eye/FX overlays).
    Prefix scrubbing was not enough: PLAY* still had emissiveMult 4.25, and
    HitInfo INDIR else-path does albedo×mult×mapboost — that alone washes
    nearby walls ("glow around the player"). See wash-qa results 01–05.
    """
    if not path.exists():
        return 0
    text = path.read_text(encoding="utf-8")
    keep = _authored_emis_keep(allow)
    n = 0

    def repl(m: re.Match[str]) -> str:
        nonlocal n
        full = m.group(0)
        name_m = re.search(r'"textureName"\s*:\s*"([^"]+)"', full)
        if not name_m:
            return full
        name = name_m.group(1).upper()
        if name in keep:
            return full
        if "emissiveMult" not in full and "lightIntensity" not in full:
            return full
        # Preserve non-emis fields (mirror, roughness, …) if present.
        keep_fields = []
        for key in (
            "isMirror",
            "isMirrorIfSmooth",
            "metallicDefault",
            "roughnessDefault",
            "isWater",
            "isGlass",
            "noShadow",
        ):
            km = re.search(rf'"{key}"\s*:\s*([^,}}\s]+)', full)
            if km:
                keep_fields.append(f'"{key}":{km.group(1)}')
        lead = m.group(1) or "    ,   "
        n += 1
        if keep_fields:
            body = f'"textureName":"{name_m.group(1)}", ' + ", ".join(keep_fields)
            return f"{lead}{{ {body} }}"
        return f'{lead}{{ "textureName":"{name_m.group(1)}"   }}'

    text2 = re.sub(
        r'^([ \t]*,?[ \t]*)\{[ \t]*"textureName"[ \t]*:[ \t]*"[^"]+"[^}}\n]*\}[ \t]*$',
        repl,
        text,
        flags=re.M,
    )
    if n:
        path.write_text(text2, encoding="utf-8")
    return n


def strip_lamp_flat_emis(path: Path) -> int:
    """Remove emissiveMult/lightIntensity from the analytic lamp flats.

    Cheap and idempotent, and deliberately independent of the allowlist plumbing:
    this exact regression already shipped once, because the names were dropped from
    the authored set but the already-written global JSON was never regenerated.
    """
    if not path.exists():
        return 0
    data = json.loads(path.read_text(encoding="utf-8"))
    targets = {n.upper() for n in LAMP_FLAT_NO_EMIS}
    n = 0
    for e in data.get("array", []):
        if str(e.get("textureName", "")).upper() not in targets:
            continue
        for key in ("emissiveMult", "lightIntensity", "lightColor", "lightColorHEX"):
            if key in e:
                del e[key]
                n += 1
    if n:
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return n


def upsert_json(path: Path, entries: dict[str, dict], replace: bool = False) -> None:
    if path.exists() and not replace:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {"version": 0, "array": []}
    else:
        data = {"version": 0, "array": []}
    by = {e["textureName"]: dict(e) for e in data.get("array", []) if "textureName" in e}
    drop_if_absent = (
        "emissiveMult",
        "lightIntensity",
        "lightColor",
        "lightColorHEX",
        "lightEvenOnDynamic",
        "attachedLightIntensity",
        "attachedLightColor",
    )
    for name, meta in entries.items():
        cur = by.get(name, {"textureName": name})
        # Drop previous emis/light fields so removing lightIntensity sticks
        for k in drop_if_absent:
            cur.pop(k, None)
        cur.update(meta)
        cur["textureName"] = name
        by[name] = cur
    data["array"] = list(by.values())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    lumps = wad_lumps(WAD)
    used = map_texture_names()
    anims = animdefs_frames(lumps)
    bm_png, bm_names = brightmap_texture_bindings()

    candidates: dict[str, tuple[float, float, tuple[int, int, int] | None]] = {}

    # 0) Forced known emitters + switch ON-frame allowlist
    candidates.update(FORCE)
    candidates.update(SWITCH_ON_EMIS)

    # 1) GLDEFS texture brightmaps — SMON/SEXIT/C22/… (OUTTEX skipped; SWX ON allowlisted)
    for tex in bm_names:
        if is_skipped(tex):
            continue
        candidates[tex] = rule_for(tex) or (1.35, 0.0, None)
    for tex in bm_png:
        if tex in candidates or is_skipped(tex):
            continue
        candidates[tex] = rule_for(tex) or (1.35, 0.0, None)

    # 2) Name heuristics on map-used textures (no OUTTEX/idle-SWX/FALL by name)
    for name in used:
        rule = rule_for(name)
        if rule:
            candidates[name] = rule

    # 3) Expand ANIMDEFS frames for selected bases / matching names
    extra: dict[str, tuple[float, float, tuple[int, int, int] | None]] = {}
    for base, frames in anims.items():
        if is_skipped(base) or base.startswith("CLOUD"):
            continue
        donor = candidates.get(base) or rule_for(base)
        if donor is None:
            for fr in frames:
                if fr in candidates:
                    donor = candidates[fr]
                    break
                donor = rule_for(fr)
                if donor:
                    break
        if not donor:
            continue
        if base.startswith("FRSKY"):
            continue
        for fr in frames:
            if not is_skipped(fr):
                extra[fr] = donor
        extra[base] = donor
    candidates.update(extra)

    for name in list(candidates):
        if is_skipped(name) or FALL_RE.match(name) or GLOW_RE.search(name):
            del candidates[name]

    # FORCE + switch ON allowlist win over brightmap defaults
    candidates.update(FORCE)
    candidates.update(SWITCH_ON_EMIS)

    entries: dict[str, dict] = {}
    by_src: dict[str, int] = defaultdict(int)

    for name, (em, li, tint) in sorted(candidates.items()):
        albedo = resolve_albedo(lumps, name)
        bm_img = open_png(bm_png[name]) if name in bm_png else None

        if tint is None and albedo is not None:
            tint = sample_bright_rgb(albedo)
        if tint is None:
            tint = (255, 200, 100)

        if bm_img is not None:
            u = name.upper()
            # EXIT: BM mask + albedo RGB (keeps letter detail, not flat red slap).
            if u.startswith("SEXIT"):
                eimg = make_e_from_brightmap(
                    bm_img, tint, albedo, use_albedo_color=True
                )
                eimg = _boost_e(eimg, 0.85)
                src = "brightmap+albedoRGB"
            else:
                eimg = make_e_from_brightmap(bm_img, tint, albedo)
                src = "brightmap"
                if _is_static_screen_smon(u) and e_max(eimg) > 0:
                    # Solid-rect screen: white static from luminance, never RGB.
                    eimg = make_e_static_screen(bm_img, albedo)
                    em = max(em, 2.8)
                    src = "brightmap+white-static"
                elif u.startswith(("SMON", "CFACE", "CRT", "CRTR")) and e_max(eimg) > 0:
                    # Tight BM LEDs only — albedo RGB (not authored teal tint / panel fill).
                    eimg = make_e_from_brightmap(
                        bm_img, tint, albedo, use_albedo_color=True
                    )
                    eimg = _boost_e(eimg, 1.15)
                    # Sparse green-text SMON: keep glyph-shaped _e only (primary = raw _e).
                    # Dilate/halo → solid blocks on the screen (terminalgreenbug.png).
                    # Cast light = emissiveMult × mapboost on the tight LEDs.
                    if u.startswith("SMON") and (
                        _is_sparse_smon_text(u) or _e_lit_frac(eimg) < 0.05
                    ):
                        em = max(em, 2.8)
                        src = "brightmap+albedoRGB+sparse"
                    else:
                        src = "brightmap+albedoRGB"
                # C22/C23 used to composite a loose albedo mask on top of the brightmap
                # here, and it was pure fabrication (2026-08-10). The mod authors marked
                # exactly what glows on these two panels:
                #
                #   C22  2 lit pixels of 4096
                #   C23  6 lit pixels of 4096   (the demon eyes, albedo 112,0,0)
                #
                # make_e_from_albedo(loose=True) thresholds albedo LUMA, and on a stone
                # panel that catches every mortar highlight: the generated masks came out
                # at 388 and 613 lit pixels, 194x and 102x what the brightmap marks. In
                # game that is not a fixture with a glow, it is the whole tile covered in
                # amber speckle -- a yellow panel that does not exist in the artwork, on a
                # texture whose only saturated pixels are six dark red dots.
                #
                # It also cost a wrong fix: the speckle field reads as a lamp, so the
                # obvious next question is "why does that lamp not light the room", and
                # the answer is that there was never a lamp. Trust the brightmap; it is
                # the authored answer to "what on this texture emits".
        elif albedo is not None:
            u = name.upper()
            if u in SWITCH_ON_EMIS:
                # Missing BMTX* brightmaps — green LED strip only, never metal luma.
                eimg = _e_switch_led_from_albedo(albedo, tint)
                src = "switch-led"
            elif u.startswith("CTEL"):
                # Red gems on the telemetry panel. Must come BEFORE the generic
                # albedo-luma path: this texture is dark cracked stone whose
                # brightest pixels are grey mortar, so luma picks the stone and
                # misses the gems entirely. Red dominance picks the gems.
                eimg = _e_ctel_gems_from_albedo(albedo)
                src = "ctel-gems"
            elif u.startswith("SPORT"):
                # Teleporter pads — cyan-tinted mask (not grey ceiling-blob luma).
                eimg = _e_teleporter_from_albedo(albedo, tint)
                eimg = _boost_e(eimg, 1.25)
                src = "teleporter"
            elif u.startswith("SKEYFL"):
                # Luma mask + key tint (albedo yellow is brown → GI looked red).
                eimg = _e_albedo_brightmap(albedo, tint, boost=1.35)
                src = "albedo"
            elif u.startswith(("CFACE", "CRT", "CRTR", "D64LOGO")):
                eimg = _screen_e_from_albedo(albedo, tint)
                eimg = _boost_e(eimg, 1.2)
                src = "albedo"
            elif u.startswith("SMON"):
                # No GLDEFS brightmap = authored non-emissive (SMONF*, SMONLB*).
                # The generic albedo-luma path painted every bright metal slat
                # with the cyan tint over ~24% of the tile, washing whole
                # console walls ice-blue (textureissuelevel7computer.png).
                # SMONLC* is the brightmapped sibling and glows at 0.5%.
                by_src["smon_no_brightmap_skip"] += 1
                continue
            else:
                # C22/C23 are not in the loose set any more -- see the brightmap branch
                # above for the 194x/102x over-painting it caused. They always ship a
                # GLDEFS brightmap, so they never reach this branch anyway; leaving them
                # listed here would only re-teach the mistake to the next reader.
                eimg = make_e_from_albedo(
                    albedo,
                    tint,
                    loose=u.startswith("CRT"),
                )
                src = "albedo"
        else:
            by_src["no_image"] += 1
            continue

        # Real emitters only — OUTTEX/SWX excluded above.

        if e_max(eimg) < 8:
            by_src["empty_skip"] += 1
            continue

        meta: dict = {"textureName": name, "emissiveMult": em}
        if li > 0:
            meta["lightIntensity"] = li
            meta["lightColor"] = list(tint)
            if name.upper() in EVEN_ON_DYNAMIC:
                meta["lightEvenOnDynamic"] = True
        entries[name] = meta
        by_src[src] += 1

        for d in (MAT, MAT_DEV, OMAT):
            d.mkdir(parents=True, exist_ok=True)
            eimg.save(d / f"{name}_e.png")

    if "SMONF4" in entries and "SMONF5" not in entries:
        donor_path = MAT / "SMONF4_e.png"
        if donor_path.exists():
            for d in (MAT, MAT_DEV, OMAT):
                Image.open(donor_path).save(d / "SMONF5_e.png")
            entries["SMONF5"] = dict(entries["SMONF4"])
            entries["SMONF5"]["textureName"] = "SMONF5"
            by_src["clone"] += 1

    # SMONF5 is a gallery clone, not in ANIMDEFS — still needs PBR companions.
    for d in (MAT, MAT_DEV, OMAT):
        if not d.exists():
            continue
        for suf in ("_n.png", "_orm.png", "_h.png"):
            src, dst = d / f"SMONF4{suf}", d / f"SMONF5{suf}"
            if src.exists() and not dst.exists():
                dst.write_bytes(src.read_bytes())

    n_pbr = clone_anim_pbr_maps(anims, [MAT, MAT_DEV, OMAT])
    if n_pbr:
        print(f"cloned SMON anim PBR companions: {n_pbr} files")

    print(f"world emis: {len(entries)} textures with _e.png")
    for k, v in sorted(by_src.items(), key=lambda x: -x[1]):
        print(f"  {k}: {v}")
    for sample in (
        "SMONAA",
        "SEXIT",
        "HLAVA1",
        "SKEYFLYL",
        "SKEYFLRD",
        "SKEYFLBL",
        "BFALL01",
        "H36YGLOW",
        "D64LAVA1",
        "C22",
        "D64LOGO",
        "CRTRAKA",
        "SMONF5",
        "OUTTEX08",
        "SWXS4B",
        "SWXSAB",
    ):
        print(sample, entries.get(sample))

    # Generic SFLAT* flats are geometry, not fixture identities. They used to
    # receive ceiling-blob masks here, which created false point emitters in
    # unrelated rooms (notably MAP02). Remove artifacts from older runs.
    removed_sflat = 0
    for d in (MAT, MAT_DEV, OMAT):
        if not d.exists():
            continue
        for stem in LAMP_FLAT_NO_EMIS:
            p = d / f"{stem}_e.png"
            if p.exists():
                p.unlink()
                removed_sflat += 1
    if removed_sflat:
        print(f"removed obsolete generic SFLAT _e.png: {removed_sflat}")

    # Drop stale non-emitters (falls / glow / OUTTEX / idle SWX).
    keep_e = {k.upper() for k in entries}
    removed_e = 0
    for d in (MAT, MAT_DEV, OMAT):
        if not d.exists():
            continue
        for p in d.glob("*_e.png"):
            stem = p.name[: -len("_e.png")]
            u = stem.upper()
            stale = (
                FALL_RE.match(u)
                or GLOW_RE.search(u)
                or re.match(r"^(OUTTEX|SWX)", u)
            )
            if stale and u not in keep_e:
                p.unlink()
                removed_e += 1
    if removed_e:
        print(f"removed stale fall/glow/OUTTEX/SWX _e.png: {removed_e}")

    def scrub_array_stale(path: Path) -> int:
        if not path.exists():
            return 0
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return 0
        arr = data.get("array", [])
        keep_u = {k.upper() for k in entries}
        new = []
        n = 0
        for e in arr:
            name = str(e.get("textureName", ""))
            u = name.upper()
            if (FALL_RE.match(u) or GLOW_RE.search(u) or u in set(LAMP_FLAT_NO_EMIS)) and u not in keep_u:
                n += 1
                continue
            new.append(e)
        if n:
            data["array"] = new
            path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        return n

    upsert_json(OVERLAY, entries, replace=True)
    for scene in (SCENE_MAP01, SCENE_GALLERY):
        if scene.exists():
            upsert_json(scene, entries, replace=False)
            scrub_array_stale(scene)
    for scene in (OVERLAY_MAP01, OVERLAY_GALLERY):
        scene.parent.mkdir(parents=True, exist_ok=True)
        upsert_json(scene, entries, replace=False)
        scrub_array_stale(scene)

    if GLOBAL_JSON.exists():
        # Strip stock false-panel / unmasked fall metas, then write authored.
        cleared = scrub_false_panel_emis(GLOBAL_JSON, keep=set(entries))
        if cleared:
            print(f"cleared false-panel stock emis in global: {cleared}")
        patch_global_inline(GLOBAL_JSON, entries)
        # Unconditional — NOT gated behind --no-scrub. These four are lit by
        # analytic lights; an emissiveMult with no _e mask makes the whole flat
        # self-emit (see LAMP_FLAT_NO_EMIS).
        dropped = strip_lamp_flat_emis(GLOBAL_JSON)
        if dropped:
            print(f"dropped analytic-lamp emissiveMult in global: {dropped}")
        # Full stock scrub is DEFAULT (wash-qa root cause: stock high-mult
        # meta e.g. PLAY* @4.25 floods GI via albedo*mult*mapboost).
        # --no-scrub escapes for debugging only. --scrub is accepted as a no-op
        # for backward compat with old scripts.
        if "--no-scrub" in sys.argv:
            print("skip full global scrub (--no-scrub) — DEBUG ONLY, wash risk")
        else:
            scrubbed = scrub_stock_world_emis(GLOBAL_JSON, set(entries))
            if scrubbed:
                print(f"scrubbed stock world emis lines in global: {scrubbed}")

    print("overlay ->", OVERLAY)
    print("done")


if __name__ == "__main__":
    main()
