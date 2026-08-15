from __future__ import annotations

import re
import struct
from collections import defaultdict
from pathlib import Path

# Repo root, derived from this file so a clone can live anywhere.
PROJ_ROOT = Path(__file__).resolve().parents[1]

ROOT = PROJ_ROOT


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


def wad_lumps(path: Path) -> set[str]:
    d = path.read_bytes()
    n, o = struct.unpack_from("<II", d, 4)
    names = set()
    for i in range(n):
        off, sz, name = struct.unpack_from("<II8s", d, o + i * 16)
        nm = name.split(b"\0")[0].decode("ascii", "replace")
        if sz > 0:
            names.add(nm)
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
    stock = parse_textures_json(ROOT / r"gzdoom-rt-1.0.2\rt\data\textures.json")
    lumps = wad_lumps(ROOT / r"Doom64-Retribution\D64RTR_v15.WAD")
    dec = decorate_text(ROOT / r"Doom64-Retribution\D64RTR_v15.WAD")

    frames: set[str] = set()
    for m in re.finditer(
        r"(?im)\b([A-Z][A-Z0-9]{3})\s+([A-Z0-9\[\]\\]+)\s+(\d+)([^\n;{]*)", dec
    ):
        spr, fr, rest = m.group(1), m.group(2), m.group(4)
        if "BRIGHT" not in rest.upper():
            continue
        letters = set(re.findall(r"[A-Z]", fr))
        for L in letters:
            for rot in list("012345678"):
                cand = f"{spr}{L}{rot}"
                if cand in lumps:
                    frames.add(cand)
        # composite names like A1A5 present as full lump
        for tok in re.findall(r"[A-Z]\d[A-Z]\d|[A-Z]\d|[A-Z]", fr):
            cand = f"{spr}{tok}"
            if cand in lumps:
                frames.add(cand)

    # also include all projectile-ish lumps regardless of BRIGHT
    prefixes = (
        "BAR1",
        "BEXP",
        "MISL",
        "MISF",
        "BAL1",
        "BAL2",
        "BAL3",
        "BAL7",
        "BAL8",
        "PLSS",
        "PLSE",
        "PLSF",
        "BFS1",
        "BFE1",
        "BFE2",
        "BFGF",
        "MANF",
        "APLS",
        "APBX",
        "FIRE",
        "PUFF",
        "PUF2",
        "TFOG",
        "IFOG",
        "TRCR",
        "RBAL",
        "CPLS",
        "CRCK",
        "RECT",
        "CBFG",
        "LPUF",
        "UNMF",
        "UNML",
        "ART1",
        "ART2",
        "ART3",
        "PINS",
        "PINV",
        "SUIT",
        "PISF",
        "SHTF",
        "SSGF",
        "CHGF",
        "CLCG",
        "CPIS",
        "CSHT",
        "CSSG",
        "PLSG",
        "BFGG",
        "SKUL",
        "FATB",
        "FATJ",
        "BLUD",
        "SPAW",
        "BOSF",
        "TNT1",
    )
    for nm in lumps:
        if any(nm.startswith(p) for p in prefixes):
            frames.add(nm)

    missing = []
    weak = []
    for n in sorted(frames):
        e = stock.get(n, {})
        if not e:
            missing.append(n)
        elif not e.get("lightIntensity") and (e.get("emissiveMult") or 0) < 0.15:
            weak.append(n)
        elif not e.get("lightIntensity") and e.get("emissiveMult"):
            weak.append(n)  # emis only — often want light too for FX

    print("candidate textures", len(frames))
    print("not in stock at all", len(missing))
    g = defaultdict(list)
    for n in missing:
        g[n[:4]].append(n)
    for k in sorted(g, key=lambda x: -len(g[x]))[:50]:
        print("MISS", k, len(g[k]), g[k][:10])

    g2 = defaultdict(list)
    for n in weak:
        if n in missing:
            continue
        g2[n[:4]].append(n)
    print("stock emis-only or weak (want lights?):", sum(len(v) for v in g2.values()))
    for k in sorted(g2, key=lambda x: -len(g2[x]))[:40]:
        e0 = stock.get(g2[k][0], {})
        print(
            "WEAK",
            k,
            len(g2[k]),
            "eg",
            g2[k][0],
            "emis",
            e0.get("emissiveMult"),
            "I",
            e0.get("lightIntensity"),
            "col",
            e0.get("lightColorHEX"),
        )

    print("BAR1A0", stock.get("BAR1A0"))
    print("BAR1B0", stock.get("BAR1B0"))


if __name__ == "__main__":
    main()
