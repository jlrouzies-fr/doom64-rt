"""Build MAP96/MAP97, the UE MONITOR LAB: one SMONDA wall in an empty dark room.

    python tools/build_ue_monitor_lab.py
    python tools/build_ue_monitor_lab.py --room 768 --depth 384

    -> Doom64-UnseenEvil/d64ue-monitor-lab.wad   (MAP96 substitute, MAP97 + reference)

    .\\tools\\ue-monitor-lab.cmd            MAP96, the wall as UE ships it
    .\\tools\\ue-monitor-lab.cmd ref        MAP97, the hand-placed 9802 alone

WHY THIS EXISTS. The SMONDA monitors read as dead under Unseen Evil while the
engine tally said they were working -- `rt_wall_strip: uploaded=30 matchedTex=14
rejected: lightlevel=0` on UE MAP01 -- and the verdict from play was "nothing from
SMONDA". That pairing, the
instrument saying yes and the eye saying no, is the same shape as the pillar lab's
bug, and DOOM II MAP01 is the worst room in the game to settle it in: its computer
bank is ~1400 units from the player start, behind a doorway, in a room the mod
lights by other means. An upload counter proves a light was SUBMITTED, never that
it READS.

This is the same fixture with nothing else in the map.

THE LAB IS BUILT THE MOD'S WAY, and that is the whole point of it:

  * The wall texture is `SPACEW3`, NOT `SMONDA`. Unseen Evil's Terraformer maps
    SPACEW3 -> SMONDA at WorldLoaded (resources/d64ue_textures.txt, the ONLY line
    in the whole 663-entry table that produces a SMOND* name). Authoring SMONDA
    directly would build a lab the mod's own pipeline never touches, and the
    engine's monitor path is gated on that pipeline being active.

  * The filler textures are checked against the mapping too. FLAT2, TLITE6_5,
    TLITE6_6 -> SFLATAS; GRNLITE1 -> SFLATAQ; CEIL3_6, FLOOR1_7 -> SFLATCH;
    FLAT22 -> SPORTB. Every one of those is a LAMP family in
    rt_lights_fixtures.cpp, so using the obvious "light floor" flat as filler
    would quietly add a second fixture and make the lab lie. The ones below map
    to plain Doom 64 walls and flats.

DO NOT TRY TO MAKE THE ROOM DARK BY LOWERING lightlevel -- it cannot work, and
finding out why took a read of the mod's source. terraformer.zsc's main sector
loop stashes each sector's brightness into d64_sectorinfo and then calls
`daSector.SetLightLevel(240)` on EVERY sector, unconditionally. Whatever this
file writes is overwritten before the first frame. The room is dark anyway,
because the UE launcher runs `rt_world_white 1` and `rt_sector_emis 0`: under RT
the sector lightlevel does not reach world albedo and does not self-emit, so a
room with no analytic light in it is black no matter what number the sector
holds. That forced 240 is also why the wall strip walk's `rt_wall_strip_minlight
120` gate never rejects anything under this mod.

MAP96 -- the SMONDA wall as Unseen Evil ships it: the engine's steady cyan
wall-strip light (RT_UnseenEvilMonitorHue) plus the 9802s that
d64ue-monitor-lights.pk3 spawns on every SMOND face.

MAP97 -- the same room plus the REFERENCE: a real 9802 PointLightFlicker thing in
front of the wall, which is how Retribution lights its SMON panels (SMONDA 25 of
27). Its arguments are COPIED from Retribution MAP29, not invented: arg1=255,
arg2=180, arg3=24, arg4=20, height 32. Run `ue-monitor-lab.cmd ref` to see the
authored fixture on its own, `both` to see it beside the spawned ones.
"""

import argparse
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "Doom64-UnseenEvil" / "d64ue-monitor-lab.wad"

# The fixture. SPACEW3 is the DOOM II name; the Terraformer turns it into SMONDA.
MONITOR = "SPACEW3"

# Filler, all verified against d64ue_textures.* to land on non-lamp Doom 64 names:
#   BROWN1   -> textures/pepy/d64_brown1   (png, plain wall)
#   FLOOR0_1 -> SFLATAF                    (plain flat)
#   CEIL5_1  -> SPACEC                     (plain flat)
WALL = "BROWN1"
FLOOR = "FLOOR0_1"
CEIL = "CEIL5_1"

FLOOR_H = 0
CEIL_H = 128
TILE = 64  # SMONDA is 64 wide; Retribution places one 9802 per tile

# Written for completeness; the Terraformer forces 240 over it. See the docstring.
ROOM_LIGHT = 0

# Retribution MAP29's own 9802, copied. arg0 (red) is absent there and so is 0.
REF_G, REF_B = 255, 180
REF_HI, REF_LO = 24, 20
REF_HEIGHT = 32


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


def build_textmap(room: int, depth: int, with_reference: bool) -> str:
    parts = ['namespace = "zdoom";']

    # Corners, clockwise from the origin. The NORTH edge (v1->v2) is the monitor
    # wall; every other edge is plain filler, so anything that lights up in this
    # room came from that one wall.
    corners = [(0, 0), (0, depth), (room, depth), (room, 0)]
    for x, y in corners:
        parts.append(blk("vertex", x=float(x), y=float(y)))

    parts.append(
        blk(
            "sector",
            heightfloor=FLOOR_H,
            heightceiling=CEIL_H,
            texturefloor=FLOOR,
            textureceiling=CEIL,
            lightlevel=ROOM_LIGHT,
        )
    )

    sides, lines = [], []
    # Clockwise loop, so each one-sided front faces INTO the room at the player
    # rather than out into the void. The wall-strip walk decides which way to
    # nudge its emitter off the wall by testing against the sector's centrespot,
    # and for a convex box that centre is unambiguously inside -- which is the
    # other reason this lab is a plain rectangle and not something shaped.
    for i in range(4):
        tex = MONITOR if i == 1 else WALL
        sides.append(blk("sidedef", sector=0, texturemiddle=tex))
        lines.append(
            blk(
                "linedef",
                v1=i,
                v2=(i + 1) % 4,
                sidefront=len(sides) - 1,
                blocking=True,
            )
        )
    parts.extend(sides)
    parts.extend(lines)

    # Player back from the monitor wall and facing it (angle 90 = north). Close
    # enough that a 180-intensity, 0.35 m source has something to land on: the
    # MAP01 panel that read as "nothing" was ~1400 units away.
    parts.append(
        blk(
            "thing",
            x=float(room / 2),
            y=float(depth * 0.25),
            angle=90,
            type=1,
            skill1=True,
            skill2=True,
            skill3=True,
            skill4=True,
            skill5=True,
            single=True,
            coop=True,
            dm=True,
        )
    )

    if with_reference:
        # Retribution's mechanism, for comparison in the same room: a 9802 a few
        # units off the face, ONE PER PANEL -- its MAP01 SMONDA lights sit 64
        # apart, one per tile. A single centred reference under a twelve-panel
        # wall was the first version of this lab and it was wrong on sight.
        for i in range(room // TILE):
          parts.append(
            blk(
                "thing",
                x=float(i * TILE + TILE / 2),
                y=float(depth - 8),
                height=float(REF_HEIGHT),
                angle=90,
                type=9802,
                arg1=REF_G,
                arg2=REF_B,
                arg3=REF_HI,
                arg4=REF_LO,
                skill1=True,
                skill2=True,
                skill3=True,
                skill4=True,
                skill5=True,
                single=True,
                coop=True,
                dm=True,
            )
        )
    return "\n".join(parts)


def build_mapinfo() -> bytes:
    out = []
    for num, title in (
        (96, "UE Monitor Lab (overlay)"),
        (97, "UE Monitor Lab (+ hand-placed 9802 per tile)"),
    ):
        out.append(
            f'map MAP{num} "{title}"\n'
            "{\n"
            f"    levelnum = {num}\n"
            '    sky1 = "SKY1"\n'
            '    music = "D_RUNNIN"\n'
            f'    next = "MAP{num}"\n'
            "}\n"
        )
    return "\n".join(out).encode("ascii")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--room", type=int, default=768, help="room width in map units")
    ap.add_argument("--depth", type=int, default=384, help="distance to the monitor wall")
    args = ap.parse_args()

    items = [
        ("MAP96", b""),
        ("TEXTMAP", build_textmap(args.room, args.depth, False).encode("ascii")),
        ("ENDMAP", b""),
        ("MAP97", b""),
        ("TEXTMAP", build_textmap(args.room, args.depth, True).encode("ascii")),
        ("ENDMAP", b""),
        ("MAPINFO", build_mapinfo()),
    ]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes(write_wad(items))

    dist = args.depth - args.depth * 0.25
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")
    print(f"  room {args.room}x{args.depth}, ceiling {CEIL_H}")
    print(f"  monitor wall: {MONITOR} -> SMONDA, {args.room} units wide, {dist:.0f} from the player")
    print(f"  filler: {WALL} walls, {FLOOR} floor, {CEIL} ceiling (all non-lamp)")
    print(f"  MAP96 overlay only | MAP97 adds {args.room // TILE} hand-placed 9802s, one per tile (g={REF_G} b={REF_B} {REF_HI}/{REF_LO})")
    print()
    print("  .\\tools\\launch-unseenevil-rt.cmd map96")
    print("  .\\tools\\launch-unseenevil-rt.cmd map97 -- +rt_ue_monitor_flicker 0")


if __name__ == "__main__":
    main()
