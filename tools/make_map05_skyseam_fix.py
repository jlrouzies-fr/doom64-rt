"""Build d64r-map05-skyseam-fix.wad: blank the ISUCK top texture on MAP05's
world-edge seam, sectors 321/311.

Reported 2026-08-21 (screen/map5NotCulledWall.png, map5unculledWall.png,
downTheWallMap5.png): a wall appears to occlude the moon from a spot in MAP05's
open-sky canyon area, angle-dependent, not fixed by rt_cpu_nocullradius at any
value, and *worse* (not better) under rt_cpu_cullmode 1 -- ruling out every
selection/culling heuristic as the cause (see the session's own investigation
in the commit log around this date). whatsthat, aimed precisely by flying to
the spot, resolved it to sector 321's TOP texture on 5 linedefs (1744, 1745,
1746, 1802, 1803), all bordering sector 311.

Sector 311 is a zero-height void sector (heightfloor == heightceiling == 200):
the classic Doom "edge of the map" boundary, never meant to be seen. Both 321
and 311 have an F_SKY1 ceiling, and the mapper assigned the map's own sky
texture (ISUCK -- every MAPINFO's `sky1`, see tools/gen_d64_skies.py) to that
boundary rather than leaving it blank, presumably because the ISUCK graphic
itself was expected to blend with the sky behind it under the original
renderer. It does not blend under this project's RT sky (a dynamic dome +
moon disc + directional light, not a static graphic) -- so wherever a sightline
actually reaches that boundary, real geometry sits between the camera and the
sky, and occludes it.

hw_walls.cpp already has the correct handling for this exact configuration --
matching F_SKY1 on both sides with a MISSING top texture skips drawing the
wall entirely and lets the already-rendered sky show through, no clipping.
That branch never fires here because ISUCK is a REAL, valid texture, not a
missing one. Blanking it (not deleting the linedef -- sectors need a bounding
line even where it is invisible) reactivates that existing, already-correct
code path. This does not patch whatever lets a sightline reach this boundary
in the first place; it removes the wrongly-visible object so there is nothing
there for that sightline to hit.

Reads MAP05 from d64r-seqlight-fix.wad, not the stock D64RTR_v15.WAD --
seqlight-fix already carries this map's other live fixes and loads before this
one in the launcher's file list, so this wad must be self-contained with
everything seqlight-fix did, plus this one edit, to actually win.

  python tools/make_map05_skyseam_fix.py             # build + verify
  python tools/make_map05_skyseam_fix.py --dry-run    # report only
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from make_map_3dfloor_rtfix import (
    ROOT,
    decode_textmap,
    map_lump_range,
    read_wad_lumps,
    write_wad,
)

SRC = ROOT / r"Doom64-Retribution\d64r-seqlight-fix.wad"
OUTWAD = ROOT / r"Doom64-Retribution\d64r-map05-skyseam-fix.wad"
MAPNAME = "MAP05"

# Sidedef index -> (expected sector, expected texturetop). Front sidedefs of
# linedefs 1744, 1745, 1746, 1802, 1803 -- all sector 321, all bordering the
# void sector 311. Indices, not linedef numbers, because the texture lives on
# the sidedef in UDMF.
WANTED = {
    2465: ("321", "ISUCK"),
    2467: ("321", "ISUCK"),
    2469: ("321", "ISUCK"),
    2565: ("321", "ISUCK"),
    2567: ("321", "ISUCK"),
}


def blank_skyseam(text: str) -> tuple[str, int]:
    index = -1
    patched = 0

    def scrub(m: re.Match[str]) -> str:
        nonlocal index, patched
        index += 1
        if index not in WANTED:
            return m.group(0)
        body = m.group(1)
        want_sector, want_tex = WANTED[index]
        got_sector = re.search(r'sector\s*=\s*(\d+)\s*;', body)
        got_tex = re.search(r'texturetop\s*=\s*"([^"]*)"\s*;', body)
        if not got_sector or got_sector.group(1) != want_sector:
            raise SystemExit(
                f"sidedef {index}: expected sector {want_sector}, found "
                f"{got_sector.group(1) if got_sector else None} -- map data "
                f"changed, refusing to patch blind."
            )
        if not got_tex or got_tex.group(1) != want_tex:
            raise SystemExit(
                f"sidedef {index}: expected texturetop \"{want_tex}\", found "
                f"{got_tex.group(1) if got_tex else None} -- map data changed, "
                f"refusing to patch blind."
            )
        patched += 1
        new_body = re.sub(r'(?m)^\s*texturetop\s*=\s*"[^"]*";\s*\n', "", body)
        return "sidedef\n{" + new_body + "}"

    return re.sub(r"(?ms)^sidedef\s*\{(.*?)\}", scrub, text), patched


def main() -> None:
    dry = "--dry-run" in sys.argv
    if not SRC.exists():
        raise SystemExit(f"missing {SRC} -- build it with tools/make_seqlight_fix.py first")

    lumps = read_wad_lumps(SRC)
    start, end = map_lump_range(lumps, MAPNAME)
    members = {nm.upper(): blob for nm, blob in lumps[start:end]}
    if "TEXTMAP" not in members:
        raise SystemExit(f"{MAPNAME}: no TEXTMAP in {SRC.name}")

    text = decode_textmap(members["TEXTMAP"])
    fixed, n = blank_skyseam(text)
    print(f"{MAPNAME}: blanked ISUCK top texture on {n}/{len(WANTED)} sidedef(s)")
    if n != len(WANTED):
        raise SystemExit("did not patch every expected sidedef -- see above")

    if dry:
        return

    out_items: list[tuple[str, bytes]] = [(MAPNAME, b"")]
    for nm, blob in lumps[start + 1 : end]:
        upper = nm.upper()
        if upper == "TEXTMAP":
            out_items.append((nm, fixed.encode("utf-8")))
        else:
            out_items.append((nm, blob))
    if out_items[-1][0].upper() != "ENDMAP":
        out_items.append(("ENDMAP", b""))

    write_wad(OUTWAD, out_items)
    print(f"wrote {OUTWAD}  lumps={[n for n, _ in out_items]}")


if __name__ == "__main__":
    main()
