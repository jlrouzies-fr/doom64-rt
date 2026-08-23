"""
Sector_Set3dFloor (linedef special 160) handling for the Retribution map overlays.

HISTORY. From 2026-08-02 to 2026-08-23 this stripped every 3D floor in the game
(44 maps / 209 linedefs) because a single one on MAP01 froze the engine. The
freeze was never in the map data: gzdoom-rt clears a 3D-floor sector's lightlist
under RT and P_GetPlaneLight then read past the end of the empty array on the
render worker thread (p_3dfloors.cpp). That is fixed in the engine, and 166 of the
209 floors are the bridges and catwalks Nevander built the levels around --
stripping them made levels uncompletable. Default is now MODE "keep".

MODES (rewrite_3dfloor / --mode):
  keep   -- leave special 160 alone (default). Nothing to write; the script
            reports the census and writes no wad.
  strip  -- the old behaviour: delete `special` + `argN` on every 160 linedef.
            Emergency arm only, for an engine without the P_GetPlaneLight guard.

Other overlay builders (make_seqlight_fix.py, add_smonf_lights.py) import
rewrite_3dfloor so every map-replacing wad applies the SAME policy; a map in a
later-loading wad silently wins, so they must never disagree.

  python tools/make_map_3dfloor_rtfix.py                 # census (keep)
  python tools/make_map_3dfloor_rtfix.py --mode strip    # old combined wad
  python tools/make_map_3dfloor_rtfix.py --mode strip 2  # MAP02 only
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

    Name-matching on ``MAP\\d\\d`` is what left the extra campaigns out of the
    strip while it existed: the Absolution / Outcast / Redemption / bonus sets
    are ``ABS01``, ``OUT01``, ``RDM01``, ``FUN00`` (v15 has no ``REC*`` or
    ``RTR*`` maps). Structural detection also makes the census above complete.
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


# Policy shared by every overlay builder. "keep" or "strip"; see module docstring.
MODE3D = "keep"


def count_3dfloor(text: str) -> int:
    """Number of linedefs carrying special 160, untouched."""
    return sum(
        1
        for m in re.finditer(r"(?ms)^linedef\s*\{(.*?)\}", text)
        if re.search(r"special\s*=\s*160\s*;", m.group(1))
    )


def rewrite_3dfloor(text: str, mode: str | None = None) -> tuple[str, int]:
    """Apply the 3D-floor policy. Returns (text, linedefs_changed).

    mode "keep" returns the text unchanged with 0; "strip" is strip_3dfloor.
    """
    mode = MODE3D if mode is None else mode
    if mode == "keep":
        return text, 0
    if mode == "strip":
        return strip_3dfloor(text)
    raise ValueError(f"unknown 3D-floor mode {mode!r} (keep|strip)")


def strip_3dfloor(text: str) -> tuple[str, int]:
    """The old unconditional strip. Prefer rewrite_3dfloor(); this ignores MODE3D."""
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
    fixed, n = rewrite_3dfloor(text)
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


def census(lumps: list[tuple[str, bytes]]) -> dict[str, int]:
    """Map name -> number of special-160 linedefs, for every map in the IWAD."""
    out: dict[str, int] = {}
    for mapname in list_map_names(lumps):
        start, end = map_lump_range(lumps, mapname)
        members = {nm.upper(): blob for nm, blob in lumps[start:end]}
        if "TEXTMAP" in members:
            out[mapname] = count_3dfloor(decode_textmap(members["TEXTMAP"]))
    return out


def build_all() -> Path | None:
    lumps = read_wad_lumps(WAD)
    if MODE3D == "keep":
        c = {k: v for k, v in census(lumps).items() if v}
        print(f"3D-floor mode keep: nothing to write. {sum(c.values())} special-160 "
              f"linedefs on {len(c)} maps stay in the game.")
        print("  " + ", ".join(f"{k}({v})" for k, v in c.items()))
        if COMBINED.exists():
            print(f"NOTE: stale {COMBINED} still on disk; nothing loads it any more.")
        return None
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
    global MODE3D
    args = sys.argv[1:]
    if "--mode" in args:
        i = args.index("--mode")
        MODE3D = args[i + 1]
        del args[i : i + 2]
    if MODE3D not in ("keep", "strip"):
        raise SystemExit(f"--mode must be keep or strip, not {MODE3D!r}")
    if not args or args == ["--all"]:
        build_all()
        return
    if MODE3D == "keep":
        raise SystemExit("per-map wads only make sense with --mode strip")
    lumps = read_wad_lumps(WAD)
    for a in args:
        if a == "--all":
            build_all()
            return
        build_map(int(a), lumps)


if __name__ == "__main__":
    main()
