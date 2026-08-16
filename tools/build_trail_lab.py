"""Build MAP94, the WEAPON TRAIL LAB: a pure dark room and one flat wall.

The artefact this exists for: fire the super shotgun into fog, and the reload
animation drags a dark stripe across the muzzle-lit medium behind it. See
docs/rt-volumetric-weapon-trails.md.

WHY THIS IS NOT MAP93. The edge lab is a BRIGHT hall full of pillars and
monsters, built so that silhouettes are everywhere -- which is exactly wrong
here. Two reasons:

  * The only light must be the MUZZLE FLASH. The trail is history that was
    filled with a transient light and then thrown away; if the room has its own
    lamps, the fog is lit by them too, the flash is a small perturbation on top,
    and the stripe is a few percent of a bright frame instead of most of a dark
    one. A black room makes the flash the entire signal.
  * The backdrop must be FLAT AND FEATURELESS. In MAP93 every pillar edge and
    every monster silhouette puts structure into the same part of the frame the
    trail lives in, and separating "a dark line at a silhouette" (the OTHER
    artefact, docs/rt-volumetric-edge-outlines.md) from "a dark stripe along the
    weapon's path" would be guesswork. One flat wall, nothing on it: any
    structure in the fog is the artefact, full stop.

So: a small box, lightlevel 0, no lamps, no monsters, no pillars, and the player
standing 4 m from the far wall facing it -- close enough that the wall fills the
view and the muzzle flash reaches it, which is what makes the fog in front of it
readable at all.

THE WEAPON IS THE INSTRUMENT. The super shotgun is the right one and not a
preference: its reload animation swings the sprite across most of the lower
frame and takes ~1.5 s, so it sweeps a wide path through the medium and holds
each pixel long enough for the history to be discarded and refilled. A pistol
barely moves and shows nothing.

Usage:
    py tools/build_trail_lab.py
    .\\tools\\trail-lab.ps1 -Arm fpfreeze-off

Outputs:
    Doom64-Retribution/d64rtraillab.wad          (MAP94)
    Doom64-Retribution/d64r-traillab-mapinfo.pk3
"""
from __future__ import annotations

import struct
import zipfile
from pathlib import Path

PROJ_ROOT = Path(__file__).resolve().parents[1]
OUT_WAD = PROJ_ROOT / r"Doom64-Retribution\d64rtraillab.wad"
OUT_MAPINFO = PROJ_ROOT / r"Doom64-Retribution\d64r-traillab-mapinfo.pk3"

# Plain IWAD textures: no brightmap, no authored _e, nothing that puts light
# into the volume. In this room that matters more than anywhere else -- a single
# emissive texel would be a second light source in a scene whose whole design is
# "one transient light".
WALL = "STONE2"
FLOOR = "FLOOR0_1"
CEIL = "CEIL1_1"

ROOM_W = 512           # x -- narrow, so the walls are close and the flash fills
ROOM_D = 384           # y -- the sight line
CEIL_H = 160
FLOOR_H = 0

# 4 m from the far wall (32 map units = 1 m). Close enough that the flash lights
# the wall and the fog between, far enough that the reload sprite has fog in
# front of it rather than bare wall.
PLAYER = (ROOM_W // 2, 128)


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


def thing(x: float, y: float, type_: int, **extra) -> str:
    return blk(
        "thing",
        x=float(x), y=float(y), angle=extra.pop("angle", 0), type=type_,
        skill1=True, skill2=True, skill3=True, skill4=True, skill5=True,
        single=True, coop=True, dm=True, **extra,
    )


def build_textmap() -> str:
    parts = ['namespace = "zdoom";']

    # Room outline CLOCKWISE: a one-sided linedef's FRONT is the right-hand side
    # of v1->v2, so clockwise faces every wall inward. Wound the other way the
    # player stands in the void and the screen is sky.
    for x, y in [(0, 0), (0, ROOM_D), (ROOM_W, ROOM_D), (ROOM_W, 0)]:
        parts.append(blk("vertex", x=float(x), y=float(y)))

    # lightlevel 0. THE POINT OF THE MAP. Not 40, not 20 -- the sector's light is
    # what the medium is lit by when nothing else is happening, and any of it
    # puts a floor under the artefact.
    parts.append(
        blk("sector", heightfloor=FLOOR_H, heightceiling=CEIL_H,
            texturefloor=FLOOR, textureceiling=CEIL, lightlevel=0)
    )

    for _ in range(4):
        parts.append(blk("sidedef", sector=0, texturemiddle=WALL))
    for i in range(4):
        parts.append(blk("linedef", v1=i, v2=(i + 1) % 4, sidefront=i,
                         blocking=True))

    # Angle 270 = -y, facing the near wall at y=0, which is the one 4 m away.
    parts.append(thing(PLAYER[0], PLAYER[1], 1, angle=270))

    # NO LAMPS. NO MONSTERS. Deliberately: see the module docstring.
    return "\n".join(parts)


def build_mapinfo() -> None:
    txt = (
        'map MAP94 "RT Weapon Trail Lab"\n'
        "{\n"
        '    sky1 = "SKY1"\n'
        '    music = ""\n'
        "    cluster = 1\n"
        '    next = "MAP94"\n'
        '    secretnext = "MAP94"\n'
        "    // No fade and no auto effects: the froxel volume must contain the\n"
        "    // muzzle flash and nothing the map format added for us.\n"
        "}\n"
    )
    with zipfile.ZipFile(OUT_MAPINFO, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("MAPINFO", txt)


def main() -> None:
    wad = write_wad([
        ("MAP94", b""),
        ("TEXTMAP", build_textmap().encode("ascii")),
        ("ENDMAP", b""),
    ])
    OUT_WAD.write_bytes(wad)
    build_mapinfo()
    print(f"wrote {OUT_WAD}  ({len(wad)} bytes)")
    print(f"wrote {OUT_MAPINFO}")
    print()
    print(f"  room       {ROOM_W} x {ROOM_D}, ceiling {CEIL_H}, lightlevel 0")
    print(f"  player     {PLAYER}, facing -y")
    print(f"  wall ahead {PLAYER[1] / 32.0:.1f} m")
    print("  lights     none -- the muzzle flash is the only one")


if __name__ == "__main__":
    main()
