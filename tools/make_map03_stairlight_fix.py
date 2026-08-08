"""
Build d64r-map03-stairlight.wad: kill the phased-light chase on MAP03's twin stairs.

The room at y ~ -620..-1140 has two mirrored staircases, one on each side. Each
step is a single sector used on BOTH sides (sector 35 spans x -352..-224 and
x 224..352, and so on), so the two stairs are lit as one chain. The steps carry
alternating LightSequenceSpecial1/2 (3/4), anchored by a LightSequenceStart (2)
dummy sector, which makes GZDoom spawn a DPhased chain: each sector ramps from
its base lightlevel (180) up to 255 and back, one after the next, forever.

Nothing in the room casts that light -- there is no ceiling fixture over the
stairs. Under RT the wave is doubly wrong: rt_sector_emis turns lightlevel into
surface emission (minlight 160, and these sit at 180), so the steps themselves
glow and pulse with no source. Clearing the special leaves every step at its
base 180 -- steady, and the same brightness it already has between waves.

Only the stair chain is touched. MAP03 has two other sequence chains -- the
SFLATAQ corridor (sectors 72-114, start 84) and the SDFLTA room (131-158,
start 150) -- and both are left running.

  python tools/make_map03_stairlight_fix.py

Load it after the map wad; see tools/launch-retribution-rt.cmd (STAIR).
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

MAPNAME = "MAP03"
OUTWAD = OUT / "d64r-map03-stairlight.wad"

# sector index -> the special it must currently carry, as a check that this is
# still the map we surveyed. 2 = LightSequenceStart, 3/4 = the alternating chain.
STAIR_SECTORS = {
    156: 2,
    34: 4,
    35: 3,
    36: 4,
    37: 3,
    38: 4,
    39: 3,
    40: 4,
    41: 3,
    42: 3,
}


def clear_stair_specials(text: str) -> tuple[str, int]:
    index = -1
    cleared = 0

    def scrub(m: re.Match[str]) -> str:
        nonlocal index, cleared
        index += 1
        want = STAIR_SECTORS.get(index)
        if want is None:
            return m.group(0)
        body = m.group(1)
        found = re.search(r"special\s*=\s*(\d+)\s*;", body)
        got = int(found.group(1)) if found else 0
        if got != want:
            raise SystemExit(
                f"sector {index}: expected special {want}, found {got} — "
                f"map data changed, refusing to patch blind"
            )
        cleared += 1
        return "sector\n{" + re.sub(r"(?m)^\s*special\s*=\s*\d+;\s*\n", "", body) + "}"

    out = re.sub(r"(?ms)^sector\s*\{(.*?)\}", scrub, text)
    return out, cleared


def main() -> None:
    lumps = read_wad_lumps(WAD)
    start, end = map_lump_range(lumps, MAPNAME)
    members = {nm.upper(): blob for nm, blob in lumps[start:end]}
    if "TEXTMAP" not in members or "BEHAVIOR" not in members:
        raise SystemExit(f"{MAPNAME}: missing TEXTMAP/BEHAVIOR in {WAD}")

    fixed, n = clear_stair_specials(decode_textmap(members["TEXTMAP"]))
    if n != len(STAIR_SECTORS):
        raise SystemExit(f"cleared {n} of {len(STAIR_SECTORS)} stair sectors")

    items: list[tuple[str, bytes]] = [(MAPNAME, b"")]
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

    write_wad(OUTWAD, items)
    print(f"wrote {OUTWAD} cleared={n} lumps={[nm for nm, _ in items]}")


if __name__ == "__main__":
    main()
