"""Build MAP97, the SMOKE LAB: one dark room built to make muzzle smoke judgeable.

Muzzle smoke cannot be judged in a normal level and that is not a matter of
convenience. `docs/rt-smoke.md` says to fire at a wall in a dark room, and MAP01
is neither dark nor plain: its own lights, its wall panels and its sector
emissives all land in the froxel volume, so a change to the smoke and a change to
what is BEHIND the smoke look identical on screen. Three rounds of pistol tuning
were spent that way.

So this map removes every variable except the ones being judged:

  * ZERO ambient light. The room's sectors are at lightlevel 0 and the only
    illumination is the fixtures below, so a puff is exactly as bright as what is
    lighting it -- which is the property the whole feature is about.
  * A MATTE DARK WALL 3 m in front of the player, with no emissive, no
    brightmap and no panel art, so a wisp is read against a flat background
    rather than against something with structure of its own.
  * THREE LIGHTING CASES side by side in one room, because "too faded" depends
    entirely on which one you mean:
        LEFT   a bright lamp beside the barrel   -- smoke lit from the side
        MIDDLE nothing but the muzzle flash      -- the hard case, and the one
                                                    the feature is really for
        RIGHT  a dim backlight behind the smoke  -- silhouette / rim
  * A TALL CEILING (256) so a rising puff never touches it. The sector clamp in
    RT_UpdateSmokePuffs is correct behaviour and completely wrong for a test:
    it flattens the plume and would read as the smoke "spreading out".
  * A 1024-unit runway so the walk cases (rt_smoke_inherit) are testable in the
    same map without leaving the lit area.

The player starts in the MIDDLE lane facing the wall. Screenshots are framed by
the spawn angle, so the wisp is always in the same place on screen and two
captures can be diffed.

Usage:
    python tools/build_smoke_lab.py
    .\\tools\\smoke-lab.cmd [arm]

Outputs:
    Doom64-Retribution/d64rsmokelab.wad          (MAP97)
    Doom64-Retribution/d64r-smokelab-mapinfo.pk3
"""
from __future__ import annotations

import struct
import zipfile
from pathlib import Path

ROOT = Path(r"G:\AI\Doom64-RT")
OUT_WAD = ROOT / r"Doom64-Retribution\d64rsmokelab.wad"
OUT_MAPINFO = ROOT / r"Doom64-Retribution\d64r-smokelab-mapinfo.pk3"

# Deliberately plain, matte, non-emissive surfaces. Anything with a brightmap or
# an authored _e would put light into the volume that is not one of the three
# fixtures, and the whole point is knowing exactly what lights the smoke.
WALL = "STONE2"
FLOOR = "FLOOR0_1"
CEIL = "CEIL1_1"
# The BEIGE room's ceiling: Retribution's lit panel flat, so the bright room is
# lit the way the game's actually are -- a ceiling of light panels -- rather than
# by a lamp standing in for them.
CEIL_LIT = "SFLATAQ"

CEIL_H = 256          # tall: a rising puff must never reach it (see docstring)
FLOOR_H = 0

ROOM_W = 1024         # x: three lanes across
ROOM_D = 1280         # y: the runway, for the inherit/walk cases
LANE = ROOM_W // 3

# GZDoom light things. 9800 = PointLight, args = r,g,b,radius.
# Radius is in map units and is NOT brightness -- see AGENTS.md pitfall on
# rt_dynlight_rsoft; these stay in a sane range rather than being cranked.
T_POINTLIGHT = 9800


def write_wad(items: list[tuple[str, bytes]]) -> bytes:
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


def build_textmap(warm: bool = False) -> str:
    """warm=False -> MAP97, a dark cool room. warm=True -> MAP96, a BRIGHT BEIGE
    one, which is the case a dark blue lab cannot answer: reported from play as
    "a room full of ceiling lights where the gun smoke takes the room colour and
    is very hard to see". Judging smoke only against dark walls is how that went
    unnoticed -- a grey puff on a dark blue wall is easy, and on a lit beige wall
    it is the actual problem."""
    parts = ['namespace = "zdoom";']

    # ---- one rectangular room -------------------------------------------
    # CLOCKWISE, and this is not a style choice. A one-sided linedef's FRONT
    # side is the one facing the sector, and "front" is the right-hand side of
    # v1->v2. Wound counter-clockwise, every wall in the room faces OUTWARD: the
    # player stands in what the renderer treats as the void, the walls vanish,
    # and the whole screen is sky. That is exactly what the first capture from
    # this map showed -- clouds, no geometry, and nothing for smoke to be seen
    # against.
    #
    # Check one edge: (0,0)->(0,ROOM_D) points +y, and the right of +y is +x,
    # which is the inside. Every following edge turns the same way.
    verts = [
        (0, 0),
        (0, ROOM_D),
        (ROOM_W, ROOM_D),
        (ROOM_W, 0),
    ]
    for x, y in verts:
        parts.append(blk("vertex", x=float(x), y=float(y)))

    # lightlevel 0: the room is BLACK except for the three fixtures. This is the
    # single most important property of the map -- a sector with any painted
    # light puts a floor under everything and "faded smoke" stops being
    # measurable.
    parts.append(
        blk(
            "sector",
            heightfloor=FLOOR_H,
            heightceiling=CEIL_H,
            texturefloor=FLOOR,
            textureceiling=(CEIL_LIT if warm else CEIL),
            # The beige room is PAINTED bright as well as lit. A ceiling of
            # light panels in this game comes with a high sector lightlevel, and
            # that floor under everything is a real part of why smoke
            # disappears there -- leaving it at 0 would have tested a room that
            # merely has lamps in it, which is not the reported case.
            lightlevel=(200 if warm else 0),
        )
    )

    for i in range(4):
        parts.append(blk("sidedef", sector=0, texturemiddle=WALL))
    for i in range(4):
        parts.append(
            blk("linedef", v1=i, v2=(i + 1) % 4, sidefront=i, blocking=True)
        )

    # ---- the player, in the MIDDLE lane, facing the far wall -------------
    # 3 m (~96 map units at 32/m) is a normal engagement distance and puts the
    # far wall inside the froxel volume's useful range. Angle 90 = +y.
    parts.append(
        blk(
            "thing",
            x=float(ROOM_W // 2),
            y=float(ROOM_D - 384),
            angle=90,
            type=1,
            skill1=True, skill2=True, skill3=True, skill4=True, skill5=True,
            single=True, coop=True, dm=True,
        )
    )

    # A ROCKET LAUNCHER AND AMMO ON THE SPAWN. The rocket is the loudest smoke
    # source in the game -- a trail in flight plus a burst where it lands -- so
    # it is the one to judge "is the smoke still glowing" against. Dropped on the
    # player start rather than given by console: `give` runs before a player
    # exists, and GZDoom auto-switches on pickup, so walking onto it at spawn
    # arms it with no input at all.
    for kind, dx in ( ( 2003, 0.0 ), ( 2046, 24.0 ), ( 2046, -24.0 ) ):
        parts.append(
            blk("thing",
                x=float(ROOM_W // 2) + dx,
                y=float(ROOM_D - 384),
                angle=0, type=kind,
                skill1=True, skill2=True, skill3=True, skill4=True, skill5=True,
                single=True, coop=True, dm=True)
        )

    # ---- the three lighting cases ---------------------------------------
    # All at 64 units up, roughly muzzle height, so they light the puff rather
    # than the floor under it.
    #
    # LEFT: a bright white lamp offset to the side of the firing line. Smoke lit
    # from the side is the flattering case and the one that shows SHAPE.
    parts.append(
        blk("thing", x=float(LANE // 2), y=float(ROOM_D - 384), height=64.0,
            angle=0, type=T_POINTLIGHT, arg0=255, arg1=255, arg2=255, arg3=20,
            skill1=True, skill2=True, skill3=True, skill4=True, skill5=True,
            single=True, coop=True, dm=True)
    )
    # RIGHT: a dim backlight PAST the smoke, for rim/silhouette. Deliberately
    # weaker -- a second bright lamp would just be the left case again.
    parts.append(
        blk("thing", x=float(ROOM_W - LANE // 2), y=float(ROOM_D - 640), height=64.0,
            angle=0, type=T_POINTLIGHT, arg0=180, arg1=190, arg2=255, arg3=16,
            skill1=True, skill2=True, skill3=True, skill4=True, skill5=True,
            single=True, coop=True, dm=True)
    )
    # THE BACKDROP, and the reason a pitch-black room was the wrong test. Smoke
    # needs CONTRAST, and which kind depends on the case: a lit puff reads
    # against a dark wall, a dark puff reads against a lit one. With nothing but
    # black behind it, a wisp that is merely thin looks identical to a wisp that
    # is not there -- which is how three rounds of tuning went by on a
    # description instead of a measurement.
    #
    # So the far wall is washed to a mid tone by a lamp placed high and BEHIND
    # the firing line: it lights the wall without lighting the smoke from the
    # front. Both directions are then readable in one frame -- the puff is
    # brighter than the wall where its own muzzle flash catches it, and darker
    # where it occludes.
    # A ROW of them, hard against the far wall, rather than one bright one.
    #
    # arg3 is a RADIUS in map units and radius is NOT brightness -- past
    # rt_dynlight_rsoft a bigger radius is actually DIMMER (AGENTS.md pitfall
    # 28), so the way to wash a wall is more lights, not a larger one. These sit
    # 40 units off the wall at 20-unit radius, which is inside the sane band.
    #
    # Being close to the wall is also what keeps the FIRING LINE dark: inverse
    # square means a lamp 40 units from the wall and 340 from the player barely
    # reaches him. The wall is bright, the smoke's own neighbourhood is not, and
    # that separation is the entire reason this map exists.
    #
    # AND THEY ARE DEEP BLUE, which matters more than it sounds. The first
    # version washed the wall white, so grey powder smoke sat on a grey stone
    # wall lit grey -- the one backdrop that hides it completely, and a whole
    # sweep of four settings came back visually identical because of it. Smoke
    # here is warm and pale (rt_smoke_color 9E9689 lit by a warm muzzle lamp),
    # so the backdrop is its opposite: the puff separates in CHROMA as well as
    # in brightness, and a thin one still reads.
    for i in range(6):
        parts.append(
            blk("thing",
                x=float(ROOM_W * (i + 0.5) / 6.0),
                y=float(ROOM_D - 40),
                height=110.0,
                angle=0, type=T_POINTLIGHT,
                arg0=(255 if warm else 40),
                arg1=(228 if warm else 90),
                arg2=(180 if warm else 255),
                arg3=(24 if warm else 20),
                skill1=True, skill2=True, skill3=True, skill4=True, skill5=True,
                single=True, coop=True, dm=True)
        )

    # THE CEILING LIGHTS, beige room only. A GRID of them under the SFLATAQ
    # panels, because the reported case is "a room full of ceiling lights" --
    # smoke that reads fine against one lamp in the dark can vanish completely
    # under an even wash from above, which lights the puff and the wall behind
    # it by the same amount and leaves no contrast anywhere.
    if warm:
        for gx in range(4):
            for gy in range(5):
                parts.append(
                    blk("thing",
                        x=float(ROOM_W * (gx + 0.5) / 4.0),
                        y=float(ROOM_D * (gy + 0.5) / 5.0),
                        height=float(CEIL_H - 16),
                        angle=0, type=T_POINTLIGHT,
                        arg0=255, arg1=244, arg2=224, arg3=20,
                        skill1=True, skill2=True, skill3=True, skill4=True,
                        skill5=True, single=True, coop=True, dm=True)
                )

    # A STAND-IN FOR THE MUZZLE FLASH, and the lab is useless without it.
    #
    # The first version of this map left the firing line pitch dark on the
    # grounds that "a puff lit only by its own muzzle flash" is the case the
    # feature exists for. That is true in the GAME and false in the LAB, because
    # rt_smoke_autospawn does not go through RT_AddMuzzleFlash -- it spawns
    # parcels directly. So there was no flash, nothing lit the smoke, and the
    # capture showed an empty room even at 4x density with 30 puffs confirmed
    # uploaded and confirmed covering froxels by the shader probe.
    #
    # That is worth stating plainly because it is the same false negative this
    # project keeps paying for: "I can't see it" meant "nothing is lighting it",
    # not "the smoke is too thin".
    #
    # So: a small lamp at muzzle height, just behind the spawn point. STEADY
    # rather than flashing, which is deliberate -- a flash lasting 2-3 frames
    # makes every screenshot a lottery, and the thing being judged here is the
    # shape of the plume, not the timing of the light.
    parts.append(
        blk("thing", x=float(ROOM_W // 2 - 24), y=float(ROOM_D - 400), height=52.0,
            angle=0, type=T_POINTLIGHT, arg0=255, arg1=190, arg2=110, arg3=20,
            skill1=True, skill2=True, skill3=True, skill4=True, skill5=True,
            single=True, coop=True, dm=True)
    )

    return "\n".join(parts)


# The launcher and ammo are dropped on the player start (see build_textmap), and
# the SELECTION is done by rt_autofire_slot in the engine rather than here. A
# custom player class with Player.StartItem was tried first and is fatal: MAPINFO
# is parsed BEFORE DECORATE, so `playerclass` names a class that does not exist
# yet and the game dies during G_ParseMapInfo with nothing useful in the log.


def build_mapinfo() -> bytes:
    txt = (
        "map MAP97 \"RT Smoke Lab\"\n"
        "{\n"
        "    sky1 = \"SKY1\"\n"
        "    music = \"\"\n"
        "    cluster = 1\n"
        "    next = \"MAP97\"\n"
        "    secretnext = \"MAP97\"\n"
        "    // No auto-map effects, no fade: the volume must contain exactly the\n"
        "    // fixtures placed above and nothing the map format added for us.\n"
        "}\n"
    )
    # clearplayerclasses/playerclass is game-wide, which is exactly right: this
    # pk3 is only ever loaded by the lab.
    # clearplayerclasses/playerclass is game-wide, which is exactly right:
    # this pk3 is only ever loaded by the lab.
    with zipfile.ZipFile(OUT_MAPINFO, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('MAPINFO', txt)
    return txt.encode()


def main() -> None:
    # BOTH rooms in one wad. MAP97 dark and cool, MAP96 bright and beige -- the
    # same geometry and the same spawn, so a capture in one crops identically to
    # a capture in the other and the only difference is what the smoke is seen
    # against.
    wad = write_wad(
        [
            ("MAP97", b""),
            ("TEXTMAP", build_textmap(False).encode("ascii")),
            ("ENDMAP", b""),
            ("MAP96", b""),
            ("TEXTMAP", build_textmap(True).encode("ascii")),
            ("ENDMAP", b""),
        ]
    )
    OUT_WAD.write_bytes(wad)
    build_mapinfo()
    print(f"wrote {OUT_WAD}  ({len(wad)} bytes)")
    print(f"wrote {OUT_MAPINFO}")
    print()
    print("  room     %d x %d, ceiling %d (tall enough that a puff never clamps)"
          % (ROOM_W, ROOM_D, CEIL_H))
    print("  lanes    LEFT lit / MIDDLE dark (muzzle flash only) / RIGHT backlit")
    print("  player   middle lane, facing +y at the far wall")


if __name__ == "__main__":
    main()
