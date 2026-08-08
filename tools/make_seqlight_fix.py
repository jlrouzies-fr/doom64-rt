"""
Build d64r-seqlight-fix.wad: strip chosen animated sector-light specials.

Two families, two tables. CHAINS holds LightSequence chains, described below.
BLINKS holds per-sector blink specials (dLight_Flicker and friends), which need
no walk to resolve -- one special animates one sector, so the sector list is the
effect. Both end up in the same output wad, which may cover several maps.

A LightSequenceStart (special 2) sector anchors a chain of alternating
LightSequenceSpecial1/2 (3/4) sectors. GZDoom walks it once at map load
(DPhased::PhaseHelper) and spawns a thinker per sector, each ramping from its
base lightlevel to 255 and back, offset by phase -- so a wave of light travels
along the chain forever, with nothing in the world casting it.

Under RT that is worse than in the original renderer: rt_sector_emis turns
sector lightlevel into surface emission above a PER-MAP threshold,
max(rt_sector_emis_minlight, map median + margin) -- 220 on MAP03 and MAP12,
240 on MAP05 with the launcher's 160/40. The crest of a phased wave is 255,
which clears any such threshold, so every sequence chain flares into being a
real emitter as the wave passes. The base lightlevel only decides whether it
also emits steadily in between.

Clearing the special leaves each sector at its base lightlevel -- the value it
already shows between waves -- so nothing gets darker.

Only entries with enabled=True are stripped. The whole survey is listed here so
the rejected ones stay visible; see docs/sequence-light-chains.md for what each
one looks like in game and why it is or is not on. A blink with a real fixture
in the room -- a hanging lamp, a monitor with its own light thing -- is kept:
the complaint is sourceless light, not animation as such.

Any map that also appears in d64r-3dfloor-rtfix.wad gets its Sector_Set3dFloor
linedefs re-stripped here, because this wad loads later and therefore wins.

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
    strip_3dfloor,
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
             "base 150. Previously written off as harmless for being under the "
             "threshold -- wrong: the crest is 255, above MAP03's 220, so these "
             "do flare as the wave passes, and the low base gives the pulse the "
             "HIGHEST contrast of the three, not the least.",
    ),
    Chain(
        "MAP12", 196,
        [196, 199, 214, 212, 182, 192, 184, 185, 190, 189, 188, 187, 205, 210,
         203, 194, 201, 180, 216, 218],
        enabled=False,
        note="PENDING PLAYTEST. 20 wedge sectors nested concentrically around "
             "(-1340,-930), CASFL27/CASF80, base 160, under MAP12's threshold of "
             "220 but cresting to 255 like every chain. The layout reads like a "
             "deliberate rotating beacon, so this one may be worth keeping.",
    ),
]


class Blink:
    """A set of sectors carrying a per-sector blink special (dLight_Flicker and
    friends) rather than a sequence chain. No walk to resolve -- blink specials
    animate one sector each, so the sector list IS the effect."""

    def __init__(self, mapname: str, sectors: list[int], special: int,
                 enabled: bool, note: str):
        self.mapname = mapname
        self.sectors = sectors
        self.special = special
        self.enabled = enabled
        self.note = note


BLINKS = [
    Blink(
        "MAP05", [258, 259, 260, 261, 262], 65,
        enabled=True,
        note="The light pylons. Five gateways between corridors, each one a bar "
             "176x80 and 136 tall whose middle 80 units are the opening and whose "
             "two 48-unit ends are solid, clad floor-to-ceiling in SPACECC -- a "
             "dark panel of vertical blue light strips. That is two lit pylons "
             "flanking every gate, ten in all. dLight_Flicker on the sector "
             "flashes the strips with nothing casting the light. Reported from "
             "play.",
    ),
    Blink(
        "MAP05", [122], 65,
        enabled=False,
        note="KEPT. 264x264 room, 208 tall, light 255 -- and it contains a "
             "64LampTechLongHang (thing type 1015) hanging in it. The flicker has "
             "a real fixture to come from, which is the whole difference from the "
             "pylons.",
    ),
    Blink(
        "MAP05", [155, 162, 164, 295], 65,
        enabled=False,
        note="KEPT. Thin 64x8x64 slabs faced with SMONDA/SMONAA -- computer "
             "monitors set into walls. Each holds its own 9802 FlickerLight thing "
             "at height 32, so the blink is authored deliberately and has a "
             "source. A flickering CRT is not a fake light.",
    ),
]


def clear_specials(
    text: str, wanted: dict[int, tuple[int, ...]], mapname: str
) -> tuple[str, int]:
    """wanted maps sector index -> the specials it may currently carry. A chain
    member is allowed the whole LightSequence family (the walk decided which of
    2/3/4 each one is); a blink sector must match its exact special. Either way
    the check is what stops this patching a map whose numbering has shifted."""
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
        want = wanted[index]
        if got not in want:
            raise SystemExit(
                f"{mapname} sector {index}: expected special in {want}, found "
                f"{got} — map data changed, refusing to patch blind. Re-run "
                f"tools/scan_light_specials.py --chains."
            )
        cleared += 1
        return "sector\n{" + re.sub(r"(?m)^\s*special\s*=\s*\d+;\s*\n", "", body) + "}"

    return re.sub(r"(?ms)^sector\s*\{(.*?)\}", scrub, text), cleared


def show_table() -> None:
    for c in CHAINS:
        state = "STRIP" if c.enabled else "keep "
        print(f"[{state}] {c.mapname} sequence start={c.start:4d} "
              f"sectors={len(c.sectors):3d}")
        print(f"          {c.note}")
    for b in BLINKS:
        state = "STRIP" if b.enabled else "keep "
        print(f"[{state}] {b.mapname} blink special={b.special} "
              f"sectors={b.sectors}")
        print(f"          {b.note}")


def main() -> None:
    if "--list" in sys.argv:
        show_table()
        return

    active = [c for c in CHAINS if c.enabled]
    activeBlinks = [b for b in BLINKS if b.enabled]
    if not active and not activeBlinks:
        raise SystemExit("nothing enabled — nothing to build")

    # sector index -> the specials it may currently carry, per map
    SEQ_FAMILY = ( 1, 2, 3, 4 )
    by_map: dict[str, dict[int, tuple[int, ...]]] = {}
    labels: dict[str, list[str]] = {}
    for c in active:
        m = by_map.setdefault(c.mapname, {})
        for i in c.sectors:
            m[i] = SEQ_FAMILY
        labels.setdefault(c.mapname, []).append(f"chain {c.start}")
    for b in activeBlinks:
        m = by_map.setdefault(b.mapname, {})
        for i in b.sectors:
            m[i] = ( b.special, )
        labels.setdefault(b.mapname, []).append(
            f"blink {b.special} x{len(b.sectors)}")

    lumps = read_wad_lumps(WAD)
    items: list[tuple[str, bytes]] = []
    for mapname, wanted in by_map.items():
        start, end = map_lump_range(lumps, mapname)
        members = {nm.upper(): blob for nm, blob in lumps[start:end]}
        if "TEXTMAP" not in members or "BEHAVIOR" not in members:
            raise SystemExit(f"{mapname}: missing TEXTMAP/BEHAVIOR in {WAD}")

        fixed, n = clear_specials(decode_textmap(members["TEXTMAP"]), wanted, mapname)
        if n != len(wanted):
            raise SystemExit(f"{mapname}: cleared {n} of {len(wanted)} sectors")

        # Carry the 3D-floor strip forward on any map that needs it.
        #
        # This wad loads AFTER d64r-3dfloor-rtfix.wad, so for a map present in
        # both, ours is the one GZDoom uses and ours alone decides what the map
        # contains. MAP03 was safe by accident -- it has no special-160 linedefs
        # and is absent from the combined wad. MAP05 has one and IS in it, so
        # replacing the map without re-stripping would silently hand back the 3D
        # floor that hangs RT live upload, undoing a fix from another tool
        # entirely. Re-derived here rather than assumed.
        fixed, n3d = strip_3dfloor(fixed)

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
        print(f"{mapname}: cleared {n} sectors ({', '.join(labels[mapname])})"
              f"{f', re-stripped {n3d} 3D-floor linedef(s)' if n3d else ''}")

    write_wad(OUTWAD, items)
    print(f"wrote {OUTWAD} maps={len(by_map)} lumps={[nm for nm, _ in items]}")


if __name__ == "__main__":
    main()
