"""Scan stock RT meta + Retribution brightmaps/DECORATE for emissive FX candidates."""
from __future__ import annotations

import re
import struct
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

# Repo root, derived from this file so a clone can live anywhere.
PROJ_ROOT = Path(__file__).resolve().parents[1]

ROOT = PROJ_ROOT
STOCK = ROOT / r"gzdoom-rt-1.0.2\rt\data\textures.json"
BUILD = ROOT / r"sourcecode\gzdoom-rt\build\RelWithDebInfo\rt\data\textures.json"
WAD = ROOT / r"Doom64-Retribution\D64RTR_v15.WAD"
BM = ROOT / r"Doom64-Retribution\D64RTR_BRIGHTMAPS.PK3"


def parse_textures_json(path: Path) -> dict[str, dict]:
    text = path.read_text(encoding="utf-8", errors="replace")
    # strip // comments
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


def wad_lumps(path: Path) -> list[str]:
    d = path.read_bytes()
    n, o = struct.unpack_from("<II", d, 4)
    names = []
    for i in range(n):
        off, sz, name = struct.unpack_from("<II8s", d, o + i * 16)
        nm = name.split(b"\0")[0].decode("ascii", "replace")
        if sz > 0:
            names.append(nm)
    return names


def decorate_text(path: Path) -> str:
    d = path.read_bytes()
    n, o = struct.unpack_from("<II", d, 4)
    for i in range(n):
        off, sz, name = struct.unpack_from("<II8s", d, o + i * 16)
        nm = name.split(b"\0")[0].decode("ascii", "replace")
        if nm == "DECORATE":
            return d[off : off + sz].decode("latin1", "replace")
    return ""


def main() -> None:
    stock = parse_textures_json(STOCK)
    build = parse_textures_json(BUILD)
    print(f"stock entries={len(stock)} with emis/light={sum(1 for e in stock.values() if e.get('emissiveMult') or e.get('lightIntensity'))}")
    print(f"build entries={len(build)} with emis/light={sum(1 for e in build.values() if e.get('emissiveMult') or e.get('lightIntensity'))}")

    missing_stock = [
        n
        for n, e in stock.items()
        if (e.get("emissiveMult") or e.get("lightIntensity")) and n not in build
    ]
    print("missing stock FX in build:", len(missing_stock), missing_stock[:20])

    # brightmaps pk3
    with zipfile.ZipFile(BM) as z:
        bm_names = [Path(n).stem.upper() for n in z.namelist() if not n.endswith("/")]
        print("brightmap stems", len(bm_names))
        # also dump any txt
        for n in z.namelist():
            if n.lower().endswith((".txt", ".gl", ".gldefs")):
                print("---", n)
                print(z.read(n).decode("latin1", "replace")[:1500])

    # BAR* and projectile-like lumps in wad
    lumps = set(wad_lumps(WAD))
    for prefix in ("BAR", "BEXP", "MISL", "BAL", "PLSS", "PLSE", "BFS", "BFE", "FATB", "MANF", "APLS", "APBX", "FIRE", "PUFF", "TFOG", "IFOG", "BLUD", "SPAW"):
        hits = sorted(x for x in lumps if x.startswith(prefix))
        if hits:
            print(prefix, hits[:40], "..." if len(hits) > 40 else f"({len(hits)})")

    # BRIGHT frames in decorate
    dec = decorate_text(WAD)
    bright_frames = Counter()
    for m in re.finditer(r"(?im)^\s*([A-Z0-9]{4})\s+[A-Z\[\]\\]+\s+\d+[^\n]*\bBRIGHT\b", dec):
        bright_frames[m.group(1)] += 1
    # also "BRIGHT" after frame letters more loosely
    for m in re.finditer(r"\b([A-Z][A-Z0-9]{3})\s+[A-Z0-9\[\]\\]+\s+\d+[^\n;{]*BRIGHT", dec):
        bright_frames[m.group(1)] += 1
    print("bright sprite prefixes (top):", bright_frames.most_common(50))

    # actors that spawn projectiles / have Missile states
    proj = re.findall(r'(?im)actor\s+(\S+)[^{]*\{[^}]{0,200}?PROJECTILE', dec)
    print("PROJECTILE actors sample", len(proj), proj[:40])


if __name__ == "__main__":
    main()
