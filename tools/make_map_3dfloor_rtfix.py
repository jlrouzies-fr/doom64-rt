"""
Build RT hang fixes: strip Sector_Set3dFloor (linedef special 160).

Same root cause as MAP01 (compat-patches.md): 3D floors hang RT live upload.
Keeps original BEHAVIOR + ZNODES so ACS still runs.

Default: scan all MAPxx in D64RTR_v15.WAD, write one combined PWAD
  Doom64-Retribution/d64r-3dfloor-rtfix.wad
plus per-map copies d64r-mapNN-rtfix.wad for maps that had 160s.

  python tools/make_map_3dfloor_rtfix.py           # all maps → combined
  python tools/make_map_3dfloor_rtfix.py 2         # MAP02 only
  python tools/make_map_3dfloor_rtfix.py --all     # same as default
"""
from __future__ import annotations

import re
import struct
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WAD = ROOT / r"Doom64-Retribution\D64RTR_v15.WAD"
OUT = ROOT / "Doom64-Retribution"
COMBINED = OUT / "d64r-3dfloor-rtfix.wad"


def read_wad_lumps(path: Path) -> list[tuple[str, bytes]]:
    data = path.read_bytes()
    _kind, n, o = struct.unpack_from("<4sII", data, 0)
    lumps: list[tuple[str, bytes]] = []
    for i in range(n):
        off, sz, raw = struct.unpack_from("<II8s", data, o + i * 16)
        name = raw.split(b"\0")[0].decode("ascii", "replace")
        lumps.append((name, data[off : off + sz]))
    return lumps


def write_wad(path: Path, items: list[tuple[str, bytes]]) -> None:
    body = b""
    directory = b""
    offset = 12
    for name, blob in items:
        directory += struct.pack(
            "<II8s", offset, len(blob), name.encode("ascii")[:8].ljust(8, b"\0")
        )
        body += blob
        offset += len(blob)
    path.write_bytes(
        struct.pack("<4sII", b"PWAD", len(items), 12 + len(body)) + body + directory
    )


def is_map_marker(lumps: list[tuple[str, bytes]], i: int) -> bool:
    """A map marker is a zero-length lump whose next lump starts the map body.

    Name-matching on ``MAP\\d\\d`` is what left the five extra campaigns
    unprotected: Retribution's own levels are ``RTR01``, and the Absolution /
    Outcast / Redemption / Reckoning / bonus sets are ``ABS01``, ``OUT01``,
    ``RDM01``, ``REC01``, ``FUN00``. Those maps kept their 3D floors and froze
    on entry exactly like MAP01 used to.
    """
    if i + 1 >= len(lumps):
        return False
    if lumps[i][1]:
        return False
    return lumps[i + 1][0].upper() in ("TEXTMAP", "THINGS")


def map_lump_range(lumps: list[tuple[str, bytes]], mapname: str) -> tuple[int, int]:
    start = next(i for i, (nm, _) in enumerate(lumps) if nm.upper() == mapname.upper())
    end = start + 1
    while end < len(lumps):
        nm = lumps[end][0].upper()
        if is_map_marker(lumps, end) and nm != mapname.upper():
            break
        if nm == "ENDMAP":
            end += 1
            break
        end += 1
    return start, end


def list_map_names(lumps: list[tuple[str, bytes]]) -> list[str]:
    return [
        nm.upper() for i, (nm, _) in enumerate(lumps) if is_map_marker(lumps, i)
    ]


def decode_textmap(blob: bytes) -> str:
    if blob[:2] in (b"\x78\x9c", b"\x78\xda"):
        blob = zlib.decompress(blob)
    return blob.decode("utf-8", "replace")


def strip_3dfloor(text: str) -> tuple[str, int]:
    count = 0

    def scrub(m: re.Match[str]) -> str:
        nonlocal count
        body = m.group(1)
        if not re.search(r"special\s*=\s*160\s*;", body):
            return m.group(0)
        count += 1
        body = re.sub(r"(?m)^\s*special\s*=\s*\d+;\s*\n", "", body)
        body = re.sub(r"(?m)^\s*arg\d+\s*=\s*-?\d+;\s*\n", "", body)
        return "linedef\n{" + body + "}"

    out = re.sub(r"(?ms)^linedef\s*\{(.*?)\}", scrub, text)
    return out, count


def build_map_items(
    lumps: list[tuple[str, bytes]], mapname: str
) -> tuple[list[tuple[str, bytes]] | None, int]:
    start, end = map_lump_range(lumps, mapname)
    members = {nm.upper(): blob for nm, blob in lumps[start:end]}
    if "TEXTMAP" not in members:
        print(f"{mapname}: no TEXTMAP — skip")
        return None, 0
    if "BEHAVIOR" not in members:
        print(f"{mapname}: no BEHAVIOR — skip (ACS would break)")
        return None, 0

    text = decode_textmap(members["TEXTMAP"])
    fixed, n = strip_3dfloor(text)
    if n == 0:
        return None, 0

    out_items: list[tuple[str, bytes]] = [(mapname, b"")]
    for nm, blob in lumps[start + 1 : end]:
        upper = nm.upper()
        if upper == "TEXTMAP":
            out_items.append((nm, fixed.encode("utf-8")))
        elif upper == "SCRIPTS":
            continue
        else:
            out_items.append((nm, blob))
    if out_items[-1][0].upper() != "ENDMAP":
        out_items.append(("ENDMAP", b""))
    return out_items, n


def build_map(mapnum: int, lumps: list[tuple[str, bytes]] | None = None) -> Path | None:
    if lumps is None:
        lumps = read_wad_lumps(WAD)
    mapname = f"MAP{mapnum:02d}"
    items, n = build_map_items(lumps, mapname)
    if not items:
        print(f"{mapname}: no special=160 linedefs — skip")
        return None
    out = OUT / f"d64r-map{mapnum:02d}-rtfix.wad"
    write_wad(out, items)
    print(f"wrote {out} stripped_3dfloors={n} lumps={[n for n, _ in items]}")
    return out


def build_all() -> Path:
    lumps = read_wad_lumps(WAD)
    combined: list[tuple[str, bytes]] = []
    total = 0
    maps_fixed: list[str] = []
    for mapname in list_map_names(lumps):
        items, n = build_map_items(lumps, mapname)
        if not items:
            continue
        combined.extend(items)
        total += n
        maps_fixed.append(f"{mapname}({n})")
        # Keep per-map copy for debugging / selective load. Named off the map
        # lump, not a parsed number -- "FUN00" and "MAP00" would collide.
        per = OUT / f"d64r-{mapname.lower()}-rtfix.wad"
        write_wad(per, items)

    if not combined:
        raise SystemExit("no maps needed 3D-floor strip")

    write_wad(COMBINED, combined)
    print(f"wrote {COMBINED} maps={len(maps_fixed)} stripped_total={total}")
    print("  " + ", ".join(maps_fixed))
    return COMBINED


def main() -> None:
    args = sys.argv[1:]
    if not args or args == ["--all"]:
        build_all()
        return
    lumps = read_wad_lumps(WAD)
    for a in args:
        if a == "--all":
            build_all()
            return
        build_map(int(a), lumps)


if __name__ == "__main__":
    main()
