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


SEQL_WAD = WAD.parent / "d64r-seqlight-fix.wad"

# Families that are SUPPOSED to read as lit: switches, exit signs, monitors, teleport
# pads, key floors. SEXIT even ships an emissive mask. Stripping these is the CRTRAKA
# mistake -- a rule applied by name to art that never asked for it.
EMITTER_FAMILIES = ("SWX", "SEXIT", "CRT", "SMON", "CFACE", "SPORT", "SKEYFL", "CMPSW")


def is_emitter_family(tex: str) -> bool:
    return tex.upper().startswith(EMITTER_FAMILIES)


def effective_lumps():
    """Map name -> the lumps the GAME actually loads for it.

    d64r-seqlight-fix.wad loads after the base wad, so for any map it contains, ITS
    version is the one in play. Reading that instead of the original is what makes
    'already fixed' disappear from the survey by construction, rather than by keeping a
    list of what was done and hoping it stays in sync.
    """
    base = read_wad_lumps(WAD)
    patched = read_wad_lumps(SEQL_WAD) if SEQL_WAD.exists() else []
    have = set()
    for n, _ in patched:
        if re.fullmatch(r"MAP\d\d", n.upper()):
            have.add(n.upper())
    return base, patched, have


def map_text(base, patched, have, mapname):
    src = patched if mapname in have else base
    try:
        s, e = map_lump_range(src, mapname)
    except StopIteration:
        return None
    return next((decode_textmap(b) for n, b in src[s:e] if n.upper() == "TEXTMAP"), None)


def known_fixture_textures(base):
    """Texture signatures of everything we have ALREADY confirmed and repaired.

    Read off the enabled SHAFTS entries against the ORIGINAL map data, so the set is
    'what a confirmed fake looks like' rather than a hand-kept list. Finding the same
    textures elsewhere is the safest possible extrapolation: it is the same fixture,
    built the same way, painted the same way, on another map.
    """
    try:
        import make_seqlight_fix as S
    except Exception:
        return {}
    out: dict[str, list[str]] = defaultdict(list)
    for h in getattr(S, "SHAFTS", []):
        if not h.enabled:
            continue
        text = None
        try:
            s, e = map_lump_range(base, h.mapname)
            text = next((decode_textmap(b) for n, b in base[s:e]
                         if n.upper() == "TEXTMAP"), None)
        except StopIteration:
            pass
        if not text:
            continue
        m = MapInfo(text)
        for si in h.sectors:
            if si < len(m.sec):
                for t in m.tex.get(si, ()):
                    if not is_emitter_family(t):
                        out[t.upper()].append(f"{h.mapname}:{si}")
    return out


def elements(m, thr: float, min_delta: int):
    """Group the map's over-threshold sectors into ELEMENTS, then test each element
    against what borders it.

    Three shapes of the same defect defeated a per-sector test, each found the hard way
    from a report (MAP11, MAP18, MAP12):

      SINGLE   a recess or panel, brighter than the wall it is cut into.
      NESTED   a floor plus the one-unit ring around it. The inner sector's ONLY
               neighbour is its own ring, so per-sector it looks like it has no darker
               host and is skipped entirely.
      REGION   a whole painted area -- MAP12's cave is eleven connected sectors. A
               contiguous region has no INTERNAL darker neighbour; only its boundary
               does, so a per-sector test sees a few edge cases and misses the body.

    Connected components of over-threshold sectors handle all three, because in every
    case the element IS exactly one component. The comparison is then the component
    against its BOUNDARY -- the "frame test": the surface the element is set into.

    `host` (the repair target) is the BRIGHTEST bordering sector, so a repair can never
    take an element below the room around it. That is the property that makes bulk
    application safe even where a call is wrong: the failure mode is "a panel stops
    standing out", never "a room goes black".
    """
    above = {i for i in range(len(m.sec)) if m.light(i) > thr}
    seen: set[int] = set()
    out = []
    for s0 in above:
        if s0 in seen:
            continue
        comp = {s0}
        stack = [s0]
        seen.add(s0)
        while stack:
            x = stack.pop()
            for n in m.adj.get(x, ()):
                if n in above and n not in seen:
                    seen.add(n)
                    comp.add(n)
                    stack.append(n)
        border = {n for i in comp for n in m.adj.get(i, ()) if n not in above}
        if not border:
            continue                      # sealed off; nothing to compare against
        host = max(m.light(n) for n in border)
        lo = min(m.light(i) for i in comp)
        if lo - host < min_delta:
            continue
        out.append((sorted(comp), host, lo))
    return out


def scan_text(text: str, mapname: str, delta: int, lit_nums: set[int], known: dict):
    m = MapInfo(text)
    if not m.sec:
        return []
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
            fixtures.append((float(t.get("x", 0)), float(t.get("y", 0))))

    def nearest_fixture(ids):
        best = None
        for i in ids:
            c = m.centre(i)
            if not c or not fixtures:
                continue
            d = min(math.hypot(x - c[0], y - c[1]) for x, y in fixtures)
            best = d if best is None else min(best, d)
        return best

    rows = []
    for comp, host, lo in elements(m, thr, delta):
        tex = {t.upper() for i in comp for t in m.tex.get(i, ())}
        # Drop anything whose ONLY identity is an emitter family: switches, exit signs,
        # monitors, teleport pads and key floors are meant to read as lit.
        plain = {t for t in tex if not is_emitter_family(t)}
        if not plain:
            continue
        rows.append({
            "map": mapname, "sectors": comp, "host": host, "from": lo,
            "froms": sorted({m.light(i) for i in comp}),
            "shape": "single" if len(comp) == 1 else ("pair" if len(comp) == 2 else "region"),
            "tex": ",".join(sorted(plain)[:3]),
            "known": sorted(plain & set(known)),
            "fixture": nearest_fixture(comp), "thr": thr,
        })
    return rows


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    entries = "--entries" in sys.argv
    known_only = "--known" in sys.argv
    delta = 30
    if "--delta" in sys.argv:
        delta = int(sys.argv[sys.argv.index("--delta") + 1])

    base, patched, have = effective_lumps()
    lit_nums = lit_actor_editor_numbers(base)
    known = known_fixture_textures(base)

    maps = [f"MAP{int(a):02d}" for a in args] or [f"MAP{i:02d}" for i in range(1, 35)]
    allrows = []
    for mp in maps:
        text = map_text(base, patched, have, mp)
        if text is None:
            continue
        allrows.extend(scan_text(text, mp, delta, lit_nums, known))

    if known_only:
        allrows = [r for r in allrows if r["known"]]

    print()
    print("=" * 80)
    print("PAINTED LIGHT — elements above their map's emission threshold and at least")
    print(f"{delta} brighter than everything bordering them.")
    print()
    print(f"Reading the PATCHED map where one exists ({len(have)} maps in "
          f"d64r-seqlight-fix.wad), so anything already repaired is simply gone.")
    print("Switch / exit / monitor / teleporter / key families are excluded — those are")
    print("meant to read as lit.")
    if known_only:
        print()
        print("--known: showing ONLY elements built from a texture we have already")
        print("confirmed and repaired elsewhere. Same fixture, another map.")
    print("=" * 80)

    if known:
        print()
        print(f"Confirmed-fake fixture textures ({len(known)}), from the enabled SHAFTS entries:")
        for t in sorted(known):
            where = known[t]
            print(f"   {t:12} already fixed at {', '.join(where[:4])}"
                  f"{' …' if len(where) > 4 else ''}")

    bymap: dict[str, list] = defaultdict(list)
    for r in allrows:
        bymap[r["map"]].append(r)

    print()
    print(f"{'map':7}{'elems':>6}{'sectors':>8}{'single':>7}{'pair':>5}{'region':>7}"
          f"   biggest element")
    for mp in sorted(bymap, key=lambda k: -sum(len(r["sectors"]) for r in bymap[k])):
        rs = bymap[mp]
        big = max(rs, key=lambda r: len(r["sectors"]))
        print(f"{mp:7}{len(rs):6}{sum(len(r['sectors']) for r in rs):8}"
              f"{sum(1 for r in rs if r['shape']=='single'):7}"
              f"{sum(1 for r in rs if r['shape']=='pair'):5}"
              f"{sum(1 for r in rs if r['shape']=='region'):7}"
              f"   {big['tex'][:26]} x{len(big['sectors'])}")

    print()
    print(f"TOTAL: {len(allrows)} elements, {sum(len(r['sectors']) for r in allrows)} "
          f"sectors, {len(bymap)} maps")
    for sh in ("single", "pair", "region"):
        k = [r for r in allrows if r["shape"] == sh]
        if k:
            print(f"   {sh:7} {len(k):4d} elements  "
                  f"{sum(len(r['sectors']) for r in k):4d} sectors")

    if known_only and allrows:
        print()
        print("EVERY MATCH (same fixture as one already repaired):")
        print(f"   {'map':7}{'n':>3}{'from':>6}{'->':>5}{'shape':>8}  "
              f"{'matched texture(s)':28} sectors")
        for r in sorted(allrows, key=lambda r: (r["map"], -len(r["sectors"]))):
            ids = str(r["sectors"][:8]) + ("…" if len(r["sectors"]) > 8 else "")
            print(f"   {r['map']:7}{len(r['sectors']):3}{r['from']:6}{r['host']:5}"
                  f"{r['shape']:>8}  {','.join(r['known'])[:28]:28} {ids}")

    if entries:
        print()
        print("  --- paste-ready ---")
        for mp in sorted(bymap):
            for r in sorted(bymap[mp], key=lambda r: -len(r["sectors"])):
                froms = r["froms"]
                if len(froms) != 1:
                    print(f"    # {mp} {r['sectors']}: mixed from_light {froms} — split first")
                    continue
                why = ("matches " + ",".join(r["known"])) if r["known"] else r["tex"]
                print("    Shaft(")
                print(f'        "{mp}", {r["sectors"]}, from_light={froms[0]}, '
                      f'to_light={r["host"]},')
                print(f'        enabled=False,   # {why}')
                print(f'        note="{r["tex"]} x{len(r["sectors"])} — UNREVIEWED.",')
                print("    ),")


if __name__ == "__main__":
    main()
