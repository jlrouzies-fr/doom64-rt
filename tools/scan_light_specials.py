"""
Survey every Retribution map for animated sector-light specials.

Two families, and they are not the same problem:

  SEQUENCE  Light_Phased (1) / LightSequenceStart (2) / LightSequenceSpecial1,2
            (3,4). GZDoom chains adjacent 3/4 sectors off a 2 and spawns
            DPhased: each sector ramps base -> 255 -> base in turn, so a wave
            travels along the chain forever. This is the MAP03 stairs effect --
            a moving light with no fixture anywhere near it.

  BLINK     dLight_Flicker (65), the strobes (64,66,67,72,73), dLight_Glow (8),
            FireFlicker (17), Strobe_Hurt (4 in Doom numbering -> 71/115 here),
            lightning (198,199,200). These are per-sector, not chains, and are
            often authored under a real lamp texture -- worth judging one by one
            rather than stripping wholesale.

The RT column is what makes this actionable. rt_sector_emis turns sector
lightlevel into surface emission above a PER-MAP threshold -- not the flat 160
this tool first assumed. rt_main.cpp computes it as
max(rt_sector_emis_minlight, map median lightlevel + margin), which with the
launcher's 160/40 works out to 220 on MAP03 and MAP12 and 240 on MAP05.

For a SEQUENCE chain the base lightlevel is therefore only half the question.
DPhased ramps every sector to 255 at the crest of the wave, which clears any
threshold a Doom map can produce, so every chain in the game becomes a
sourceless emitter as the wave passes -- the base only says whether it also
emits steadily in between. For BLINK specials the base IS the question, because
they only ever dim below it.

  python tools/scan_light_specials.py            # every map, summary
  python tools/scan_light_specials.py 3 5        # only MAP03 and MAP05
  python tools/scan_light_specials.py --chains   # + resolved sequence chains
"""

from __future__ import annotations

import re
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

# The emission threshold is NOT the flat 160 this file first assumed. rt_main.cpp
# computes it per map as max(rt_sector_emis_minlight, map median lightlevel + margin),
# with the launcher pinning minlight 160 and margin 40 -- so the floor of 160 is almost
# never what binds. MAP03 and MAP12 have median 180 and land at 220, MAP05 at 240.
#
# Assuming 160 mis-triaged whole chains: it labelled MAP03's chain 150 (base 150) as
# "RT never makes these a source", when in fact every sequence chain crosses its map's
# threshold anyway -- see peak_emits below.
EMIS_MINLIGHT = 160.0
EMIS_MARGIN = 40.0

# DPhased ramps each sector from its base lightlevel to 255 and back. So for a SEQUENCE
# chain the base only decides whether it emits steadily between crests; the crest is 255
# and clears any threshold a Doom map can produce. For the BLINK family the opposite
# holds: DFlicker and the strobes alternate DOWN from the sector's own lightlevel toward
# a dimmer neighbour value, never above it, so there the base is the whole story.
PHASED_PEAK = 255


def emis_threshold(levels: list[int]) -> float:
    """Reproduce rt_main.cpp's per-map threshold, including its choice of median."""
    if not levels:
        return EMIS_MINLIGHT
    # nth_element with mid = size/2 -> the upper median for even counts.
    median = sorted(levels)[len(levels) // 2]
    return max(EMIS_MINLIGHT, median + EMIS_MARGIN)

SEQUENCE = {
    1: "Light_Phased",
    2: "LightSequenceStart",
    3: "LightSequenceSpecial1",
    4: "LightSequenceSpecial2",
}
BLINK = {
    8: "dLight_Glow",
    17: "dLight_FireFlicker",
    64: "dLight_Flicker",
    65: "dLight_Flicker",
    66: "dLight_StrobeFast",
    67: "dLight_StrobeSlow",
    68: "dLight_Strobe_Hurt",
    69: "dLight_StrobeSlowSync",
    70: "dLight_StrobeFastSync",
    71: "sLight_Strobe_Hurt",
    198: "Light_OutdoorLightning",
    199: "Light_IndoorLightning1",
    200: "Light_IndoorLightning2",
}


def fields(body: str) -> dict[str, str]:
    return {k: v.strip() for k, v in re.findall(r"(\w+)\s*=\s*([^;]+);", body)}


class MapData:
    def __init__(self, text: str):
        self.sectors = [fields(b) for b in re.findall(r"(?ms)^sector\s*\{(.*?)\}", text)]
        self.verts = [
            (float(d["x"]), float(d["y"]))
            for d in (fields(b) for b in re.findall(r"(?ms)^vertex\s*\{(.*?)\}", text))
        ]
        self.sides = [
            int(fields(b).get("sector", 0))
            for b in re.findall(r"(?ms)^sidedef\s*\{(.*?)\}", text)
        ]
        self.pts: dict[int, list[tuple[float, float]]] = defaultdict(list)
        self.adj: dict[int, set[int]] = defaultdict(set)
        for b in re.findall(r"(?ms)^linedef\s*\{(.*?)\}", text):
            d = fields(b)
            touched = []
            for key in ("sidefront", "sideback"):
                if key in d:
                    s = self.sides[int(d[key])]
                    touched.append(s)
                    self.pts[s].extend([self.verts[int(d["v1"])], self.verts[int(d["v2"])]])
            if len(touched) == 2 and touched[0] != touched[1]:
                self.adj[touched[0]].add(touched[1])
                self.adj[touched[1]].add(touched[0])

    def special(self, i: int) -> int:
        return int(self.sectors[i].get("special", "0"))

    def light(self, i: int) -> int:
        return int(self.sectors[i].get("lightlevel", "0"))

    def center(self, i: int) -> tuple[float, float]:
        p = self.pts.get(i, [])
        if not p:
            return (float("nan"), float("nan"))
        return (sum(a for a, _ in p) / len(p), sum(b for _, b in p) / len(p))

    def chain_from(self, start: int) -> list[int]:
        """Mirror DPhased::PhaseHelper: a single linear walk from the start
        sector, hopping through two-sided linedefs to the next sector whose
        special is the opposite of the current one. Per a_lights.cpp the rule is
        `special == Special1 ? Special2 : Special1`, so a start (2) and a
        Special2 (4) both look for a Special1 (3). validcount stops it revisiting,
        and P_NextSpecialSector takes the FIRST matching neighbour, so this is a
        path, not a flood -- sectors off that path never get a thinker."""
        chain: list[int] = []
        seen = {start}
        cur = start
        while True:
            want = 4 if self.special(cur) == 3 else 3
            nxt = next(
                (s for s in sorted(self.adj[cur]) if s not in seen and self.special(s) == want),
                None,
            )
            if nxt is None:
                return chain
            seen.add(nxt)
            chain.append(nxt)
            cur = nxt


def scan(mapname: str, text: str, show_chains: bool) -> tuple[int, int, int]:
    m = MapData(text)
    seq = [i for i in range(len(m.sectors)) if m.special(i) in SEQUENCE]
    blink = [i for i in range(len(m.sectors)) if m.special(i) in BLINK]
    thr = emis_threshold([m.light(i) for i in range(len(m.sectors))])
    # Sequence sectors are reported on BOTH counts: base (steady emission between
    # crests) and peak (emission as the wave passes). Blink sectors only ever fall
    # below their base, so peak is meaningless for them.
    seq_emis = [i for i in seq if m.light(i) >= thr]
    seq_peak = [i for i in seq if PHASED_PEAK >= thr]
    blink_emis = [i for i in blink if m.light(i) >= thr]
    starts = [i for i in seq if m.special(i) in (1, 2)]

    if not seq and not blink:
        return 0, 0, 0

    print(
        f"{mapname}  sectors={len(m.sectors):4d}  thr={thr:.0f}  "
        f"sequence={len(seq):3d} (emit at base {len(seq_emis):3d}, at peak "
        f"{len(seq_peak):3d}, chains {len(starts)})  "
        f"blink={len(blink):3d} (emitting {len(blink_emis):3d})"
    )
    if blink:
        kinds = defaultdict(int)
        for i in blink:
            kinds[BLINK[m.special(i)]] += 1
        print("      blink kinds: " + ", ".join(f"{k}x{v}" for k, v in sorted(kinds.items())))

    if show_chains:
        for s in starts:
            members = m.chain_from(s)
            all_of = [s] + members
            lights = sorted({m.light(i) for i in all_of})
            xs = [m.center(i)[0] for i in all_of if m.center(i)[0] == m.center(i)[0]]
            ys = [m.center(i)[1] for i in all_of if m.center(i)[1] == m.center(i)[1]]
            emitting = sum(1 for i in all_of if m.light(i) >= thr)
            print(
                f"      chain start={s:4d} len={len(all_of):3d} emitting={emitting:3d} "
                f"light={lights} area=({min(xs):.0f}..{max(xs):.0f}, {min(ys):.0f}..{max(ys):.0f})"
            )
            print(f"        sectors: {all_of}")
        orphans = sorted(set(seq) - {i for s in starts for i in [s] + m.chain_from(s)})
        if orphans:
            print(f"      unreached 3/4 sectors (no start adjacent): {orphans}")
    return len(seq), len(blink), len(starts)


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    show_chains = "--chains" in sys.argv
    lumps = read_wad_lumps(WAD)
    names = list_map_names(lumps)
    if args:
        wanted = {f"MAP{int(a):02d}" for a in args}
        names = [n for n in names if n in wanted]

    tot_seq = tot_blink = tot_chain = 0
    for name in names:
        start, end = map_lump_range(lumps, name)
        members = {nm.upper(): blob for nm, blob in lumps[start:end]}
        if "TEXTMAP" not in members:
            continue
        s, b, c = scan(name, decode_textmap(members["TEXTMAP"]), show_chains)
        tot_seq += s
        tot_blink += b
        tot_chain += c
    print(f"\nTOTAL sequence sectors={tot_seq} in {tot_chain} chains; blink sectors={tot_blink}")


if __name__ == "__main__":
    main()
