"""
Measure Retribution's SKY-HACK WALL GAPS -- the steps Doom leaves open on purpose.

What this measures, exactly
---------------------------
A two-sided line whose sectors BOTH have an F_SKY1 ceiling, at different heights.
GZDoom's HWWall::SkyTop (hw_sky.cpp) handles that case specially: it does not
draw the upper texture, it draws a *sky wall* spanning from the lower ceiling up
to z=32768. The step between the two ceilings is deliberately left open, because
in a raster renderer you are looking at sky on both sides and nobody can tell.

Under RT you can tell. That sky wall is handed to RTGL1 as
RG_MESH_PRIMITIVE_SKY_VISIBILITY, lands in the BLAS with
INSTANCE_CUSTOM_INDEX_FLAG_SKY, and every ray that hits it returns sky radiance.
It is a light-emitting surface standing in a wall. Where the solid world around
it does not occlude cleanly -- and in a hand-built 1997 map it often does not --
light gets into rooms that look sealed.

The column that matters is GAP: the ceiling step, in map units, that the sky wall
is covering. That is the quantity `rt_sky_wallgap` compares against, so this tool
is how you choose a value for it. Everything at or below the threshold stops
being a sky wall and is left to the normal upper texture.

What this does NOT measure
--------------------------
Anything else that can leak sky. A room whose own ceiling is mistakenly F_SKY1,
a missing upper texture on an ordinary line, a hairline crack at a T-junction --
none of those are visible here, and the first two are indistinguishable from
deliberate design in the map data alone. There is no clean static predicate for
"this opening was not meant to be there", so this tool deliberately reports only
the one case where the map format says outright that a gap was left open.

  python tools/scan_sky_apertures.py            # every map, one line each
  python tools/scan_sky_apertures.py 1 13       # detail for those maps
  python tools/scan_sky_apertures.py --hist     # gap-size histogram, whole game
"""

from __future__ import annotations

import math
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from make_map_3dfloor_rtfix import (
    WAD,
    decode_textmap,
    list_map_names,
    map_lump_range,
    read_wad_lumps,
)
from scan_light_specials import fields

SKY_FLATS = {"F_SKY1", "F_SKY001", "SKY1"}


class Geom:
    def __init__(self, text: str):
        self.sectors = [fields(b) for b in _blocks(text, "sector")]
        self.verts = [
            (float(d.get("x", 0)), float(d.get("y", 0)))
            for d in (fields(b) for b in _blocks(text, "vertex"))
        ]
        self.sides = [fields(b) for b in _blocks(text, "sidedef")]
        self.lines = [fields(b) for b in _blocks(text, "linedef")]

    def sky(self, sec: int) -> bool:
        return self.sectors[sec].get("textureceiling", "").strip('"').upper() in SKY_FLATS

    def ceil(self, sec: int) -> float:
        return float(self.sectors[sec].get("heightceiling", 0))


def _blocks(text: str, kind: str) -> list[str]:
    return re.findall(r"(?ms)^" + kind + r"\s*\{(.*?)\}", text)


def gaps(g: Geom) -> list[dict]:
    """Every sky-hack step: both sectors sky, ceilings at different heights."""
    out = []
    for ln in g.lines:
        if "sidefront" not in ln or "sideback" not in ln:
            continue  # one-sided line: solid, no upper to leave open
        # ML_NOSKYWALLS = 0x1000. The map can already suppress the sky wall on a
        # line by hand, and SkyTop honours it before anything else -- so a line
        # carrying it is not a gap and must not be counted as one.
        if int(ln.get("flags", 0) or 0) & 0x1000:
            continue
        fs = int(g.sides[int(ln["sidefront"])].get("sector", 0))
        bs = int(g.sides[int(ln["sideback"])].get("sector", 0))
        if fs == bs or not (g.sky(fs) and g.sky(bs)):
            continue
        gap = abs(g.ceil(fs) - g.ceil(bs))
        if gap <= 0:
            continue
        v1, v2 = g.verts[int(ln["v1"])], g.verts[int(ln["v2"])]
        out.append({
            "gap": gap,
            "length": math.hypot(v2[0] - v1[0], v2[1] - v1[1]),
            "at": ((v1[0] + v2[0]) / 2, (v1[1] + v2[1]) / 2),
            "sectors": (fs, bs),
        })
    return out


def scan(mapname: str, text: str, detail: bool, hist: Counter | None) -> int:
    g = Geom(text)
    gg = gaps(g)
    if hist is not None:
        for a in gg:
            hist[int(a["gap"])] += 1
    if not gg:
        return 0

    sizes = sorted(a["gap"] for a in gg)
    print(
        f"{mapname}  sky-hack gaps={len(gg):4d}  "
        f"gap units: min {sizes[0]:.0f} / med {sizes[len(sizes)//2]:.0f} / "
        f"max {sizes[-1]:.0f}   <=32: {sum(1 for s in sizes if s <= 32):3d}  "
        f"<=64: {sum(1 for s in sizes if s <= 64):3d}"
    )
    if detail:
        for a in sorted(gg, key=lambda a: a["gap"]):
            print(f"      gap {a['gap']:6.0f} x len {a['length']:7.0f}  "
                  f"at ({a['at'][0]:.0f}, {a['at'][1]:.0f})  sectors {a['sectors']}")
    return len(gg)


def main() -> None:
    argv = sys.argv[1:]
    want_hist = "--hist" in argv
    args = [a for a in argv if not a.startswith("--")]

    lumps = read_wad_lumps(WAD)
    names = list_map_names(lumps)
    if args:
        wanted = {f"MAP{int(a):02d}" for a in args}
        names = [n for n in names if n in wanted]
    detail = bool(args)
    hist: Counter | None = Counter() if want_hist else None

    n = 0
    for name in names:
        start, end = map_lump_range(lumps, name)
        members = {nm.upper(): blob for nm, blob in lumps[start:end]}
        if "TEXTMAP" not in members:
            continue
        n += scan(name, decode_textmap(members["TEXTMAP"]), detail, hist)

    print(f"\nTOTAL sky-hack gaps={n}")
    if hist:
        print("\ngap size histogram (what rt_sky_wallgap would close):")
        run = 0
        for size in sorted(hist):
            run += hist[size]
            print(f"  {size:5d} units  x{hist[size]:4d}   "
                  f"cumulative {run:4d} ({100.0 * run / n:5.1f}% closed at "
                  f"rt_sky_wallgap {size})")


if __name__ == "__main__":
    main()
