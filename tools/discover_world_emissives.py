"""
Discover Retribution world textures that likely need RT emissives.

Scores candidates from:
  - GLDEFS texture brightmaps (D64RTR_BRIGHTMAPS.PK3)
  - Name heuristics (LAVA / LITE / GLOW / FIRE / …)
  - ANIMDEFS animated bases matching those names
  - Bright / saturated pixel fraction in albedo (PNG or TEXTURES composite)

Compares against textures_world_emis.json and writes a review table.

Usage:
  python tools/discover_world_emissives.py
  python tools/discover_world_emissives.py --apply-missing   # regen via gen_world_emissives rules only
"""
from __future__ import annotations

import argparse
import io
import json
import re
import struct
import zipfile
from collections import defaultdict
from pathlib import Path

from PIL import Image

# Repo root, derived from this file so a clone can live anywhere.
PROJ_ROOT = Path(__file__).resolve().parents[1]

ROOT = PROJ_ROOT
WAD = ROOT / r"Doom64-Retribution\D64RTR_v15.WAD"
BM_PK3 = ROOT / r"Doom64-Retribution\D64RTR_BRIGHTMAPS.PK3"
WORLD_EMIS = (
    ROOT / r"Doom64-Retribution\Retribution-RT-Materials\rt\data\textures_world_emis.json"
)
OUT_MD = ROOT / r"tools\_emissive_candidates.md"
OUT_JSON = ROOT / r"tools\_emissive_candidates.json"

# Stronger tokens first
NAME_HINTS: list[tuple[str, int, str]] = [
    ("HLAVA", 100, "lava"),
    ("D64LAVA", 100, "lava"),
    ("LAVA", 95, "lava"),
    ("SMON", 90, "monitor"),
    ("SEXIT", 90, "exit"),
    ("SKEYFL", 90, "key_floor"),
    ("CFACE", 75, "face_light"),
    ("NUKE", 80, "nukage"),
    # Liquid falls / *GLOW names are NOT cast-light sources for RT authoring.
    ("BFALL", 10, "liquid_fall_skip"),
    ("SFALL", 10, "liquid_fall_skip"),
    ("WFALL", 5, "liquid_fall_skip"),
    ("OUTTEX", 60, "outdoor_lit"),
    ("SWX", 65, "switch"),
    ("LITE", 75, "light"),
    ("TLITE", 75, "light"),
    ("LIGHT", 50, "light"),
    ("GLOW", 15, "glow_name_skip"),
    ("FIRE", 70, "fire"),
    ("LAMP", 70, "lamp"),
    ("BLINK", 70, "blink"),
    ("TECH", 25, "tech"),
    ("PANEL", 20, "panel"),
    ("COMP", 30, "computer"),
    ("CRT", 40, "screen"),
    ("SCREEN", 40, "screen"),
    ("WARN", 35, "warning"),
    ("RED", 15, "color"),
]

SKIP_RE = re.compile(
    r"^(SPACE|METAL|STEEL|DOOR|GATE|FRSKY|FIRE[A-Z0]|PLAY|POSS|TROO|SPOS|SARG|SKUL|MISL|BAL)",
    re.I,
)


def wad_lumps() -> dict[str, bytes]:
    d = WAD.read_bytes()
    n, o = struct.unpack_from("<II", d, 4)
    out: dict[str, bytes] = {}
    for i in range(n):
        off, sz, raw = struct.unpack_from("<II8s", d, o + i * 16)
        nm = raw.split(b"\0")[0].decode("ascii", "replace").rstrip().upper()
        if sz > 0:
            out[nm] = d[off : off + sz]
    return out


def map_used() -> set[str]:
    names: set[str] = set()
    d = WAD.read_bytes()
    n, o = struct.unpack_from("<II", d, 4)
    for i in range(n):
        off, sz, raw = struct.unpack_from("<II8s", d, o + i * 16)
        nm = raw.split(b"\0")[0].decode("ascii", "replace").rstrip()
        if nm != "TEXTMAP" or sz <= 0:
            continue
        t = d[off : off + sz].decode("utf-8", "replace")
        for m in re.finditer(
            r'texture(?:floor|ceiling|middle|top|bottom)\s*=\s*"([^"]+)"', t, re.I
        ):
            names.add(m.group(1).upper())
    return names


def textures_names(lumps: dict[str, bytes]) -> set[str]:
    tex = lumps.get("TEXTURES")
    if not tex:
        return set()
    t = tex.decode("latin1", "replace")
    return {
        x.upper()
        for x in re.findall(
            r"(?im)^\s*(?:Texture|WallTexture|Flat)\s+([A-Za-z0-9_]+)", t
        )
    }


def anim_bases(lumps: dict[str, bytes]) -> dict[str, list[str]]:
    raw = lumps.get("ANIMDEFS", b"").decode("latin1", "replace")
    out: dict[str, list[str]] = {}
    cur = None
    pics: list[str] = []
    for line in raw.splitlines():
        s = line.strip()
        m = re.match(r"texture\s+(\S+)", s, re.I)
        if m:
            if cur and pics:
                out[cur] = pics
            cur = m.group(1).upper()
            pics = []
            continue
        m = re.match(r"pic\s+(\S+)", s, re.I)
        if m and cur:
            pics.append(m.group(1).upper())
    if cur and pics:
        out[cur] = pics
    return out


def brightmap_textures() -> set[str]:
    if not BM_PK3.exists():
        return set()
    with zipfile.ZipFile(BM_PK3) as z:
        g = z.read("GLDEFS").decode("latin1", "replace")
    return {
        m.group(1).upper()
        for m in re.finditer(
            r"brightmap\s+texture\s+\"?([^\"{\s]+)\"?", g, re.I
        )
    }


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
        if pname not in lumps or lumps[pname][:4] != b"\x89PNG":
            continue
        patch = Image.open(io.BytesIO(lumps[pname])).convert("RGBA")
        canvas.paste(patch, (px, py), patch)
    if canvas.getbbox() is None:
        for pm in re.finditer(r"(?im)Patch\s+([A-Za-z0-9_]+)", body):
            pname = pm.group(1).upper()
            if pname in lumps and lumps[pname][:4] == b"\x89PNG":
                patch = Image.open(io.BytesIO(lumps[pname])).convert("RGBA")
                return patch.crop((0, 0, min(w, patch.size[0]), min(h, patch.size[1])))
        return None
    return canvas


def resolve_albedo(lumps: dict[str, bytes], name: str) -> Image.Image | None:
    key = name.upper()
    if key in lumps and lumps[key][:4] == b"\x89PNG":
        return Image.open(io.BytesIO(lumps[key])).convert("RGBA")
    return compose_from_textures(lumps, key)


def bright_score(img: Image.Image) -> tuple[float, float, tuple[int, int, int]]:
    """Return (bright_frac, sat_frac, mean_bright_rgb)."""
    px = img.load()
    bright = sat = tot = 0
    acc = [0, 0, 0]
    for y in range(img.size[1]):
        for x in range(img.size[0]):
            r, g, b, a = px[x, y]
            if a < 40:
                continue
            tot += 1
            s = r + g + b
            mx, mn = max(r, g, b), min(r, g, b)
            if s >= 400 or mx >= 200:
                bright += 1
                acc[0] += r
                acc[1] += g
                acc[2] += b
            if (mx - mn) >= 60 and mx >= 120:
                sat += 1
    if tot == 0:
        return 0.0, 0.0, (0, 0, 0)
    mean = (
        (acc[0] // max(1, bright), acc[1] // max(1, bright), acc[2] // max(1, bright))
        if bright
        else (0, 0, 0)
    )
    return bright / tot, sat / tot, mean  # type: ignore[return-value]


def name_hint(name: str) -> tuple[int, str] | None:
    u = name.upper()
    if SKIP_RE.match(u):
        return None
    best = None
    for pref, score, tag in NAME_HINTS:
        if u.startswith(pref) or (len(pref) >= 4 and pref in u):
            if best is None or score > best[0]:
                best = (score, tag)
    return best


def already_emis() -> set[str]:
    if not WORLD_EMIS.exists():
        return set()
    doc = json.loads(WORLD_EMIS.read_text(encoding="utf-8"))
    return {e["textureName"].upper() for e in doc.get("array", []) if "textureName" in e}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--min-score",
        type=int,
        default=40,
        help="Minimum total score to list (default 40)",
    )
    ap.add_argument(
        "--map-used-only",
        action="store_true",
        help="Only textures referenced in TEXTMAP lumps",
    )
    args = ap.parse_args()

    lumps = wad_lumps()
    used = map_used()
    texnames = textures_names(lumps)
    anims = anim_bases(lumps)
    bm = brightmap_textures()
    have = already_emis()

    pool = used | bm | set(anims)
    if not args.map_used_only:
        # include TEXTURES that match name hints or brightmaps
        for n in texnames:
            if name_hint(n) or n in bm:
                pool.add(n)
        for base, frames in anims.items():
            if name_hint(base) or base in bm:
                pool.add(base)
                pool.update(frames)

    rows = []
    for name in sorted(pool):
        if SKIP_RE.match(name):
            continue
        reasons: list[str] = []
        score = 0
        tag = ""

        if name in bm:
            score += 100
            reasons.append("brightmap")
        nh = name_hint(name)
        if nh:
            score += nh[0]
            tag = nh[1]
            reasons.append(f"name:{nh[1]}")
        if name in used:
            score += 15
            reasons.append("map-used")
        if name in anims or any(name in frs for frs in anims.values()):
            score += 10
            reasons.append("anim")

        bfrac = sfrac = 0.0
        mean = (0, 0, 0)
        img = resolve_albedo(lumps, name)
        if img is not None:
            bfrac, sfrac, mean = bright_score(img)
            if bfrac >= 0.08:
                score += int(min(40, bfrac * 120))
                reasons.append(f"bright={bfrac:.2f}")
            if sfrac >= 0.12 and mean[0] + mean[1] + mean[2] > 300:
                # hot colored — lava/monitor-ish; dampen for dull metal reds
                score += int(min(25, sfrac * 80))
                reasons.append(f"sat={sfrac:.2f}")

        if score < args.min_score:
            continue

        rows.append(
            {
                "texture": name,
                "score": score,
                "tag": tag or ("brightmap" if name in bm else ""),
                "covered": name in have,
                "map_used": name in used,
                "bright_frac": round(bfrac, 3),
                "sat_frac": round(sfrac, 3),
                "mean_bright_rgb": list(mean),
                "reasons": reasons,
            }
        )

    rows.sort(key=lambda r: (-r["score"], r["texture"]))
    missing = [r for r in rows if not r["covered"]]
    covered = [r for r in rows if r["covered"]]

    by_tag: dict[str, int] = defaultdict(int)
    for r in missing:
        by_tag[r["tag"] or "untagged"] += 1

    OUT_JSON.write_text(json.dumps({"candidates": rows}, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# World emissive candidates",
        "",
        f"Scored {len(rows)} textures (min_score={args.min_score}). "
        f"**Covered:** {len(covered)}. **Missing:** {len(missing)}.",
        "",
        "Generator: `python tools/gen_world_emissives.py`",
        "This scan: `python tools/discover_world_emissives.py`",
        "",
        "## Missing by tag",
        "",
    ]
    for k, v in sorted(by_tag.items(), key=lambda x: -x[1]):
        lines.append(f"- `{k}`: {v}")
    lines += ["", "## Missing (review)", "", "| Score | Texture | Tag | Map | Bright | Reasons |", "|---:|---|---|---|---:|---|"]
    for r in missing[:120]:
        lines.append(
            f"| {r['score']} | `{r['texture']}` | {r['tag']} | "
            f"{'Y' if r['map_used'] else ''} | {r['bright_frac']:.2f} | "
            f"{', '.join(r['reasons'])} |"
        )
    if len(missing) > 120:
        lines.append(f"| … | _{len(missing) - 120} more in JSON_ | | | | |")
    lines += ["", "## Already covered (top)", "", "| Score | Texture | Tag |", "|---:|---|---|"]
    for r in covered[:40]:
        lines.append(f"| {r['score']} | `{r['texture']}` | {r['tag']} |")

    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"candidates {len(rows)} covered {len(covered)} missing {len(missing)}")
    print(f"missing tags: {dict(by_tag)}")
    print("top missing:")
    for r in missing[:25]:
        print(f"  {r['score']:3d} {r['texture']:<12} {r['tag']:<12} {r['reasons']}")
    print("->", OUT_MD)
    print("->", OUT_JSON)


if __name__ == "__main__":
    main()
