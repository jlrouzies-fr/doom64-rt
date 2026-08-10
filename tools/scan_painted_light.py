"""Survey a map for STATIC fake light: sectors lit by a number, not by a fixture.

The animated families have their own scanner (tools/scan_light_specials.py: sequence
chains, per-sector blinks, ACS Light_* calls). This one covers what is left, which is
the half that never moves and therefore never draws attention to itself:

  BRIGHTNESS  a sector whose lightlevel is above the map's rt_sector_emis threshold
              AND higher than every sector touching it. Under RT that surface emits,
              so it glows with nothing casting it. tools/scan_fake_lightshafts.py
              finds the SHAFT sub-case only -- it requires the sector to match its
              neighbour's flats, which a wall alcove or a door recess never does, so
              it misses most of them.

  COLOUR      a sector whose Doom 64 colormap differs sharply from every neighbour.
              Lightlevel is dropped and re-derived by RT, but colour is NOT --
              rt_sector_tint_albedo carries the sector hue into albedo at full
              strength on purpose -- so a warm patch inside a cold room lands as a
              hard-edged colour change across a continuous floor, with no gradient
              and nothing casting it.

Neither is a bug on its own. Doom 64 authors light by painting it, and most of the
painting is deliberate art direction. What makes an entry actionable is the third
column: IS THERE A FIXTURE? A real lamp cannot light a recess and leave the wall
beside it black, so an element painted brighter or warmer than its room with no
light-bearing thing near it is the defect this project keeps finding by screenshot.

The fixture test is derived from the mod, not guessed. GLDEFS `object <Actor>` blocks
say which actors carry lights; DECORATE says which of those are placeable and under
what editor number. That is 39 actors here -- torches, tech lamps, fires, candles --
plus the stock 9800..9804 light things.

Candidates are GROUPED by their distinguishing wall texture and target lightlevel, so
a fixture repeated eleven times reads as one row and gets one table entry, not eleven.

  python tools/scan_painted_light.py 13              # one map
  python tools/scan_painted_light.py                 # every map, summary only
  python tools/scan_painted_light.py 13 --entries    # + paste-ready table entries
  python tools/scan_painted_light.py 13 --delta 20   # widen the brightness test

Repairs go in tools/make_seqlight_fix.py -- SHAFTS for brightness, TINTS for colour.
Anything already listed there is marked [done] and excluded from the suggestions.
"""

from __future__ import annotations

import math
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from make_map_3dfloor_rtfix import WAD, decode_textmap, map_lump_range, read_wad_lumps

EMIS_MINLIGHT = 160.0
EMIS_MARGIN = 40.0

# Stock GZDoom dynamic-light things.
LIGHT_THINGS = {9800, 9801, 9802, 9803, 9804}

# A colour counts as "different from the room" at this max-channel distance.
COLOUR_DELTA = 60
# ...and the element has to be small relative to the room, or it IS the room.
AREA_RATIO = 0.35


def fields(body: str) -> dict[str, str]:
    return {k: v.strip() for k, v in re.findall(r"(\w+)\s*=\s*([^;]+);", body)}


def rgb(v: int) -> tuple[int, int, int]:
    v &= 0xFFFFFF
    return ((v >> 16) & 255, (v >> 8) & 255, v & 255)


def colour_dist(a: tuple[int, int, int], b: tuple[int, int, int]) -> int:
    return max(abs(x - y) for x, y in zip(a, b))


def lit_actor_editor_numbers(lumps) -> set[int]:
    """Editor numbers of actors that carry a GLDEFS light. Derived, never guessed."""
    gl = next((d.decode("latin-1") for n, d in lumps if n.upper() == "GLDEFS"), "")
    dec = next((d.decode("latin-1") for n, d in lumps if n.upper() == "DECORATE"), "")
    lit = {m.group(1).upper() for m in re.finditer(r"(?im)^\s*object\s+(\w+)\s*\{", gl)}
    out: set[int] = set()
    for m in re.finditer(
        r"(?im)^\s*actor\s+(\w+)\s*(?::\s*\w+\s*)?(?:replaces\s+\w+\s*)?(\d+)?", dec
    ):
        cls, num = m.group(1).upper(), m.group(2)
        if num and cls in lit:
            out.add(int(num))
    return out


class MapInfo:
    def __init__(self, text: str):
        self.sec = [fields(b) for b in re.findall(r"(?ms)^sector\s*\{(.*?)\}", text)]
        self.verts = [
            (float(d["x"]), float(d["y"]))
            for d in (fields(b) for b in re.findall(r"(?ms)^vertex\s*\{(.*?)\}", text))
        ]
        self.sides = [fields(b) for b in re.findall(r"(?ms)^sidedef\s*\{(.*?)\}", text)]
        self.things = [fields(b) for b in re.findall(r"(?ms)^thing\s*\{(.*?)\}", text)]
        self.adj: dict[int, set[int]] = defaultdict(set)
        self.pts: dict[int, list[tuple[float, float]]] = defaultdict(list)
        self.tex: dict[int, set[str]] = defaultdict(set)
        for b in re.findall(r"(?ms)^linedef\s*\{(.*?)\}", text):
            d = fields(b)
            touched = []
            for key in ("sidefront", "sideback"):
                if key not in d:
                    continue
                side = self.sides[int(d[key])]
                si = int(side.get("sector", -1))
                touched.append(si)
                self.pts[si].extend(
                    [self.verts[int(d["v1"])], self.verts[int(d["v2"])]]
                )
                for tk in ("texturetop", "texturemiddle", "texturebottom"):
                    v = side.get(tk, '"-"').strip('"')
                    if v != "-":
                        self.tex[si].add(v)
            if len(touched) == 2 and touched[0] != touched[1]:
                self.adj[touched[0]].add(touched[1])
                self.adj[touched[1]].add(touched[0])

    def light(self, i: int) -> int:
        return int(self.sec[i].get("lightlevel", "160"))

    def colour(self, i: int) -> tuple[int, int, int]:
        return rgb(int(self.sec[i].get("lightcolor", "16777215")))

    def bbox(self, i: int):
        p = self.pts.get(i, [])
        if not p:
            return None
        xs = [a for a, _ in p]
        ys = [b for _, b in p]
        return min(xs), min(ys), max(xs), max(ys)

    def area(self, i: int) -> float:
        b = self.bbox(i)
        return 0.0 if not b else max(1.0, (b[2] - b[0]) * (b[3] - b[1]))

    def centre(self, i: int):
        b = self.bbox(i)
        return None if not b else ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)

    def signature(self, i: int) -> str:
        """The texture that identifies this element: the rarest one on its sidedefs."""
        t = self.tex.get(i, set())
        if not t:
            f = self.sec[i].get("texturefloor", '"?"').strip('"')
            return f
        return sorted(t, key=lambda n: (self.texcount.get(n, 0), n))[0]


def already_handled(mapname: str):
    """Sectors this map's entries in make_seqlight_fix.py already repair."""
    try:
        import make_seqlight_fix as S
    except Exception:
        return set(), set()
    bright = {
        si
        for h in getattr(S, "SHAFTS", [])
        if h.enabled and h.mapname == mapname
        for si in h.sectors
    }
    tinted = {
        si
        for t in getattr(S, "TINTS", [])
        if t.enabled and t.mapname == mapname
        for si in t.sectors
    }
    return bright, tinted


def scan_map(lumps, mapname: str, delta: int, entries: bool, lit_nums: set[int]) -> int:
    start, end = map_lump_range(lumps, mapname)
    text = next(
        (decode_textmap(b) for n, b in lumps[start:end] if n.upper() == "TEXTMAP"), None
    )
    if text is None:
        return 0
    m = MapInfo(text)
    if not m.sec:
        return 0

    counts: dict[str, int] = defaultdict(int)
    for i in range(len(m.sec)):
        for t in m.tex.get(i, ()):
            counts[t] += 1
    m.texcount = counts

    levels = [m.light(i) for i in range(len(m.sec))]
    thr = max(EMIS_MINLIGHT, sorted(levels)[len(levels) // 2] + EMIS_MARGIN)

    fixtures = []
    for t in m.things:
        try:
            ty = int(t.get("type", "0"))
        except ValueError:
            continue
        if ty in LIGHT_THINGS or ty in lit_nums:
            fixtures.append((float(t.get("x", 0)), float(t.get("y", 0)), ty))

    def nearest_fixture(i: int):
        c = m.centre(i)
        if not c or not fixtures:
            return None
        return min((math.hypot(x - c[0], y - c[1]), ty) for x, y, ty in fixtures)

    done_bright, done_tint = already_handled(mapname)

    bright, tinted = [], []
    for i in range(len(m.sec)):
        nb = list(m.adj.get(i, ()))
        if not nb:
            continue
        hi_nb = max(m.light(n) for n in nb)
        if m.light(i) > thr and m.light(i) - hi_nb >= delta:
            bright.append((i, m.light(i), hi_nb))
        # Colour: differs from EVERY neighbour, and is small enough to be an element
        # inside a room rather than a room in its own right.
        mine = m.colour(i)
        if all(colour_dist(mine, m.colour(n)) >= COLOUR_DELTA for n in nb):
            big = max(m.area(n) for n in nb)
            if m.area(i) <= big * AREA_RATIO:
                tinted.append((i, mine, max(nb, key=lambda n: m.area(n))))

    if not bright and not tinted:
        return 0

    print(f"\n=== {mapname}   sectors={len(m.sec)}  emis threshold={thr:.0f}  "
          f"fixtures placed={len(fixtures)}")

    groups: dict[tuple, list] = defaultdict(list)
    for i, l, hi in bright:
        groups[(m.signature(i), hi)].append((i, l))

    if groups:
        print(f"\n  PAINTED BRIGHTNESS  (lightlevel > {thr:.0f} and >= {delta} over every neighbour)")
        print(f"    {'texture':10} {'->':>4} {'n':>3}  {'fixture':>16}  sectors")
        for (sig, to), members in sorted(groups.items(), key=lambda kv: -len(kv[1])):
            ids = [i for i, _ in members]
            nf = [nearest_fixture(i) for i in ids]
            nf = [x for x in nf if x]
            near = f"{min(x[0] for x in nf):.0f}u" if nf else "none on map"
            mark = " [done]" if set(ids) <= done_bright else ""
            print(f"    {sig:10} {to:4d} {len(ids):3d}  {near:>16}  "
                  f"{ids if len(ids) <= 12 else str(ids[:12]) + '...'}{mark}")

    if tinted:
        print(f"\n  PAINTED COLOUR  (differs >= {COLOUR_DELTA} from every neighbour, "
              f"area <= {AREA_RATIO:.0%} of host)")
        print(f"    {'sec':>5} {'colour':>16} {'host':>5} {'host colour':>16}  "
              f"{'fixture':>12}  texture")
        for i, c, host in tinted:
            nf = nearest_fixture(i)
            near = f"{nf[0]:.0f}u" if nf else "none"
            mark = " [done]" if i in done_tint else ""
            print(f"    {i:5d} {str(c):>16} {host:5d} {str(m.colour(host)):>16}  "
                  f"{near:>12}  {m.signature(i)}{mark}")

    if entries:
        print("\n  --- paste-ready entries for tools/make_seqlight_fix.py ---")
        for (sig, to), members in sorted(groups.items(), key=lambda kv: -len(kv[1])):
            ids = [i for i, _ in members]
            if set(ids) <= done_bright:
                continue
            froms = sorted({l for _, l in members})
            if len(froms) != 1:
                print(f"    # {sig}: mixed from_light {froms}, split before using")
                continue
            nf = [nearest_fixture(i) for i in ids]
            nf = [x for x in nf if x]
            near = f"{min(x[0] for x in nf):.0f}u" if nf else "no fixture on the map"
            print(f'    Shaft(\n        "{mapname}", {ids}, from_light={froms[0]}, '
                  f'to_light={to},\n        enabled=False,   # nearest fixture {near}\n'
                  f'        note="{sig} x{len(ids)} — UNREVIEWED, judge in play.",\n    ),')
        for i, c, host in tinted:
            if i in done_tint:
                continue
            print(f'    Tint(\n        "{mapname}", [{i}], donor={host}, '
                  f'from_lightcolor=0x{int(m.sec[i].get("lightcolor", "0")) & 0xFFFFFF:06X},\n'
                  f'        enabled=False,   # {m.signature(i)}\n'
                  f'        note="UNREVIEWED.",\n    ),')

    return len(bright) + len(tinted)


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    entries = "--entries" in sys.argv
    delta = 30
    if "--delta" in sys.argv:
        delta = int(sys.argv[sys.argv.index("--delta") + 1])

    lumps = read_wad_lumps(WAD)
    lit_nums = lit_actor_editor_numbers(lumps)
    print(f"light-bearing actor editor numbers from GLDEFS+DECORATE: {len(lit_nums)}")

    maps = [f"MAP{int(a):02d}" for a in args] or [f"MAP{i:02d}" for i in range(1, 35)]
    total = 0
    for mp in maps:
        try:
            total += scan_map(lumps, mp, delta, entries, lit_nums)
        except StopIteration:
            continue
    print(f"\nTOTAL candidates across {len(maps)} map(s): {total}")


if __name__ == "__main__":
    main()
