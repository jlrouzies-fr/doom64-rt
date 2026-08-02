#!/usr/bin/env python3
"""Inventory Doom 64: Retribution WAD + brightmaps PK3."""
from __future__ import annotations

import collections
import struct
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WAD_PATH = ROOT / "Doom64-Retribution" / "D64RTR[v1.5].WAD"
BM_PATH = ROOT / "Doom64-Retribution" / "D64RTR_BRIGHTMAPS.PK3"
OUT_PATH = ROOT / "retribution-asset-inventory.md"

MAP_MEMBER = {
    "TEXTMAP",
    "THINGS",
    "LINEDEFS",
    "SIDEDEFS",
    "VERTEXES",
    "SEGS",
    "SSECTORS",
    "NODES",
    "SECTORS",
    "REJECT",
    "BLOCKMAP",
    "BEHAVIOR",
    "ZNODES",
    "DIALOGUE",
    "ENDMAP",
}

DEF_NAMES = {
    "MAPINFO",
    "ZMAPINFO",
    "GAMEINFO",
    "SNDINFO",
    "GLDEFS",
    "ANIMDEFS",
    "MODELDEF",
    "TEXTURES",
    "TERRAIN",
    "MENUDEF",
    "LANGUAGE",
    "LOCKDEFS",
    "DECALDEF",
    "FONTDEFS",
    "KEYCONF",
    "COMPATMAP",
    "XHAIRS",
    "VOXELDEF",
    "REVERBS",
    "SBARINFO",
    "TEAMINFO",
    "UMAPINFO",
    "DEHACKED",
    "LOADACS",
    "DECORATE",
    "ZSCRIPT",
}


def read_wad(path: Path):
    data = path.read_bytes()
    ident = data[0:4].decode("ascii", errors="replace")
    numlumps, diroffs = struct.unpack_from("<II", data, 4)
    lumps = []
    for i in range(numlumps):
        off, size, name = struct.unpack_from("<II8s", data, diroffs + i * 16)
        name = name.split(b"\0", 1)[0].decode("ascii", errors="replace")
        lumps.append((name, size, off))
    return ident, lumps


def between(names: list[str], start: str, end: str) -> list[str]:
    try:
        a = names.index(start)
        b = names.index(end)
        return names[a + 1 : b]
    except ValueError:
        return []


def is_map_marker(name: str, size: int) -> bool:
    if size != 0:
        return False
    if name.startswith("MAP") and len(name) <= 5:
        return True
    if len(name) == 4 and name[0] == "E" and name[2] == "M" and name[1].isdigit() and name[3].isdigit():
        return True
    return False


def collect_maps(lumps):
    maps = []
    i = 0
    while i < len(lumps):
        name, size, _ = lumps[i]
        if not is_map_marker(name, size):
            i += 1
            continue
        members = []
        j = i + 1
        while j < len(lumps):
            nn, ns, _ = lumps[j]
            if is_map_marker(nn, ns) and nn != name:
                break
            if nn in MAP_MEMBER:
                members.append(nn)
                j += 1
                if nn == "ENDMAP":
                    break
            else:
                break
        if "TEXTMAP" in members:
            fmt = "UDMF"
        elif "BEHAVIOR" in members:
            fmt = "Hexen/BEHAVIOR"
        else:
            fmt = "Doom/Boom"
        maps.append((name, fmt, members))
        i = j
    return maps


def main() -> None:
    ident, lumps = read_wad(WAD_PATH)
    names = [n for n, _, _ in lumps]

    maps = collect_maps(lumps)
    sprites = between(names, "S_START", "S_END") or between(names, "SS_START", "SS_END")
    flats = between(names, "F_START", "F_END") or between(names, "FF_START", "FF_END")
    patches = between(names, "P_START", "P_END") or between(names, "PP_START", "PP_END")
    tx = between(names, "TX_START", "TX_END")

    defs = []
    textures_defs = []
    sounds = []
    music = []
    other = []

    map_member_set = set(MAP_MEMBER) | {m[0] for m in maps}
    namespace_set = set(sprites) | set(flats) | set(patches) | set(tx)
    skip = namespace_set | map_member_set | {
        "S_START",
        "S_END",
        "SS_START",
        "SS_END",
        "F_START",
        "F_END",
        "FF_START",
        "FF_END",
        "P_START",
        "P_END",
        "PP_START",
        "PP_END",
        "TX_START",
        "TX_END",
    }

    for name, size, _ in lumps:
        upper = name.upper()
        if name in skip:
            continue
        if upper in DEF_NAMES or upper.startswith(
            ("GLDEFS", "ANIMDEFS", "DECORATE", "ZSCRIPT", "MAPINFO", "SNDINFO")
        ):
            defs.append(f"{name} ({size} bytes)")
        elif upper in ("TEXTURE1", "TEXTURE2", "PNAMES", "TEXTURES"):
            textures_defs.append(f"{name} ({size} bytes)")
        elif upper.startswith(("DS", "DP")) and size > 0:
            sounds.append(name)
        elif upper.startswith("D_") or upper.endswith("MUS"):
            music.append(name)
        elif size > 0:
            other.append((name, size))

    if tx:
        textures_defs.append(f"TX_ namespace: {len(tx)} textures")

    bm_files: list[str] = []
    if BM_PATH.exists():
        with zipfile.ZipFile(BM_PATH) as zf:
            bm_files = zf.namelist()

    tops: collections.Counter[str] = collections.Counter()
    for f in bm_files:
        tops[f.split("/")[0]] += 1

    lines = [
        "# Doom 64: Retribution — Asset Inventory",
        "",
        f"Source: `{WAD_PATH.name}` ({WAD_PATH.stat().st_size / 1e6:.1f} MB), "
        f"WAD ident `{ident}`, **{len(lumps)}** lumps",
        f"Brightmaps: `{BM_PATH.name}` ({len(bm_files)} files)",
        "",
        "## Maps",
        f"Count: **{len(maps)}**",
    ]
    for name, fmt, members in maps:
        lines.append(f"- {name} ({fmt}; lumps: {', '.join(members)})")

    lines += ["", "## Definition / script lumps"]
    for d in sorted(set(defs)):
        lines.append(f"- {d}")

    lines += ["", "## Texture systems"]
    for t in textures_defs:
        lines.append(f"- {t}")
    lines += [
        f"- Sprites (S_/SS_): **{len(sprites)}**",
        f"- Flats (F_/FF_): **{len(flats)}**",
        f"- Patches (P_/PP_): **{len(patches)}**",
    ]
    if tx:
        sample = ", ".join(tx[:15]) + ("..." if len(tx) > 15 else "")
        lines.append(f"- TX_ hi-res/override textures: **{len(tx)}** (sample: {sample})")

    lines += [
        "",
        "## Sounds / Music (counts)",
        f"- Sound lumps (DS*/DP*): **{len(sounds)}**",
        f"- Music-like: **{len(music)}**",
        "",
        "## Brightmaps PK3 structure",
    ]
    for k, v in tops.most_common(30):
        lines.append(f"- `{k}` — {v} entries")

    lines += ["", "## Notable other lumps (largest 80)"]
    for name, size in sorted(other, key=lambda x: x[1], reverse=True)[:80]:
        lines.append(f"- {name} ({size})")

    lines += [
        "",
        "## Load notes (from official instructions)",
        "- Load as `-file D64RTR[v1.5].WAD` on a Doom IWAD (e.g. DOOM2.WAD); not an IWAD itself as of v1.5",
        "- Optional: `D64RTR_BRIGHTMAPS.PK3`",
        "- Music: FluidSynth + `DOOMSND.SF2`",
        "",
        "## Phase 2 / RT relevance",
        "- Map format: mostly UDMF (`TEXTMAP`) — colored sector lighting should be present in UDMF fields",
        "- Check defs list for GLDEFS (dynamic lights), ZSCRIPT/DECORATE version needs, MODELDEF, ANIMDEFS",
        "- Brightmaps PK3 is separate; useful reference for emissive/glow surfaces when authoring RT materials",
        "",
    ]
    OUT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {OUT_PATH}")
    print(
        f"Maps={len(maps)} Sprites={len(sprites)} Flats={len(flats)} "
        f"Patches={len(patches)} TX={len(tx)} Defs={len(set(defs))} Other={len(other)}"
    )
    print("--- Defs ---")
    print("\n".join(sorted(set(defs))))


if __name__ == "__main__":
    main()
