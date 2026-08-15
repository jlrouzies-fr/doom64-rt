"""
Survey every Retribution map for PAINTED light shafts.

The fourth family of sourceless light, and the first one that never animates --
which is why `scan_light_specials.py` cannot see it. There is no special, no ACS
call, and nothing moves. The map author simply carved wedge-shaped sectors out
of a room's floorplan, gave them a *higher lightlevel* than the room they sit
in, and left every other property identical: same floor height, same ceiling
height, same floor flat, same ceiling flat. In the software renderer that reads
as sunlight slanting in through a window. It is the Doom 64 equivalent of
painting the light onto the floor.

Under RT it stops being paint. `rt_sector_emis` turns any sector at or above the
per-map threshold into a *surface emitter*, so a wedge at lightlevel 255 in a
room at 170 does not merely look brighter -- it radiates, casts its own GI, and
lights the pillars around it, with nothing anywhere in the world casting it.
MAP13's west hall is the reported case (`screen/level13fakeoutside light
streaks.png`): bands across both floor and ceiling, reading as moonlight from a
window, with no moon.

The signature this looks for is exactly that "identical but brighter" relation:

    sector S touches sector N through a two-sided line
    S.lightlevel - N.lightlevel >= --delta
    S.heightfloor   == N.heightfloor
    S.heightceiling == N.heightceiling
    S.texturefloor    == N.texturefloor
    S.textureceiling  == N.textureceiling
    S has no special

A real fixture almost never looks like this: a lamp recess changes the ceiling
height, a light panel changes the flat, a glowing pool changes the floor. When
*nothing* changes but the number, the brightness is not describing anything
that is there.

The RT column is the same one `scan_light_specials.py` computes -- a wedge only
matters if it clears max(rt_sector_emis_minlight, map median + margin). A wedge
that stays below it is merely shaded, and left alone.

  python tools/scan_fake_lightshafts.py             # every map, one line each
  python tools/scan_fake_lightshafts.py 13          # only MAP13, with detail
  python tools/scan_fake_lightshafts.py 13 --all    # include sub-threshold wedges
"""

from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from make_map_3dfloor_rtfix import (
    WAD,
    decode_textmap,
    list_map_names,
    map_lump_range,
    read_wad_lumps,
)
from scan_light_specials import MapData, emis_threshold

# How much brighter than its neighbour a sector has to be before the difference
# reads as painted light rather than as ordinary shading variation. Doom maps
# nudge lightlevel by 8-32 all the time to break up flat surfaces; the painted
# shafts are far coarser than that -- MAP13's wedges are 255 against 170.
DEFAULT_DELTA = 48

SKY_FLATS = {"F_SKY1", "F_SKY001", "SKY1"}


def geometry_matches(a: dict[str, str], b: dict[str, str]) -> bool:
    """True when two sectors differ in nothing that a light could be attached to."""
    keys = ("heightfloor", "heightceiling", "texturefloor", "textureceiling")
    return all(a.get(k, "0") == b.get(k, "0") for k in keys)


def find_shafts(m: MapData, delta: int) -> dict[int, list[int]]:
    """bright sector -> the darker, otherwise-identical sectors it sits inside."""
    out: dict[int, list[int]] = {}
    for i, sec in enumerate(m.sectors):
        if m.special(i) != 0:
            continue  # animated: that is scan_light_specials.py's problem, not ours
        if sec.get("textureceiling", "").upper().strip('"') in SKY_FLATS:
            continue  # open to the sky: bright is what it is supposed to be, and
            # the sky is a real RT light, so this one is not sourceless at all
        hosts = [
            n
            for n in sorted(m.adj[i])
            if m.light(i) - m.light(n) >= delta and geometry_matches(sec, m.sectors[n])
        ]
        if hosts:
            out[i] = hosts
    return out


def nearest_sky(m: MapData, i: int) -> tuple[int, float] | None:
    """Closest sector with a sky ceiling, and how far its centre is.

    A painted shaft is usually painted *from* somewhere -- MAP13's wedges fan out
    of two real F_SKY1 window slots in the west wall. That matters for the repair:
    where a genuine aperture exists, the light can be given back for real (a
    directional moon through the window) instead of merely deleted.
    """
    cx, cy = m.center(i)
    if cx != cx:
        return None
    best = None
    for j, sec in enumerate(m.sectors):
        if sec.get("textureceiling", "").upper().strip('"') not in SKY_FLATS:
            continue
        jx, jy = m.center(j)
        if jx != jx:
            continue
        d = ((jx - cx) ** 2 + (jy - cy) ** 2) ** 0.5
        if best is None or d < best[1]:
            best = (j, d)
    return best


def scan(mapname: str, text: str, delta: int, detail: bool, show_all: bool) -> int:
    m = MapData(text)
    thr = emis_threshold([m.light(i) for i in range(len(m.sectors))])
    shafts = find_shafts(m, delta)
    emitting = {i: h for i, h in shafts.items() if m.light(i) >= thr}
    shown = shafts if show_all else emitting
    if not shown:
        return 0

    print(
        f"{mapname}  sectors={len(m.sectors):4d}  thr={thr:.0f}  "
        f"painted={len(shafts):3d}  emitting={len(emitting):3d}"
    )
    if not detail:
        return len(emitting)

    for i in sorted(shown):
        hosts = shown[i]
        cx, cy = m.center(i)
        xs = [p[0] for p in m.pts[i]]
        ys = [p[1] for p in m.pts[i]]
        sky = nearest_sky(m, i)
        skytxt = f"  sky sec {sky[0]} at {sky[1]:.0f}u" if sky else "  no sky in map"
        print(
            f"      sec {i:4d} L{m.light(i):3d} vs "
            f"{', '.join(f'{h}(L{m.light(h)})' for h in hosts)}"
            f"  {'EMITS' if m.light(i) >= thr else 'shaded only'}"
            f"  area=({min(xs):.0f}..{max(xs):.0f}, {min(ys):.0f}..{max(ys):.0f})"
            f"  centre=({cx:.0f}, {cy:.0f}){skytxt}"
        )
    return len(emitting)


def main() -> None:
    argv = sys.argv[1:]
    show_all = "--all" in argv
    delta = DEFAULT_DELTA
    for a in argv:
        if a.startswith("--delta="):
            delta = int(a.split("=", 1)[1])
    args = [a for a in argv if not a.startswith("--")]

    lumps = read_wad_lumps(WAD)
    names = list_map_names(lumps)
    if args:
        wanted = {f"MAP{int(a):02d}" for a in args}
        names = [n for n in names if n in wanted]
    detail = bool(args)

    total = 0
    for name in names:
        start, end = map_lump_range(lumps, name)
        members = {nm.upper(): blob for nm, blob in lumps[start:end]}
        if "TEXTMAP" not in members:
            continue
        total += scan(name, decode_textmap(members["TEXTMAP"]), delta, detail, show_all)
    print(f"\nTOTAL emitting painted shafts={total} (delta>={delta})")


if __name__ == "__main__":
    main()
