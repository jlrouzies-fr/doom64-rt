"""Build MAP93, the EDGE LAB: silhouettes seen THROUGH a wall of smoke.

The known issue this exists for (README, "Black outlines behind volumetrics"):
where a participating medium meets a geometric edge, a thin dark line appears
along that edge. The medium is resolved on the froxel grid -- 160x88 columns,
64 slices -- which is far coarser than the image, so a column that straddles a
silhouette gets a depth that belongs to neither side of it. The depth gate
(`rt_volume_depthgate`, see docs/plan-light-shafts.md 4d) takes the MAXIMUM
depth over the column's ~12x12 px footprint on purpose, so a column on an edge
keeps cells the near surface cannot see -- and only what the medium ADDS is
gated, never its extinction. That asymmetry is what a line at a silhouette
would look like.

None of that is judgeable in a real level. MAP01 has its own lights, its own
emissives and its own geometry in the same froxel volume, and a puff drifts
somewhere different every run. So this room removes everything except the two
things being judged -- SMOKE in front, EDGES behind -- and makes the edges every
kind at once:

  * A SMOKE CURTAIN 2.2 m in front of the eye, from `rt_smoke_autospawn`, which
    births puffs at the real muzzle geometry with no weapon and no trigger.
  * EDGES AT FOUR DEPTHS behind it, 7 m to 34 m, so an artefact that depends on
    froxel slice thickness (0.94 m at rt_volume_far 60) shows which slices it
    lives in rather than being one anecdote at one distance.
  * BOTH KINDS OF EDGE, because the report names both and they are not the same
    thing to the renderer: PILLARS are opaque geometry with a hard depth, and
    MONSTERS are alpha-tested sprites -- one flat quad whose silhouette is a
    cutout inside it, not its own outline.
  * A THIN pillar (32 units, 1 m) dead centre. The gate's footprint MAX is
    documented to under-cull exactly here: a column narrower than the footprint
    keeps its far cells and the near surface gets in-scatter it cannot see.
  * A LIT FAR WALL and lamps above every pillar row, because a dark line is only
    visible against something bright. A black room is the one backdrop that
    hides this artefact completely -- the same mistake the smoke lab's first
    version made with a grey puff on a grey wall.
  * MONSTERS SPAWNED DORMANT (`dormant = true`). A monster that wakes walks and
    attacks, and a moving silhouette gives the denoiser nothing to reproject, so
    every capture would be a different frame with its own smear. Deactivate()
    on a monster with no Inactive state sets `tics = -1` -- it stands in its
    spawn frame, visible and solid, for as long as the capture takes.

Usage:
    python tools/build_edge_lab.py
    .\\tools\\edge-lab.cmd            # capture, ~4 s, quits itself

Outputs:
    Doom64-Retribution/d64redgelab.wad          (MAP93)
    Doom64-Retribution/d64r-edgelab-mapinfo.pk3
"""
from __future__ import annotations

import struct
import zipfile
from pathlib import Path

PROJ_ROOT = Path(__file__).resolve().parents[1]
OUT_WAD = PROJ_ROOT / r"Doom64-Retribution\d64redgelab.wad"
OUT_MAPINFO = PROJ_ROOT / r"Doom64-Retribution\d64r-edgelab-mapinfo.pk3"

# IWAD textures, deliberately plain: no brightmap, no authored _e, nothing that
# puts light into the volume that is not one of the fixtures placed below.
WALL = "STONE2"
FLOOR = "FLOOR0_1"
CEIL = "CEIL1_1"

ROOM_W = 1024          # x
ROOM_D = 1408          # y, the sight line
CEIL_H = 256
FLOOR_H = 0

T_POINTLIGHT = 9800    # GZDoom PointLight; args = r, g, b, radius(map units)

# Radius is NOT brightness -- past rt_dynlight_rsoft a bigger radius is DIMMER
# (AGENTS.md pitfall 28). Everything here stays in the sane 16-20 band and gets
# its brightness from rt_dynlight_intensity instead.
LAMP_R = 20

PLAYER = (ROOM_W // 2, 160)     # facing +y, straight down the room


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


def lamp(x: float, y: float, z: float, rgb=(255, 244, 224), r=LAMP_R) -> str:
    return thing(x, y, T_POINTLIGHT, height=float(z),
                 arg0=rgb[0], arg1=rgb[1], arg2=rgb[2], arg3=r)


# ---------------------------------------------------------------------------
# The edges. (centre x, centre y, half-width) -- pillars are VOID islands in the
# one room sector, so they need no sector of their own and cannot be lit from
# inside. Depths are chosen off the froxel slice: 0.94 m at rt_volume_far 60, so
# 7 / 13 / 21 / 34 m spreads them over ~7, ~14, ~22 and ~36 slices.
PILLARS = [
    (300, 384, 40),      #  7 m  wide-ish, left
    (724, 384, 40),      #  7 m  wide-ish, right
    (512, 576, 16),      # 13 m  THE THIN ONE, dead centre, 1 m across
    (232, 800, 64),      # 21 m  wide, left
    (792, 800, 64),      # 21 m  wide, right
    (512, 1088, 48),     # 34 m  centre, far
]

# Doom 2 monster editor numbers. Every one is an alpha-tested SPRITE, which is
# the other half of the report -- an outline around a cutout is not the same
# case as an outline around geometry.
MONSTERS = [
    (400, 470, 3001, 90),    #  imp,        just behind the near pillars
    (640, 470, 3001, 90),    #  imp
    (356, 690, 3005, 90),    #  cacodemon,  floats: a silhouette with no ground
    (668, 690, 3002, 90),    #  demon
    (512, 880, 3003, 90),    #  baron,      the big silhouette
    (300, 980, 9, 90),       #  shotgunner
    (740, 980, 3004, 90),    #  zombieman
]


def build_textmap() -> str:
    parts = ['namespace = "zdoom";']

    # ---- vertices --------------------------------------------------------
    # Room outline CLOCKWISE. A one-sided linedef's FRONT is the right-hand side
    # of v1->v2, so clockwise makes every wall face INWARD. Wound the other way
    # the player stands in what the renderer calls the void and the whole screen
    # is sky -- which is what the smoke lab's first capture actually showed.
    for x, y in [(0, 0), (0, ROOM_D), (ROOM_W, ROOM_D), (ROOM_W, 0)]:
        parts.append(blk("vertex", x=float(x), y=float(y)))
    # Pillar outlines COUNTER-CLOCKWISE -- the opposite winding, for the same
    # reason: an island's fronts must face OUT of it, into the room.
    for cx, cy, h in PILLARS:
        for x, y in [(cx - h, cy - h), (cx + h, cy - h),
                     (cx + h, cy + h), (cx - h, cy + h)]:
            parts.append(blk("vertex", x=float(x), y=float(y)))

    # ---- the one sector --------------------------------------------------
    # lightlevel 180: a BRIGHT room, not a black one. An outline needs something
    # to be an outline against, and a thick curtain is a luminous veil -- at 120
    # the room behind was darker than the smoke in front and the whole frame
    # went flat grey whatever the density.
    parts.append(
        blk("sector", heightfloor=FLOOR_H, heightceiling=CEIL_H,
            texturefloor=FLOOR, textureceiling=CEIL, lightlevel=180)
    )

    # ---- sidedefs / linedefs --------------------------------------------
    for _ in range(4 + 4 * len(PILLARS)):
        parts.append(blk("sidedef", sector=0, texturemiddle=WALL))
    for i in range(4):
        parts.append(blk("linedef", v1=i, v2=(i + 1) % 4, sidefront=i,
                         blocking=True))
    for p in range(len(PILLARS)):
        v0 = 4 + p * 4
        s0 = 4 + p * 4
        for e in range(4):
            parts.append(blk("linedef", v1=v0 + e, v2=v0 + (e + 1) % 4,
                             sidefront=s0 + e, blocking=True))

    # ---- the player ------------------------------------------------------
    # Angle 90 = +y, so the smoke curtain, both pillar rows and every monster
    # are in one frame and a capture crops identically to the last one.
    parts.append(thing(PLAYER[0], PLAYER[1], 1, angle=90))

    # ---- monsters, DORMANT ----------------------------------------------
    for x, y, kind, ang in MONSTERS:
        parts.append(thing(x, y, kind, angle=ang, dormant=True))

    # ---- light -----------------------------------------------------------
    # 1. THE BACKDROP. A row hard against the far wall, 40 units off it, so the
    #    wall is washed and the firing line is not: inverse square means a lamp
    #    40 units from the wall and 1200 from the player barely reaches him. The
    #    smoke has to be lit by its OWN lamp, not by the backdrop, or the two
    #    cannot be told apart.
    for i in range(6):
        parts.append(lamp(ROOM_W * (i + 0.5) / 6.0, ROOM_D - 40, 150,
                          rgb=(255, 238, 214)))

    # 2. OVERHEAD, a GRID over the whole hall rather than one lamp per pillar
    #    row. A dim room is the wrong backdrop here for a reason that only shows
    #    up once the curtain is thick: the smoke is a LUMINOUS veil, so what
    #    decides whether the edges behind it are still readable is not the
    #    medium's opacity but the CONTRAST between the veil and what is behind
    #    it. At lightlevel 120 with four lamps, a wide curtain washed the room
    #    out completely at every density from 2 to 8 -- the surfaces behind were
    #    darker than the lit smoke in front of them. Lighting the hall properly
    #    is what buys the spread.
    for gy in range(288, ROOM_D - 96, 192):
        for gx in (ROOM_W * 0.2, ROOM_W * 0.5, ROOM_W * 0.8):
            parts.append(lamp(gx, gy, CEIL_H - 24, rgb=(240, 242, 255)))

    # 3. THE CURTAIN'S OWN LIGHT, warm, from BOTH SIDES at 10 m -- not from the
    #    camera. Without a light on it the medium adds nothing and "no outline"
    #    would mean "nothing is lighting the smoke" rather than "the artefact is
    #    absent", which is the false negative the smoke lab paid for twice.
    #
    #    But it cannot sit AT the eye either: the first version put a warm lamp
    #    28 units left of the spawn, i.e. INSIDE the cloud that spawns 2.4 m
    #    ahead, and the capture was one white ball with the room behind it gone.
    #    A medium is lit from outside it. Side lighting is also the case that
    #    shows a plume's SHAPE (smoke lab, LEFT lane), and 10 m out keeps the
    #    lamps clear of the froxels the smoke occupies.
    for lx in (PLAYER[0] - 312, PLAYER[0] + 312):
        parts.append(lamp(lx, PLAYER[1] + 140, 110, rgb=(255, 214, 160)))

    return "\n".join(parts)


def build_mapinfo() -> None:
    txt = (
        'map MAP93 "RT Edge Lab"\n'
        "{\n"
        '    sky1 = "SKY1"\n'
        '    music = ""\n'
        "    cluster = 1\n"
        '    next = "MAP93"\n'
        '    secretnext = "MAP93"\n'
        "    // No fade, no auto effects: the froxel volume must contain the\n"
        "    // fixtures placed above and nothing the map format added for us.\n"
        "}\n"
    )
    with zipfile.ZipFile(OUT_MAPINFO, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("MAPINFO", txt)


def main() -> None:
    wad = write_wad([
        ("MAP93", b""),
        ("TEXTMAP", build_textmap().encode("ascii")),
        ("ENDMAP", b""),
    ])
    OUT_WAD.write_bytes(wad)
    build_mapinfo()
    print(f"wrote {OUT_WAD}  ({len(wad)} bytes)")
    print(f"wrote {OUT_MAPINFO}")
    print()
    print(f"  room     {ROOM_W} x {ROOM_D}, ceiling {CEIL_H}")
    print(f"  player   {PLAYER}, facing +y")
    print(f"  pillars  {len(PILLARS)} void islands at "
          + ", ".join(f"{(p[1] - PLAYER[1]) / 32.0:.0f} m" for p in PILLARS))
    print(f"  monsters {len(MONSTERS)}, dormant")


if __name__ == "__main__":
    main()
