"""
Build d64r-seqlight-fix.wad: strip chosen sources of sourceless sector light.

Four families, four tables. CHAINS holds LightSequence chains, described below.
BLINKS holds per-sector blink specials (dLight_Flicker and friends), which need
no walk to resolve -- one special animates one sector, so the sector list is the
effect. SCRIPTED holds Light_Glow/Flicker/Strobe calls the map's own ACS makes at
runtime, which carry no sector special at all and so are invisible to any survey
of the map geometry -- see the Scripted class. SHAFTS holds painted light shafts,
which carry no special and never animate at all: wedge sectors given a higher
lightlevel than the room they sit in, identical to it in every other respect --
see the Shaft class. All four end up in the same output wad, which may cover
several maps.

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

Painted shafts come from tools/scan_fake_lightshafts.py, which has to be a
separate survey because nothing about them is a special:

  python tools/scan_fake_lightshafts.py 13
"""

from __future__ import annotations

import re
import struct
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


class Shaft:
    """A painted light shaft: sectors whose only claim to being lit is a number.

    The fourth family, and the only one that never animates -- which is why the
    first three surveys all missed it. There is no special and no script. The
    author cut wedge-shaped sectors out of a room's floorplan and gave them a
    higher lightlevel than the room, leaving floor height, ceiling height and
    both flats identical. In the software renderer that is sunlight slanting
    through a window, drawn by hand.

    Under RT it stops being a drawing. rt_sector_emis makes any sector at or
    above the per-map threshold a surface emitter, so a wedge at 255 inside a
    room at 170 radiates, casts GI on the pillars beside it and lights the
    ceiling as well as the floor, with nothing in the world casting it.

    The repair is not to delete a special -- there is none -- but to rewrite the
    lightlevel down to the host room's, which is what the room would have been
    if the shaft had never been painted. `to_light` is therefore normally the
    neighbouring sector's own value. `from_light` is asserted before the write,
    the same way the other three families assert their specials: if the map data
    ever changes the build fails rather than rewriting the wrong sector.

    Where the shaft was painted under a real F_SKY1 aperture, dropping it is only
    half the job -- the room then has a window and no light through it. That half
    is the moon: see rt_sun_* in tools/launch-retribution-rt.cmd.
    """

    def __init__(self, mapname: str, sectors: list[int], from_light: int,
                 to_light: int, enabled: bool, note: str):
        self.mapname = mapname
        self.sectors = sectors
        self.from_light = from_light
        self.to_light = to_light
        self.enabled = enabled
        self.note = note


SHAFTS = [
    Shaft(
        "MAP13", [136, 137], from_light=255, to_light=170,
        enabled=True,
        note="THE REPORTED ONE (screen/level13fakeoutside light streaks.png). "
             "The west hall, room sector 75 at L170, x -2016..-1024. Two sectors, "
             "each one a FAN of five disjoint wedges -- Doom sectors need not be "
             "contiguous -- splaying east out of the two real F_SKY1 window slots "
             "in the west wall (sectors 54/55, 15 units deep at x -2063..-2048, "
             "z 40..160). The wedges span the room's full height (floor -24, "
             "ceiling 192) and share its CASFL4 floor and HFL15 ceiling exactly, "
             "so at L255 against MAP13's threshold of 200 they emit from BOTH "
             "surfaces -- which is why the streaks appear on the ceiling as well "
             "as the floor. Dropped to 170 to match sector 75; the light comes "
             "back through the windows for real, from the moon.",
    ),
    Shaft(
        "MAP13", [126], from_light=255, to_light=180,
        enabled=True,
        note="The CTEL alcove, and the reason its panel read as BAKED LIT. 64x64, "
             "floor 8 / ceiling 120, the telemetry flat on both, painted at 255 "
             "inside room sector 127 at 180 -- its only neighbour. MAP13's "
             "emission threshold is 200, so both flats self-emitted and the panel "
             "lit itself: a surface glowing with nothing casting it, which is this "
             "file's whole subject. The animated gems made it read as a light "
             "SEQUENCE turning on and off, which is what it was mistaken for. "
             "Dropping to the room's own 180 puts the alcove under the threshold, "
             "and the light in it is now the real one -- see the Lamp family.",
    ),
    Shaft(
        "MAP13", [134, 135], from_light=255, to_light=180,
        enabled=True,
        note="The north hall, room sector 14 at L180, the same defect twice more: "
             "two five-wedge fans at (216..688, 664..872) and (-488..-16, "
             "664..872), splaying south off the north wall, floor 0 / ceiling 192 "
             "and CASFL27/HFL15 on both sides of the boundary. Fixed with the "
             "west pair rather than left to be re-reported -- it is one room away "
             "and the same shot would have caught it next.",
    ),
]


class Scripted:
    """A single Light_* call made by the map's ACS at runtime.

    The third family, and the one no sector-special survey can see: the map
    carries no special at all, an OPEN script installs the effect at load. That
    is why tools/scan_light_specials.py reported MAP07 clean while the map was
    visibly blinking -- it reads special= out of TEXTMAP, and there is nothing
    there to read.

    Identity is (script, special, args). Args are matched exactly, because that
    tuple is what the byte signature below is built from and an exact match is
    the whole safety story: if the map is ever recompiled and the call moves or
    its arguments change, the signature stops matching and the build aborts
    rather than NOP-ing out some unrelated instruction.
    """

    def __init__(self, mapname: str, script: int, special: int,
                 args: tuple[int, ...], enabled: bool, note: str):
        self.mapname = mapname
        self.script = script
        self.special = special
        self.args = args
        self.enabled = enabled
        self.note = note

    @property
    def label(self) -> str:
        name = ACS_LIGHT_SPECIALS.get(self.special, f"special {self.special}")
        return f"{name}({', '.join(str(a) for a in self.args)})"


ACS_LIGHT_SPECIALS = {
    112: "Light_ChangeToValue",
    113: "Light_Fade",
    114: "Light_Glow",
    115: "Light_Flicker",
    116: "Light_Strobe",
    117: "Light_Stop",
}


SCRIPTED = [
    # MAP07 script 669 OPEN is nothing BUT these eight calls, so stripping all
    # of them leaves an OPEN script that runs a run of NOPs and terminates.
    #
    # Every one of them crests at 255, which clears any threshold rt_sector_emis
    # can produce (max(minlight, map median + margin) -- 160/40 in the launcher),
    # so each one turns its sectors into sourceless emitters exactly the way a
    # phased sequence chain does. Reported from play on the tag 8 alcoves: a
    # white patch blinking on the wall beside a 64TechPoleLong, with the pole
    # itself -- which has a real GLDEFS pointlight -- visibly steady throughout.
    Scripted(
        "MAP07", 669, 115, (8, 255, 200), enabled=True,
        note="THE REPORTED ONE. Flicker 255<->200 on sectors 243/245/265/303 -- "
             "64-tall alcoves clad SMONBA/SPACEBK/SPACEBO, ceiling SFLATAS, "
             "around (-700..-1160, -1000..-1900). Sector 243 contains the "
             "64TechPoleLong at (-768,-1536) and 245 the one at (-1140,-1892), "
             "which is the pole-plus-blinking-patch in screen/"
             "fakelightblinklevel7.png. Base is 255 on 243/245/303 and 220 on "
             "265, so clearing it leaves the alcoves steady bright -- 265 sits "
             "at 220 rather than pulsing up to 255, the only change worth "
             "noticing.",
    ),
    Scripted(
        "MAP07", 669, 115, (28, 255, 220), enabled=True,
        note="Flicker 255<->220 on sectors 193/194/195, the stepped bay at "
             "(1808..1920, 16..208). Same defect, same map, base 255 so same "
             "no-darkening result. Stripped with tag 8 rather than left to be "
             "re-reported.",
    ),
    Scripted(
        "MAP07", 669, 116, (16, 255, 140, 2, 2), enabled=True,
        note="Strobe 2 tics on / 2 off on sector 218 -- a 64x64 cell at "
             "(64..128, -512..-448) floored AND ceilinged in SPORT1. Note this "
             "is the one entry here with an arguable source: SPORT1 is a lamp "
             "texture, so a room lit by it flashing is not quite the sourceless "
             "lie the others are. Stripped on the instruction to remove the "
             "scripted sequences; base 255 so it stays lit, just steady. Flip "
             "this one first if the room reads dead.",
    ),
    Scripted(
        "MAP07", 669, 114, (7, 255, 180, 35), enabled=True,
        note="Glow 255<->180 on sectors 224/257/262/348/354/423 -- thin 24x12 "
             "slivers faced with STRAKB1/STRAKY1, the animated light-strip "
             "textures. Base 255, so clearing leaves them at full.",
    ),
    Scripted(
        "MAP07", 669, 114, (17, 255, 140, 70), enabled=True,
        note="Glow 255<->140 on sectors 236/426/427, the SPACEBB/SPACEBD/SPACEBI "
             "room at (16..336, -720..-400). Base 255, no darkening.",
    ),
    # The three below DO darken. Their sectors sit at base 140, i.e. the dim end
    # of the ramp, so removing the glow pins them there instead of letting them
    # rise to 255. Stripped anyway on the instruction to remove the scripted
    # sequences -- but these are the three to flip back first if the rooms read
    # too dark, and they are called out separately in the doc for that reason.
    Scripted(
        "MAP07", 669, 114, (5, 255, 140, 35), enabled=True,
        note="DARKENS. Glow on sectors 94/351, base 140 -- the 12-unit slivers "
             "at (1012..1088, -1472..-1396), SFLATBF/SPACEBE. Pinned at 140.",
    ),
    Scripted(
        "MAP07", 669, 114, (6, 255, 140, 35), enabled=True,
        note="DARKENS. Glow on sector 95, base 140 -- 180x180 room at "
             "(896..1076, -1460..-1280), SFLATAJ/SPACEB. Pinned at 140.",
    ),
    Scripted(
        "MAP07", 669, 114, (39, 255, 140, 70), enabled=True,
        note="DARKENS. Glow on sectors 120/121, base 140 -- the CMPSW17A/SDOOR3 "
             "switch room at (464..688, -32..144). Pinned at 140.",
    ),
]


# ACS bytecode patching -------------------------------------------------------
#
# There is no ACS compiler in this tree, so the calls are NOP-ed out of the
# compiled BEHAVIOR in place rather than removed from the SCRIPTS source and
# rebuilt. In place is the point: every instruction is overwritten with an equal
# number of PCD_NOP bytes, so no script address, jump target or chunk offset
# moves, and the rest of the map's ACS is bit-identical.
#
# Retribution's BEHAVIOR lumps are ACSe -- "little enhanced", the byte-coded
# variant: an ACS\0 header whose directory is a dummy, with the real script
# table in an SPTR chunk and one-byte opcodes. The two opcode families used by
# these calls, derived from MAP07's own bytecode and asserted on every build:
#
#     PUSHnBYTES = 174 + n   (n = 3, 4, 5)   push n one-byte literals
#     LSPECn     =   3 + n   (n = 1..5)      call line special, byte operand
#
# so Light_Flicker(8, 255, 200) compiles to 177 8 255 200 6 115, and that exact
# six-byte string is what gets matched and zeroed.
ACS_NOP = 0


def _acs_chunks(behavior: bytes, mapname: str) -> tuple[dict[str, bytes], int]:
    """Return the map's ACSe chunks by name, plus where the chunk area starts.

    GZDoom locates the chunks for this format via the dword at dirofs-8, with
    the format marker in the four bytes after it; both are checked here so a map
    in some other ACS format fails loudly instead of being patched as if it were
    this one.
    """
    if behavior[:4] != b"ACS\0":
        raise SystemExit(f"{mapname}: BEHAVIOR is not ACS ({behavior[:4]!r})")
    dirofs = struct.unpack_from("<I", behavior, 4)[0]
    marker = behavior[dirofs - 4 : dirofs]
    if marker != b"ACSe":
        raise SystemExit(
            f"{mapname}: BEHAVIOR format marker is {marker!r}, expected b'ACSe'. "
            f"Only the byte-coded variant is understood -- refusing to patch."
        )
    start = struct.unpack_from("<I", behavior, dirofs - 8)[0]
    chunks: dict[str, bytes] = {}
    p = start
    while p < dirofs - 8:
        name = behavior[p : p + 4].decode("latin-1")
        size = struct.unpack_from("<I", behavior, p + 4)[0]
        chunks[name] = behavior[p + 8 : p + 8 + size]
        p += 8 + size
    return chunks, start


def _acs_script_range(behavior: bytes, script: int, mapname: str) -> tuple[int, int]:
    """Byte range of one script's code: its own address, up to the next address
    used by any script or function (the chunk area if it is the last one)."""
    chunks, chunk_start = _acs_chunks(behavior, mapname)
    if "SPTR" not in chunks:
        raise SystemExit(f"{mapname}: BEHAVIOR has no SPTR chunk")
    sptr = chunks["SPTR"]
    addrs: dict[int, int] = {}
    for i in range(0, len(sptr), 8):
        num, _type, _argc, addr = struct.unpack_from("<HBBI", sptr, i)
        addrs[num] = addr
    if script not in addrs:
        raise SystemExit(
            f"{mapname}: no script {script} in BEHAVIOR (have "
            f"{sorted(addrs)}) -- map data changed, refusing to patch blind."
        )
    here = addrs[script]
    later = [a for a in addrs.values() if a > here]
    if "FUNC" in chunks:
        func = chunks["FUNC"]
        for i in range(0, len(func), 8):
            addr = struct.unpack_from("<I", func, i + 4)[0]
            if addr > here:
                later.append(addr)
    return here, min(later) if later else chunk_start


def acs_call_signature(special: int, args: tuple[int, ...]) -> bytes:
    n = len(args)
    if not 3 <= n <= 5:
        raise SystemExit(f"unsupported arg count {n} for special {special}")
    if any(not 0 <= a <= 255 for a in args):
        raise SystemExit(
            f"special {special} args {args}: outside one byte, so the compiler "
            f"would not have emitted PUSH{n}BYTES -- signature would not match."
        )
    return bytes([174 + n, *args, 3 + n, special])


def strip_acs_lights(
    behavior: bytes, wanted: list[Scripted], mapname: str
) -> tuple[bytes, int]:
    out = bytearray(behavior)
    for entry in wanted:
        lo, hi = _acs_script_range(behavior, entry.script, mapname)
        sig = acs_call_signature(entry.special, entry.args)
        window = bytes(out[lo:hi])
        hits = [m.start() for m in re.finditer(re.escape(sig), window)]
        if len(hits) != 1:
            raise SystemExit(
                f"{mapname} script {entry.script}: found {len(hits)} matches for "
                f"{entry.label} (bytes {list(sig)}), expected exactly 1 -- map "
                f"data changed, refusing to patch blind."
            )
        at = lo + hits[0]
        out[at : at + len(sig)] = bytes([ACS_NOP]) * len(sig)
    return bytes(out), len(wanted)


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


class Lamp:
    """A light THING to add to a map, for a fixture the art draws but nobody wired.

    The fifth family, and the only one that ADDS rather than strips. It exists
    because the other four all answer "this light has no source" by removing the
    light; sometimes the right answer is to give it the source.

    This is how Retribution itself does it. MAP02's red corridor elements are lit
    by 48 PointLight (9800) and 35 PointLightFlicker (9802) things placed in the
    map, with the red ones at arg0=255, arg3=32 -- not by anything on the texture.
    A texture cannot cast light here: RTGL1's attached lights only exist for
    sprites and simple flats, and rt_sector_emis makes the SURFACE glow without
    illuminating anything. A thing in the map is the mechanism that works, and it
    is the one the mod already uses.

    9801 (PointLightPulse) rather than 9800/9802: the CTEL panel's gems ramp up
    and down over its 8-frame ANIMDEFS loop, so the light wants a smooth cycle,
    not a constant or a random flicker. GZDoom reads the pulse period off the
    thing's ANGLE -- specialf1/TICRATE seconds (a_dynlight.cpp Activate) -- and
    sine-cycles the radius between arg3 and arg4.

    `lo` must stay above rt_dynlight_minradius (16 in the launcher) or the light
    is culled outright at the bottom of the cycle and the fixture blinks OFF
    instead of dimming.
    """

    def __init__(self, mapname: str, sectors: list[int], flat: str,
                 heights: list[int], color: tuple[int, int, int],
                 hi: int, lo: int, period_tics: int, enabled: bool, note: str):
        self.mapname = mapname
        self.sectors = sectors
        self.flat = flat
        self.heights = heights
        self.color = color
        self.hi = hi
        self.lo = lo
        self.period_tics = period_tics
        self.enabled = enabled
        self.note = note


LAMPS = [
    Lamp(
        "MAP13", [126], flat="CTEL",
        heights=[16, 96], color=(255, 0, 0), hi=144, lo=60, period_tics=140,
        enabled=True,
        note="THE REPORTED ONE. CTEL1 is an 8-frame telemetry panel whose small "
             "red gems ramp up and down; the panel is on BOTH the floor and the "
             "ceiling of sector 126, a 64x64 alcove (floor 8, ceiling 120). Two "
             "lights, one 16 above the floor panel and one 16 under the ceiling "
             "one, so each reads as coming off its own fixture rather than one "
             "light floating in the middle of the shaft. period 140 tics = 4.0s, "
             "matching 'slow'. Radii are 3x the first pass (48/20): with the "
             "alcove's painted 255 dropped to the room's 180 by the Shaft entry "
             "above, the surface no longer lights itself and the real light has "
             "to carry the whole fixture. Everything tried on the TEXTURE side -- _e mask, "
             "emissiveMult, attached lightIntensity -- made it glow and never lit "
             "the alcove; see the Lamp docstring for why that cannot work.",
    ),
]


class StaticAnim:
    """An ANIMDEFS animation to freeze, because the animation IS baked lighting.

    The sixth family, and the second one that is not about sector lightlevel at
    all. Some Doom 64 fixtures animate by repainting their own lit elements
    brighter and darker frame by frame -- the light is drawn into the artwork.
    In the software renderer that is the only way to do it. Under RT it is the
    same defect as a painted light shaft, one level down: the surface cycles
    between "lit" and "unlit" with nothing in the world casting either state, and
    no amount of real lighting can fix a texture that is lighting itself.

    Freezing the animation to one frame leaves a fixture with a constant albedo,
    which a real light can then light. It is deliberately a texture-level fix, so
    it applies on every map that uses the texture, not just the reported one.

    `pin` is the frame the base name displays forever. Prefer a DIM frame: the
    albedo should describe the material unlit, and let the map's light supply the
    brightness. A bright pin just re-bakes a dimmer version of the same problem.
    """

    def __init__(self, base: str, first: str, pin: str, enabled: bool, note: str):
        self.base = base
        self.first = first
        self.pin = pin
        self.enabled = enabled
        self.note = note


STATIC_ANIMS = [
    StaticAnim(
        "CTEL", first="CTEL1", pin="CTEL5",
        enabled=True,
        note="THE REPORTED ONE. CTEL1..8, 4 tics each, is a telemetry panel whose "
             "red gems ramp up and down: 45 gem pixels whose luminance runs 2058 "
             "at the crest (CTEL8) to 936 in the trough (CTEL5/6/7), with the "
             "stone byte-identical in all eight frames. Nothing in the map casts "
             "any of it -- MAP13 has no sector special, no ACS Light_* call on the "
             "alcove's tag 30, and the mod ships no ZSCRIPT. The 'light sequence' "
             "was the artwork the whole time. Pinned to CTEL5, the trough, so the "
             "gems read as unlit material; the pulsing red PointLightPulse in the "
             "alcove (see LAMPS) is what makes them brighten and dim now.",
    ),
]


def animdefs_lump(anims: list[StaticAnim]) -> bytes:
    """One ANIMDEFS lump freezing each listed animation to a single frame.

    GZDoom takes the LAST definition it loads for a texture, and this wad loads
    after the mod, so redefining the base name with a single pic replaces the
    original run without touching the mod's own ANIMDEFS lump.
    """
    out = [
        "// Generated by tools/make_seqlight_fix.py -- do not edit by hand.",
        "//",
        "// These animations paint their own lighting: the fixture's lit elements are",
        "// repainted brighter and darker frame by frame, so the surface cycles between",
        "// lit and unlit with nothing in the world casting either state. Under a path",
        "// tracer that is baked lighting, and it cannot be corrected by adding light --",
        "// the texture is lighting itself. Each one is frozen to a single dim frame so a",
        "// real light in the map can do the work. See the StaticAnim class.",
        "",
    ]
    for a in anims:
        out.append(f"// {a.base}: {a.first} pinned to {a.pin}")
        out.append(f"texture {a.first}")
        out.append("allowdecals")
        # TWO identical frames, not one. animations.cpp:480 rejects a single-frame
        # animation outright -- "Animation needs at least 2 frames" -- and the error
        # aborts startup inside Texman.Init, before the game ever reaches a map.
        # Two copies of the same pic satisfy the parser and are visually static.
        out.append(f"pic {a.pin} tics 65535")
        out.append(f"pic {a.pin} tics 65535")
        out.append("")
    return "\n".join(out).encode("ascii")


def add_light_things(
    text: str, lamps: list[Lamp], mapname: str
) -> tuple[str, int]:
    """Append PointLightPulse things at the centre of each listed sector.

    The sector centre is derived from the vertices of the linedefs that touch it,
    the same way tools/scan_light_specials.py does it -- UDMF stores no centre.

    The flat name is asserted before anything is written, for the reason
    set_lightlevels asserts lightlevel: sector indices are positional, so a map
    edit that inserts a sector silently shifts every entry below it.
    """
    def flds(b: str) -> dict[str, str]:
        return {k: v.strip() for k, v in re.findall(r"(\w+)\s*=\s*([^;]+);", b)}

    verts = [
        (float(d["x"]), float(d["y"]))
        for d in (flds(b) for b in re.findall(r"(?ms)^vertex\s*\{(.*?)\}", text))
    ]
    sides = [flds(b) for b in re.findall(r"(?ms)^sidedef\s*\{(.*?)\}", text)]
    secs = [flds(b) for b in re.findall(r"(?ms)^sector\s*\{(.*?)\}", text)]

    pts: dict[int, list[tuple[float, float]]] = {}
    for b in re.findall(r"(?ms)^linedef\s*\{(.*?)\}", text):
        d = flds(b)
        for key in ("sidefront", "sideback"):
            if key not in d:
                continue
            s = int(sides[int(d[key])].get("sector", -1))
            pts.setdefault(s, []).extend(
                [verts[int(d["v1"])], verts[int(d["v2"])]]
            )

    added = 0
    out = [text.rstrip("\n")]
    for lamp in lamps:
        for si in lamp.sectors:
            sec = secs[si]
            flats = {
                sec.get("texturefloor", '"-"').strip('"').upper(),
                sec.get("textureceiling", '"-"').strip('"').upper(),
            }
            if not any(f.startswith(lamp.flat) for f in flats):
                raise SystemExit(
                    f"{mapname} sector {si}: expected flat {lamp.flat}*, found "
                    f"{sorted(flats)} — map data changed, refusing to patch blind."
                )
            p = pts.get(si, [])
            if not p:
                raise SystemExit(f"{mapname} sector {si}: no linedefs found")
            cx = sum(a for a, _ in p) / len(p)
            cy = sum(b for _, b in p) / len(p)
            r, g, b = lamp.color
            for h in lamp.heights:
                out.append(
                    "thing\n{\n"
                    f"x = {cx:.3f};\n"
                    f"y = {cy:.3f};\n"
                    f"height = {h:.3f};\n"
                    f"angle = {lamp.period_tics};\n"
                    "type = 9801;\n"
                    f"arg0 = {r};\n"
                    f"arg1 = {g};\n"
                    f"arg2 = {b};\n"
                    f"arg3 = {lamp.hi};\n"
                    f"arg4 = {lamp.lo};\n"
                    "skill1 = true;\nskill2 = true;\nskill3 = true;\n"
                    "skill4 = true;\nskill5 = true;\n"
                    # Flag set copied from the mod's own light things (MAP02 9800/9802):
                    # skill1-5, single, coop, class1-5. No `dm` — they do not set it.
                    "single = true;\ncoop = true;\n"
                    "class1 = true;\nclass2 = true;\nclass3 = true;\n"
                    "class4 = true;\nclass5 = true;\n"
                    "}\n"
                )
                added += 1
    return "\n".join(out) + "\n", added


def set_lightlevels(
    text: str, wanted: dict[int, tuple[int, int]], mapname: str
) -> tuple[str, int]:
    """wanted maps sector index -> (expected lightlevel, new lightlevel).

    The expected value is asserted before the write for the same reason
    clear_specials asserts the special: sector indices are positional, so a map
    edit that inserts one sector silently shifts every entry below it. Checking
    the value we think is there turns that into a build failure.

    A sector with no lightlevel= line at all is at the UDMF default of 160, and
    is written out with the field added rather than skipped.
    """
    index = -1
    changed = 0

    def rewrite(m: re.Match[str]) -> str:
        nonlocal index, changed
        index += 1
        if index not in wanted:
            return m.group(0)
        body = m.group(1)
        expect, new = wanted[index]
        found = re.search(r"lightlevel\s*=\s*(\d+)\s*;", body)
        got = int(found.group(1)) if found else 160
        if got != expect:
            raise SystemExit(
                f"{mapname} sector {index}: expected lightlevel {expect}, found "
                f"{got} — map data changed, refusing to patch blind. Re-run "
                f"tools/scan_fake_lightshafts.py."
            )
        changed += 1
        if found:
            body = re.sub(r"lightlevel\s*=\s*\d+\s*;", f"lightlevel = {new};", body)
        else:
            body = body.rstrip() + f"\nlightlevel = {new};\n"
        return "sector\n{" + body + "}"

    return re.sub(r"(?ms)^sector\s*\{(.*?)\}", rewrite, text), changed


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
    for s in SCRIPTED:
        state = "STRIP" if s.enabled else "keep "
        print(f"[{state}] {s.mapname} acs script {s.script} {s.label}")
        print(f"          {s.note}")
    for h in SHAFTS:
        state = "STRIP" if h.enabled else "keep "
        print(f"[{state}] {h.mapname} painted shaft sectors={h.sectors} "
              f"L{h.from_light} -> L{h.to_light}")
        print(f"          {h.note}")


def main() -> None:
    if "--list" in sys.argv:
        show_table()
        return

    active = [c for c in CHAINS if c.enabled]
    activeBlinks = [b for b in BLINKS if b.enabled]
    activeScripted = [s for s in SCRIPTED if s.enabled]
    activeShafts = [h for h in SHAFTS if h.enabled]
    activeLamps = [l for l in LAMPS if l.enabled]
    activeAnims = [a for a in STATIC_ANIMS if a.enabled]
    if (not active and not activeBlinks and not activeScripted
            and not activeShafts and not activeLamps and not activeAnims):
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

    # ACS entries live on the same maps or on their own; a map can appear here
    # with no sector work at all, which is exactly MAP07's case.
    acs_by_map: dict[str, list[Scripted]] = {}
    for s in activeScripted:
        acs_by_map.setdefault(s.mapname, []).append(s)
        labels.setdefault(s.mapname, []).append(f"acs {s.label}")

    # Painted shafts rewrite a value rather than removing a special, so they get
    # their own per-map dict: sector index -> (expected, new) lightlevel. A map
    # can appear here with no special work at all, which is MAP13's case.
    light_by_map: dict[str, dict[int, tuple[int, int]]] = {}
    lamp_by_map: dict[str, list] = {}
    for l in activeLamps:
        lamp_by_map.setdefault(l.mapname, []).append(l)
        labels.setdefault(l.mapname, []).append(
            f"lamp {l.sectors} {l.flat}* x{len(l.heights)}")

    for h in activeShafts:
        m = light_by_map.setdefault(h.mapname, {})
        for i in h.sectors:
            m[i] = (h.from_light, h.to_light)
        labels.setdefault(h.mapname, []).append(
            f"shaft {h.sectors} L{h.from_light}->L{h.to_light}")

    lumps = read_wad_lumps(WAD)
    items: list[tuple[str, bytes]] = []
    for mapname in dict.fromkeys([*by_map, *acs_by_map, *light_by_map, *lamp_by_map]):
        wanted = by_map.get(mapname, {})
        start, end = map_lump_range(lumps, mapname)
        members = {nm.upper(): blob for nm, blob in lumps[start:end]}
        if "TEXTMAP" not in members or "BEHAVIOR" not in members:
            raise SystemExit(f"{mapname}: missing TEXTMAP/BEHAVIOR in {WAD}")

        fixed, n = clear_specials(decode_textmap(members["TEXTMAP"]), wanted, mapname)
        if n != len(wanted):
            raise SystemExit(f"{mapname}: cleared {n} of {len(wanted)} sectors")

        lights = light_by_map.get(mapname, {})
        fixed, nlight = set_lightlevels(fixed, lights, mapname)
        if nlight != len(lights):
            raise SystemExit(f"{mapname}: relit {nlight} of {len(lights)} sectors")

        lamps = lamp_by_map.get(mapname, [])
        fixed, nlamp = add_light_things(fixed, lamps, mapname)
        if nlamp != sum(len(l.heights) * len(l.sectors) for l in lamps):
            raise SystemExit(f"{mapname}: added {nlamp} light things, expected more")

        behavior, nacs = (
            strip_acs_lights(members["BEHAVIOR"], acs_by_map[mapname], mapname)
            if mapname in acs_by_map
            else (members["BEHAVIOR"], 0)
        )

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
            elif upper == "BEHAVIOR":
                items.append((nm, behavior))
            elif upper == "SCRIPTS":
                continue  # ACS source; BEHAVIOR is the compiled lump and is kept
            else:
                items.append((nm, blob))
        if items[-1][0].upper() != "ENDMAP":
            items.append(("ENDMAP", b""))
        print(f"{mapname}: cleared {n} sectors, relit {nlight} sectors, "
              f"added {nlamp} light thing(s), "
              f"{nacs} acs call(s) ({', '.join(labels[mapname])})"
              f"{f', re-stripped {n3d} 3D-floor linedef(s)' if n3d else ''}")

    if activeAnims:
        items.append(("ANIMDEFS", animdefs_lump(activeAnims)))
        for a in activeAnims:
            print(f"ANIMDEFS: {a.first} pinned to {a.pin} "
                  f"({a.base} animation frozen)")

    write_wad(OUTWAD, items)
    maps = len({*by_map, *acs_by_map, *light_by_map, *lamp_by_map})
    print(f"wrote {OUTWAD} maps={maps} lumps={[nm for nm, _ in items]}")


if __name__ == "__main__":
    main()
