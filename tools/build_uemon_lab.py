"""Build the UE monster labs: one map per monster, plus a side-by-side pair map.

    python tools/build_uemon_lab.py
    -> Doom64-Retribution/d64r-uemon-lab.wad

    MAP80 sergeant   MAP81 chaingunner   MAP82 revenant
    MAP83 archvile   MAP84 mastermind    -- one monster each, dark, at range
    MAP88 pairs (lit)                    MAP89 pairs (dark)

WHY ONE MAP PER MONSTER. The first version of this put all ten monsters in one
room. That is fine for comparing silhouettes and useless for anything else: with
ten actors awake at once you cannot tell which one fired, whether a given monster
ever performed its attack at all, or which effect the light on the wall came
from. "The Arch-Vile casts no light" and "the Arch-Vile never attacked" look
identical from the doorway, and they need completely different fixes.

So each of MAP80..MAP84 holds exactly ONE monster, alone, in a dark corridor,
with the player start far enough away to force the RANGED attack:

  * 768 units, which is past the Revenant's MeleeThreshold of 196 (so it fires
    missiles rather than punching) and inside the Arch-Vile's MaxTargetRange of
    896 (so it can start its fire attack at all).
  * lightlevel 48, because every one of these effects is emissive and a bright
    room hides all of them.
  * ceiling at 320, which clears the Mastermind's 136.

PROVE THE ATTACK FIRED, do not assume it. Each monster's effect has its own
sprite, so rt_tex_probe answers it directly -- it prints the texture name the
renderer actually saw and a draw count:

    tools\\uemon-lab.cmd archvile +rt_tex_probe AVFR

  drawn=0 or no line at all -> the attack never happened. Look at the monster,
                               not at the lighting.
  drawn>0                    -> it fired and the sprite rendered under that name,
                               so anything still wrong is the material meta.
"""
from __future__ import annotations

import argparse
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "Doom64-Retribution" / "d64r-uemon-lab.wad"

WALL, FLOOR, CEIL = "STONE2", "FLOOR0_1", "CEIL1_1"
ROOM_F, ROOM_C = 0, 320
LIGHT_LIT, LIGHT_DARK = 160, 48

# One map each. (map number, title, editor number, probe prefix for the effect)
SOLO = [
    (80, "Former Sergeant", 30001, "SPO2"),
    (81, "Chaingunner",     30002, "CPOS"),
    (82, "Revenant",        30003, "TRC2"),
    (83, "Arch-Vile",       30004, "AVFR"),
    (84, "Spider Mastermind", 30005, "LPUF"),
]

# The pair map: reference on the left, ours on the right.
PAIRS = [
    ("sergeant",    9,    30001),
    ("chaingunner", 9,    30002),
    ("revenant",    3007, 30003),
    ("archvile",    3003, 30004),
    ("mastermind",  68,   30005),
]

SOLO_RANGE = 768      # see the docstring: past melee, inside vile range
SOLO_W, SOLO_MARGIN = 640, 192
BAY, PAIR_GAP, MARGIN, DEPTH = 320, 128, 320, 768


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


def room(width: int, height: int, light: int) -> list[str]:
    """Four walls, one sector. Clockwise so the one-sided fronts face inward."""
    parts = ['namespace = "zdoom";']
    for x, y in [(0, 0), (0, height), (width, height), (width, 0)]:
        parts.append(blk("vertex", x=float(x), y=float(y)))
    parts.append(blk("sector", heightfloor=ROOM_F, heightceiling=ROOM_C,
                     texturefloor=FLOOR, textureceiling=CEIL, lightlevel=light))
    for _ in range(4):
        parts.append(blk("sidedef", sector=0, texturemiddle=WALL))
    for i in range(4):
        parts.append(blk("linedef", v1=i, v2=(i + 1) % 4, sidefront=i, blocking=True))
    return parts


def thing(x: float, y: float, type_: int, angle: int) -> str:
    return blk("thing", x=x, y=y, type=type_, angle=angle,
               skill1=True, skill2=True, skill3=True, skill4=True, skill5=True,
               single=True)


# A Lost Soul, as an OPT-IN control (--control). Its flame is the one emitter in
# this project already known to cast light, so standing it in the same dark room
# turns "does this cast light" from a judgement call into a comparison inside a
# single frame. That is exactly how the Arch-Vile flame was diagnosed: same
# textures.json recipe, Lost Soul pooled orange on the floor, flame lit nothing,
# and rt_tex_probe showed the flame drawing at alpha 0.72 instead of opaque.
#
# OFF by default, because once you know the answer a second light source in the
# room only makes it harder to see what the monster under test is doing.
CONTROL_LOSTSOUL = 3006


def build_solo(ednum: int, control: bool = False) -> str:
    height = SOLO_MARGIN * 2 + SOLO_RANGE
    parts = room(SOLO_W, height, LIGHT_DARK)
    cx = SOLO_W / 2.0
    # Monster at the far end facing the player, player at the near end facing it.
    parts.append(thing(cx, float(SOLO_MARGIN + SOLO_RANGE), ednum, 270))
    if control:
        # Off to one side, halfway down, so it and the monster's effect are both
        # in frame from the player start.
        parts.append(thing(cx - 224.0, float(SOLO_MARGIN + SOLO_RANGE * 0.5),
                           CONTROL_LOSTSOUL, 270))
    parts.append(thing(cx, float(SOLO_MARGIN), 1, 90))
    return "\n".join(parts) + "\n"


def build_pairs(light: int) -> str:
    width = MARGIN * 2 + BAY * (len(PAIRS) - 1) + PAIR_GAP
    height = MARGIN * 2 + DEPTH
    parts = room(width, height, light)
    row_y = float(MARGIN + DEPTH)
    for i, (_label, ref, ours) in enumerate(PAIRS):
        x = MARGIN + i * BAY
        parts.append(thing(float(x), row_y, ref, 270))
        parts.append(thing(float(x + PAIR_GAP), row_y, ours, 270))
    parts.append(thing(width / 2.0, float(MARGIN), 1, 90))
    return "\n".join(parts) + "\n"


def build_mapinfo() -> bytes:
    out = []
    entries = [(n, f"UE Lab: {t}") for n, t, _e, _p in SOLO]
    entries += [(88, "UE Lab: pairs (lit)"), (89, "UE Lab: pairs (dark)")]
    for num, title in entries:
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
    ap.add_argument("--range", type=int, default=SOLO_RANGE,
                    help="player-to-monster distance in the solo maps")
    ap.add_argument("--control", action="store_true",
                    help="add a Lost Soul to each solo map as a known-good "
                         "cast-light reference")
    args = ap.parse_args()
    globals()["SOLO_RANGE"] = args.range

    lumps = []
    for num, _title, ednum, _probe in SOLO:
        lumps += [(f"MAP{num}", b""),
                  ("TEXTMAP", build_solo(ednum, args.control).encode("ascii")),
                  ("ENDMAP", b"")]
    lumps += [("MAP88", b""), ("TEXTMAP", build_pairs(LIGHT_LIT).encode("ascii")),
              ("ENDMAP", b""),
              ("MAP89", b""), ("TEXTMAP", build_pairs(LIGHT_DARK).encode("ascii")),
              ("ENDMAP", b""),
              ("MAPINFO", build_mapinfo())]
    OUT.write_bytes(write_wad(lumps))

    print(f"{OUT.relative_to(ROOT)}")
    for num, title, ednum, probe in SOLO:
        print(f"  MAP{num}  {title:18s} thing {ednum}  probe {probe}")
    print("  MAP88  pairs (lit)        MAP89  pairs (dark)")


if __name__ == "__main__":
    main()
