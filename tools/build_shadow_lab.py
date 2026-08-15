"""Build MAP93, the SHADOW LAB: MAP01's cage, alone in a dark room.

    python tools/build_shadow_lab.py            128-unit cage (16 bulbs)
    python tools/build_shadow_lab.py --cage 64  one tile, exactly 4 bulbs

    -> Doom64-Retribution/d64rshadowlab.wad     (MAP93)

WHY THIS EXISTS. The MAP01 cage question -- "why does the grating cast no
shadow" -- has been tuned against a room containing 283 analytic lights, a moon,
wall strips, dynlights, faux and solo fixtures and a level's worth of emissive
GI. Every arm run there moved one of those and left the other 282, and the
results were unreadable for exactly that reason (rt-lighting-practices 34c).

This is the same fixture with nothing else in the map:

  * ONE SFLATAS lamp pane, in the ceiling INSIDE the cage, like MAP01.
  * The cage's four walls are two-sided lines carrying the grating as a MIDDLE
    texture -- the same construction MAP01 uses, so the primitive reaches RTGL1
    the same way (alpha-tested, in the BLAS, WORLD_0).
  * A plain dark room around it, lightlevel 64, no light things at all.

So the only thing that can light the floor is the pane's own bulb lattice, and
the only thing that can occlude it is the grating. If a shadow does not appear
here it is not because something else filled it in.

THE GRATING IS SPACECM, and this lab is how that was settled. `whatsthat` aimed
at the MAP01 cage returned `middle texture 'SPACEAF'`, which was taken at face
value -- but SPACEAF has ZERO transparent pixels. Scanning every SPACE* PNG in
D64RTR_v15.WAD for alpha gives exactly five masked candidates, and SPACECM
(64x64, 56.2% transparent) is the only 64x64 diamond mesh among them. The
whatsthat hit had landed on the wall BESIDE the cage.

The lab caught it in one frame: built with SPACEAF the cage is a sealed opaque
box, so no light escapes and the room renders black. That is worth keeping in
mind about practices 30 -- `whatsthat` reports the surface the ray HIT, which is
only the surface you meant if you were aimed at it. Confirm a texture's identity
from its pixels (practices 17) before building on the name.

BULB COUNT IS THE POINT, so it is derived and printed rather than guessed.
SFLATAS tiles 2x2 bulbs per 64-unit tile, so a 64-unit cage is exactly 4 bulbs
and a 128-unit cage is 16. At rt_ceiling_bulb_spacing 16 the lattice places one
light per painted bulb, so the light count in this map is knowable in advance --
and `rt_ceiling_edge_debug 1` must agree with it, or the arm did not apply.
"""

import argparse
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "Doom64-Retribution" / "d64rshadowlab.wad"

# Plain, matte, non-emissive. Anything with an authored _e would put light into
# the room that is not the pane, which is the one thing this map must not have.
WALL = "STONE2"
FLOOR = "FLOOR0_1"
CEIL = "CEIL1_1"

# The fixture under test, and the occluder under test.
PANE = "SFLATAS"
FENCE = "SPACECM"

# Room is square with the cage in the middle, and the GAP between them is the
# thing that matters. A pane in the cage ceiling throws its light DOWN, so it
# meets the floor outside at a grazing angle where cos(theta)/d^2 is tiny -- the
# outside floor there is lit almost entirely by bounce, which carries no shadow.
# A wall close to the cage is face-on to that light instead. MAP01 is the same
# story: screen/oneLamp.png put the diamonds on the WALL beside the cage, never
# on the floor, and this map's first version had its walls 320 units away.
ROOM = 384        # overridden by --room
CEIL_H = 192      # 6 m -- MAP01's cage is a tall box, not a crawlspace
LIGHTLEVEL = 64   # dark. A high painted lightlevel would put a floor under
                  # everything and hide the contribution being measured, and
                  # above the rt_sector_emis threshold the walls would self-emit.

# Bulbs per 64-unit tile per axis, from rt_lights_fixtures.cpp's own lattice
# tables (BulbLatticeAS = {15.5, 47.5}, BulbLatticeAQ = {7.5, 23.5, 39.5, 55.5} --
# the _e masks' blob centroids, detected by gen_bulb_flat_masks.py, not assumed).
# SFLATAQ packs four times as many bulbs into the same area, which is exactly what
# rt_ceiling_bulb_aq_scale exists to trim back out.
BULBS_PER_TILE_AXIS = {"SFLATAS": 2, "SFLATAQ": 4, "SFLATCH": 1, "SFLATDE": 1}
TILE = 64

# Which upload path a pane texture takes, because they are NOT the same family and
# do not share a single cvar. SFLATAS/SFLATAQ are the "real bulb arrays" and go
# through addLattice under rt_ceiling_edge_lattice; SFLATCH/SFLATDE are "solo
# bulbs" -- one painted bulb dead centre of the tile (SoloBulbTextures in
# rt_lights_fixtures.cpp gives SFLATCH 32.0,32.0) -- and go through addSoloLattice
# under rt_solo_lamps, with their own intensity, radius, zofs, stride and budget.
# Pointing the bulb-lattice cvars at a solo pane does nothing at all, which is
# exactly the class of silent no-op that has cost this problem days already.
SOLO_TEXTURES = ("SFLATCH", "SFLATDE")


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


def build_textmap(cage: int, pan: int = 0) -> str:
    parts = ['namespace = "zdoom";']

    c0 = (ROOM - cage) // 2
    c1 = c0 + cage

    # Room outline, CLOCKWISE. Doom's front sidedef is the RIGHT of v1->v2, so a
    # clockwise loop puts every front sidedef on the inside -- which is what makes
    # the one-sided room walls face the player instead of the void.
    for x, y in [(0, 0), (0, ROOM), (ROOM, ROOM), (ROOM, 0)]:
        parts.append(blk("vertex", x=float(x), y=float(y)))
    # Cage outline, also clockwise, so its front sidedefs face INTO the cage and
    # the pane sector is the front. Same convention as the smoke lab's panes.
    for x, y in [(c0, c0), (c0, c1), (c1, c1), (c1, c0)]:
        parts.append(blk("vertex", x=float(x), y=float(y)))

    # Sector 0 -- the room. Plain ceiling: it must not be a second fixture.
    parts.append(blk("sector", heightfloor=0, heightceiling=CEIL_H,
                     texturefloor=FLOOR, textureceiling=CEIL,
                     lightlevel=LIGHTLEVEL))
    # Sector 1 -- the cage. Identical heights, so the grating spans the full
    # opening and nothing steps; only the ceiling texture differs. That is
    # exactly MAP01: the lamp pane is the cage's own ceiling.
    cagesec = dict(heightfloor=0, heightceiling=CEIL_H,
                   texturefloor=FLOOR, textureceiling=PANE,
                   lightlevel=LIGHTLEVEL)
    if pan:
        # GZDoom UDMF: shifts the ceiling flat only. The floor is left alone so any
        # movement seen is unambiguously the pane's.
        cagesec["xpanningceiling"] = float(pan)
        cagesec["ypanningceiling"] = float(pan)
    parts.append(blk("sector", **cagesec))

    # Room walls: one-sided, front = the room.
    for _ in range(4):
        parts.append(blk("sidedef", sector=0, texturemiddle=WALL))
    for i in range(4):
        parts.append(blk("linedef", v1=i, v2=(i + 1) % 4, sidefront=i,
                         blocking=True))

    # The cage walls. TWO-SIDED with a MIDDLE texture on BOTH sidedefs -- that is
    # what makes a Doom grating: the middle of a two-sided line is masked, so the
    # texture's holes are see-through and its wires are solid. Both sides carry it
    # because the cage is looked at from outside and lit from inside.
    #
    # wrapmidtex, because a middle texture on a two-sided line otherwise draws
    # only once in the opening rather than tiling to fill it -- a 192-unit cage
    # with a 128-tall texture would be a fence with a gap over it.
    #
    # NOT blocking: the shadow is the subject, and a solid cage makes the map
    # tedious to move around in. Blocking has no effect on how it renders.
    side = 4
    for e in range(4):
        parts.append(blk("sidedef", sector=1, texturemiddle=FENCE))  # front: cage
        parts.append(blk("sidedef", sector=0, texturemiddle=FENCE))  # back:  room
        parts.append(blk("linedef", v1=4 + e, v2=4 + (e + 1) % 4,
                         sidefront=side, sideback=side + 1,
                         twosided=True, wrapmidtex=True))
        side += 2

    # Player in a CORNER, looking diagonally at the cage. Two reasons, both
    # learned from this map's earlier versions:
    #
    #   * the shadow lands on the WALLS, not the floor. A pane in the cage ceiling
    #     throws its light down, so it meets the outside floor at a grazing angle
    #     and that floor is lit mostly by bounce, which carries no pattern. MAP01
    #     says the same: screen/oneLamp.png put the diamonds on the wall.
    #   * square-on from the middle of a wall, the near grating fills the frame and
    #     hides everything it is casting onto. From a corner the cage is off to one
    #     side and two lit walls are visible behind it.
    parts.append(blk("thing", x=float(ROOM * 0.14), y=float(ROOM * 0.14), angle=45, type=1,
                     skill1=True, skill2=True, skill3=True, skill4=True,
                     skill5=True, single=True, coop=True, dm=True))
    return "\n".join(parts)


def build_mapinfo() -> bytes:
    return (
        'map MAP93 "RT Shadow Lab"\n'
        "{\n"
        "    levelnum = 93\n"
        "    sky1 = \"SKY1\"\n"
        "    music = \"D_RUNNIN\"\n"
        "    next = \"MAP93\"\n"
        "    secretnext = \"MAP93\"\n"
        "    cluster = 93\n"
        "    nointermission\n"
        "}\n"
    ).encode("ascii")


def main() -> None:
    # Must precede any read of these, including argparse defaults below.
    global ROOM, CEIL_H, LIGHTLEVEL, PANE, FENCE
    ap = argparse.ArgumentParser()
    ap.add_argument("--room", type=int, default=ROOM,
                    help="room side in map units; the gap to the cage is what "
                         "decides whether a wall is face-on to the pane")
    ap.add_argument("--pan", type=int, default=0,
                    help="pan the cage's ceiling flat by N units on both axes. Used to "
                         "verify that addLattice follows flat panning: the painted bulb "
                         "and the lit spot must move TOGETHER")
    ap.add_argument("--ceil", type=int, default=CEIL_H,
                    help="ceiling height. Raising it moves the pane further from "
                         "the floor, which widens the projected pattern and dims it")
    ap.add_argument("--light", type=int, default=LIGHTLEVEL,
                    help="sector lightlevel. Keep it under the rt_sector_emis "
                         "threshold (max(160, map median+40)) or the walls start "
                         "self-emitting and add shadowless fill of their own")
    ap.add_argument("--pane", default=PANE,
                    help="ceiling fixture texture. SFLATAS = 2x2 bulbs per 64-unit "
                         "tile, SFLATAQ = 4x4 (four times the light count for the "
                         "same area, which is what rt_ceiling_bulb_aq_scale trims), "
                         "SFLATCH/SFLATDE = ONE bulb dead centre of the tile -- so "
                         "--cage 64 is 1 bulb and 1 light, --cage 128 is 4 and 4")
    ap.add_argument("--fence", default=FENCE,
                    help="the occluder. Must be a MASKED texture -- SPACECM is "
                         "56.2%% transparent; SPACEAF has no holes at all and makes "
                         "the cage a sealed box that renders the room black")
    ap.add_argument("--cage", type=int, default=128,
                    help="cage side in map units; a multiple of 64 "
                         "(64 = one SFLATAS tile = exactly 4 painted bulbs)")
    args = ap.parse_args()
    cage = max(64, (args.cage // 64) * 64)
    ROOM = max(cage + 128, args.room)
    CEIL_H, LIGHTLEVEL, PANE, FENCE = args.ceil, args.light, args.pane, args.fence

    tiles = (cage // TILE) ** 2
    bulbs = tiles * BULBS_PER_TILE_AXIS.get(PANE, 2) ** 2

    wad = write_wad([
        ("MAP93", b""),
        ("TEXTMAP", build_textmap(cage, args.pan).encode("ascii")),
        ("ENDMAP", b""),
        ("MAPINFO", build_mapinfo()),
    ])
    OUT.write_bytes(wad)

    print(f"wrote {OUT}  ({len(wad)} bytes)")
    print(f"  room {ROOM}x{ROOM}, ceiling {CEIL_H}, lightlevel {LIGHTLEVEL}, no light things")
    print(f"  gap cage->wall {(ROOM - cage)//2} units" + (f", ceiling flat panned {args.pan}" if args.pan else ""))
    print(f"  cage {cage}x{cage} -- {tiles} {PANE} tile(s) = {bulbs} painted bulbs, fence {FENCE}")
    solo = PANE in SOLO_TEXTURES
    if solo:
        print(f"  SOLO family: rt_solo_lamps, rt_solo_lamp_radius/_intensity/_zofs/_stride")
        print(f"  expect rt_ceiling_edge_debug to report \"solo 1 flat(s), {bulbs} of {bulbs} wanted\".")
    else:
        print(f"  BULB LATTICE family: rt_ceiling_bulb_spacing, rt_ceiling_edge_radius")
        print(f"  at spacing 16 expect \"+ 1 bulb lattice(s)\" and uploaded={bulbs}.")
    print(f"  If the count differs, the arm did not apply and the result is void.")
    # The wrapper reads this so it cannot point bulb-lattice cvars at a solo pane.
    (ROOT / "tools" / "_shadowlab_pane.txt").write_text(PANE, encoding="ascii")


if __name__ == "__main__":
    main()
