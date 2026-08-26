"""Build the POISON LAB: one pool of nukage you stand at the edge of.

WHY THIS EXISTS. The poison bubbles were first judged on MAP07, which has 50
poison sectors and is therefore the obvious map -- and it is a bad test, for
three reasons that all look identical from inside the game:

  * MAP07's nukage sits at z = -256, in pits. The spawner reported bubbles at
    583-810 units from the player and 256 units BELOW him. A 20-unit sprite at
    that range is a couple of pixels, so "nothing happens" and "it works and you
    cannot see it" produce exactly the same screenshot.
  * The map is lit. A "slight green light" cannot be separated from the room's
    own lights, and the nukage's own emissive tints the walls green anyway.
  * The flat is tagged RG_MESH_PRIMITIVE_WATER by the RT path (the log says so:
    `RT water: tagging "D64N1_31" ... liquid 1 (nukage)`). A sprite spawned one
    unit above that surface may be drawn, occluded or swallowed by it, and
    nothing in MAP07 tells the three apart.

So this map removes every variable except the ones being judged.

  MAP90  DARK.  lightlevel 0, and NOT ONE light thing in the map. The bubbles
         are the only thing in it that can emit, so whatever green lands on the
         wall came from them. This is the room for the LIGHT half.
  MAP91  LIT.   the same geometry at lightlevel 160 with a ceiling grid, so the
         sprite can be read as a shape -- size, growth, whether the burst reads
         as a burst, whether it sinks into the water plane. This is the room for
         the SPRITE half.

Same geometry and same spawn in both, so a capture in one crops identically to
a capture in the other. That is the smoke lab's rule and it is worth keeping.

THE PLAYER STANDS AT THE POOL EDGE, facing up its long axis, with a matte wall
128 units past the far edge. Nothing is more than a few hundred units away and
nothing is below him.

SIX STATIC PROBES sit in a row between the player and the pool, one locked to
each frame, at 72 units. They are the control that the spawner cannot give you:
if the row is six green bubbles the sprites exist, load, and have their offsets
right, and any remaining problem is the spawner or the water surface. If the row
is six exclamation marks, nothing downstream matters. That distinction cost the
lava sprays a whole round.

Usage:
    tools\\.venv-ai\\Scripts\\python.exe tools/build_poison_lab.py
    .\\tools\\poison-lab.cmd [arm]

Outputs:
    Doom64-Retribution/d64rpoisonlab.wad           (MAP90 dark, MAP91 lit)
    Doom64-Retribution/d64r-poisonlab-mapinfo.pk3  (MAPINFO + the probe actors)
"""
from __future__ import annotations

import struct
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_WAD = ROOT / r"Doom64-Retribution\d64rpoisonlab.wad"
OUT_MAPINFO = ROOT / r"Doom64-Retribution\d64r-poisonlab-mapinfo.pk3"

# Deliberately plain, matte, non-emissive surfaces -- doom2 stock rather than
# Retribution art, because a D64 wall texture brings a brightmap and an authored
# _e with it, and then the green on the wall is not only the bubbles'.
WALL = "STONE2"
FLOOR = "FLOOR0_1"
CEIL = "CEIL1_1"
POOL = "D64N1_01"   # frame 1 of the 64-frame ANIMDEFS sequence; the engine cycles it

ROOM_W = 1024
ROOM_D = 1408
CEIL_H = 256
POOL_X0, POOL_X1 = 128, 896
POOL_Y0, POOL_Y1 = 256, 1280
POOL_Z = -32        # a step down, not a pit: the surface stays near eye level

T_POINTLIGHT = 9800
T_PROBE = 9910      # one frame, held forever; args[0] picks which
T_PROBE_ANIM = 9911 # the whole six-frame cycle on a loop
T_STALAGTITE = 47   # MAP94's control prop -- see build_bridge_textmap

# MAP94, the BRIDGE lab. The numbers are MAP07's, measured out of its UDMF:
# sec164 and sec202 are the only two nukage sectors in the game with a solid
# rover over them, their fluid is at z -174 and the slabs run -30..42 and
# -30..102, so the clearance from fluid to deck top is 144 UNITS. Reproducing
# that number matters -- the whole question is whether something 144 units under
# an opaque deck is drawn through it.
BRIDGE_POOL_Z = -144    # the fluid, a pit like MAP07's
BRIDGE_DECK_TOP = 0     # flush with the walkway, so you WALK onto the deck
BRIDGE_DECK_BOT = -40   # slab thickness 40; MAP07's are 72 and 132
BRIDGE_TAG = 94


def write_wad(items) -> bytes:
    body, directory, offset = b"", b"", 12
    for name, data in items:
        directory += struct.pack(
            "<II8s", offset, len(data), name.encode("ascii")[:8].ljust(8, b"\0")
        )
        body += data
        offset += len(data)
    return struct.pack("<4sII", b"PWAD", len(items), 12 + len(body)) + body + directory


def blk(kind: str, **f) -> str:
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


def thing(**f) -> str:
    return blk("thing", skill1=True, skill2=True, skill3=True, skill4=True,
               skill5=True, single=True, coop=True, dm=True, **f)


def build_textmap(lit: bool) -> str:
    parts = ['namespace = "zdoom";']

    # CLOCKWISE, and this is not a style choice. A one-sided linedef's FRONT is
    # the right-hand side of v1->v2. Wound the other way every wall faces
    # OUTWARD, the player stands in what the renderer treats as the void, and
    # the whole screen is sky. Check one edge: (0,0)->(0,ROOM_D) points +y, and
    # the right of +y is +x, which is the inside.
    room_v = [(0, 0), (0, ROOM_D), (ROOM_W, ROOM_D), (ROOM_W, 0)]
    pool_v = [(POOL_X0, POOL_Y0), (POOL_X0, POOL_Y1),
              (POOL_X1, POOL_Y1), (POOL_X1, POOL_Y0)]
    for x, y in room_v + pool_v:
        parts.append(blk("vertex", x=float(x), y=float(y)))

    light = 160 if lit else 0
    # sector 0: the walkway. sector 1: the pool, one step down.
    parts.append(blk("sector", heightfloor=0, heightceiling=CEIL_H,
                     texturefloor=FLOOR, textureceiling=CEIL, lightlevel=light))
    parts.append(blk("sector", heightfloor=POOL_Z, heightceiling=CEIL_H,
                     texturefloor=POOL, textureceiling=CEIL, lightlevel=light))

    # Room walls: one-sided, front = the walkway.
    for _ in range(4):
        parts.append(blk("sidedef", sector=0, texturemiddle=WALL))
    for i in range(4):
        parts.append(blk("linedef", v1=i, v2=(i + 1) % 4, sidefront=i,
                         blocking=True))

    # Pool border: two-sided. The step is 32 units and the WALKWAY is the higher
    # side, so the lower texture that shows is the one on the walkway-facing
    # sidedef -- the BACK here. Written on both so a rewind of the winding
    # cannot leave a black band around the pool.
    side = 4
    for e in range(4):
        parts.append(blk("sidedef", sector=1, texturebottom=WALL))  # front: pool
        parts.append(blk("sidedef", sector=0, texturebottom=WALL))  # back: walkway
        parts.append(blk("linedef", v1=4 + e, v2=4 + (e + 1) % 4,
                         sidefront=side, sideback=side + 1, twosided=True))
        side += 2

    # The player, on the south walkway, facing +y up the long axis of the pool.
    # 128 units from the near edge: close enough that a 20-unit bubble is a
    # real object on screen, which MAP07 never managed.
    parts.append(thing(x=float(ROOM_W // 2), y=128.0, angle=90, type=1))

    # THE PROBE ROW, down the WEST walkway rather than across the spawn.
    #
    # The first version put it 72 units in front of the player, and at that
    # range a 20-unit sprite is most of the screen: the two nearest probes sat
    # over the status bar and the pool behind them was unreadable. Turn left to
    # audit the frames, look ahead to judge the effect -- the two questions do
    # not want the same shot.
    #
    # They sit on the walkway FLOOR, so their grAb offsets are exercised the
    # same way a spawned bubble's are. A probe floating at an arbitrary height
    # would hide exactly the offset bug it is there to catch.
    for i in range(6):
        parts.append(thing(x=64.0, y=float(320 + i * 160),
                           angle=90, type=T_PROBE, arg0=i))
    # And one running the whole cycle, at the end of the row, for the timing.
    parts.append(thing(x=64.0, y=1280.0, angle=90, type=T_PROBE_ANIM))

    # THE LIT ROOM ONLY. A ceiling grid, white, so the sprite is read as a
    # SHAPE. The dark room gets nothing at all -- not one light thing -- because
    # the moment anything else in the map emits, "the bubbles light the wall"
    # stops being answerable.
    #
    # arg3 is a RADIUS and radius is NOT brightness: past rt_dynlight_rsoft (20)
    # a bigger one is DIMMER, so an even wash is more lights, not larger ones.
    if lit:
        for gx in range(3):
            for gy in range(4):
                parts.append(thing(x=float(ROOM_W * (gx + 0.5) / 3.0),
                                   y=float(ROOM_D * (gy + 0.5) / 4.0),
                                   height=float(CEIL_H - 16), angle=0,
                                   type=T_POINTLIGHT,
                                   arg0=255, arg1=250, arg2=240, arg3=20))

    return "\n".join(parts)


# The probes live HERE, in the lab's own pk3, not in d64r-poison-fx.pk3. They
# are debug scaffolding with a DoomEdNum, and a shipping pk3 should not carry a
# map thing that exists to be looked at.
#
# D64PoisonProbe derives from the shipping actor rather than redeclaring the
# sprite, so it inherits whatever the real bubble inherits -- if the render
# flags are the reason nothing shows, the probe is wrong in the same way and the
# test still means something. Load order therefore matters: the fx pk3 has to
# come first on the command line, which poison-lab.cmd does.
PROBE_ZSCRIPT = r'''version "4.12"

class D64PoisonProbe : D64PoisonBubble
{
    Default
    {
        // The parent's Tick damps vel.z and the parent's states run the growth
        // sequence; neither is wanted here. Height/Radius stay tiny so the row
        // cannot block the player's path to the pool.
        Radius 1;
        Height 1;
        // SHIPPING SIZE, not authored size -- the midpoint of the spawner's
        // 0.7-1.25 spread times the shipping d64_poison_size of 0.35. A
        // reference row drawn at scale 1 would be three times what the pool
        // shows, and a reference that does not match the thing it is a
        // reference for is worse than none. Walk up to them to audit the frames.
        Scale 0.34;
    }
    States
    {
    Spawn:
        PBUB A -1;
    Hold0:
        PBUB A -1;
    Hold1:
        PBUB B -1;
    Hold2:
        PBUB C -1;
    Hold3:
        PBUB D -1;
    Hold4:
        PBUB E -1;
    Hold5:
        PBUB F -1;
    }

    // Jump to a STATE rather than writing `frame` directly: the state is what
    // carries the sprite AND the GLDEFS light binding, so poking the frame
    // field would show the right picture with the wrong light and quietly
    // invalidate the thing this probe is for.
    //
    // And it is a switch over literal labels, not String.Format: a StateLabel
    // is resolved at COMPILE time, so a runtime String will not convert to one
    // -- "Cannot convert String to StateLabel", which is exactly how the first
    // version of this file failed to compile.
    override void PostBeginPlay()
    {
        Super.PostBeginPlay();
        vel = ( 0, 0, 0 );

        State s;
        switch( clamp( args[0], 0, 5 ) )
        {
            case 0:  s = ResolveState( "Hold0" ); break;
            case 1:  s = ResolveState( "Hold1" ); break;
            case 2:  s = ResolveState( "Hold2" ); break;
            case 3:  s = ResolveState( "Hold3" ); break;
            case 4:  s = ResolveState( "Hold4" ); break;
            default: s = ResolveState( "Hold5" ); break;
        }
        if( s ) { SetState( s ); }
    }
}

// A SIBLING of the probe, not a subclass of it. Deriving from D64PoisonProbe
// would inherit its PostBeginPlay, which jumps straight to a Hold label and
// would stop this one on frame A before its own Spawn state ever ran.
class D64PoisonProbeAnim : D64PoisonBubble
{
    Default
    {
        Radius 1;
        Height 1;
    }
    States
    {
    Spawn:
        PBUB A 8;
        PBUB B 6;
        PBUB C 6;
        PBUB D 6;
        PBUB E 10;
        PBUB F 7;
        TNT1 A 12;        // a beat of nothing, so the loop reads as a loop
        Loop;
    }
}
'''


def build_channel_textmap(lit: bool = True) -> str:
    """MAP92 -- a NARROW CHANNEL of poison, which is what the game actually has.

    MAP91 is a 768x1024 lake, and a lake hides the one bug that matters: the
    spawner samples a random point in a disc around the player and keeps it only
    if it lands on a poison floor. On the lake nearly every sample hits. In
    MAP07 the nukage runs down corridors a couple of hundred units wide, so
    almost every sample lands on rock, and the handful that survive are wherever
    the disc happened to clip some other pool -- which is how a bubble ends up
    reported "1000 from player" while the poison you are standing in stays
    still.

    So: the same room, the same spawn, the same lighting, and the poison is a
    192-unit channel down the middle instead of a lake. Any sampler that works
    here works in the game."""
    parts = ['namespace = "zdoom";']

    RW, RD = 320, ROOM_D
    CX0, CX1 = 64, 256          # the channel: 192 wide, like a corridor

    room_v = [(0, 0), (0, RD), (RW, RD), (RW, 0)]
    pool_v = [(CX0, 192), (CX0, RD - 192), (CX1, RD - 192), (CX1, 192)]
    for x, y in room_v + pool_v:
        parts.append(blk("vertex", x=float(x), y=float(y)))

    light = 160 if lit else 0
    parts.append(blk("sector", heightfloor=0, heightceiling=CEIL_H,
                     texturefloor=FLOOR, textureceiling=CEIL, lightlevel=light))
    parts.append(blk("sector", heightfloor=POOL_Z, heightceiling=CEIL_H,
                     texturefloor=POOL, textureceiling=CEIL, lightlevel=light))

    for _ in range(4):
        parts.append(blk("sidedef", sector=0, texturemiddle=WALL))
    for i in range(4):
        parts.append(blk("linedef", v1=i, v2=(i + 1) % 4, sidefront=i,
                         blocking=True))

    side = 4
    for e in range(4):
        parts.append(blk("sidedef", sector=1, texturebottom=WALL))
        parts.append(blk("sidedef", sector=0, texturebottom=WALL))
        parts.append(blk("linedef", v1=4 + e, v2=4 + (e + 1) % 4,
                         sidefront=side, sideback=side + 1, twosided=True))
        side += 2

    # Standing ON the channel, looking down it -- which is where the report came
    # from, and the case a disc sampler is worst at.
    parts.append(thing(x=float((CX0 + CX1) // 2), y=96.0, angle=90, type=1))

    # MAP93 gets NO ceiling grid and lightlevel 0 -- the corridor as the game
    # actually presents it. This is the room the "no bubbles on MAP07" report is
    # really about: a lit lab proves the sprite draws, and proves nothing at all
    # about whether it lights anything.
    if lit:
        for gx in range(2):
            for gy in range(5):
                parts.append(thing(x=float(RW * (gx + 0.5) / 2.0),
                                   y=float(RD * (gy + 0.5) / 5.0),
                                   height=float(CEIL_H - 16), angle=0,
                                   type=T_POINTLIGHT,
                                   arg0=255, arg1=250, arg2=240, arg3=20))
    return "\n".join(parts)


def build_bridge_textmap() -> str:
    """MAP94 -- a solid 3D FLOOR over half the poison. The map for the bug in
    screen/poison3Dfloor.png: bubbles drawn ON a deck they sit 144 units under.

    MAP07 cannot be the test, for the same reason it could not test anything
    else here: its nukage is in pits, and "the gate works" and "you cannot see
    the bubbles from up there anyway" give the identical screenshot. So this is
    one room, one pool, and the pool is cut in half:

        SOUTH half   DECKED -- a solid rover, top flush with the walkway, so
                     you walk straight out over it from the spawn and look
                     down at your own feet. Nothing green may appear here.
        NORTH half   OPEN   -- the control. Bubbles here must be untouched, or
                     the gate is rejecting more than it should.

    Both halves are the same flat at the same height in the same light, so the
    only difference between them is the rover. That is the whole design.

    THE STALAGTITE IS THE POINT OF THE MAP, not scenery. It stands on the poison
    UNDER the deck, with a light of its own next to it so it cannot fail to be
    visible for a lighting reason. It is what tells us whether RT fails to
    occlude EVERY actor under a rover -- which would matter for all 209 of
    Retribution's rovers and the 22 water sectors under bridges on MAP11 -- or
    only these bubbles. An ordinary stock prop on purpose: a second green bubble
    down there could not be told from a spawned one, and 47/Stalagtite carries
    no GLDEFS light, so it cannot light the room it is being judged in.
    """
    parts = ['namespace = "zdoom";']

    MID = (POOL_Y0 + POOL_Y1) // 2

    #  0-3  room, clockwise (see build_textmap for why the winding matters)
    #  4-9  pool, split at MID into a decked south half and an open north half
    # 10-13 the control closet, off the play area
    room_v = [(0, 0), (0, ROOM_D), (ROOM_W, ROOM_D), (ROOM_W, 0)]
    pool_v = [(POOL_X0, POOL_Y0), (POOL_X0, MID), (POOL_X0, POOL_Y1),
              (POOL_X1, POOL_Y1), (POOL_X1, MID), (POOL_X1, POOL_Y0)]
    ctrl_v = [(ROOM_W + 128, 0), (ROOM_W + 128, 128),
              (ROOM_W + 256, 128), (ROOM_W + 256, 0)]
    for x, y in room_v + pool_v + ctrl_v:
        parts.append(blk("vertex", x=float(x), y=float(y)))

    LIGHT = 160
    # 0 walkway | 1 pool DECKED (tagged) | 2 pool OPEN | 3 the rover's control
    parts.append(blk("sector", heightfloor=0, heightceiling=CEIL_H,
                     texturefloor=FLOOR, textureceiling=CEIL, lightlevel=LIGHT))
    parts.append(blk("sector", heightfloor=BRIDGE_POOL_Z, heightceiling=CEIL_H,
                     texturefloor=POOL, textureceiling=CEIL, lightlevel=LIGHT,
                     id=BRIDGE_TAG))
    parts.append(blk("sector", heightfloor=BRIDGE_POOL_Z, heightceiling=CEIL_H,
                     texturefloor=POOL, textureceiling=CEIL, lightlevel=LIGHT))
    # THE CONTROL SECTOR IS THE ROVER. P_Add3DFloor takes the slab's BOTTOM from
    # this sector's FLOOR and its TOP from this sector's CEILING -- verified
    # against MAP07, where ctrl sec282 runs -30..42 and produces a deck whose
    # top is 42. Its flats become the rover's underside and walking surface.
    parts.append(blk("sector", heightfloor=BRIDGE_DECK_BOT,
                     heightceiling=BRIDGE_DECK_TOP,
                     texturefloor=FLOOR, textureceiling=FLOOR, lightlevel=LIGHT))

    # Room walls: one-sided, front = the walkway.
    for _ in range(4):
        parts.append(blk("sidedef", sector=0, texturemiddle=WALL))
    for i in range(4):
        parts.append(blk("linedef", v1=i, v2=(i + 1) % 4, sidefront=i,
                         blocking=True))

    # Pool border. Front is the right of v1->v2 and every edge below is wound so
    # that the right-hand side is the pool; the split line (5->8) is the one
    # whose back is the OTHER pool half rather than the walkway.
    #   4=(X0,Y0) 5=(X0,MID) 6=(X0,Y1) 7=(X1,Y1) 8=(X1,MID) 9=(X1,Y0)
    edges = [
        (4, 5, 1, 0),   # decked, west
        (5, 8, 1, 2),   # THE SPLIT -- decked in front, open behind
        (8, 9, 1, 0),   # decked, east
        (9, 4, 1, 0),   # decked, south
        (5, 6, 2, 0),   # open, west
        (6, 7, 2, 0),   # open, north
        (7, 8, 2, 0),   # open, east
    ]
    side = 4
    for v1, v2, front, back in edges:
        parts.append(blk("sidedef", sector=front, texturebottom=WALL))
        parts.append(blk("sidedef", sector=back, texturebottom=WALL))
        parts.append(blk("linedef", v1=v1, v2=v2, sidefront=side,
                         sideback=side + 1, twosided=True))
        side += 2

    # The control closet: four one-sided walls, and ONE of them carries
    # Sector_Set3DFloor. arg1 = 1 is plain FF_SOLID and arg3 = 255 opaque --
    # both copied from MAP07's two rovers, which are exactly type 1 alpha 255.
    for _ in range(4):
        parts.append(blk("sidedef", sector=3, texturemiddle=WALL))
    for i in range(4):
        parts.append(blk("linedef", v1=10 + i, v2=10 + (i + 1) % 4,
                         sidefront=side + i, blocking=True,
                         **({"special": 160, "arg0": BRIDGE_TAG, "arg1": 1,
                             "arg2": 0, "arg3": 255} if i == 0 else {})))

    # The player, on the south walkway facing +y -- straight at the deck. The
    # deck top is flush with this floor, so walking forward puts him standing
    # over the covered poison with no stair, lift or noclip in the way.
    parts.append(thing(x=float(ROOM_W // 2), y=128.0, angle=90, type=1))

    # THE CONTROL, under the deck, with its own light so "invisible" can only
    # mean occluded. Placed mid-way into the decked half, on the fluid.
    probe_y = float((POOL_Y0 + MID) // 2)
    parts.append(thing(x=float(ROOM_W // 2), y=probe_y, angle=90,
                       type=T_STALAGTITE))
    # height is RELATIVE TO THE SECTOR FLOOR in UDMF (the ceiling grid below
    # reads CEIL_H - 16 for the same reason), so 48 is 48 above the fluid, not
    # 48 in world z. Written absolute first, which put the light 96 units under
    # the floor and lit nothing.
    parts.append(thing(x=float(ROOM_W // 2 + 96), y=probe_y,
                       height=48.0, angle=0,
                       type=T_POINTLIGHT, arg0=255, arg1=250, arg2=240, arg3=20))

    # Ceiling grid, as MAP91. It lights the open half and the walkway; under the
    # deck it deliberately does not reach, which is what the light above is for.
    for gx in range(3):
        for gy in range(4):
            parts.append(thing(x=float(ROOM_W * (gx + 0.5) / 3.0),
                               y=float(ROOM_D * (gy + 0.5) / 4.0),
                               height=float(CEIL_H - 16), angle=0,
                               type=T_POINTLIGHT,
                               arg0=255, arg1=250, arg2=240, arg3=20))

    return "\n".join(parts)


MAPINFO = """map MAP90 "RT Poison Lab (dark)"
{
    sky1 = "SKY1"
    music = ""
    cluster = 1
    next = "MAP90"
    secretnext = "MAP90"
    // No fade, no auto-map effects: the only thing that may emit in this room
    // is a bubble.
}

map MAP91 "RT Poison Lab (lit)"
{
    sky1 = "SKY1"
    music = ""
    cluster = 1
    next = "MAP91"
    secretnext = "MAP91"
}

map MAP92 "RT Poison Lab (channel)"
{
    sky1 = "SKY1"
    music = ""
    cluster = 1
    next = "MAP92"
    secretnext = "MAP92"
}

map MAP93 "RT Poison Lab (channel, dark)"
{
    sky1 = "SKY1"
    music = ""
    cluster = 1
    next = "MAP93"
    secretnext = "MAP93"
}

map MAP94 "RT Poison Lab (bridge)"
{
    sky1 = "SKY1"
    music = ""
    cluster = 1
    next = "MAP94"
    secretnext = "MAP94"
}

DoomEdNums
{
    9910 = D64PoisonProbe
    9911 = D64PoisonProbeAnim
}
"""


def main() -> None:
    wad = write_wad([
        ("MAP90", b""),
        ("TEXTMAP", build_textmap(False).encode("ascii")),
        ("ENDMAP", b""),
        ("MAP91", b""),
        ("TEXTMAP", build_textmap(True).encode("ascii")),
        ("ENDMAP", b""),
        ("MAP92", b""),
        ("TEXTMAP", build_channel_textmap(True).encode("ascii")),
        ("ENDMAP", b""),
        ("MAP93", b""),
        ("TEXTMAP", build_channel_textmap(False).encode("ascii")),
        ("ENDMAP", b""),
        ("MAP94", b""),
        ("TEXTMAP", build_bridge_textmap().encode("ascii")),
        ("ENDMAP", b""),
    ])
    OUT_WAD.write_bytes(wad)
    with zipfile.ZipFile(OUT_MAPINFO, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("MAPINFO", MAPINFO)
        z.writestr("ZSCRIPT", PROBE_ZSCRIPT)

    print(f"wrote {OUT_WAD}  ({len(wad)} bytes)")
    print(f"wrote {OUT_MAPINFO}")
    print()
    print(f"  room    {ROOM_W} x {ROOM_D}, ceiling {CEIL_H}")
    print(f"  pool    {POOL} from ({POOL_X0},{POOL_Y0}) to ({POOL_X1},{POOL_Y1}) at z {POOL_Z}")
    print( "  player  south walkway, 128 units off the near edge, facing +y")
    print( "  probes  six frames in a row at 72 units, plus one on a loop")
    print( "  MAP90   dark: lightlevel 0, no light things -- judge the LIGHT")
    print( "  MAP91   lit:  lightlevel 160 + ceiling grid -- judge the SPRITE")
    print( "  MAP92   channel: a 192-unit corridor of poison -- the shape the game has")
    print( "  MAP93   channel, DARK: the same corridor at lightlevel 0, no lights at all")
    print(f"  MAP94   bridge: a solid 3D floor over the SOUTH half of the pool,")
    print(f"          deck top {BRIDGE_DECK_TOP} flush with the walkway, fluid at "
          f"{BRIDGE_POOL_Z} -- {BRIDGE_DECK_TOP - BRIDGE_POOL_Z} units of clearance, MAP07's number.")
    print( "          North half is the untouched control; the Stalagtite under the")
    print( "          deck says whether RT occludes ORDINARY actors under a rover.")


if __name__ == "__main__":
    main()
