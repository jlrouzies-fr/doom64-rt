"""Build MAP94/MAP95, the PILLAR LAB: MAP01's pre-exit pillar, alone in a room.

    python tools/build_pillar_lab.py
    python tools/build_pillar_lab.py --room 640 --light 150

    -> Doom64-Retribution/d64rpillarlab.wad     (MAP94 dark, MAP95 lit)

WHY THIS EXISTS. `rt_pillar_chase` was built, verified live in the log
(`chased=6`, multipliers swinging 0.35..1.00 every lap) and showed NOTHING on
screen. That pairing -- the instrument says it is working, the eye says it is
not -- is the shape of a light being uploaded INTO SOLID GEOMETRY, and MAP01's
hall is the worst room in the game to prove it in: twelve wall strips, a bulb
lattice, faux panels, a moon and a level's worth of emissive GI, any of which
could be what you are actually looking at.

This is the same fixture with nothing else in the map.

THE GEOMETRY IS COPIED, NOT APPROXIMATED, and that is the whole point. The
pillar is not a block. Sector 131 of MAP01 is a RING:

  * an OUTER octagon at r~32 of sixteen TWO-SIDED edges onto the hall, and
  * an INNER octagon at r=24 of eight ONE-SIDED BLOCKING walls -- four SFLATAQ
    bulb panels at 0/90/180/270 degrees, four SPACEAA bevels between them --
  * around a VOID core. The space inside r=24 is not a sector at all.

The ring's floor is 80 and its ceiling 144 inside a room that runs 0..192, so
from outside you read one solid column: a SPACEAG plinth, the bulb-panel band,
a SPACEAB cap.

A BLOCK WOULD NOT REPRODUCE THE BUG. `sector_t::centerspot` is a BOUNDING-BOX
MIDPOINT and a sector is not required to contain it; for this ring it lands in
the hole. So the wall-strip walk's "nudge the emitter 2 units toward the sector
centre" pushed all six of the pillar's lights into the void core, fully
occluded. Rebuild the pillar as a convex block and centerspot lands in real
sector air, the nudge is correct, and the map you built to demonstrate the bug
quietly does not have it.

The vertex ring below is MAP01's own, translated so the pillar's axis is at the
room centre. Re-derive it from the WAD any time; script 12, the ACS the chase
replaces, is found with:

    python tools/scan_light_specials.py 1 --chains
"""

import argparse
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "Doom64-Retribution" / "d64rpillarlab.wad"

PANEL = "SFLATAQ"   # the 4x4 bulb array: the four faces that get lights
BEVEL = "SPACEAA"   # the four corner faces between them; no bulbs painted

# INNER octagon, COUNTER-CLOCKWISE, as offsets from the pillar axis.
#
# The winding is load-bearing. Doom's front sidedef is the RIGHT of v1->v2, so a
# counter-clockwise inner loop puts every front sidedef on the OUTSIDE of the
# octagon -- facing the ring, void behind. That is what makes these walls
# one-sided, and it is the fact the fix in rt_lights_fixtures.cpp uses to decide
# which way is "off the wall" once centerspot has been ruled out.
INNER = [
    ((24, -16), (24, 16), PANEL),     #   0 deg  east
    ((24, 16), (16, 24), BEVEL),      #  45
    ((16, 24), (-16, 24), PANEL),     #  90 deg  north
    ((-16, 24), (-24, 16), BEVEL),    # 135
    ((-24, 16), (-24, -16), PANEL),   # 180 deg  west
    ((-24, -16), (-16, -24), BEVEL),  # 225
    ((-16, -24), (16, -24), PANEL),   # 270 deg  south
    ((16, -24), (24, -16), BEVEL),    # 315
]

# OUTER octagon, also counter-clockwise, sixteen edges. Front (right) is the
# ROOM and back is the ring -- the reverse of the inner loop, because here the
# ring is on the inside. Sixteen rather than eight because MAP01 splits each
# straight run in two, and edge counts are what the debug dumps are read against.
OUTER = [
    (32, -16), (32, 0), (32, 16), (24, 24), (16, 32), (0, 32),
    (-16, 32), (-24, 24), (-32, 16), (-32, 0), (-32, -16), (-24, -24),
    (-16, -32), (0, -32), (16, -32), (24, -24),
]

PLINTH = "SPACEAG"   # 0..80,    what the room sees below the panel band
CAP = "SPACEAB"      # 144..192, what the room sees above it
RING_F, RING_C = 80, 144
ROOM_F, ROOM_C = 0, 192

# Plain and matte. Anything with an authored _e would put light into the room
# that is not the pillar, which is the one thing this map must not have.
WALL, FLOOR, CEIL = "STONE2", "FLOOR0_1", "CEIL1_1"

# THE RING'S LIGHTLEVEL SITS BETWEEN TWO THRESHOLDS AND MUST STAY THERE.
#   >= rt_wall_strip_minlight (120), or the walk REJECTS the panels before it
#      ever places anything and the map shows nothing for a reason that has
#      nothing to do with what is being tested.
#   <  the rt_sector_emis threshold, max(rt_sector_emis_minlight 160, map median
#      + 40), or the panel band self-emits and lays shadowless fill over the
#      exact contribution being measured.
# 150 clears the first and stays under the second. MAP01's hall sits at 160 after
# make_seqlight_fix.py's Shaft repaints it, which is the top of that window.
RING_LIGHT = 150
ROOM_LIGHT_DARK = 64     # MAP94
ROOM_LIGHT_LIT = 150     # MAP95
ROOM = 512


def write_wad(items):
    body, directory, offset = b"", b"", 12
    for name, data in items:
        directory += struct.pack(
            "<II8s", offset, len(data), name.encode("ascii")[:8].ljust(8, b"\0")
        )
        body += data
        offset += len(data)
    return struct.pack("<4sII", b"PWAD", len(items), 12 + len(body)) + body + directory


def blk(kind, **f):
    out = [kind, "{"]
    for k, v in f.items():
        if isinstance(v, bool):
            if v:
                out.append(f"{k} = true;")
        elif isinstance(v, str):
            out.append(f'{k} = "{v}";')
        elif isinstance(v, float):
            out.append(f"{k} = {v:.3f};")
        else:
            out.append(f"{k} = {v};")
    out.append("}")
    return "\n".join(out)


def build_textmap(room: int, room_light: int, ring_light: int) -> str:
    cx = cy = room / 2.0
    parts = ['namespace = "zdoom";']

    verts = []

    def vert(x, y):
        verts.append((float(x), float(y)))
        return len(verts) - 1

    room_v = [vert(0, 0), vert(0, room), vert(room, room), vert(room, 0)]
    outer_v = [vert(cx + dx, cy + dy) for dx, dy in OUTER]
    # Built from the edge list's own start points, so the vertex loop cannot
    # drift out of step with the textures attached to it.
    inner_v = [vert(cx + a[0], cy + a[1]) for a, _b, _t in INNER]

    for x, y in verts:
        parts.append(blk("vertex", x=x, y=y))

    # sector 0 -- the room
    parts.append(blk("sector", heightfloor=ROOM_F, heightceiling=ROOM_C,
                     texturefloor=FLOOR, textureceiling=CEIL,
                     lightlevel=room_light))
    # sector 1 -- THE RING, tagged 29, the tag MAP01 gives sector 131. The chase
    # table kChasePillars keys on (map name, tag), so this lab's MAPINFO names
    # are what decide whether it also needs a row of its own -- see build_mapinfo.
    parts.append(blk("sector", heightfloor=RING_F, heightceiling=RING_C,
                     texturefloor=PLINTH, textureceiling=PLINTH,
                     lightlevel=ring_light, id=29))

    sides, lines = [], []

    def side(**f):
        sides.append(blk("sidedef", **f))
        return len(sides) - 1

    # Room walls: one-sided, front = the room. Clockwise loop, so the fronts
    # face inward at the player rather than out into the void.
    for i in range(4):
        sd = side(sector=0, texturemiddle=WALL)
        lines.append(blk("linedef", v1=room_v[i], v2=room_v[(i + 1) % 4],
                         sidefront=sd, blocking=True))

    # OUTER ring: two-sided. The room side carries BOTH the cap and the plinth,
    # because the room's floor is lower and its ceiling higher than the ring's.
    n = len(outer_v)
    for i in range(n):
        f = side(sector=0, texturetop=CAP, texturebottom=PLINTH)
        b = side(sector=1, texturetop=PLINTH)
        lines.append(blk("linedef", v1=outer_v[i], v2=outer_v[(i + 1) % n],
                         sidefront=f, sideback=b, twosided=True))

    # INNER ring: ONE-SIDED and BLOCKING, front = the ring, void behind. This is
    # the construction the whole lab exists for.
    for i, (_a, _b, tex) in enumerate(INNER):
        sd = side(sector=1, texturemiddle=tex)
        lines.append(blk("linedef", v1=inner_v[i], v2=inner_v[(i + 1) % len(inner_v)],
                         sidefront=sd, blocking=True))

    parts.extend(sides)
    parts.extend(lines)

    # Player back from the pillar and OFF-AXIS, facing it. Square-on to one panel
    # the chase cannot be read at all: its entire claim is that the bright face
    # MOVES, which needs more than one face in frame. From this corner the east
    # and north panels are both visible.
    parts.append(blk("thing", x=float(cx + room * 0.32), y=float(cy - room * 0.32),
                     angle=135, type=1, skill1=True, skill2=True, skill3=True,
                     skill4=True, skill5=True, single=True, coop=True, dm=True))
    return "\n".join(parts)


def build_mapinfo() -> bytes:
    out = []
    for num, title in ((94, "RT Pillar Lab (dark)"), (95, "RT Pillar Lab (lit)")):
        out.append(
            f'map MAP{num} "{title}"\n'
            "{\n"
            f"    levelnum = {num}\n"
            '    sky1 = "SKY1"\n'
            '    music = "D_RUNNIN"\n'
            f'    next = "MAP{num}"\n'
            f'    secretnext = "MAP{num}"\n'
            f"    cluster = {num}\n"
            "    nointermission\n"
            "}\n"
        )
    return "".join(out).encode("ascii")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--room", type=int, default=ROOM,
                    help="room side in map units. The gap to the pillar decides "
                         "how much wall the panels have to throw light onto")
    ap.add_argument("--light", type=int, default=RING_LIGHT,
                    help="the RING's lightlevel. Must be >= rt_wall_strip_minlight "
                         "(120) or the panels are rejected before placement, and "
                         "under the rt_sector_emis threshold (>=160) or the band "
                         "self-emits and hides what is being measured")
    ap.add_argument("--dark", type=int, default=ROOM_LIGHT_DARK,
                    help="MAP94's room lightlevel")
    args = ap.parse_args()

    room = max(256, args.room)
    wad = write_wad([
        ("MAP94", b""),
        ("TEXTMAP", build_textmap(room, args.dark, args.light).encode("ascii")),
        ("ENDMAP", b""),
        ("MAP95", b""),
        ("TEXTMAP", build_textmap(room, ROOM_LIGHT_LIT, args.light).encode("ascii")),
        ("ENDMAP", b""),
        ("MAPINFO", build_mapinfo()),
    ])
    OUT.write_bytes(wad)

    panels = sum(1 for _a, _b, t in INNER if t == PANEL)
    print(f"wrote {OUT}  ({len(wad)} bytes)")
    print(f"  MAP94 room {room}x{room} lightlevel {args.dark}; MAP95 the same at {ROOM_LIGHT_LIT}")
    print(f"  ring sector: tag 29, floor {RING_F} ceiling {RING_C}, lightlevel {args.light}")
    print(f"  inner octagon: {len(INNER)} ONE-SIDED walls -- {panels} x {PANEL}, "
          f"{len(INNER) - panels} x {BEVEL}, VOID core")
    print(f"  outer octagon: {len(OUTER)} two-sided edges onto the room")
    print()
    print(f"  EXPECT rt_wall_strip_debug to report uploaded={panels}, chased={panels},")
    print(f"  and winding-flipped={panels}. That last number is the bug: it counts the")
    print(f"  lights the centrespot test would have buried in the void core.")
    print(f"  MAP01 reports 6 because its ring carries an extra SPACEAZ face; this lab")
    print(f"  has only the four panels, so {panels} is the number that must appear here.")


if __name__ == "__main__":
    main()
