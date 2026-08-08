"""
Build d64r-seqlight-fix.wad: strip chosen LightSequence chains from Retribution.

A LightSequenceStart (special 2) sector anchors a chain of alternating
LightSequenceSpecial1/2 (3/4) sectors. GZDoom walks it once at map load
(DPhased::PhaseHelper) and spawns a thinker per sector, each ramping from its
base lightlevel to 255 and back, offset by phase -- so a wave of light travels
along the chain forever, with nothing in the world casting it.

Under RT that is worse than in the original renderer: rt_sector_emis turns
sector lightlevel into surface emission for any sector at or above
rt_sector_emis_minlight (160 in the launcher), so an animated sector at or
above 160 IS the light source. The wave becomes a pulsing sourceless glow.
Below 160 the special only shades the surface and reads far less wrong.

Clearing the special leaves each sector at its base lightlevel -- the value it
already shows between waves -- so nothing gets darker.

Only chains with enabled=True are stripped. The whole survey is listed here so
the rejected ones stay visible; see docs/sequence-light-chains.md for what each
one looks like in game and why it is or is not on.

  python tools/make_seqlight_fix.py           # build the wad
  python tools/make_seqlight_fix.py --list    # show the table, build nothing

Chain membership comes from tools/scan_light_specials.py, which mirrors
PhaseHelper's walk. Re-run it after any map data change:

  python tools/scan_light_specials.py 3 12 --chains
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from make_map_3dfloor_rtfix import (
    OUT,
    WAD,
    decode_textmap,
    map_lump_range,
    read_wad_lumps,
    write_wad,
)

OUTWAD = OUT / "d64r-seqlight-fix.wad"


class Chain:
    def __init__(self, mapname: str, start: int, sectors: list[int],
                 enabled: bool, note: str):
        self.mapname = mapname
        self.start = start
        self.sectors = sectors  # start sector first, then the walk
        self.enabled = enabled
        self.note = note


CHAINS = [
    Chain(
        "MAP03", 156, [156, 42, 34, 35, 36, 37, 38, 39, 40, 41],
        enabled=True,
        note="Twin staircases, y -620..-1140. Each step is ONE sector spanning "
             "both sides (s35 is x -352..-224 and x 224..352), so both stairs "
             "pulse in lockstep. Base 180, above the emission threshold, and no "
             "fixture anywhere in the room. Reported and confirmed in game.",
    ),
    Chain(
        "MAP03", 84,
        [84, 72, 75, 76, 77, 78, 79, 80, 81, 82, 83, 87, 88, 89, 90, 91, 92, 93,
         94, 95, 96, 97, 98, 99, 100, 101, 102, 103, 104, 105, 106, 107, 108,
         109, 110, 111, 112, 113, 114],
        enabled=False,
        note="PENDING PLAYTEST. 39 sectors, SFLATAQ, base 180 -> all emitting. "
             "Corridor from y -1664 that opens into a wide hall (x +/-416). "
             "Same defect class as the stairs, same map.",
    ),
    Chain(
        "MAP03", 150,
        [150, 131, 140, 141, 142, 143, 144, 145, 146, 147, 148, 149, 157, 158],
        enabled=False,
        note="PENDING PLAYTEST. 14 sectors, SDFLTA room around (-700,-2450), "
             "base 150 -- BELOW rt_sector_emis_minlight 160, so RT never makes "
             "these a source. The pulse only shades. Lowest priority.",
    ),
    Chain(
        "MAP12", 196,
        [196, 199, 214, 212, 182, 192, 184, 185, 190, 189, 188, 187, 205, 210,
         203, 194, 201, 180, 216, 218],
        enabled=False,
        note="PENDING PLAYTEST. 20 wedge sectors nested concentrically around "
             "(-1340,-930), CASFL27/CASF80, base 160 -- exactly on the emission "
             "threshold. The layout reads like a deliberate rotating beacon, so "
             "this one may be worth keeping.",
    ),
]


def clear_specials(text: str, wanted: dict[int, None], mapname: str) -> tuple[str, int]:
    index = -1
    cleared = 0

    def scrub(m: re.Match[str]) -> str:
        nonlocal index, cleared
        index += 1
        if index not in wanted:
            return m.group(0)
        body = m.group(1)
        found = re.search(r"special\s*=\s*(\d+)\s*;", body)
        got = int(found.group(1)) if found else 0
        if got not in (2, 3, 4):
            raise SystemExit(
                f"{mapname} sector {index}: expected a LightSequence special "
                f"(2/3/4), found {got} — map data changed, refusing to patch "
                f"blind. Re-run tools/scan_light_specials.py --chains."
            )
        cleared += 1
        return "sector\n{" + re.sub(r"(?m)^\s*special\s*=\s*\d+;\s*\n", "", body) + "}"

    return re.sub(r"(?ms)^sector\s*\{(.*?)\}", scrub, text), cleared


def show_table() -> None:
    for c in CHAINS:
        state = "STRIP" if c.enabled else "keep "
        print(f"[{state}] {c.mapname} start={c.start:4d} sectors={len(c.sectors):3d}")
        print(f"          {c.note}")


def main() -> None:
    if "--list" in sys.argv:
        show_table()
        return

    active = [c for c in CHAINS if c.enabled]
    if not active:
        raise SystemExit("no chains enabled — nothing to build")

    by_map: dict[str, list[Chain]] = {}
    for c in active:
        by_map.setdefault(c.mapname, []).append(c)

    lumps = read_wad_lumps(WAD)
    items: list[tuple[str, bytes]] = []
    for mapname, chains in by_map.items():
        start, end = map_lump_range(lumps, mapname)
        members = {nm.upper(): blob for nm, blob in lumps[start:end]}
        if "TEXTMAP" not in members or "BEHAVIOR" not in members:
            raise SystemExit(f"{mapname}: missing TEXTMAP/BEHAVIOR in {WAD}")

        wanted = {i: None for c in chains for i in c.sectors}
        fixed, n = clear_specials(decode_textmap(members["TEXTMAP"]), wanted, mapname)
        if n != len(wanted):
            raise SystemExit(f"{mapname}: cleared {n} of {len(wanted)} sectors")

        items.append((mapname, b""))
        for nm, blob in lumps[start + 1 : end]:
            upper = nm.upper()
            if upper == "TEXTMAP":
                items.append((nm, fixed.encode("utf-8")))
            elif upper == "SCRIPTS":
                continue  # ACS source; BEHAVIOR is the compiled lump and is kept
            else:
                items.append((nm, blob))
        if items[-1][0].upper() != "ENDMAP":
            items.append(("ENDMAP", b""))
        print(f"{mapname}: cleared {n} sectors "
              f"({', '.join(f'chain {c.start}' for c in chains)})")

    write_wad(OUTWAD, items)
    print(f"wrote {OUTWAD} maps={len(by_map)} lumps={[nm for nm, _ in items]}")


if __name__ == "__main__":
    main()
