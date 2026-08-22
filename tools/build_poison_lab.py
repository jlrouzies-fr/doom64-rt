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


if __name__ == "__main__":
    main()
