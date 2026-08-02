"""
Red eye emissives for Retribution enemies (RTGL1) — eyes only, no body glow.

Sources (strict):
  1) D64RTR_BRIGHTMAPS.PK3 brightmaps/bd64/* eye masks (validated compact/head)
  2) Clone TROO→TRO2 and SARG→SAR2 for matching frames
  3) Lost Soul (SKUL): fire _e (separate path)
  Auto red-pixel detect is OFF — it painted armor/blood/backs on soldiers & pinkies.

Output:
  rt/mat/<SPRITE>_e.png
  textures.json: emissiveMult only (no cast light)
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
MAT_DEV = ROOT / r"sourcecode\gzdoom-rt\build\RelWithDebInfo\rt\mat_dev"
OMAT = ROOT / r"Doom64-Retribution\Retribution-RT-Materials\rt\mat"
GLOBAL = ROOT / r"sourcecode\gzdoom-rt\build\RelWithDebInfo\rt\data\textures.json"
SCENE = ROOT / r"sourcecode\gzdoom-rt\build\RelWithDebInfo\rt\data\scenes\d64rtr_v15_map01\textures.json"
ENEMY_GALLERY_SCENE = (
    ROOT
    / r"sourcecode\gzdoom-rt\build\RelWithDebInfo\rt\data\scenes"
    / "d64renemyg_map98"
    / "textures.json"
)
OVERLAY = ROOT / r"Doom64-Retribution\Retribution-RT-Materials\rt\data\textures_enemy_eyes.json"

# Eyes: surface glow only. Cast light (lightIntensity) turns zombies into lanterns.
EMIS = 2.0
EYE_LIGHT = 0
EYE_HEX = "ff0a00"
# Pure hot red — avoid G/B lift that blooms pink under RT emis.
RED = (255, 10, 0)
# Broken on soldiers/pinky backs — do not re-enable without paired-cluster QA.
AUTO_EYES = False

# Lost Soul: stock actor. Mat albedo retints white fire → yellow/orange; low _e + milder cast light.
SKUL_EMIS = 0.12
# 0 = no attached light (bloom on sprite was blowing yellow→white). Floor glow is weaker.
SKUL_LIGHT = 0
SKUL_HEX = "ff9028"
SKUL_WRITE_E = True
SKUL_TONE_ALBEDO = True  # + d64r-lostsoul-rt.pk3 sprite replacements

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


def sprite_frame_info(name: str) -> tuple[str, str]:
    """Return (frame_letter, rotation_token) from Doom sprite name, e.g. SARGA2A8 → (A, 2A8)."""
    if len(name) < 5:
        return "", ""
    rest = name[4:]
    if not rest:
        return "", ""
    frame = rest[0]
    rot = rest[1:] if len(rest) > 1 else ""
    return frame, rot


def is_death_or_gib_frame(name: str) -> bool:
    """Living walk/attack frames are A–G; H+ / *0 corpses must not glow."""
    frame, rot = sprite_frame_info(name)
    if not frame:
        return False
    if frame >= "H":
        return True
    if rot == "0" and frame >= "H":
        return True
    return False


def is_rear_view(name: str) -> bool:
    """Pure back (*5) — eyes not visible; skip (fixes pinky backside glow)."""
    _, rot = sprite_frame_info(name)
    return rot == "5"


def is_valid_eye_mask(eimg: Image.Image, albedo: Image.Image | None = None) -> bool:
    """Reject body/armor false positives: eyes are tiny and in the head band."""
    w, h = eimg.size
    lit_xy: list[tuple[int, int]] = []
    for i, (_r, _g, _b, a) in enumerate(eimg.getdata()):
        if a > 20:
            lit_xy.append((i % w, i // w))
    if len(lit_xy) < 2:
        return False
    # Hard cap — real eyes are a handful of pixels on these sprites.
    if len(lit_xy) > 70:
        return False
    xs = [p[0] for p in lit_xy]
    ys = [p[1] for p in lit_xy]
    x0, x1 = min(xs), max(xs)
    y0, y1 = min(ys), max(ys)
    if (y1 - y0) > max(10, h // 5):
        return False
    if (x1 - x0) > max(28, w // 2):
        return False

    # Head band relative to opaque albedo bbox (not empty canvas padding).
    head_lo, head_hi = 0.0, h * 0.55
    if albedo is not None and albedo.size == eimg.size:
        ap = list(albedo.convert("RGBA").getdata())
        ays = [i // w for i, p in enumerate(ap) if p[3] > 40]
        if ays:
            top, bot = min(ays), max(ays)
            body_h = max(1, bot - top)
            head_lo = top
            head_hi = top + body_h * 0.42
    if y0 < head_lo - 2 or y1 > head_hi + 2:
        return False
    return True


def mask_to_red_e(mask: Image.Image, albedo: Image.Image | None) -> Image.Image:
    """Brightmap → red _e. Geometry from mask only (no dilate, no body paint)."""
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
        if a < 24 or lum < 40:
            pixels.append((0, 0, 0, 0))
            continue
        # Drop mask bleed over fully transparent canvas
        if ap is not None and ap[i][3] < 20:
            pixels.append((0, 0, 0, 0))
            continue
        t = min(1.0, lum / 220.0)
        pixels.append((int(RED[0] * t), int(RED[1] * t), int(RED[2] * t), 255))
    out = Image.new("RGBA", size)
    out.putdata(pixels)
    return out


def meta_for(name: str) -> dict:
    # Do NOT set noShadow here — that flag applies to the whole sprite texture
    # and stops enemies casting shadows under emissive/world lights.
    if name.startswith("SKUL"):
        meta = {
            "textureName": name,
            "emissiveMult": SKUL_EMIS,
        }
        if SKUL_LIGHT > 0:
            meta["lightIntensity"] = SKUL_LIGHT
            meta["lightColorHEX"] = SKUL_HEX
            meta["lightEvenOnDynamic"] = True
        return meta
    meta = {
        "textureName": name,
        "emissiveMult": EMIS,
    }
    if EYE_LIGHT > 0:
        meta["lightIntensity"] = EYE_LIGHT
        meta["lightColorHEX"] = EYE_HEX
        meta["lightEvenOnDynamic"] = True
    return meta


def tone_skul_albedo(albedo: Image.Image) -> Image.Image:
    """Mat-only: recolor pale/white fire cores to yellow→orange; leave skull bone alone."""
    a = albedo.convert("RGBA")
    out_px = []
    # Dimmer saturated fire — BRIGHT + bloom will still lift it; start well below white
    YELLOW = (210, 130, 28)
    ORANGE = (200, 85, 22)
    RED = (175, 38, 14)
    for r, g, b, al in a.getdata():
        if al < 8:
            out_px.append((0, 0, 0, 0))
            continue
        lum = 0.45 * r + 0.4 * g + 0.15 * b
        # Fire / hot glow (not dark horns / sockets)
        is_fire = lum > 120 and r > 90 and r + 15 >= g
        pale = r > 200 and g > 180 and b > 140  # the white-hot cores
        if is_fire or pale:
            t = min(1.0, max(0.0, (lum - 100) / 140.0))
            if t > 0.7:
                fr, fg, fb = YELLOW
            elif t > 0.35:
                u = (t - 0.35) / 0.35
                fr = int(ORANGE[0] * (1 - u) + YELLOW[0] * u)
                fg = int(ORANGE[1] * (1 - u) + YELLOW[1] * u)
                fb = int(ORANGE[2] * (1 - u) + YELLOW[2] * u)
            else:
                u = t / 0.35
                fr = int(RED[0] * (1 - u) + ORANGE[0] * u)
                fg = int(RED[1] * (1 - u) + ORANGE[1] * u)
                fb = int(RED[2] * (1 - u) + ORANGE[2] * u)
            # Cap so BRIGHT can't present a white triple
            fb = min(fb, 60)
            fg = min(fg, 195)
            out_px.append((fr, fg, fb, al))
        else:
            out_px.append((r, g, b, al))
    out = Image.new("RGBA", a.size)
    out.putdata(out_px)
    return out


def save_albedo(tex: str, img: Image.Image) -> None:
    for dest in (MAT / f"{tex}.png", MAT_DEV / f"{tex}.png", OMAT / f"{tex}.png"):
        dest.parent.mkdir(parents=True, exist_ok=True)
        img.save(dest)


def fire_body_e(albedo: Image.Image) -> Image.Image | None:
    """Dedicated Lost Soul fire _e: yellow→orange, hard-capped (never white cores)."""
    a = albedo.convert("RGBA")
    w, h = a.size
    out_px = []
    lit = 0
    # Explicit fire palette (RGB). Peak kept modest — strength comes from emisMult.
    YELLOW = (255, 200, 48)
    ORANGE = (255, 120, 28)
    RED = (220, 48, 16)
    for r, g, b, al in a.getdata():
        if al < 24:
            out_px.append((0, 0, 0, 0))
            continue
        warm = r > 80 and r >= g - 8 and r > b + 8
        hot = (r + g + b) > 340 and max(r, g, b) > 120
        if not (warm or hot):
            out_px.append((0, 0, 0, 0))
            continue
        lum = (0.45 * r + 0.4 * g + 0.15 * b) / 255.0
        # Soft mask weight from albedo brightness (skull sockets stay out)
        wgt = min(1.0, max(0.15, (lum - 0.25) / 0.65))
        # Map: bright core → yellow, mid → orange, tips → red
        if lum > 0.75:
            fr, fg, fb = YELLOW
            wgt *= 0.85  # core slightly softer so it doesn't clip white on screen
        elif lum > 0.45:
            u = (lum - 0.45) / 0.30
            fr = int(ORANGE[0] * (1 - u) + YELLOW[0] * u)
            fg = int(ORANGE[1] * (1 - u) + YELLOW[1] * u)
            fb = int(ORANGE[2] * (1 - u) + YELLOW[2] * u)
        else:
            u = lum / 0.45
            fr = int(RED[0] * (1 - u) + ORANGE[0] * u)
            fg = int(RED[1] * (1 - u) + ORANGE[1] * u)
            fb = int(RED[2] * (1 - u) + ORANGE[2] * u)
        # Hard cap — no channel at 255 together (white)
        fr = min(230, int(fr * wgt))
        fg = min(180, int(fg * wgt))
        fb = min(50, int(fb * wgt))
        out_px.append((fr, fg, fb, 255))
        lit += 1
    if lit < 8:
        return None
    out = Image.new("RGBA", (w, h))
    out.putdata(out_px)
    return out


def auto_eye_e(albedo: Image.Image) -> Image.Image | None:
    """Disabled legacy detector — kept only if AUTO_EYES is re-enabled with care."""
    if not AUTO_EYES:
        return None
    return None


def strip_monster_noshadow(text: str) -> str:
    """Remove noShadow from monster sprite metas (was blocking enemy shadows)."""

    def repl(m: re.Match[str]) -> str:
        block = m.group(0)
        name_m = re.search(r'"textureName"\s*:\s*"([^"]+)"', block)
        if not name_m:
            return block
        name = name_m.group(1)
        if not any(name.startswith(p) for p in MONSTER_PREFIXES):
            return block
        if "noShadow" not in block:
            return block
        block = re.sub(r',?\s*"noShadow"\s*:\s*true', "", block, flags=re.I)
        block = re.sub(r"\{\s*,", "{ ", block)
        block = re.sub(r",\s*,", ", ", block)
        block = re.sub(r",\s*\}", " }", block)
        return block

    return re.sub(r'\{[^{}]*"textureName"[^{}]*\}', repl, text)


def patch_global(entries: dict[str, dict]) -> None:
    text = strip_monster_noshadow(GLOBAL.read_text(encoding="utf-8"))
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
        # Hard replace so lowering/removing lightIntensity actually sticks.
        by[name] = dict(meta)
        by[name]["textureName"] = name
    data["array"] = list(by.values())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def save_e(tex: str, eimg: Image.Image) -> None:
    for dest in (MAT / f"{tex}_e.png", MAT_DEV / f"{tex}_e.png", OMAT / f"{tex}_e.png"):
        dest.parent.mkdir(parents=True, exist_ok=True)
        eimg.save(dest)


def main() -> None:
    lumps = wad_lumps()
    entries: dict[str, dict] = {}
    from_bm = 0
    from_auto = 0
    from_skul = 0
    by_pref: dict[str, int] = defaultdict(int)

    # 0) Lost Soul — mat albedo fire retint + yellow _e + cast light (stock actor)
    for name, data in lumps.items():
        if not name.startswith("SKUL"):
            continue
        img = open_img(data)
        if img is None:
            continue
        if SKUL_TONE_ALBEDO:
            toned = tone_skul_albedo(img)
            save_albedo(name, toned)
            src_for_e = toned
        else:
            for d in (MAT, MAT_DEV, OMAT):
                ap = d / f"{name}.png"
                if ap.exists():
                    ap.unlink()
            src_for_e = img
        if SKUL_WRITE_E:
            eimg = fire_body_e(src_for_e)
            if eimg is not None:
                save_e(name, eimg)
        entries[name] = meta_for(name)
        from_skul += 1
        by_pref["SKUL"] += 1

    # 1) Brightmap eye masks in bd64/ (validated — no rear/death, compact head only)
    rejected_bm = 0
    with zipfile.ZipFile(BM) as z:
        for n in z.namelist():
            if "bd64" not in n.lower() or not n.lower().endswith(".png"):
                continue
            stem = Path(n).stem
            u = stem.upper()
            if any(s in u for s in SKIP_STEM_SUBSTR):
                continue
            if u.startswith("SKUL"):
                continue
            if not any(u.startswith(p) for p in MONSTER_PREFIXES):
                continue
            tex = bm_to_texname(stem)
            if is_death_or_gib_frame(tex) or is_rear_view(tex):
                rejected_bm += 1
                continue
            mask = Image.open(io.BytesIO(z.read(n)))
            albedo = open_img(lumps[tex]) if tex in lumps else None
            eimg = mask_to_red_e(mask, albedo)
            if not is_valid_eye_mask(eimg, albedo):
                rejected_bm += 1
                continue
            save_e(tex, eimg)
            entries[tex] = meta_for(tex)
            from_bm += 1
            by_pref[tex[:4]] += 1

    # 2) Auto-detect (OFF) — previously false-positived soldiers / pinky backs
    if AUTO_EYES:
        for name, data in lumps.items():
            if name.startswith("SKUL"):
                continue
            if not any(name.startswith(p) for p in MONSTER_PREFIXES):
                continue
            if name in entries:
                continue
            if is_death_or_gib_frame(name) or is_rear_view(name):
                continue
            # Never auto-paint humanoids / player-like — armor & blood look "red".
            if name.startswith(("POSS", "SPOS", "CPOS", "SSWV", "PLAY")):
                continue
            img = open_img(data)
            if img is None:
                continue
            eimg = auto_eye_e(img)
            if eimg is None or not is_valid_eye_mask(eimg, img):
                continue
            save_e(name, eimg)
            entries[name] = meta_for(name)
            from_auto += 1
            by_pref[name[:4]] += 1

    # 3) Clone eye masks for Retribution variants that share layouts
    from_clone = 0
    clone_pairs = (("TRO2", "TROO"), ("SAR2", "SARG"))
    for dest_pref, src_pref in clone_pairs:
        for name, data in lumps.items():
            if not name.startswith(dest_pref) or name in entries:
                continue
            if is_death_or_gib_frame(name) or is_rear_view(name):
                continue
            donor = src_pref + name[4:]
            donor_path = MAT / f"{donor}_e.png"
            if not donor_path.exists():
                continue
            eimg = Image.open(donor_path).convert("RGBA")
            albedo = open_img(data)
            if albedo is not None and eimg.size != albedo.size:
                eimg = eimg.resize(albedo.size, Image.Resampling.NEAREST)
            if not is_valid_eye_mask(eimg, albedo):
                continue
            save_e(name, eimg)
            entries[name] = meta_for(name)
            from_clone += 1
            by_pref[dest_pref] += 1

    # Drop stale _e for monster frames we are no longer authoring (keeps SKUL).
    authored = set(entries)
    for d in (MAT, MAT_DEV, OMAT):
        if not d.exists():
            continue
        for p in d.glob("*_e.png"):
            tex = p.name[: -len("_e.png")]
            if not any(tex.startswith(pref) for pref in MONSTER_PREFIXES):
                continue
            if tex.startswith("SKUL"):
                continue
            if tex not in authored:
                p.unlink(missing_ok=True)

    print(
        f"eye maps: bm={from_bm} auto={from_auto} clone={from_clone} "
        f"skul_fire={from_skul} rejected_bm={rejected_bm} total={len(entries)} "
        f"eyeLight={EYE_LIGHT} skulLight={SKUL_LIGHT} AUTO_EYES={AUTO_EYES}"
    )
    for k in sorted(by_pref, key=lambda x: -by_pref[x]):
        print(f"  {k}: {by_pref[k]}")

    patch_global(entries)
    if SCENE.exists():
        upsert_json(SCENE, entries, replace=False)
    ENEMY_GALLERY_SCENE.parent.mkdir(parents=True, exist_ok=True)
    upsert_json(ENEMY_GALLERY_SCENE, entries, replace=True)
    overlay_scene = (
        ROOT
        / r"Doom64-Retribution\Retribution-RT-Materials\rt\data\scenes"
        / "d64renemyg_map98"
        / "textures.json"
    )
    upsert_json(overlay_scene, entries, replace=True)
    upsert_json(OVERLAY, entries, replace=True)

    pinky = ROOT / r"Doom64-Retribution\Retribution-RT-Materials\rt\data\textures_pinky_eyes.json"
    if pinky.exists():
        upsert_json(pinky, {k: v for k, v in entries.items() if k.startswith("SARG")}, replace=True)

    print("done ->", OVERLAY)
    print("scene ->", ENEMY_GALLERY_SCENE)


if __name__ == "__main__":
    main()
