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
    """A sector whose only claim to being lit is a number.

    Named for the case it was written for -- painted light shafts -- but the family
    is broader than that, and the repair is identical for all of it: a sector given
    a lightlevel its room does not have, with nothing in the world casting it. Wall
    alcoves and door recesses on MAP13 are the same defect on a different shape.

    Note that tools/scan_fake_lightshafts.py only finds the SHAFT sub-case: its
    geometric test requires the sector to match its neighbour's floor and ceiling
    flats, which a recess never does. For anything else, widen the test to "above
    the map's emission threshold AND brighter than every neighbour" -- see the MAP13
    alcove entries in SHAFTS.

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
    # ---- PANEL SWEEP -----------------------------------------------------------
    # 29 elements, 36 sectors, 9 maps. Not found by eye: found by taking the fixtures
    # ALREADY confirmed from screenshots and repaired in this table, then looking for
    # the same ones everywhere else.
    #
    # The match set is DERIVED, not hand-listed. tools/scan_painted_light.py reads the
    # textures off this table's own enabled entries, then keeps only those used on
    # FEWER THAN 40 sectors game-wide. That cut is the whole safety of the sweep --
    # C53 appears on 597 sectors, C35 on 245, C10 on 234, C52 on 179. Matching those
    # would strip whole walls because a wall somewhere else was painted, which is "how
    # the level looks", not a defect. What survives is C921, C22, C911, C402/C403,
    # HDOR10, C74, C77, C79, H56, H66, H90, H116, HTRAC1, HELLAE, C19, C307B1 --
    # alcoves, recessed panels, door surrounds and trap faces.
    #
    # Every entry is above its map's emission threshold, at least 30 brighter than
    # EVERYTHING bordering it, and six sectors or fewer. to_light is the brightest
    # bordering sector, so no entry here can take a room below what surrounds it.
    #
    # Deliberately excluded: the switch / exit / monitor / teleporter / key families,
    # which are supposed to read as lit (stripping those would be the CRTRAKA mistake);
    # and one 28-sector region on MAP32 that matched HDOR10 -- a 28-sector region is not
    # a panel and wants looking at rather than sweeping.
    Shaft(
        "MAP12", [30], from_light=255, to_light=180,
        enabled=True,
        note="C402 panel x1 -- same fixture already confirmed and repaired elsewhere; see the PANEL SWEEP note above.",
    ),
    Shaft(
        "MAP12", [132], from_light=255, to_light=180,
        enabled=True,
        note="C402 panel x1 -- same fixture already confirmed and repaired elsewhere; see the PANEL SWEEP note above.",
    ),
    Shaft(
        "MAP14", [78], from_light=255, to_light=220,
        enabled=True,
        note="C74 panel x1 -- same fixture already confirmed and repaired elsewhere; see the PANEL SWEEP note above.",
    ),
    Shaft(
        "MAP14", [79], from_light=255, to_light=220,
        enabled=True,
        note="C74 panel x1 -- same fixture already confirmed and repaired elsewhere; see the PANEL SWEEP note above.",
    ),
    Shaft(
        "MAP14", [81], from_light=255, to_light=220,
        enabled=True,
        note="C74 panel x1 -- same fixture already confirmed and repaired elsewhere; see the PANEL SWEEP note above.",
    ),
    Shaft(
        "MAP16", [114], from_light=255, to_light=160,
        enabled=True,
        note="C22 panel x1 -- same fixture already confirmed and repaired elsewhere; see the PANEL SWEEP note above.",
    ),
    Shaft(
        "MAP16", [121], from_light=255, to_light=160,
        enabled=True,
        note="C911 panel x1 -- same fixture already confirmed and repaired elsewhere; see the PANEL SWEEP note above.",
    ),
    Shaft(
        "MAP16", [183], from_light=255, to_light=160,
        enabled=True,
        note="C911 panel x1 -- same fixture already confirmed and repaired elsewhere; see the PANEL SWEEP note above.",
    ),
    Shaft(
        "MAP16", [190], from_light=255, to_light=200,
        enabled=True,
        note="C22 panel x1 -- same fixture already confirmed and repaired elsewhere; see the PANEL SWEEP note above.",
    ),
    Shaft(
        "MAP16", [197], from_light=255, to_light=220,
        enabled=True,
        note="C921 panel x1 -- same fixture already confirmed and repaired elsewhere; see the PANEL SWEEP note above.",
    ),
    Shaft(
        "MAP16", [209], from_light=255, to_light=180,
        enabled=True,
        note="C921 panel x1 -- same fixture already confirmed and repaired elsewhere; see the PANEL SWEEP note above.",
    ),
    Shaft(
        "MAP18", [82, 83, 84], from_light=255, to_light=150,
        enabled=True,
        note="C307B1 panel x3 -- same fixture already confirmed and repaired elsewhere; see the PANEL SWEEP note above.",
    ),
    Shaft(
        "MAP18", [133], from_light=255, to_light=200,
        enabled=True,
        note="C22 panel x1 -- same fixture already confirmed and repaired elsewhere; see the PANEL SWEEP note above.",
    ),
    Shaft(
        "MAP18", [202], from_light=255, to_light=200,
        enabled=True,
        note="C921 panel x1 -- same fixture already confirmed and repaired elsewhere; see the PANEL SWEEP note above.",
    ),
    Shaft(
        "MAP18", [264], from_light=255, to_light=150,
        enabled=True,
        note="C911 panel x1 -- same fixture already confirmed and repaired elsewhere; see the PANEL SWEEP note above.",
    ),
    Shaft(
        "MAP18", [265], from_light=255, to_light=150,
        enabled=True,
        note="C911 panel x1 -- same fixture already confirmed and repaired elsewhere; see the PANEL SWEEP note above.",
    ),
    Shaft(
        "MAP20", [254], from_light=255, to_light=180,
        enabled=True,
        note="H116 panel x1 -- same fixture already confirmed and repaired elsewhere; see the PANEL SWEEP note above.",
    ),
    Shaft(
        "MAP21", [232], from_light=255, to_light=170,
        enabled=True,
        note="C921 panel x1 -- same fixture already confirmed and repaired elsewhere; see the PANEL SWEEP note above.",
    ),
    Shaft(
        "MAP21", [233, 234, 235], from_light=255, to_light=170,
        enabled=True,
        note="C921 panel x3 -- same fixture already confirmed and repaired elsewhere; see the PANEL SWEEP note above.",
    ),
    Shaft(
        "MAP21", [245], from_light=255, to_light=170,
        enabled=True,
        note="C921 panel x1 -- same fixture already confirmed and repaired elsewhere; see the PANEL SWEEP note above.",
    ),
    Shaft(
        "MAP21", [246], from_light=255, to_light=170,
        enabled=True,
        note="C921 panel x1 -- same fixture already confirmed and repaired elsewhere; see the PANEL SWEEP note above.",
    ),
    Shaft(
        "MAP21", [247], from_light=255, to_light=170,
        enabled=True,
        note="C921 panel x1 -- same fixture already confirmed and repaired elsewhere; see the PANEL SWEEP note above.",
    ),
    Shaft(
        "MAP22", [112], from_light=255, to_light=200,
        enabled=True,
        note="C74,C911 panel x1 -- same fixture already confirmed and repaired elsewhere; see the PANEL SWEEP note above.",
    ),
    Shaft(
        "MAP22", [122], from_light=255, to_light=160,
        enabled=True,
        note="C921 panel x1 -- same fixture already confirmed and repaired elsewhere; see the PANEL SWEEP note above.",
    ),
    Shaft(
        "MAP22", [123], from_light=255, to_light=160,
        enabled=True,
        note="C911 panel x1 -- same fixture already confirmed and repaired elsewhere; see the PANEL SWEEP note above.",
    ),
    Shaft(
        "MAP22", [153], from_light=255, to_light=180,
        enabled=True,
        note="C911 panel x1 -- same fixture already confirmed and repaired elsewhere; see the PANEL SWEEP note above.",
    ),
    Shaft(
        "MAP22", [158], from_light=255, to_light=190,
        enabled=True,
        note="C921 panel x1 -- same fixture already confirmed and repaired elsewhere; see the PANEL SWEEP note above.",
    ),
    # ---- MAP22 REVIEW ---------------------------------------------------------
    # 17 elements, 18 sectors -- the rest of MAP22's painted 255s, reviewed one at a
    # time rather than swept. Every one is above the map's threshold (240), at least
    # 30 brighter than EVERYTHING bordering it, and carries no authored `_e` -- so
    # none of them is a real emitter (checked against rt/mat_dev; the switch / exit /
    # monitor / teleporter / key families are excluded by the scanner already).
    #
    # NOTE the PANEL SWEEP's "fewer than 40 sectors game-wide" cut is NOT what admits
    # most of these, because scan_painted_light.py does not currently apply that cut at
    # all -- its "confirmed-fake" set includes C53 (597 sectors), C35 (245), C10 (234).
    # So its `# matches C10,C35` on sectors 124/125 is exactly the blind extrapolation
    # the note warns against, and is NOT the reason that entry is enabled here.
    # These are enabled on the per-element frame test instead, which is per-map
    # evidence and does not extrapolate. Only 275/276 (CYTRAKA, 27) and 277 (CDOR4,
    # 11) would also pass the rarity cut.
    #
    # to_light is the brightest bordering sector throughout, so the failure mode of a
    # wrong call here is "a panel stops standing out", never "a room goes black".

    # Door surrounds, tracks and recesses -- 1x16 to 384x64, the classic panel shape.
    Shaft(
        "MAP22", [266], from_light=255, to_light=180,
        enabled=True,
        note="CTRAK1 door track x1, 1x16u. A 64BigFire-class fixture sits 22u away, so under RT the track is lit for real -- the paint is a second sourceless copy of it (practices §31).",
    ),
    Shaft(
        "MAP22", [267], from_light=255, to_light=180,
        enabled=True,
        note="CTRAK1 door track x1, 1x16u -- twin of 266, same fixture 22u away.",
    ),
    Shaft(
        "MAP22", [271], from_light=255, to_light=160,
        enabled=True,
        note="C37,C921F sill x1, 128x1u. C921F is used on ONE sector game-wide; both neighbours (75, 82) sit at 160.",
    ),
    Shaft(
        "MAP22", [272], from_light=255, to_light=160,
        enabled=True,
        note="CBTRAKA,CDOR3 door surround x1, 128x16u; fixture 48u away, host 160.",
    ),
    Shaft(
        "MAP22", [273], from_light=255, to_light=180,
        enabled=True,
        note="CBTRAKA,CDOR3 door surround x1, 128x16u -- same doorway as 272.",
    ),
    Shaft(
        "MAP22", [275], from_light=255, to_light=170,
        enabled=True,
        note="CYTRAKA door surround x1 -- same fixture already confirmed and repaired at MAP16:114, MAP16:190; 27 sectors game-wide, so this one also clears the PANEL SWEEP rarity cut.",
    ),
    Shaft(
        "MAP22", [276], from_light=255, to_light=180,
        enabled=True,
        note="CYTRAKA door surround x1 -- twin of 275, same MAP16 precedent.",
    ),
    Shaft(
        "MAP22", [277], from_light=255, to_light=190,
        enabled=True,
        note="CDOR4 door surround x1 -- same fixture already confirmed and repaired at MAP10:189; 11 sectors game-wide, clears the rarity cut.",
    ),
    Shaft(
        "MAP22", [34], from_light=255, to_light=180,
        enabled=True,
        note="C24,C37 recess x1, 64x64u cut into sector 33 at 180. C24 is 9 sectors game-wide.",
    ),
    Shaft(
        "MAP22", [35], from_light=255, to_light=180,
        enabled=True,
        note="C24,C37 recess x1, 64x64u -- twin of 34, same host sector 33.",
    ),
    Shaft(
        "MAP22", [139], from_light=255, to_light=180,
        enabled=True,
        note="C18,C24 recess x1, 64x64u; sole neighbour 138 at 180.",
    ),
    Shaft(
        "MAP22", [141], from_light=255, to_light=180,
        enabled=True,
        note="C18,C24 recess x1, 64x64u; sole neighbour 140 at 180.",
    ),
    Shaft(
        "MAP22", [18], from_light=255, to_light=220,
        enabled=True,
        note="C3F strip x1, 384x64u; sole neighbour 17 at 220. C3F is 7 sectors game-wide and has no _e -- it is panelling, not a fixture.",
    ),

    # Room-sized painted areas -- the 'baked lit environment' half. Each is a whole
    # room at 255 whose ONLY neighbour is the corridor around it at 160-180, with no
    # light-bearing actor inside it and no sky ceiling to be moonlit through. Nothing
    # in the room can be casting this, which is the §5 test: it is baked shading, not
    # a light. After the repair each room sits level with the corridor it opens off.
    Shaft(
        "MAP22", [91], from_light=255, to_light=160,
        enabled=True,
        note="C2 room x1, 384x312u, ceiling CASF203 (not sky). Sole neighbour 28 at 160; nearest light-bearing actor 206u away, i.e. outside the room.",
    ),
    Shaft(
        "MAP22", [124, 125], from_light=255, to_light=160,
        enabled=True,
        note="C10,C35 room x2, 256x256u. Neighbours 118 and 126 both at 160; nearest light-bearing actor 1663u away -- there is nothing on this side of the map to cast it. NOT enabled on the C10/C35 texture match, which is too common to sweep on (234/245 sectors).",
    ),
    Shaft(
        "MAP22", [127], from_light=255, to_light=160,
        enabled=True,
        note="WFALL01 waterfall room x1, 256x320u; sole neighbour 126 at 160, nearest fixture 1697u. Liquid falls are deliberately not auto-emitters here (pitfall 20), so nothing lights this room -- the 255 is pure baked shading.",
    ),
    Shaft(
        "MAP22", [172], from_light=255, to_light=180,
        enabled=True,
        note="C35,C3F hall x1, 576x384u -- the largest one. Sole neighbour 90 at 180; nearest light-bearing actor 160u away, outside it.",
    ),
    # ---- MAP22 COURTYARD ------------------------------------------------------
    # The open courtyard: 2456x1648u, 19 sectors at 255 (17 of them F_SKY1) plus
    # sector 1 at 230. This is what the level22-1/-2 screenshots show -- flat, evenly
    # bright grey walls with dark ground at their base, under a dim red sky.
    #
    # It was initially left alone here on the grounds that a sky ceiling means the
    # moon lights it for real. That is wrong on this map twice over:
    #
    #   - MAP22's moon is off ENTIRELY, disc and light, in RT_MOON_PRESETS. It is a
    #     fire-sky map; the burning dome does the lighting, arriving from every
    #     azimuth at once (rt_presets.cpp, "The five fire-sky maps").
    #   - That dome light is real, so the paint is a SECOND, sourceless copy of it --
    #     §31 again, the same shape as the 64BigFire inside the MAP12 cages. A sky
    #     ceiling is evidence the paint is REDUNDANT, not that it is earned.
    #
    # And the paint is not passive: the earlier repairs on this map dropped the median
    # 200 -> 180 and the threshold 240 -> 220, so at 255/230 these sectors are now
    # ABOVE it and SELF-EMIT (rt_sector_emis). That self-emission is the flat glow.
    #
    # to_light is 200, which is not a guess: the brightest bordering sector is 106,
    # itself an open-sky F_SKY1 sector at 200 that the scanner does NOT flag. The
    # courtyard's own neighbour is the reference for what an unpainted open-sky sector
    # looks like here. 200 also sits below the 220 threshold, so the self-emission
    # stops, while the courtyard stays the brightest thing outside it -- lit by the
    # dome rather than by itself.
    #
    # Split in two because the scanner refuses a mixed from_light ("[230, 255] --
    # split first"): a single entry would have to lie about one of the two levels.
    Shaft(
        "MAP22", [0, 5, 6, 7, 8, 9, 100, 101, 102, 103, 104, 105, 107, 108, 109,
                  254, 255, 263, 278],
        from_light=255, to_light=200,
        enabled=True,
        note="Open courtyard x19 (17 F_SKY1) -- painted 255 under a fire sky that already lights it. to_light 200 matches bordering open-sky sector 106 and drops it under the 220 emission threshold.",
    ),
    Shaft(
        "MAP22", [1], from_light=230, to_light=200,
        enabled=True,
        note="Courtyard x1 at 230, the one non-sky sector in the same region -- levelled with the rest of the courtyard.",
    ),
    # General trap this exposed: every repair lowers the median, which lowers the
    # threshold, which can bring a fresh region above it. Re-scanning after a fix does
    # not give you the same map with less paint on it, so the scan has to be re-run
    # until it is quiet rather than once.
    #
    # ---- and the two below are that trap actually biting -----------------------
    # Reported as screen/coloredtexturelevel22yesOrno.png: "the whole floor is
    # overlight bright sticking out, pillars on it are properly in the dark".
    #
    # That description is the tell, and it is worth keeping. A real light cannot
    # brighten a floor and leave the pillars standing ON it dark. Only a SURFACE-LOCAL
    # term can, because RTGL1 emissive lights the surface it is on and nothing else
    # (practices §12) -- the same signature already written up in rt_draw.cpp's
    # l_worldemissive comment about MAP09's self-glowing courtyard.
    #
    # The sector under the crosshair (17, L220) was innocent: lightlevel feeds
    # l_worldemissive and nothing else, and at exactly the threshold it returns 0.
    # The culprit was sector 41, one room over, and it is a regression from the
    # repairs ABOVE: they dropped MAP22's median 200 -> 180, so the threshold fell
    # 240 -> 220, and sector 41 at L240 crossed it. It emitted NOTHING before this
    # file touched the map, and 0.57x rt_sector_emis afterwards, over 448x448 units
    # of open-sky floor.
    #
    # The scanners cannot catch this class: scan_painted_light only reports elements
    # at least 30 brighter than their boundary, and 41's brightest neighbour is 220,
    # a delta of 20. Checking the (new_threshold, old_threshold] band after every
    # repair is the check that does catch it -- MAP23 and MAP24 came back empty.
    Shaft(
        "MAP22", [41], from_light=240, to_light=220,
        enabled=True,
        note="448x448u open-sky floor, F_SKY1. NOT painted-bright originally -- it is levelled with its brightest neighbour (274, also 220) purely to put it back under the emission threshold that this file's own repairs lowered. Delta 20, so no scanner reports it.",
    ),
    Shaft(
        "MAP22", [85], from_light=255, to_light=200,
        enabled=True,
        note="64x64u CTEL1 pad, no wall textures at all -- which is why scan_painted_light skips it (it keys on sidedef textures and has none to key on). At L255 against a 220 threshold it was emitting at FULL strength. Checked for a teleport destination first and there is none, so it is an alcove like MAP13:126, not a pad that is meant to read as lit.",
    ),

    Shaft(
        "MAP23", [255, 256, 292, 326], from_light=255, to_light=160,
        enabled=True,
        note="C22 panel x4 -- same fixture already confirmed and repaired elsewhere; see the PANEL SWEEP note above.",
    ),

    # ---- MAP23 REVIEW ---------------------------------------------------------
    # 48 elements, 72 sectors -- the level23panellit.png case: a carved relief panel
    # glowing in a pitch-black room with the wall it is bolted to left black. A real
    # fixture cannot light a panel and leave its own wall dark, so the panel is
    # self-emitting (rt_sector_emis) rather than lit.
    #
    # The whole set was checked the same way as MAP22, and it is unusually clean:
    #   - NONE of the 48 has a sky ceiling, so the MAP22 courtyard mistake (paint that
    #     turned out to be redundant against real fire-sky dome light) cannot recur.
    #   - NONE carries an authored _e in rt/mat_dev, asserted while generating these,
    #     so none is a real emitter being stripped.
    #   - All are at 255 against a 140-200 host, and 43 of the 48 are a single sector.
    #     Sizes run 1x16 to 64x64: door tracks, trim bands, recesses and panels.
    #
    # Two are worth naming because they are not panel-shaped:
    #   [71, 129..134, 144]   448x128u, 8 sectors, host 160, nothing within 649u.
    #   [34, 258, 259, 290]   832x688u, a room, host 200 -- but a light-bearing actor
    #                         sits 72u away, so RT lights it for real and the paint is
    #                         the redundant second copy (§31).
    # Entries generated from the scanner rather than transcribed, so the sector lists
    # and to_light values are the scan's own output.
    Shaft(
        "MAP23", [71, 129, 130, 131, 132, 133, 134, 144], from_light=255, to_light=160,
        enabled=True,
        note="H127,H130,H24 x8, 448x128u; nearest light-bearing actor 649u.",
    ),
    Shaft(
        "MAP23", [116, 159, 160, 161, 170, 227, 228], from_light=255, to_light=180,
        enabled=True,
        note="C53,H131,H31 x7, 24x448u; nearest light-bearing actor 638u.",
    ),
    Shaft(
        "MAP23", [76, 87, 88, 328, 329], from_light=255, to_light=180,
        enabled=True,
        note="C53,H131,H31 x5, 24x64u; nearest light-bearing actor 409u.",
    ),
    Shaft(
        "MAP23", [77, 78, 85, 86, 111], from_light=255, to_light=180,
        enabled=True,
        note="C53,H131,H31 x5, 24x64u; nearest light-bearing actor 409u.",
    ),
    Shaft(
        "MAP23", [34, 258, 259, 290], from_light=255, to_light=200,
        enabled=True,
        note="C53,H119,H15 x4, 832x688u; nearest light-bearing actor 72u.",
    ),
    Shaft(
        "MAP23", [73], from_light=255, to_light=140,
        enabled=True,
        note="C53 x1, 1x16u; nearest light-bearing actor 564u.",
    ),
    Shaft(
        "MAP23", [82], from_light=255, to_light=180,
        enabled=True,
        note="C53 x1, 48x48u; nearest light-bearing actor 23u.",
    ),
    Shaft(
        "MAP23", [83], from_light=255, to_light=180,
        enabled=True,
        note="C53 x1, 48x48u; nearest light-bearing actor 23u.",
    ),
    Shaft(
        "MAP23", [94], from_light=255, to_light=160,
        enabled=True,
        note="H531 x1, 128x52u; nearest light-bearing actor 56u.",
    ),
    Shaft(
        "MAP23", [96], from_light=255, to_light=160,
        enabled=True,
        note="H531 x1, 128x128u; nearest light-bearing actor 56u.",
    ),
    Shaft(
        "MAP23", [98], from_light=255, to_light=160,
        enabled=True,
        note="H531 x1, 56x128u; nearest light-bearing actor 56u.",
    ),
    Shaft(
        "MAP23", [100], from_light=255, to_light=160,
        enabled=True,
        note="H531 x1, 56x128u; nearest light-bearing actor 56u.",
    ),
    Shaft(
        "MAP23", [112], from_light=255, to_light=140,
        enabled=True,
        note="C53,CYTRAKA x1, 1x16u; nearest light-bearing actor 564u.",
    ),
    Shaft(
        "MAP23", [120], from_light=255, to_light=140,
        enabled=True,
        note="C53,CYTRAKA x1, 1x16u; nearest light-bearing actor 564u.",
    ),
    Shaft(
        "MAP23", [122], from_light=255, to_light=160,
        enabled=True,
        note="H112,H15 x1, 64x8u; nearest light-bearing actor 37u.",
    ),
    Shaft(
        "MAP23", [123], from_light=255, to_light=160,
        enabled=True,
        note="H112,H15 x1, 64x8u; nearest light-bearing actor 229u.",
    ),
    Shaft(
        "MAP23", [125], from_light=255, to_light=160,
        enabled=True,
        note="H112,H261 x1, 64x8u; nearest light-bearing actor 417u.",
    ),
    Shaft(
        "MAP23", [126], from_light=255, to_light=160,
        enabled=True,
        note="H112,H261 x1, 8x64u; nearest light-bearing actor 453u.",
    ),
    Shaft(
        "MAP23", [127], from_light=255, to_light=160,
        enabled=True,
        note="H112,H261 x1, 64x8u; nearest light-bearing actor 316u.",
    ),
    Shaft(
        "MAP23", [128], from_light=255, to_light=160,
        enabled=True,
        note="H112,H261 x1, 8x64u; nearest light-bearing actor 253u.",
    ),
    Shaft(
        "MAP23", [137], from_light=255, to_light=200,
        enabled=True,
        note="C53 x1, 8x32u; nearest light-bearing actor 40u.",
    ),
    Shaft(
        "MAP23", [141], from_light=255, to_light=200,
        enabled=True,
        note="C53,H131 x1, 32x8u; nearest light-bearing actor 40u.",
    ),
    Shaft(
        "MAP23", [152], from_light=255, to_light=200,
        enabled=True,
        note="C53 x1, 32x8u; nearest light-bearing actor 40u.",
    ),
    Shaft(
        "MAP23", [153], from_light=255, to_light=200,
        enabled=True,
        note="C53,CBTRAKA x1, 16x8u; nearest light-bearing actor 0u.",
    ),
    Shaft(
        "MAP23", [154], from_light=255, to_light=200,
        enabled=True,
        note="C53,CYTRAKA x1, 8x16u; nearest light-bearing actor 0u.",
    ),
    Shaft(
        "MAP23", [155], from_light=255, to_light=200,
        enabled=True,
        note="C53 x1, 16x8u; nearest light-bearing actor 0u.",
    ),
    Shaft(
        "MAP23", [156], from_light=255, to_light=200,
        enabled=True,
        note="C53 x1, 16x8u; nearest light-bearing actor 0u.",
    ),
    Shaft(
        "MAP23", [157], from_light=255, to_light=200,
        enabled=True,
        note="C53,CYTRAKA x1, 8x16u; nearest light-bearing actor 0u.",
    ),
    Shaft(
        "MAP23", [158], from_light=255, to_light=200,
        enabled=True,
        note="C53,CBTRAKA x1, 16x8u; nearest light-bearing actor 0u.",
    ),
    Shaft(
        "MAP23", [172], from_light=255, to_light=180,
        enabled=True,
        note="H21 x1, 64x64u; nearest light-bearing actor 233u.",
    ),
    Shaft(
        "MAP23", [173], from_light=255, to_light=180,
        enabled=True,
        note="H21 x1, 64x64u; nearest light-bearing actor 233u.",
    ),
    Shaft(
        "MAP23", [191], from_light=255, to_light=180,
        enabled=True,
        note="C35,H991 x1, 64x16u; nearest light-bearing actor 390u.",
    ),
    Shaft(
        "MAP23", [192], from_light=255, to_light=180,
        enabled=True,
        note="C35,H991 x1, 64x16u; nearest light-bearing actor 264u.",
    ),
    Shaft(
        "MAP23", [193], from_light=255, to_light=180,
        enabled=True,
        note="C53 x1, 32x8u; nearest light-bearing actor 608u.",
    ),
    Shaft(
        "MAP23", [194], from_light=255, to_light=180,
        enabled=True,
        note="C53 x1, 32x8u; nearest light-bearing actor 553u.",
    ),
    Shaft(
        "MAP23", [220], from_light=255, to_light=140,
        enabled=True,
        note="C53,CBTRAKA x1, 1x16u; nearest light-bearing actor 565u.",
    ),
    Shaft(
        "MAP23", [221], from_light=255, to_light=140,
        enabled=True,
        note="C53 x1, 1x16u; nearest light-bearing actor 564u.",
    ),
    Shaft(
        "MAP23", [222], from_light=255, to_light=140,
        enabled=True,
        note="C53,CBTRAKA x1, 1x16u; nearest light-bearing actor 566u.",
    ),
    Shaft(
        "MAP23", [229], from_light=255, to_light=140,
        enabled=True,
        note="C53,CYTRAKA x1, 1x16u; nearest light-bearing actor 564u.",
    ),
    Shaft(
        "MAP23", [231], from_light=255, to_light=140,
        enabled=True,
        note="C53 x1, 32x8u; nearest light-bearing actor 430u.",
    ),
    Shaft(
        "MAP23", [232], from_light=255, to_light=140,
        enabled=True,
        note="C53 x1, 1x16u; nearest light-bearing actor 564u.",
    ),
    Shaft(
        "MAP23", [233], from_light=255, to_light=160,
        enabled=True,
        note="C53 x1, 32x8u; nearest light-bearing actor 1302u.",
    ),
    Shaft(
        "MAP23", [257], from_light=255, to_light=160,
        enabled=True,
        note="H15 x1, 64x64u; nearest light-bearing actor 640u.",
    ),
    Shaft(
        "MAP23", [260], from_light=255, to_light=140,
        enabled=True,
        note="C53,CBTRAKA x1, 1x16u; nearest light-bearing actor 566u.",
    ),
    Shaft(
        "MAP23", [262], from_light=255, to_light=180,
        enabled=True,
        note="C53,H991 x1, 64x12u; nearest light-bearing actor 81u.",
    ),
    Shaft(
        "MAP23", [272], from_light=255, to_light=140,
        enabled=True,
        note="C53 x1, 8x32u; nearest light-bearing actor 0u.",
    ),
    Shaft(
        "MAP23", [273], from_light=255, to_light=140,
        enabled=True,
        note="C53 x1, 8x32u; nearest light-bearing actor 0u.",
    ),
    Shaft(
        "MAP23", [287], from_light=255, to_light=180,
        enabled=True,
        note="C53,H31 x1, 64x8u; nearest light-bearing actor 309u.",
    ),
    Shaft(
        "MAP24", [72], from_light=255, to_light=170,
        enabled=True,
        note="HELLAE panel x1 -- same fixture already confirmed and repaired elsewhere; see the PANEL SWEEP note above.",
    ),

    # ---- MAP24 REVIEW ---------------------------------------------------------
    # 13 elements, 14 sectors. Reported as screen/acslevel24.png -- a freestanding
    # block lit evenly on all three visible faces in a black room -- and confirmed
    # from the game rather than the screenshot:
    #
    #   whatsthat: sector 68  lightlevel 255  tag 0  middle texture 'H12'
    #              threshold 200 -> ABOVE: this surface SELF-EMITS
    #              brightest neighbour: sector 13 at 170  (delta +85)
    #
    # tag 0, so the block is static paint and not the ACS the filename guessed at --
    # though MAP24 does carry real ACS light calls, handled in SCRIPTED below.
    #
    # screen/lightertexturelevel24.png is the same defect seen from the other side:
    #     whatsthat: sector 54  lightlevel 140 -> below: not self-emitting
    #                brightest neighbour: sector 67 at 255  (delta -115)
    # Sector 54 is innocent; its neighbour 67 is the emitter, and [66, 67] below is
    # the entry that fixes it. A surface can be washed by the sector NEXT to it.
    #
    # SECTOR 87 IS DELIBERATELY EXCLUDED. It is 64x64 with a CTEL1 floor and ceiling
    # and looks exactly like the panels above, but a teleport DESTINATION thing
    # (type 14) stands in it -- it is a working teleporter, and teleporters are meant
    # to read as lit. Its pulse is Light_Glow on tag 20, also left alone below.
    #
    # That test is worth keeping: is_emitter_family() is applied to SIDEDEF textures
    # only, so a pad whose identity is its FLAT is invisible to it. Auditing every
    # enabled Shaft for a teleport destination found exactly one bad case in the whole
    # table, MAP33:46 (SPORT1 + a type-14 dest), which predates this review and is
    # noted rather than changed here. The CTEL1 sectors on MAP23, MAP13 and MAP11 all
    # came back clean -- no destination -- so they are alcoves, not pads, and their
    # repairs stand.
    Shaft(
        "MAP24", [66, 67], from_light=255, to_light=140,
        enabled=True,
        note="H127 x2, 252x100u; nearest light-bearing actor 108u.",
    ),
    Shaft(
        "MAP24", [19], from_light=255, to_light=170,
        enabled=True,
        note="HELLAA x1, 192x192u; nearest light-bearing actor 534u. sky 1/1.",
    ),
    Shaft(
        "MAP24", [22], from_light=255, to_light=170,
        enabled=True,
        note="HELLAA x1, 192x192u; nearest light-bearing actor 1181u. sky 1/1.",
    ),
    Shaft(
        "MAP24", [34], from_light=220, to_light=170,
        enabled=True,
        note="H129,H55,H931 x1, 896x896u; nearest light-bearing actor 2009u.",
    ),
    Shaft(
        "MAP24", [50], from_light=255, to_light=140,
        enabled=True,
        note="H127 x1, 512x640u; nearest light-bearing actor 254u.",
    ),
    Shaft(
        "MAP24", [51], from_light=255, to_light=140,
        enabled=True,
        note="H113,H21 x1, 600x600u; nearest light-bearing actor 457u. sky 1/1.",
    ),
    Shaft(
        "MAP24", [68], from_light=255, to_light=170,
        enabled=True,
        note="H12 x1, 296x304u; nearest light-bearing actor 246u. sky 1/1.",
    ),
    Shaft(
        "MAP24", [77], from_light=255, to_light=160,
        enabled=True,
        note="H11 x1, 64x64u; nearest light-bearing actor 1313u.",
    ),
    Shaft(
        "MAP24", [78], from_light=255, to_light=160,
        enabled=True,
        note="H11 x1, 64x64u; nearest light-bearing actor 1187u.",
    ),
    Shaft(
        "MAP24", [79], from_light=255, to_light=160,
        enabled=True,
        note="H11 x1, 64x64u; nearest light-bearing actor 927u.",
    ),
    Shaft(
        "MAP24", [102], from_light=255, to_light=160,
        enabled=True,
        note="H52 x1, 480x608u; nearest light-bearing actor 1144u.",
    ),
    Shaft(
        "MAP24", [120], from_light=255, to_light=160,
        enabled=True,
        note="H52 x1, 66x66u; nearest light-bearing actor 1091u.",
    ),
    Shaft(
        "MAP24", [122], from_light=255, to_light=160,
        enabled=True,
        note="H36 x1, 28x40u; nearest light-bearing actor 2u.",
    ),
    # The same defect as the shafts below, on a different shape of sector: a wall
    # element painted bright while the room it sits in is not. No special, no ACS --
    # both were surveyed for MAP13 and neither covers these (scan_light_specials 13
    # reports sequence=0, blink=0, and its three ACS calls are on tags 7/30/31).
    # scan_fake_lightshafts misses them too, on purpose: its geometric test requires
    # the sector to match its neighbour's flats, which an alcove or a door recess
    # never does. They were found by widening that test to "above the emission
    # threshold AND >=30 brighter than every neighbour".
    #
    # Judged the way the MAP05 pylons were: is there anything in the room the light
    # could be coming from? For both of these, no -- and the screenshots show it,
    # because the wall immediately around each one is black while the element itself
    # is lit. A real fixture cannot light a recess and not its own wall.
    Shaft(
        "MAP13", [162, 170, 171, 172, 173], from_light=255, to_light=170,
        enabled=True,
        note="THE REPORTED ONE (screen/fakelitlevel13wallelement.png). C921 wall "
             "alcoves -- 64x16 and 16x64 recesses holding the C92 relief, the tall "
             "one with a pentagram at its foot -- in the L170 halls. At 255 they sit "
             "above MAP13's 200 threshold, so the recess and its own jambs emit while "
             "the C53 wall around them stays dark, which is exactly what was "
             "reported: the alcove interior AND the side of the alcove lit, nothing "
             "else. Torches exist elsewhere on this map but the nearest is 654-1461 "
             "units from most of these, and a torch that could light one of them "
             "would light the wall beside it too.",
    ),
    Shaft(
        "MAP13", [163, 164, 165, 188, 189, 190], from_light=255, to_light=180,
        enabled=True,
        note="The same C921 alcoves in the L180 halls -- same element, same defect, "
             "different host room, so a different resting value. Split from the "
             "group above only because to_light differs; stripping one set and not "
             "the other would leave the same fixture lit in one corridor and dark in "
             "the next.",
    ),
    # Found by tools/scan_painted_light.py rather than by screenshot. Enabled here
    # because the survey's fixture column answers the triage question outright: the
    # nearest light-bearing thing to any of them is 1040-1189 units away, and the
    # fixture set is derived from the mod's own GLDEFS+DECORATE (39 placeable actors
    # that carry lights), not guessed. Nothing within a thousand units can light a
    # 64-unit element and leave the wall beside it black.
    # MAP11 (screen/map11_stillfakelight.png). Reported as "still fake light", assumed
    # to be another ACS call -- it is not. MAP11's five ACS light calls are four literal
    # Light_Fade in script 671, whose TYPE IS 12 = the lightning script, i.e. the storm
    # flashing tags 1 and 2 to 255 and back on each strike. That is the map's authored
    # weather and stays. The panel in the screenshot is the static kind: a HELLA* face
    # recess painted bright, its jambs lit, the wall around it black.
    #
    # Enabled where the nearest light-bearing thing is 279u or further. Held back:
    # sector 210 (fixture 40u) and 152 (133u), close enough that the paint may be
    # reinforcing a real fixture, and 96 (160u) for the same reason.
    Shaft(
        "MAP12", [94, 95, 96, 97, 98, 99, 100, 101, 102, 119, 229],
        from_light=255, to_light=180,
        enabled=True,
        note="THE REPORTED ONE (screen/fakelitcave_level12.png). The cave, C402/C403 "
             "rough rock -- eleven CONNECTED sectors all painted 255 inside a map "
             "whose median is 180 and whose threshold is 220, bordered on every side "
             "by 180. The whole region emits, which is why the rock reads evenly lit "
             "with no falloff anywhere while the floor tiles in front stay dark.\n"
             "\n"
             "Found by clustering, not by the neighbour test. A contiguous painted "
             "REGION has no internal darker neighbour -- only its boundary sectors do "
             "-- so 'brighter than every neighbour' sees a handful of edge cases and "
             "misses the body of it. Connected components of above-threshold sectors, "
             "compared against what borders the component, is the test that finds "
             "this shape.\n"
             "\n"
             "The candles in that shot are real 64WallTorch/candle things and are "
             "untouched: they have proper falloff pools on the right-hand wall, which "
             "is exactly what the painted rock does not.",
    ),
    Shaft(
        "MAP12", [247, 250, 251, 252, 253, 254, 255, 260, 261, 262, 263, 264, 265],
        from_light=255, to_light=180,
        enabled=True,
        note="THE REPORTED ONE (screen/fakelitpanel_level12.png). The C53 rust panels "
             "with the stud dots, painted 255 on grey stone walls at 180. Four TRIPLES "
             "plus one single, and the triples' geometry is the screenshot: a tall "
             "centre flanked by two short ones --\n"
             "\n"
             "    250 (34x12, z 212..252)  251 (40x12, z 172..368)  252 (34x12, z 212..252)\n"
             "        short                     TALL                     short\n"
             "\n"
             "repeated at (-2107..-2021,-970), (-2411..-2325,-970), (-277..-363,-566) "
             "and (-667..-581,-566). 247 is the lone taller panel at (-2312,180).\n"
             "\n"
             "Held back by the survey's fixture column -- something light-bearing sits "
             "45u away -- and that test was wrong again for the same reason it was "
             "wrong on MAP11's face panel: the wall these are mounted ON is at 180 and "
             "stays dark. A light 45 units from a 34x12 panel cannot brighten the "
             "panel and not the stone it is bolted to.",
    ),
    Shaft(
        "MAP10", [4, 5, 186, 187, 212], from_light=255, to_light=220,
        enabled=True,
        note="THE REPORTED ONE (screen/map10fakelit.png), and the same area as the very "
             "first screenshot of this whole effort, level10bakedlighttexture.png. The "
             "brick tower in the middle of the courtyard: five NESTED sectors all at "
             "(384,256), floor 0 to ceiling 512, C301/C53 brick, every one painted 255 "
             "inside a courtyard at 220 -- above MAP10's 220 threshold, so the tower "
             "self-emits from top to bottom with no falloff anywhere.\n"
             "\n"
             "Five sectors rather than one because the tower is built as a stack of "
             "concentric rings (496, 384, 376 and a 64x64 cap at z=384). Only 212 and 4 "
             "touch the courtyard; 5, 186 and 187 border nothing but each other, so a "
             "per-sector 'brighter than every neighbour' test sees two of the five.",
    ),
    Shaft(
        "MAP33", [46], from_light=255, to_light=150,
        enabled=True,
        note="Reported via `whatsthat` (screen/map33fake.png): the 64x64 TITLEA alcove "
             "at (1952,1184), painted 255 against sector 47 at 150 -- delta +105, the "
             "widest on this map. Checked that TITLEA is not a repeated fixture before "
             "fixing the instance: it appears on exactly two sectors, and the other (61) "
             "is already at 200, below MAP33's 210 threshold.\n"
             "\n"
             "Also checked that MAP33 is not the actual title screen. Its MAPINFO name "
             "is 'Titlemap' (D64HUSTR_33), but there is no `titlemap` directive anywhere "
             "in the lump, so it is an ordinary playable level and relighting it cannot "
             "darken the menu.",
    ),
    Shaft(
        "MAP25", [19, 25, 26, 57, 58, 59, 60, 74], from_light=200, to_light=140,
        enabled=True,
        note="The brightness half of the MAP25 lamp alcoves -- see the TINTS entry for "
             "the full write-up; the COLOUR is what was reported and what actually "
             "shows. This entry changes nothing under RT and is here for consistency "
             "only: 200 is not above MAP25's threshold of 200 (the test is strictly "
             "greater), so these never self-emitted and `whatsthat` said so. Included "
             "because the instruction was to make them like the rest, and the rest is "
             "sectors 7 and 76 -- the same SFLATAS lamp ceiling, left by the author at "
             "140 with the room's own blue. Dropping 200 to the hosts' 140 makes the "
             "eight painted alcoves byte-for-byte the same fixture as the two "
             "unpainted ones.",
    ),
    # "despite the flame, the surround is fake lit" -- and it is. Same finding as the
    # MAP12 cages: a fixture INSIDE the sector makes the paint redundant, because RT
    # lights that fire or torch for real (RT_UploadFlameLights: intensity, flicker,
    # falloff). The painted 255 is a second, flat, sourceless copy laid over it, and it
    # is what makes the surround read as evenly lit with no falloff while the room
    # beyond stays dark. The flames and torches are THINGS and are untouched -- this
    # tool only rewrites sector lightlevel and colour, never the thing list.
    Shaft(
        "MAP21", [43, 44, 129], from_light=255, to_light=180,
        enabled=True,
        note="C65 alcoves with a 64BigFire in each, host 180. The fire stays and keeps "
             "lighting them; only the paint goes.",
    ),
    Shaft(
        "MAP21", [45, 46, 195, 251, 252], from_light=255, to_light=200,
        enabled=True,
        note="The same C65 fire alcoves whose host room is 200. Split from the group "
             "above only because to_light differs -- same fixture, and they must not "
             "end up lit differently from one another.",
    ),
    Shaft(
        "MAP21", [65, 66, 67, 106, 108, 180, 181, 182, 278],
        from_light=255, to_light=170,
        enabled=True,
        note="C53/C56/C57 torch bays, each holding a 64TorchLongYellow, host 170. Three "
             "connected groups of the same construction.",
    ),
    Shaft(
        "MAP21", [156, 157], from_light=255, to_light=180,
        enabled=True,
        note="Two more 64TorchLongYellow bays, C53, host 180.",
    ),
    Shaft(
        "MAP21", [90, 91, 92, 93, 102, 103, 126, 127],
        from_light=255, to_light=200,
        enabled=True,
        note="The C62 demon-relief panels (screen/level21nofix.png), EIGHT of them, all "
             "16x64 or 64x16, all painted 255 against sector 0 at 200, arranged "
             "symmetrically around the room at (+/-296,+/-128) and (+/-160,+/-264).\n"
             "\n"
             "First pass fixed only sector 93 -- the one `whatsthat` happened to be "
             "aimed at -- and the very next probe came back as 102, the same fixture "
             "four feet away, still lit. A repeated fixture has to be repaired as a "
             "SET: query the texture across the whole map and take every instance that "
             "shares the relationship, exactly as the C921 alcoves and the C52 cages "
             "were done. Fixing the instance rather than the set just moves the "
             "screenshot.",
    ),
    Shaft(
        "MAP21", [216, 217], from_light=255, to_light=200,
        enabled=True,
        note="Reported via `whatsthat`, and a good example of why the frame test has to "
             "run on ELEMENTS rather than sectors: aimed at 216 it reports 'brightest "
             "neighbour 217 at 255, delta +0', which looks like nothing to fix. 217 is "
             "its own 64x16 inner sector, also 255, also tag 46. The pair is one "
             "element, and what the ELEMENT borders is sector 19 at 200.\n"
             "\n"
             "Checked before stripping, because the pair carries a CMPSW23B switch and "
             "tag 46 could plausibly have been driven: MAP21's ACS light calls target "
             "tags 32, 33, 36, 45, 47, 48, 49, 50 and 51 -- never 46 -- and no linedef "
             "references it either. The 255 is static paint. The switch keeps its own "
             "light; that is engine-side now (see the switch-lights work) and nothing "
             "here touches things.",
    ),
    Shaft(
        "MAP10", [189], from_light=255, to_light=180,
        enabled=True,
        note="Reported via `whatsthat`: 48x128 CDOR4 door recess at (1208,256), painted "
             "255 inside sectors 218/231 at 180. Two 64WallTorchRed stand 89u away and "
             "KEEP THEIR LIGHT -- they are things, RT lights them for real, and nothing "
             "here touches them. What goes is the second, flat copy of that light "
             "painted onto the sector, which is what made the recess read as lit while "
             "the wall around it stayed dark.",
    ),
    Shaft(
        "MAP10", [78], from_light=255, to_light=140,
        enabled=True,
        note="Reported via `whatsthat`: 72x816 C53/C89 run at (-820,256), painted 255 "
             "against a host of 140 -- the widest gap on this map at +115. Same story "
             "as 189: two wall torches 80u off, untouched; only the paint goes.",
    ),
    Shaft(
        "MAP10", [18], from_light=255, to_light=200,
        enabled=True,
        note="The courtyard floor in the same shot -- CASF106 moss, 1090x1218 under "
             "F_SKY1, painted 255 inside sectors 2 and 17 at 200. This is the "
             "star-shaped bright patch visible in both MAP10 screenshots.",
    ),
    Shaft(
        "MAP12", [150, 151], from_light=255, to_light=180,
        enabled=True,
        note="THE CAGES (screen/fakelitcage_level12.png), identified by `whatsthat` "
             "after two wrong guesses from the screenshot. 80x80 enclosures at "
             "(-184,-968) and (-184,-568), C53 + SPACEBN, painted 255 inside sector 0 "
             "at 180.\n"
             "\n"
             "Each one CONTAINS a 64BigFire, and that is why I passed over them twice: "
             "the survey's fixture column read 0u and I treated a fixture inside the "
             "sector as justifying the paint. It is the opposite. Under RT that fire "
             "is a real light -- RT_UploadFlameLights gives it intensity, flicker and "
             "falloff -- so the painted 255 is not the fixture's light, it is a SECOND "
             "copy of it, flat and sourceless, laid over the real one. Dropping to the "
             "room's 180 leaves the cage lit by its own fire and nothing else, which "
             "is the whole point of the port.\n"
             "\n"
             "A fixture inside the sector makes the paint REDUNDANT under a path "
             "tracer, not warranted. The same argument applies to sectors 31, 32 and "
             "116 on this map (a 64TorchLongYellow in each, all at 255 over 180); they "
             "are left for a look rather than swept, being outdoor torch pedestals "
             "rather than a reported defect.",
    ),
    Shaft(
        "MAP12", [256, 257, 258, 259], from_light=255, to_light=180,
        enabled=True,
        note="THE OTHER REPORTED ONE (screen/fakelitcage_level12.png). The four C52 "
             "barred cages, 48x48 each, one at each corner of the same area: "
             "(-1952,-16), (-784,-16), (-784,-1568), (-1952,-1568). Painted 255 with "
             "180 all round them, so the barred panel glows and the structure it is "
             "set into stays black. Same fixture four times, so they move together.",
    ),
    Shaft(
        "MAP18", [2, 258, 110, 259], from_light=255, to_light=220,
        enabled=True,
        note="THE REPORTED ONE (screen/level18_stillfakelight.png): 'floor still fake "
             "lit, the borders around it also, and the borders above'. All three are "
             "ONE sector's lightlevel. The sky courtyards are painted 255 inside "
             "sector 1, the walkway that surrounds them, at 220 -- and MAP18's "
             "threshold is 250, so the courtyard emits and the walkway does not.\n"
             "\n"
             "Sector 2 carries C10 and C19 on its sidedefs, which is why one number "
             "produced three complaints: CASF106 is the mossy floor, C10 the tiled "
             "band on the 8-unit step around it ('the borders around it'), and C19 "
             "the frieze of winged figures on the 64-unit band above the walkway "
             "roof ('the borders above'). A lower and an upper texture on the same "
             "two-sided lines, both drawn at the courtyard's light.\n"
             "\n"
             "Listed as FOUR sectors because each courtyard is a nested pair -- 2 is a "
             "one-unit ring around 258, 110 around 259, same flats and heights "
             "throughout. The inner sector's only neighbour is its own ring, so it "
             "looks like it has no darker host and a neighbour test alone skips it. "
             "Nested same-flat sectors are one element and move together.",
    ),
    Shaft(
        "MAP11", [152], from_light=255, to_light=160,
        enabled=True,
        note="THE REPORTED ONE (screen/map11_stillfakelight.png). H66, the demon face "
             "panel -- 160x64 at (0,672), painted 255 while sector 151, the frame it "
             "is set INTO and its only neighbour, sits at 160. MAP11's threshold is "
             "220, so the face emits and its own frame does not.\n"
             "\n"
             "Held back on the first pass because a light-bearing thing stands 133u "
             "away, and that was the wrong test: the other three H66 panels on this "
             "map (180, 181, 182) sit at 160/180 and do not emit, so 255 here is not "
             "how this fixture is lit anywhere else. THE FRAME IS THE TEST -- a real "
             "light cannot brighten a recess and leave the surface it is cut into "
             "dark, whatever its distance.",
    ),
    Shaft(
        "MAP11", [123], from_light=255, to_light=200,
        enabled=True,
        note="C53 recess. Nearest fixture 279u.",
    ),
    Shaft(
        "MAP11", [148], from_light=255, to_light=180,
        enabled=True,
        note="HELLAE face panel. Nearest fixture 336u.",
    ),
    Shaft(
        "MAP11", [190], from_light=255, to_light=200,
        enabled=True,
        note="HELLAB face panel -- the one most likely in the screenshot, 672u from "
             "any fixture at all.",
    ),
    # The arrow-shooter walls, reported from play. Both were in the survey's
    # left-alone column because a fixture stands 230-313 units away, close enough that
    # the paint might have been reinforcing something real. It is not: these are the
    # faces the darts come out of, and the face is lit while the wall it is set into
    # is dark.
    Shaft(
        "MAP13", [89], from_light=220, to_light=180,
        enabled=True,
        note="C77 -- the dart ports, a grid of star-shaped holes. Nearest fixture "
             "313u.",
    ),
    Shaft(
        "MAP13", [124, 125], from_light=255, to_light=180,
        enabled=True,
        note="H90 -- the bladed relief face on the same trap walls, 192x20 and "
             "20x192 runs. Nearest fixture 230u.",
    ),
    Shaft(
        "MAP13", [57, 59], from_light=255, to_light=180,
        enabled=True,
        note="C35 trim runs, 256x32 and 256x128. Nearest fixture 1040u.",
    ),
    Shaft(
        "MAP13", [71, 72], from_light=255, to_light=180,
        enabled=True,
        note="C74 relief recesses -- the tall skeleton panel. Nearest fixture 1167u.",
    ),
    Shaft(
        "MAP13", [73, 74], from_light=255, to_light=180,
        enabled=True,
        note="C79 relief recesses, the sibling of the C74 pair above and part of the "
             "same wall arrangement. Nearest fixture 1189u.",
    ),
    Shaft(
        "MAP13", [144, 208], from_light=220, to_light=160,
        enabled=True,
        note="C911 panels. Nearest fixture 1147u.",
    ),
    Shaft(
        "MAP13", [96, 97, 98], from_light=255, to_light=180,
        enabled=True,
        note="THE REPORTED ONE (screen/morefakelitlevel13moving.png). The H116 "
             "ledges -- three long thin runs, 32x1344 and 1344x32, clad in the "
             "ribbed chevron beam -- painted 255 inside rooms at 180. A 1344-unit "
             "beam glowing evenly along its entire length with black on both sides "
             "of it is about as clearly sourceless as this defect gets: no falloff "
             "anywhere, and no fixture at either end. Carries no special.",
    ),
    Shaft(
        "MAP13", [35], from_light=220, to_light=180,
        enabled=True,
        note="THE OTHER REPORTED ONE (screen/fakelittexturearounddoorlevel13.png). "
             "The HDOR10 door recess -- HDOR10A mirrored four ways into the big "
             "symmetric panel with the star. 80x272, painted 220 inside a room at "
             "180, so it clears the 200 threshold and the door, its jambs and the "
             "lintel over it all self-emit as one pale slab. The torches flanking it "
             "are real and were reported as good: they are things, they light the "
             "C22 demon panels correctly, and nothing here touches them.",
    ),
    Shaft(
        "MAP13", [32], from_light=220, to_light=200,
        enabled=True,
        note="The second HDOR10 door of the same design, host room 200. Not "
             "reported, included so the two doors do not end up looking different "
             "from each other. 200 is not above the threshold -- the test is "
             "strictly greater -- so this stops emitting as well.",
    ),
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
    # MAP24, script 669 (type OPEN, so it runs at load, unconditionally). Found by the
    # opcode-pair scan and independently decoded by scan_light_specials.py -- two
    # methods agreeing is why these go in the exact-argument Scripted family rather
    # than ScriptedComputed.
    Scripted(
        "MAP24", 669, 114, (19, 255, 200, 35), enabled=True,
        note="THE REPORTED ONE (screen/level24anotheracs.png). Glow 255<->200 on tag "
             "19 = sectors 19 and 22, two 192x192 open-sky areas with nothing within "
             "534u. A sourceless breath over an outdoor area, the MAP13 shape. Note "
             "the SHAFTS entries alone would not have fixed this: Light_Glow drives "
             "the sector's lightlevel at RUNTIME and overrides whatever is stored, so "
             "lowering the paint without stripping the call changes nothing on screen.",
    ),
    Scripted(
        "MAP24", 669, 114, (20, 255, 180, 35), enabled=False,
        note="SURVEYED, NOT STRIPPED. Glow 255<->180 on tag 20 = sectors 73 and 87. "
             "Sector 87 has a teleport destination (thing type 14) standing in it, so "
             "this is a working teleporter's authored pulse and stripping it would be "
             "the CRTRAKA mistake. Sector 73 (HTELA, no destination) shares the tag "
             "and rides along; it is left alone rather than break the teleporter.",
    ),
    # MAP13 script 669 OPEN. Found only after building rt_tex_probe, which showed the
    # CTEL alcove's lightlevel sweeping 202..255 at runtime while the map data said 180
    # -- proof the animation was neither the texture nor the stored lightlevel. An
    # earlier hand-rolled scan of this BEHAVIOR reported "no light calls on tag 30" and
    # was simply wrong: it searched for a dword equal to the special number, when the
    # encoding is PUSHnBYTES args... LSPECn special -- which acs_call_signature in this
    # very file already spells out. The correct scan finds three calls in MAP13.
    Scripted(
        "MAP13", 669, 114, (30, 255, 200, 35), enabled=True,
        note="THE REPORTED ONE (screen/level13badlitstartred.png). Glow 255<->200 "
             "over 35 tics on tag 30 = sector 126, the 64x64 CTEL alcove. This is "
             "the 'texture fade in/out' that three rounds of texture work chased: "
             "rt_tex_probe showed sector_emis tracking it 0.013 -> 0.350 in step "
             "with the lightlevel, so the flats were self-emitting on a sine. With "
             "the call stripped the sector sits at the 180 the Shaft entry gives "
             "it, under MAP13's 200 threshold, and stops emitting entirely -- the "
             "alcove is then lit only by the two PointLightPulse things in it.",
    ),
    Scripted(
        "MAP13", 669, 115, (31, 255, 180), enabled=False,
        note="SURVEYED, NOT STRIPPED. Flicker 255<->180 on tag 31, a different "
             "sector and not what was reported. Listed so the next reader knows "
             "MAP13's OPEN script has more in it than the one call above, and can "
             "judge it on its own evidence rather than rediscovering it.",
    ),
    Scripted(
        "MAP13", 4, 114, (7, 255, 220, 35), enabled=False,
        note="SURVEYED, NOT STRIPPED. Glow 255<->220 on tag 7, in script 4 rather "
             "than the OPEN script. Same reasoning as tag 31.",
    ),
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


class ScriptedComputed:
    """An ACS Light_* call whose ARGUMENTS ARE COMPUTED, not literal.

    The Scripted family matches a call by its exact byte signature -- PUSHnBYTES, the
    literal args, LSPECn, the special. That only works when the compiler could fold
    every argument into a byte. A call like

        Light_Fade(tag, random(220, 255), tics)

    pushes its arguments with preceding instructions instead, so there is no literal
    run to match and signature matching cannot see it AT ALL. Two of these on MAP13
    survived four separate scans of the same lump, including one that decoded the
    4-byte LSPECnDIRECT form, because every one of them keyed on the arguments.

    They are found by scanning for the OPCODE PAIR instead -- LSPECn (3+n) followed by
    the special number -- which is present regardless of where the arguments came from.

    The repair cannot be the Scripted family's either. NOPing the two-byte call would
    leave its n arguments on the VM stack, and in a looping script that grows without
    bound. Instead the SPECIAL NUMBER is overwritten with 0: LSPECn still executes and
    still pops exactly n arguments, P_ExecuteSpecial gets special 0 and does nothing.
    One byte per call, stack balanced, lump length unchanged.
    """

    def __init__(self, mapname: str, script: int, special: int, argc: int,
                 count: int, enabled: bool, note: str):
        self.mapname = mapname
        self.script = script
        self.special = special
        self.argc = argc
        self.count = count      # how many such calls the script is expected to contain
        self.enabled = enabled
        self.note = note


SCRIPTED_COMPUTED = [
    # The same fixture, in the same OPEN script, on thirteen more maps. Found by the
    # opcode-pair scan once MAP13 showed what to look for: 14 maps carry
    # Light_Fade(argc=3) inside script 669, 35 calls in total, and script 669 is type
    # OPEN on every single one of them -- it runs at map load, unconditionally, forever.
    #
    # Scoped tightly on purpose, to Light_Fade with THREE arguments inside script 669:
    #
    #   - Light_Stop (67 of the 147 computed calls game-wide) is the OPPOSITE operation.
    #     It turns an effect off, and stripping it would leave that effect running.
    #     Never touch it.
    #   - Light_Fade / Light_ChangeToValue elsewhere (scripts 2-30) are triggered by
    #     gameplay -- doors, switches, events -- not installed at load. Those are
    #     authored moments and are left alone.
    #   - Other argument counts in 669 are a different call shape and are not assumed
    #     to be the same fixture without looking.
    #
    # The builder asserts the exact count per map, so if any of these is wrong the
    # build fails instead of zeroing an unrelated special.
    ScriptedComputed(
        "MAP10", 669, 113, 3, 3, enabled=True,
        note="Light_Fade x3 in the OPEN script — same sourceless sweep as MAP13.",
    ),
    ScriptedComputed(
        "MAP12", 669, 113, 3, 10, enabled=True,
        note="Light_Fade x10 in the OPEN script — the heaviest in the game. MAP12 also "
             "carries the 20-wedge sequence ring (CHAINS, still disabled pending "
             "playtest), so expect this map to change noticeably.",
    ),
    ScriptedComputed(
        "MAP15", 669, 113, 3, 2, enabled=True,
        note="Light_Fade x2 in the OPEN script — same sourceless sweep as MAP13.",
    ),
    ScriptedComputed(
        "MAP17", 669, 113, 3, 1, enabled=True,
        note="Light_Fade x1 in the OPEN script — same sourceless sweep as MAP13.",
    ),
    ScriptedComputed(
        "MAP18", 669, 113, 3, 2, enabled=True,
        note="Light_Fade x2 in the OPEN script — same sourceless sweep as MAP13.",
    ),
    ScriptedComputed(
        "MAP19", 669, 113, 3, 1, enabled=True,
        note="Light_Fade x1 in the OPEN script — same sourceless sweep as MAP13.",
    ),
    ScriptedComputed(
        "MAP20", 669, 113, 3, 1, enabled=True,
        note="Light_Fade x1 in the OPEN script — same sourceless sweep as MAP13.",
    ),
    ScriptedComputed(
        "MAP21", 669, 113, 3, 3, enabled=True,
        note="Light_Fade x3 in the OPEN script — same sourceless sweep as MAP13.",
    ),
    ScriptedComputed(
        "MAP22", 669, 113, 3, 1, enabled=True,
        note="Light_Fade x1 in the OPEN script — same sourceless sweep as MAP13.",
    ),
    ScriptedComputed(
        "MAP23", 669, 113, 3, 2, enabled=True,
        note="Light_Fade x2 in the OPEN script — same sourceless sweep as MAP13.",
    ),
    ScriptedComputed(
        "MAP24", 669, 113, 3, 1, enabled=True,
        note="Light_Fade x1 in the OPEN script — same sourceless sweep as MAP13.",
    ),
    ScriptedComputed(
        "MAP33", 669, 113, 3, 2, enabled=True,
        note="Light_Fade x2 in the OPEN script — same sourceless sweep as MAP13.",
    ),
    ScriptedComputed(
        "MAP34", 669, 113, 3, 4, enabled=True,
        note="Light_Fade x4 in the OPEN script — same sourceless sweep as MAP13.",
    ),
    ScriptedComputed(
        "MAP13", 669, 113, 3, 2,
        enabled=True,
        note="THE REPORTED ONE (screen/level13fakelitblinkpillars.png, and the wider "
             "'multiple textures in that area' report). Two Light_Fade calls in the "
             "OPEN script, arguments computed, driving tags 29 and 10 -- seven "
             "sectors: 0, 43, 94, 179, 210, 211, 243. rt_lightlevel_watch caught them "
             "sweeping 221..255 continuously, in lockstep, forever.\n"
             "\n"
             "Nothing in the map file explains them: no sector special, no linedef "
             "Light_*, no ACS call on tag 29 or 10 findable by signature, and zero "
             "light THINKERS running at level load (Light_Fade's thinker is created "
             "per call by the loop, so a dump at load sees none). The pillar sides and "
             "walls carry tag 29 and the ground does not, which is exactly why some "
             "surfaces in that courtyard pulsed and others did not.",
    ),
]


def strip_acs_computed_lights(
    behavior: bytes, wanted: list, mapname: str
) -> tuple[bytes, int]:
    """Neutralise Light_* calls with computed args by zeroing the special number."""
    if not wanted:
        return behavior, 0
    out = bytearray(behavior)
    done = 0
    for w in wanted:
        lo, hi = _acs_script_range(behavior, w.script, mapname)
        op = 3 + w.argc
        found = [
            i
            for i in range(lo, min(hi, len(out)) - 1)
            if out[i] == op and out[i + 1] == w.special
        ]
        if len(found) != w.count:
            raise SystemExit(
                f"{mapname} script {w.script}: expected {w.count} LSPEC{w.argc} -> "
                f"special {w.special} call(s), found {len(found)} — map data changed, "
                f"refusing to patch blind."
            )
        for i in found:
            out[i + 1] = 0      # special 0: pops the args, does nothing
            done += 1
    return bytes(out), done


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


class Tint:
    """A sector painted a different COLOUR from its room to fake a light's colour.

    The seventh family, and the second half of the painted-light problem. A Shaft
    fakes a light's BRIGHTNESS with lightlevel; this fakes its COLOUR with the Doom
    64 per-sector colormap (`lightcolor` plus `color1`..`color5`).

    Both halves reach RT, but by different routes. Lightlevel is dropped and
    re-derived, which is why a painted shaft shows up as self-emission. The colour
    is NOT dropped -- rt_sector_tint_albedo carries the sector hue into albedo at
    full strength on purpose, so a red corridor stays red. The consequence is that a
    sector painted warm inside a cold room puts a hard-edged colour change across a
    continuous floor, at the sector boundary, with no gradient and nothing casting
    it.

    Reported on MAP13's door: "that door floor texture still has a harsh split of
    colour. is it the texture colour that was changed to simulate light in front of
    the door?" -- yes, exactly that (2026-08-10).

    The repair copies every colour field from a DONOR sector, normally the room the
    element sits in, so the split disappears and the warmth comes from the torches
    that are actually there. `from_lightcolor` is asserted before the write, like
    every other family here, so a map edit fails the build instead of recolouring
    the wrong sector.

    Do NOT run this over a colour globally. Doom 64's per-sector colour is real art
    direction and most of it is deliberate: MAP13 has 15 sectors sharing the door's
    warm salmon, and only the two door recesses are wrong -- the rest are rooms that
    are simply warm. The test is the same as everywhere else in this file: a small
    element painted unlike the room it sits in, with no fixture to justify it.
    """

    def __init__(self, mapname: str, sectors: list[int], donor: int,
                 from_lightcolor: int, enabled: bool, note: str):
        self.mapname = mapname
        self.sectors = sectors
        self.donor = donor
        self.from_lightcolor = from_lightcolor
        self.enabled = enabled
        self.note = note


# Every colour field a Doom 64 UDMF sector carries in this WAD. color1..color5 are the
# per-surface set (floor / ceiling / wall top / wall bottom / things); lightcolor is the
# one RT reads through Colormap.LightColor. All of them are copied together -- taking
# lightcolor alone would leave the floor and the walls disagreeing.
TINT_FIELDS = ("lightcolor", "color1", "color2", "color3", "color4", "color5")


TINTS = [
    Tint(
        "MAP13",
        [47, 48, 49, 50, 51, 52, 61, 62, 63, 64, 65, 66, 67, 68, 69, 93],
        donor=46, from_lightcolor=0xFEE16D,
        enabled=True,
        note="THE REPORTED ONE (screen/level13fakelitblinkpillars.png). The H119 "
             "pillars in the outdoor courtyard -- fifteen 64x64 and 64x512 sectors "
             "plus one C77 -- painted warm yellow rgb(254,225,109) inside sector 46, "
             "a 2944x2944 open courtyard at cold blue rgb(146,194,254) under the "
             "moon.\n"
             "\n"
             "H119 itself is dull mottled brown-purple stone. The gold-brass look is "
             "ENTIRELY the sector colour: pillars lit warm, by nothing, in a night "
             "courtyard whose only real light is a cool moon. Their lightlevel is "
             "200, which is not above MAP13's threshold, so no amount of brightness "
             "work would ever have touched them -- this one is purely the colour "
             "half of the painted-light problem, and the reason TINTS exists as its "
             "own family.",
    ),
    Tint(
        "MAP25",
        [19, 25, 26, 57, 58, 59, 60, 74],
        donor=6, from_lightcolor=0xF0F08C,
        enabled=True,
        note="THE REPORTED ONE (screen/faketexturelitfloor_level25.png): 'just a "
             "texture on the floor under the ceiling light that has been color "
             "changed'. Exactly that, and the map data agrees on every count.\n"
             "\n"
             "Eight identical 64x64 alcoves, each one a shallow recess whose ceiling "
             "is SFLATAS -- a panel with FOUR LAMP BULBS painted on it, the white "
             "blobs at the top of the screenshot. The fixture is real. What is not "
             "real is the floor: SFLATAM on both sides of the line, same flat, same "
             "height, unbroken, with the alcove painted warm yellow rgb(240,240,140) "
             "inside host rooms at cold blue rgb(80,120,200). That lands as a "
             "hard-edged colour change across a continuous diamond-plate floor -- the "
             "gold tiles among the grey ones in the shot -- with no gradient and "
             "nothing casting it. It is the author drawing the lamp's pool of light "
             "onto the ground.\n"
             "\n"
             "This one is PURELY the colour half. `whatsthat` reported it outright: "
             "lightlevel 200 against MAP25's threshold of 200, 'below: not "
             "self-emitting'. The test is strictly greater, so these never emitted "
             "and no amount of brightness work would have touched them -- the same "
             "shape as the MAP13 courtyard pillars, and the reason TINTS exists "
             "separately from SHAFTS.\n"
             "\n"
             "The clinching evidence is on the same map: sectors 7 and 76 carry the "
             "SAME SFLATAS lamp ceiling and were left at 140 and rgb(80,120,200), "
             "i.e. unpainted. So warm-and-bright is not how this fixture is lit "
             "anywhere else in the level, which is the frame test from MAP11's H66 "
             "panel applied to a repeated element. Donor 6 is the host of the "
             "reported alcove; all eight hosts (5, 6, 12, 13, 29, 30, 55, 56) carry "
             "the identical blue, so one donor serves the set and the eight cannot "
             "end up looking different from each other.\n"
             "\n"
             "The bulbs themselves are untouched and the room keeps its real lamps -- "
             "thirteen 64LampTechLongHang (1015) and ten 1016 stand 120-176u from "
             "these alcoves and carry GLDEFS pointlights.",
    ),
    Tint(
        "MAP13", [32, 35], donor=15, from_lightcolor=0xFE9276,
        enabled=True,
        note="THE REPORTED ONE (screen/fakelittexturearounddoorlevel13.png, the "
             "floor). Both HDOR10 door recesses are painted warm salmon "
             "rgb(254,146,118) while the halls they open off -- sectors 14 and 15, "
             "2112x2112 and 512x2112 -- are cold blue rgb(89,164,255). The floor "
             "texture is CASFL27 on both sides of the line, so the change is purely "
             "the sector colour and lands as a hard edge across one continuous "
             "floor. It is the author drawing torchlight onto the ground in front of "
             "the door.\n"
             "\n"
             "Under RT the torches flanking that door are real lights and already "
             "warm the floor themselves, so the paint is now double-counted as well "
             "as hard-edged. Donor 15 is the hall; 32 opens off 14, which carries "
             "the identical blue, so one donor serves both and the two doors stay "
             "consistent with each other.",
    ),
]


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

    RADIUS IS NOT BRIGHTNESS, and getting that backwards cost a round. The engine
    turns a light thing's map radius into RT intensity as

        intensity = hi * rt_dynlight_intensity * blink      (capped at rt_dynlight_max)
        if radius > rt_dynlight_rsoft:  intensity *= (rsoft / radius)^2

    The cap bites almost immediately (16 * 40 = 640 > 500), so above `rsoft` the
    only term still varying is an INVERSE SQUARE in radius -- i.e. past that point
    a bigger radius makes the light DIMMER, and because the roll-off tracks the
    CURRENT radius, the pulse also runs backwards: dimmest at the crest.

    Measured, with the launcher's scale 40 / cap 500 / rsoft 20 / minradius 16:

        arg3/arg4     trough -> crest
          144/60          56 ->     10     dim and inverted   <- was shipped
           48/20         288 ->     87     inverted
           32/24         133 ->    195     inverted mid-cycle
           20/17         120 ->    500     correct, 4.2x

    So both radii belong at or below `rt_dynlight_rsoft`. Two constraints pin the
    values almost exactly:

      - `lo` >= rt_dynlight_minradius (16) or the light is CULLED at the bottom of
        the cycle and the fixture blinks OFF instead of dimming.
      - `hi` <= rt_dynlight_rsoft (20) or the roll-off inverts the pulse.

    which leaves the 16..20 band. There is no way to ask for a crest DIMMER than
    the 500 cap without re-entering the roll-off, because minradius 16 x scale 40
    already exceeds it -- if a fixture needs to be subtler, that is a job for
    rt_dynlight_intensity or a smaller rt_dynlight_minradius, not for this table.
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
        heights=[16, 96], color=(255, 0, 0), hi=20, lo=17, period_tics=140,
        enabled=False,
        note="SUPERSEDED by rt_spin_panels, kept because the values are still the "
             "worked example for this table. These PULSED, and the pulsing was "
             "imitating the ACS Light_Glow that turned out to be the actual defect: "
             "once that was stripped there was nothing left for a fade to represent. "
             "The artwork depicts a light that TRAVELS at constant brightness -- the "
             "eight rim gems carry the same luminance set shifted one frame each, "
             "total 891 in every frame -- and a map thing cannot express that, since "
             "things do not move and GZDoom has no per-thing phase offset to fake it "
             "with eight of them. So the engine orbits one constant light instead, "
             "reading its bearing from the current animation frame. Original note "
             "follows. CTEL1 is an 8-frame telemetry panel whose small "
             "red gems ramp up and down; the panel is on BOTH the floor and the "
             "ceiling of sector 126, a 64x64 alcove (floor 8, ceiling 120). Two "
             "lights, one 16 above the floor panel and one 16 under the ceiling "
             "one, so each reads as coming off its own fixture rather than one "
             "light floating in the middle of the shaft. period 140 tics = 4.0s, "
             "matching 'slow'. Radii 20/17 put the crest at the 500 cap and the "
             "trough at 120, a clean 4.2x rise -- see the class docstring for why "
             "they are NOT larger: the first two passes used 48/20 and then 144/60 "
             "on the assumption that radius means brightness, and both were dimmer "
             "than 20/17 AND ran the pulse backwards. With the alcove's painted 255 "
             "dropped to the room's 180 and the tag-30 ACS glow stripped, the "
             "surface no longer lights itself and these carry the whole fixture. "
             "Everything tried on the TEXTURE side -- _e mask, "
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
        enabled=False,
        note="WRONG FIX, KEPT AS THE RECORD. Freezing this animation threw away a "
             "feature to remove a defect, because the animation is two things at "
             "once and only one of them is baked light. Measured per gem cluster: "
             "eight 4-pixel clusters around the rim carry the same luminance set "
             "cyclically shifted by one frame, total 891 in EVERY frame -- a chase "
             "light turning around the panel, motion rather than lighting. One "
             "13-pixel blob dead centre runs 44 to 1166 with no rotation at all, "
             "and is by itself the entire 2.20x brightness envelope of the tile. "
             "Pinning to one frame stopped the fade and the rotation together. The "
             "fade is now removed at the source instead, by holding the CENTRE blob "
             "at its darkest across all eight frames and leaving the ring alone: "
             "tools/make_ctel_static_center.py -> d64r-ctel-fix.wad. "
             "Original note follows. CTEL1..8, 4 tics each, is a telemetry panel whose "
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


def set_sector_colors(
    text: str, wanted: list, mapname: str
) -> tuple[str, int]:
    """Copy every colour field from each Tint's donor sector onto its targets.

    Two passes over the sector blocks: read the donors first, then write. Doing it
    in one pass would depend on the donor happening to appear before its targets in
    the lump, which is not something the map format promises.
    """
    if not wanted:
        return text, 0

    blocks = re.findall(r"(?ms)^sector\s*\{(.*?)\}", text)

    def field(body: str, key: str) -> str | None:
        m = re.search(rf"\b{key}\s*=\s*(-?\d+)\s*;", body)
        return m.group(1) if m else None

    donors: dict[int, dict[str, str]] = {}
    for t in wanted:
        if t.donor >= len(blocks):
            raise SystemExit(f"{mapname}: no donor sector {t.donor}")
        donors[t.donor] = {
            k: v for k in TINT_FIELDS if (v := field(blocks[t.donor], k)) is not None
        }
        if not donors[t.donor]:
            raise SystemExit(
                f"{mapname} sector {t.donor}: no colour fields to donate"
            )

    targets: dict[int, tuple] = {}
    for t in wanted:
        for si in t.sectors:
            targets[si] = (t.from_lightcolor, t.donor)

    index = -1
    changed = 0

    def rewrite(m: re.Match[str]) -> str:
        nonlocal index, changed
        index += 1
        if index not in targets:
            return m.group(0)
        body = m.group(1)
        expect, donor = targets[index]
        got = field(body, "lightcolor")
        if got is None or ( int( got ) & 0xFFFFFF ) != ( expect & 0xFFFFFF ):
            raise SystemExit(
                f"{mapname} sector {index}: expected lightcolor "
                f"0x{expect & 0xFFFFFF:06X}, found "
                f"{'none' if got is None else f'0x{int(got) & 0xFFFFFF:06X}'} — map "
                f"data changed, refusing to recolour blind."
            )
        for k, v in donors[donor].items():
            if re.search(rf"\b{k}\s*=\s*-?\d+\s*;", body):
                body = re.sub(rf"\b{k}\s*=\s*-?\d+\s*;", f"{k} = {v};", body)
            else:
                body = body.rstrip() + f"\n{k} = {v};\n"
        changed += 1
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
    activeTints = [t for t in TINTS if t.enabled]
    activeComputed = [c for c in SCRIPTED_COMPUTED if c.enabled]
    if (not active and not activeBlinks and not activeScripted
            and not activeShafts and not activeLamps and not activeAnims
            and not activeTints):
        raise SystemExit("nothing enabled — nothing to build")

    # sector index -> the specials it may currently carry, per map
    SEQ_FAMILY = ( 1, 2, 3, 4 )
    by_map: dict[str, dict[int, tuple[int, ...]]] = {}
    labels: dict[str, list[str]] = {}

    # After `labels` exists — this list feeds the per-map report line.
    comp_by_map: dict[str, list] = {}
    for c in activeComputed:
        comp_by_map.setdefault(c.mapname, []).append(c)
        labels.setdefault(c.mapname, []).append(
            f"acs-computed script {c.script} special {c.special} x{c.count}")
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
    tint_by_map: dict[str, list] = {}
    for ti in activeTints:
        tint_by_map.setdefault(ti.mapname, []).append(ti)
        labels.setdefault(ti.mapname, []).append(
            f"tint {ti.sectors} <- sector {ti.donor}")

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
    for mapname in dict.fromkeys(
        [*by_map, *acs_by_map, *light_by_map, *lamp_by_map, *tint_by_map, *comp_by_map]
    ):
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

        tints = tint_by_map.get(mapname, [])
        fixed, ntint = set_sector_colors(fixed, tints, mapname)
        if ntint != sum(len(x.sectors) for x in tints):
            raise SystemExit(f"{mapname}: recoloured {ntint} sectors, expected more")

        lamps = lamp_by_map.get(mapname, [])
        fixed, nlamp = add_light_things(fixed, lamps, mapname)
        if nlamp != sum(len(l.heights) * len(l.sectors) for l in lamps):
            raise SystemExit(f"{mapname}: added {nlamp} light things, expected more")

        behavior, nacs = (
            strip_acs_lights(members["BEHAVIOR"], acs_by_map[mapname], mapname)
            if mapname in acs_by_map
            else (members["BEHAVIOR"], 0)
        )
        behavior, ncomp = strip_acs_computed_lights(
            behavior, comp_by_map.get(mapname, []), mapname
        )
        nacs += ncomp

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
              f"recoloured {ntint} sector(s), added {nlamp} light thing(s), "
              f"{nacs} acs call(s) ({', '.join(labels[mapname])})"
              f"{f', re-stripped {n3d} 3D-floor linedef(s)' if n3d else ''}")

    if activeAnims:
        items.append(("ANIMDEFS", animdefs_lump(activeAnims)))
        for a in activeAnims:
            print(f"ANIMDEFS: {a.first} pinned to {a.pin} "
                  f"({a.base} animation frozen)")

    write_wad(OUTWAD, items)
    maps = len({*by_map, *acs_by_map, *light_by_map, *lamp_by_map, *tint_by_map,
                *comp_by_map})
    print(f"wrote {OUTWAD} maps={maps} lumps={[nm for nm, _ in items]}")


if __name__ == "__main__":
    main()
