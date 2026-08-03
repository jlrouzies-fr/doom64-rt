"""
Generate RT emissive + attached-light meta for Retribution FX sprites.

- Idle barrels (BAR1*): poison green glow/light
- Barrel boom (BEXP*): toxic green (not rocket orange)
- Rockets (MISL*): keep fire orange (shared MISL boom also used by 64BarrelExplosion)
- Projectiles / enemy shots / weapon flashes / torches / pickups: color from sprite
  sample + category intensity defaults (stock RT patterns where known)
- Monster gun fire frames (POSSF/SPOSF/CPOSF/…): brief attached muzzle light around the
  shooter. Player weapons get RT_AddMuzzleFlash via A_Light1/2 extralight; monsters do not.

Writes/merges into:
  build/RelWithDebInfo/rt/data/textures.json
  build/.../scenes/d64rtr_v15_map01/textures.json  (upsert)
  Doom64-Retribution/Retribution-RT-Materials/rt/data/textures_fx.json
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
IWAD = Path(r"D:\Games\GZDoom\doom2.wad")
BM_PK3 = ROOT / r"Doom64-Retribution\D64RTR_BRIGHTMAPS.PK3"
RT_DATA = ROOT / r"sourcecode\gzdoom-rt\build\RelWithDebInfo\rt\data"
GLOBAL_JSON = RT_DATA / "textures.json"
SCENE_JSON = RT_DATA / r"scenes\d64rtr_v15_map01\textures.json"
OVERLAY_FX = ROOT / r"Doom64-Retribution\Retribution-RT-Materials\rt\data\textures_fx.json"
OVERLAY_SCENE = (
    ROOT / r"Doom64-Retribution\Retribution-RT-Materials\rt\data\scenes\d64rtr_v15_map01\textures.json"
)
MAT_DIR = ROOT / r"sourcecode\gzdoom-rt\build\RelWithDebInfo\rt\mat"
MAT_DEV = ROOT / r"sourcecode\gzdoom-rt\build\RelWithDebInfo\rt\mat_dev"
OVERLAY_MAT = ROOT / r"Doom64-Retribution\Retribution-RT-Materials\rt\mat"

# Forced profiles (override sampling). HEX without '#'.
FORCE: dict[str, dict] = {
    # Poison barrel idle — classic GLDEFS BARREL is green
    "BAR1A0": {
        "emissiveMult": 1.6,
        "noShadow": True,
        "lightIntensity": 520,
        "lightColorHEX": "3dff4a",
    },
    "BAR1B0": {
        "emissiveMult": 1.4,
        "noShadow": True,
        "lightIntensity": 420,
        "lightColorHEX": "2ecc40",
    },
}

# Prefix rules: (emissiveMult, lightIntensity, optional forced HEX or None=sample)
# Intensity 0 => emissive only (no analytic light).
# Do NOT add SKUL* here — owned by gen_enemy_eye / pack_lostsoul_rt.
PREFIX_RULES: list[tuple[str, float, float, str | None]] = [
    # barrels / toxic boom
    ("BAR1", 1.5, 480, "3dff4a"),
    ("BEXP", 0.65, 2400, "66ff44"),  # toxic green boom
    # rockets / barrel secondary boom (fire) — keep orange
    ("MISL", 0.45, 2200, "ff9a40"),
    ("MISF", 1.0, 900, "ffb060"),  # rocket launcher flash
    # imp / hell projectiles
    ("BAL1", 0.35, 700, "ff6f00"),
    ("BAL2", 0.35, 900, "b65cff"),
    ("BAL3", 0.35, 800, "ff5533"),
    ("BAL7", 0.35, 1000, "66ff55"),  # baron green
    ("BAL8", 0.35, 1000, "88ff66"),  # retribution green spit
    ("RBAL", 0.4, 1100, "ff4040"),  # red ball
    ("TRCR", 0.45, 1200, "ffaa55"),  # tracer / revenant-like
    ("RECT", 0.25, 400, "ff8844"),  # revenant missile trail-ish
    ("MANF", 0.4, 1200, "ff8c20"),  # mancubus
    ("APLS", 0.4, 1000, "88fa84"),
    ("APBX", 0.4, 1200, "6eff69"),
    ("FATB", 0.35, 900, "ff7020"),
    # plasma / bfg
    ("PLSS", 0.45, 900, "55aaff"),
    ("PLSE", 0.45, 1100, "66bbff"),
    ("PLSF", 1.0, 1000, "66bbff"),
    ("PLSG", 0.5, 900, "55aaff"),
    ("CPLS", 0.5, 1000, "66ccff"),
    ("BFS1", 0.5, 3000, "66ff33"),
    ("BFE1", 0.5, 3000, "66ff33"),
    ("BFE2", 0.45, 2500, "66ff33"),
    ("BFGF", 1.0, 1800, "66ff33"),
    ("BFGG", 0.8, 1400, "66ff33"),
    ("CBFG", 0.8, 1600, "66ff33"),
    ("CRCK", 0.5, 1400, "ffaa33"),  # custom rocket-ish
    # puffs / fog
    ("PUFF", 0.6, 250, "ffd0a0"),
    ("PUF2", 0.5, 220, "ffd0a0"),
    ("PUF3", 0.5, 220, "ffd0a0"),
    ("LPUF", 0.55, 300, "aaccff"),
    ("TFOG", 0.4, 500, "8866ff"),
    ("IFOG", 0.4, 450, "66ffaa"),
    # weapon flashes
    ("PISF", 1.0, 700, "ffcc88"),
    ("SHTF", 1.0, 1100, "ffcc88"),
    ("SSGF", 1.0, 1300, "ffcc88"),
    ("CHGF", 1.0, 900, "ffcc88"),
    ("CLCG", 1.0, 900, "66bbff"),
    ("CPIS", 1.0, 700, "ffcc88"),
    ("CSHT", 1.0, 1100, "ffcc88"),
    ("CSSG", 1.0, 1300, "ffcc88"),
    ("RLFT", 0.7, 600, "ff8844"),
    # unmaker / custom beams
    ("UNMF", 0.8, 1600, "ff3366"),
    ("UNML", 0.7, 1200, "ff2255"),
    ("A030", 0.6, 1000, None),
    ("A031", 0.6, 1000, None),
    ("A032", 0.6, 1000, None),
    # torches / flames
    ("FIRE", 0.7, 700, "ff8020"),
    ("BFLM", 0.8, 650, "4488ff"),
    ("RFLM", 0.8, 650, "ff4020"),
    ("YFLM", 0.8, 650, "ffcc33"),
    ("GFLM", 0.8, 650, "44ff66"),
    ("GTCH", 0.7, 500, "44ff66"),
    ("CAND", 0.5, 280, "ffaa55"),
    # pickups (soft glow)
    ("ART1", 0.6, 220, "66ffaa"),
    ("ART2", 0.6, 220, "66aaff"),
    ("ART3", 0.6, 220, "ff66aa"),
    ("PINS", 0.5, 200, "66ff99"),
    ("PINV", 0.5, 200, "aaaaff"),
    ("SOUL", 0.6, 260, "4488ff"),
    ("MEGA", 0.7, 300, "8866ff"),
    ("SUIT", 0.35, 120, "44ff66"),
    ("BKEY", 0.6, 160, "4488ff"),
    ("RKEY", 0.6, 160, "ff4444"),
    ("YKEY", 0.6, 160, "ffcc33"),
    ("BSKU", 0.6, 160, "4488ff"),
    ("RSKU", 0.6, 160, "ff4444"),
    ("YSKU", 0.6, 160, "ffcc33"),
]

# Monster fire frames only (…F). Aim frames (…E) must stay dark.
# Color matches player rt_mzlflsh_color (0xFF8C52). No noShadow — that kills enemy shadows.
# Intensities below HUD weapon flashes so body-centered lights do not lantern.
MONSTER_MUZZLE_RULES: list[tuple[str, float, float, str | None]] = [
    ("POSSF", 0.35, 480, "ff8c52"),  # Zombieman
    ("SPOSF", 0.4, 720, "ff8c52"),  # ShotgunGuy
    ("CPOSF", 0.35, 520, "ff8c52"),  # ChaingunGuy (IWAD sprites)
    ("PLAYF", 0.35, 480, "ff8c52"),  # 64MarineBot + player world fire frames
    ("SSWVF", 0.35, 480, "ff8c52"),  # WolfensteinSS
]


def wad_images(path: Path) -> dict[str, bytes]:
    d = path.read_bytes()
    n, o = struct.unpack_from("<II", d, 4)
    out: dict[str, bytes] = {}
    for i in range(n):
        off, sz, name = struct.unpack_from("<II8s", d, o + i * 16)
        nm = name.split(b"\0")[0].decode("ascii", "replace")
        if sz <= 0:
            continue
        out[nm] = d[off : off + sz]
    return out


def open_sprite(data: bytes) -> Image.Image | None:
    if len(data) < 16:
        return None
    # PNG / other PIL formats
    try:
        return Image.open(io.BytesIO(data)).convert("RGBA")
    except Exception:
        return None


def sample_hex(img: Image.Image) -> str | None:
    """Average of bright / saturated opaque pixels → RRGGBB."""
    px = img.getdata()
    acc = [0, 0, 0]
    n = 0
    for r, g, b, a in px:
        if a < 40:
            continue
        s = r + g + b
        if s < 180:
            continue
        # prefer saturated / bright
        mx = max(r, g, b)
        mn = min(r, g, b)
        if mx < 60:
            continue
        if (mx - mn) < 25 and s < 420:
            continue
        w = 1 + (mx - mn) // 40 + s // 300
        acc[0] += r * w
        acc[1] += g * w
        acc[2] += b * w
        n += w
    if n < 8:
        # fallback: any opaque above mid
        for r, g, b, a in px:
            if a < 40:
                continue
            if r + g + b < 120:
                continue
            acc[0] += r
            acc[1] += g
            acc[2] += b
            n += 1
    if n <= 0:
        return None
    r, g, b = (min(255, acc[i] // n) for i in range(3))
    # boost saturation a bit for light color
    mx = max(r, g, b) or 1
    scale = 255 / mx
    r, g, b = (min(255, int(c * scale * 0.92)) for c in (r, g, b))
    return f"{r:02x}{g:02x}{b:02x}"


def make_emissive_png(img: Image.Image, out: Path, boost: float = 1.4) -> None:
    """Keep bright pixels, kill dark — simple _e companion."""
    px = list(img.getdata())
    out_px = []
    for r, g, b, a in px:
        if a < 40:
            out_px.append((0, 0, 0, 0))
            continue
        s = r + g + b
        if s < 200:
            out_px.append((0, 0, 0, 0))
            continue
        # emphasize channel dominance
        out_px.append(
            (
                min(255, int(r * boost)),
                min(255, int(g * boost)),
                min(255, int(b * boost)),
                a,
            )
        )
    e = Image.new("RGBA", img.size)
    e.putdata(out_px)
    out.parent.mkdir(parents=True, exist_ok=True)
    e.save(out)


# Doom II WORLD fire/lava textures — NOT archvile flame sprites. The FIRE
# prefix rule must not swallow these: they got lightIntensity 700 + noShadow
# on a world texture (wash + killed wall shadows). Owned by world emis if wanted.
WORLD_TEX_RE = re.compile(r"^(FIRELAV|FIREWAL|FIREMAG|FIREBLU|FIREWALL)", re.I)


def rule_for(name: str) -> tuple[float, float, str | None] | None:
    u = name.upper()
    if WORLD_TEX_RE.match(u):
        return None
    for pref, em, li, hx in PREFIX_RULES:
        if u.startswith(pref):
            return em, li, hx
    return None


def monster_muzzle_rule(name: str) -> tuple[float, float, str | None] | None:
    u = name.upper()
    for pref, em, li, hx in MONSTER_MUZZLE_RULES:
        if u.startswith(pref):
            return em, li, hx
    return None


def fx_meta(
    name: str,
    em: float,
    li: float,
    color: str,
    *,
    no_shadow: bool,
) -> dict:
    meta: dict = {
        "textureName": name,
        "emissiveMult": em,
        "lightIntensity": li,
        "lightColorHEX": color,
    }
    if no_shadow:
        meta["noShadow"] = True
    return meta


def parse_textures_json(path: Path) -> dict[str, dict]:
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = []
    for line in text.splitlines():
        if "//" in line:
            line = line[: line.index("//")]
        lines.append(line)
    text = "\n".join(lines)
    out: dict[str, dict] = {}
    for m in re.finditer(r"\{([^{}]+)\}", text):
        body = m.group(1)
        if "textureName" not in body:
            continue
        entry: dict = {}
        for km in re.finditer(
            r'"(\w+)"\s*:\s*("([^"]*)"|true|false|-?\d+(?:\.\d+)?)', body
        ):
            k, raw = km.group(1), km.group(2)
            if raw.startswith('"'):
                entry[k] = km.group(3)
            elif raw in ("true", "false"):
                entry[k] = raw == "true"
            else:
                entry[k] = float(raw) if "." in raw else int(raw)
        name = entry.get("textureName")
        if name:
            out[str(name)] = entry
    return out


def upsert_json(path: Path, entries: dict[str, dict], replace: bool = False) -> None:
    if path.exists() and not replace:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            # stock-style with comments — rebuild from parsed + merge
            parsed = parse_textures_json(path)
            data = {"version": 0, "array": list(parsed.values())}
    else:
        data = {"version": 0, "array": []}
    by = {e["textureName"]: dict(e) for e in data.get("array", []) if "textureName" in e}
    for name, meta in entries.items():
        cur = by.get(name, {"textureName": name})
        cur.update(meta)
        cur["textureName"] = name
        by[name] = cur
    data["version"] = data.get("version", 0)
    data["array"] = list(by.values())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def patch_global_inline(path: Path, entries: dict[str, dict]) -> None:
    """Upsert one-liners into stock-style textures.json (keeps comments)."""
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
    path.write_text(text, encoding="utf-8")


def brightmap_names() -> set[str]:
    names: set[str] = set()
    if not BM_PK3.exists():
        return names
    with zipfile.ZipFile(BM_PK3) as z:
        for n in z.namelist():
            if n.endswith("/"):
                continue
            stem = Path(n).stem.upper()
            # brightmaps often named after texture
            names.add(stem)
            if stem.startswith("BRIGHTMAP") or stem.startswith("BM_"):
                continue
            names.add(stem)
    return names


def main() -> None:
    lumps = wad_images(WAD)
    if IWAD.exists():
        # Chaingunner / Wolf SS fire frames live in the IWAD, not Retribution.
        for name, data in wad_images(IWAD).items():
            if monster_muzzle_rule(name) and name not in lumps:
                lumps[name] = data
    # candidates = anything matching a prefix rule, present as a lump
    candidates: list[str] = []
    for name in lumps:
        if rule_for(name) or monster_muzzle_rule(name) or name in FORCE:
            # skip HUD-only
            if name.endswith("HUD"):
                continue
            candidates.append(name)
    candidates = sorted(set(candidates))

    entries: dict[str, dict] = {}
    e_png = 0
    by_pref: dict[str, int] = defaultdict(int)

    for name in candidates:
        if name in FORCE:
            meta = {"textureName": name, **FORCE[name]}
            entries[name] = meta
            by_pref[name[:4]] += 1
            continue

        mz = monster_muzzle_rule(name)
        if mz:
            em, li, hx = mz
            color = hx or "ff8c52"
            entries[name] = fx_meta(name, em, li, color, no_shadow=False)
            by_pref[name[:5] if len(name) >= 5 else name[:4]] += 1
            continue

        rule = rule_for(name)
        if not rule:
            continue
        em, li, hx = rule
        img = open_sprite(lumps[name])
        sampled = sample_hex(img) if img else None
        color = hx or sampled or "ffffff"
        # If brightmap exists and we forced no hex, prefer sample
        if hx is None and sampled:
            color = sampled

        entries[name] = fx_meta(name, em, li, color, no_shadow=True)
        by_pref[name[:4]] += 1

        # Write _e.png for idle barrels + a few hero FX (devMode PNGs)
        if img and name.startswith(("BAR1", "BEXP", "BAL7", "BAL8", "GFLM", "APLS")):
            for d in (MAT_DIR, MAT_DEV, OVERLAY_MAT):
                d.mkdir(parents=True, exist_ok=True)
                make_emissive_png(img, d / f"{name}_e.png")
            e_png += 1

    # Also bump stock entries that are emis-only weapon flashes / MISL body if still weak
    stock = parse_textures_json(GLOBAL_JSON)
    for name, e in stock.items():
        if name in entries:
            continue
        mz = monster_muzzle_rule(name)
        if mz:
            em, li, hx = mz
            entries[name] = fx_meta(name, em, li, hx or "ff8c52", no_shadow=False)
            by_pref[name[:5] if len(name) >= 5 else name[:4]] += 1
            continue
        rule = rule_for(name)
        if not rule:
            continue
        em, li, hx = rule
        if e.get("lightIntensity"):
            continue
        # overwrite stock with authored FX profile (do not keep old high emisMult)
        entries[name] = fx_meta(
            name,
            em,
            li,
            hx or e.get("lightColorHEX") or "ffffff",
            no_shadow=True,
        )
        by_pref[name[:4]] += 1

    print(f"FX metas: {len(entries)}  _e.png: {e_png}")
    for k in sorted(by_pref, key=lambda x: -by_pref[x])[:30]:
        print(f"  {k}: {by_pref[k]}")
    print("BAR1", entries.get("BAR1A0"), entries.get("BAR1B0"))
    print("BEXPC0", entries.get("BEXPC0"))
    print("BAL7A1A5", entries.get("BAL7A1A5"))
    print("RBALA1", entries.get("RBALA1"))
    print("TRCRA1", entries.get("TRCRA1"))
    print("POSSF1", entries.get("POSSF1"))
    print("SPOSF1", entries.get("SPOSF1"))
    print("CPOSF1", entries.get("CPOSF1"))
    print("PLAYF1", entries.get("PLAYF1"))
    print("PUFFA0", entries.get("PUFFA0"))
    print("PISFA0", entries.get("PISFA0"))

    patch_global_inline(GLOBAL_JSON, entries)
    upsert_json(SCENE_JSON, entries, replace=False)
    upsert_json(OVERLAY_FX, entries, replace=True)
    if OVERLAY_SCENE.exists():
        upsert_json(OVERLAY_SCENE, entries, replace=False)

    # Keep explosion-only overlay in sync conceptually
    print("done ->", GLOBAL_JSON)
    print("overlay ->", OVERLAY_FX)


if __name__ == "__main__":
    main()
