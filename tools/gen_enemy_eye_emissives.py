"""
Strong red eye emissives for all Retribution enemies (RTGL1).

Sources:
  1) D64RTR_BRIGHTMAPS.PK3 brightmaps/bd64/*  (eye masks, often unbound in GLDEFS)
  2) Auto eye detect on other monster sprites in D64RTR_v15.WAD

Output:
  rt/mat/<SPRITE>_e.png
  textures.json emissiveMult ~= 5x previous pinky (0.85 -> 4.25)
  no lightIntensity (glow on the sprite / GI, not a room lamp)
"""
from __future__ import annotations

import io
import json
import re
import struct
import zipfile
from collections import defaultdict
from pathlib import Path

from PIL import Image

ROOT = Path(r"G:\AI\Doom64-RT")
WAD = ROOT / r"Doom64-Retribution\D64RTR_v15.WAD"
BM = ROOT / r"Doom64-Retribution\D64RTR_BRIGHTMAPS.PK3"
MAT = ROOT / r"sourcecode\gzdoom-rt\build\RelWithDebInfo\rt\mat"
OMAT = ROOT / r"Doom64-Retribution\Retribution-RT-Materials\rt\mat"
GLOBAL = ROOT / r"sourcecode\gzdoom-rt\build\RelWithDebInfo\rt\data\textures.json"
SCENE = ROOT / r"sourcecode\gzdoom-rt\build\RelWithDebInfo\rt\data\scenes\d64rtr_v15_map01\textures.json"
OVERLAY = ROOT / r"Doom64-Retribution\Retribution-RT-Materials\rt\data\textures_enemy_eyes.json"

# Was 0.85 for pinky; user asked ~5x for dark path-traced maps.
EMIS = 4.25
RED = (255, 36, 28)

# Sprite prefixes that are monsters (include Retribution customs when present).
MONSTER_PREFIXES = (
    "SARG",  # pinky / spectre
    "SAR2",  # retribution variant
    "TROO",  # imp
    "TRO2",  # retribution variant
    "POSS",  # zombieman
    "SPOS",  # shotgun guy
    "CPOS",  # chaingunner
    "SSWV",
    "HEAD",  # cacodemon
    "BOSS",  # baron
    "BOS2",  # hell knight
    "SKEL",  # stock revenant (if present)
    "RECT",  # retribution revenant body
    "FATT",  # mancubus
    "BSPI",  # arachnotron
    "SPID",  # spiderdemon
    "CYBR",  # cyberdemon
    "PAIN",  # pain elemental
    "SKUL",  # lost soul
    "VILE",  # archvile
)

# World/prop brightmaps under bd64 that are NOT eyes — skip.
SKIP_STEM_SUBSTR = (
    "OUTTEX",
    "SMON",
    "TORCH",
    "BFALL",
    "PLSM",
    "PISB",
    "BON2",
    "CEL1",
    "CEL2",
    "PLAS",
    "CFACE",
    "SEXIT",
    "C22",
    "C23",
)


def wad_lumps() -> dict[str, bytes]:
    d = WAD.read_bytes()
    n, o = struct.unpack_from("<II", d, 4)
    out: dict[str, bytes] = {}
    for i in range(n):
        off, sz, name = struct.unpack_from("<II8s", d, o + i * 16)
        nm = name.split(b"\0")[0].decode("ascii", "replace")
        if sz > 0:
            out[nm] = d[off : off + sz]
    return out


def bm_to_texname(stem: str) -> str:
    s = stem.upper()
    if s.endswith("B") and len(s) > 5:
        # SARGA1B / FATTA2A8B
        s = s[:-1]
    return s


def open_img(data: bytes) -> Image.Image | None:
    try:
        return Image.open(io.BytesIO(data)).convert("RGBA")
    except Exception:
        return None


def mask_to_red_e(mask: Image.Image, albedo: Image.Image | None) -> Image.Image:
    m = mask.convert("RGBA")
    if albedo is not None and albedo.size != m.size:
        m = m.resize(albedo.size, Image.Resampling.NEAREST)
        size = albedo.size
    else:
        size = m.size
    ap = list(albedo.convert("RGBA").getdata()) if albedo is not None else None
    pixels = []
    for i, (r, g, b, a) in enumerate(m.getdata()):
        lum = max(r, g, b)
        if a < 16 or lum < 16:
            pixels.append((0, 0, 0, 0))
            continue
        t = min(1.0, lum / 220.0)
        # Punch up for 5x-era visibility
        t = min(1.0, t * 1.35)
        if ap is not None:
            ar, ag, ab, aa = ap[i]
            if aa > 40 and ar > ag + 10 and ar > ab + 10:
                pixels.append(
                    (
                        min(255, int(ar * 1.4 + RED[0] * 0.3)),
                        min(255, int(ag * 0.25)),
                        min(255, int(ab * 0.25)),
                        255,
                    )
                )
                continue
        pixels.append((int(RED[0] * t), int(RED[1] * t), int(RED[2] * t), 255))
    out = Image.new("RGBA", size)
    out.putdata(pixels)
    return out


def auto_eye_e(albedo: Image.Image) -> Image.Image | None:
    """Detect small bright/red spots in the upper half of a monster sprite."""
    a = albedo.convert("RGBA")
    w, h = a.size
    px = list(a.getdata())
    scores: list[tuple[float, int]] = []
    for i, (r, g, b, al) in enumerate(px):
        if al < 40:
            continue
        y = i // w
        if y > h * 0.55:
            continue
        # Prefer red / hot highlights
        redish = r > g + 12 and r > b + 12 and r > 70
        hot = (r + g + b) > 420 and max(r, g, b) > 160
        if not (redish or hot):
            continue
        # Weight upper + redder
        score = r * 1.5 + (g + b) * 0.2 + (h * 0.55 - y) * 0.8
        if redish:
            score += 80
        scores.append((score, i))

    if len(scores) < 2:
        return None

    scores.sort(reverse=True)
    # Keep a small elite set (eyes are tiny)
    keep_n = max(4, min(40, max(6, len(scores) // 25)))
    keep = {i for _, i in scores[:keep_n]}

    # Expand slightly to neighbors if also somewhat bright
    extra = set()
    for i in keep:
        x, y = i % w, i // w
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                nx, ny = x + dx, y + dy
                if nx < 0 or ny < 0 or nx >= w or ny >= h:
                    continue
                j = ny * w + nx
                r, g, b, al = px[j]
                if al > 40 and (r + g + b) > 200:
                    extra.add(j)
    keep |= extra

    # Reject if somehow huge (body false positive)
    if len(keep) > max(80, w * h // 40):
        return None

    out_px = []
    for i, (r, g, b, al) in enumerate(px):
        if i not in keep:
            out_px.append((0, 0, 0, 0))
            continue
        t = min(1.0, max(r, g, b) / 200.0)
        out_px.append((int(RED[0] * t), int(RED[1] * t), int(RED[2] * t), 255))
    out = Image.new("RGBA", (w, h))
    out.putdata(out_px)
    return out


def patch_global(entries: dict[str, dict]) -> None:
    text = GLOBAL.read_text(encoding="utf-8")
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
            else:
                parts.append(f'"{k}":"{v}"')
        line = "    ,   { " + "  ,".join(parts) + " }"
        pat = re.compile(
            rf'^[ \t]*,?[ \t]*\{{[ \t]*"textureName"[ \t]*:[ \t]*"{re.escape(name)}".*$',
            re.M,
        )
        if pat.search(text):
            text = pat.sub(line, text, count=1)
        else:
            text = re.sub(r"\n(\s*\]\s*\}\s*)$", "\n" + line + r"\n\1", text, count=1)
    GLOBAL.write_text(text, encoding="utf-8")


def upsert_json(path: Path, entries: dict[str, dict], replace: bool = False) -> None:
    if path.exists() and not replace:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {"version": 0, "array": []}
    else:
        data = {"version": 0, "array": []}
    by = {e["textureName"]: dict(e) for e in data.get("array", []) if "textureName" in e}
    for name, meta in entries.items():
        cur = by.get(name, {"textureName": name})
        # Don't clobber FX projectile lights — only set eye fields
        cur["emissiveMult"] = max(float(cur.get("emissiveMult") or 0), meta["emissiveMult"])
        # If this was a projectile with lightIntensity, keep it; eyes have none
        if "lightIntensity" not in cur:
            pass
        cur["textureName"] = name
        by[name] = cur
    data["array"] = list(by.values())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def save_e(tex: str, eimg: Image.Image) -> None:
    for dest in (MAT / f"{tex}_e.png", OMAT / f"{tex}_e.png"):
        dest.parent.mkdir(parents=True, exist_ok=True)
        eimg.save(dest)


def main() -> None:
    lumps = wad_lumps()
    entries: dict[str, dict] = {}
    from_bm = 0
    from_auto = 0
    by_pref: dict[str, int] = defaultdict(int)

    # 1) Brightmap eye masks in bd64/
    with zipfile.ZipFile(BM) as z:
        for n in z.namelist():
            if "bd64" not in n.lower() or not n.lower().endswith(".png"):
                continue
            stem = Path(n).stem
            u = stem.upper()
            if any(s in u for s in SKIP_STEM_SUBSTR):
                continue
            if not any(u.startswith(p) for p in MONSTER_PREFIXES):
                continue
            tex = bm_to_texname(stem)
            mask = Image.open(io.BytesIO(z.read(n)))
            albedo = open_img(lumps[tex]) if tex in lumps else None
            eimg = mask_to_red_e(mask, albedo)
            lit = sum(1 for p in eimg.getdata() if p[3] > 20)
            if lit < 2:
                continue
            save_e(tex, eimg)
            entries[tex] = {"textureName": tex, "emissiveMult": EMIS}
            from_bm += 1
            by_pref[tex[:4]] += 1

    # 2) Auto-detect for other monster frames in the WAD not already covered
    for name, data in lumps.items():
        if not any(name.startswith(p) for p in MONSTER_PREFIXES):
            continue
        if name in entries:
            continue
        # skip obvious non-rotations / debris if needed
        img = open_img(data)
        if img is None:
            continue
        eimg = auto_eye_e(img)
        if eimg is None:
            continue
        lit = sum(1 for p in eimg.getdata() if p[3] > 20)
        if lit < 2:
            continue
        save_e(name, eimg)
        entries[name] = {"textureName": name, "emissiveMult": EMIS}
        from_auto += 1
        by_pref[name[:4]] += 1

    print(f"eye maps: bm={from_bm} auto={from_auto} total={len(entries)} emis={EMIS}")
    for k in sorted(by_pref, key=lambda x: -by_pref[x]):
        print(f"  {k}: {by_pref[k]}")

    patch_global(entries)
    if SCENE.exists():
        upsert_json(SCENE, entries, replace=False)
    upsert_json(OVERLAY, entries, replace=True)

    # Keep pinky overlay file pointing at shared set / update strength note
    pinky = ROOT / r"Doom64-Retribution\Retribution-RT-Materials\rt\data\textures_pinky_eyes.json"
    if pinky.exists():
        upsert_json(pinky, {k: v for k, v in entries.items() if k.startswith("SARG")}, replace=True)

    print("done ->", OVERLAY)


if __name__ == "__main__":
    main()
