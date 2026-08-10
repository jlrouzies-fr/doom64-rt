"""Red eye emissives for the two gargoyle statues — A028 (dragon) and A029 (demon).

Sibling of tools/gen_enemy_eye_emissives.py and follows its rules: eyes only, surface
glow only, no cast light. What differs is where the mask geometry comes from.

WHY THIS IS NOT THE ENEMY-EYE TOOL
----------------------------------
That tool's mask sources are (1) the authored brightmaps in D64RTR_BRIGHTMAPS.PK3 and
(2) donor clones between frames, and its `AUTO_EYES` red-pixel detector is switched OFF
because it painted armour, blood and soldiers' backs. Neither source exists here:
`brightmaps/bd64/` has nothing for A02*, and there is only one frame per statue, so
there is nobody to clone from.

Auto-detect is nonetheless the RIGHT answer for these two, and it is not the same gamble
it was on the monsters, because the red on a statue is not a hue *range* — it is a single
exact palette entry that appears nowhere else on the sprite:

    A028A0  64x72   (128, 32, 0)   4 px   y=39,  x=24,25 | x=31,32
    A029A0  64x64   (104,  0,  0)  6 px   y=43,  x=23    | x=29
                                          y=44,  x=24,25 | x=27,28

Both are symmetric pairs about the sprite's centre line, in the head, and the whole rest
of each sprite is neutral grey-brown stone (measured: zero pixels above saturation 0.45
in the red hues outside these clusters). So EXACT_RED below is a lookup, not a threshold,
and ART_GEOMETRY asserts the count and positions on every run — if the WAD is ever
swapped for one whose statues are painted differently, this fails loudly instead of
quietly inventing eyes. That is the trap logged in
`docs/rt-lighting-practices.md`: check the source art before lighting a fixture.

COLOUR
------
Each statue keeps ITS OWN hue, normalised to full saturation. The enemy eyes all share
`ff0a00`, but these two do not agree with each other in the art — the dragon's eyes are
orange (128,32,0 is 4:1 red:green), the demon's are pure blood red (104,0,0) — and that
difference is visible when they stand in the same room, which they do in MAP23 and MAP34.

Full saturation is required, not cosmetic: RTGL1 multiplies the emissive by the surface's
baseColor, so a mask painted at the art's own dim value gets the darkness applied twice
and the eyes barely lift. Same rule as every other `_e` mask in this project.

NO CAST LIGHT
-------------
`emissiveMult` only, `lightIntensity` absent. These are 4 and 6 pixel eyes on a lump of
stone; a cast light would make a statue a lamp, which is the failure that put EYE_LIGHT=0
in the enemy tool. If a room is later found to want a red pool at a statue's feet, that is
an engine-side analytic light keyed on the sprite (the RT_FLAME_KINDS pattern), not a
number here — texture-meta light is anchored to the billboard centre and cannot be aimed.

PLACEMENT (all 71 UDMF maps, thing types 1028 / 1029)
-----------------------------------------------------
    A028 dragon  62  MAP13 (17), 15 (12), 17 (8), 21 (6), 23 (9), 22, 24, 30, 34
    A029 demon   26  MAP23 (24), 22 (1), 34 (1)

MAP23 is the one room where both appear in numbers — check there first.

Output:
    rt/mat/<SPRITE>_e.png   (+ mat_dev, + the Retribution-RT-Materials overlay)
    textures.json           emissiveMult only, upserted into the four live targets
"""
from __future__ import annotations

import json
import struct
from pathlib import Path

from PIL import Image

ROOT = Path(r"G:\AI\Doom64-RT")
WAD = ROOT / r"Doom64-Retribution\D64RTR_v15.WAD"
MAT = ROOT / r"sourcecode\gzdoom-rt\build\RelWithDebInfo\rt\mat"
MAT_DEV = ROOT / r"sourcecode\gzdoom-rt\build\RelWithDebInfo\rt\mat_dev"
OMAT = ROOT / r"Doom64-Retribution\Retribution-RT-Materials\rt\mat"

JSON_TARGETS = [
    ROOT / r"sourcecode\gzdoom-rt\build\RelWithDebInfo\rt\data\textures.json",
    ROOT / r"sourcecode\gzdoom-rt\build\RelWithDebInfo\rt\data\scenes\d64rtr_v15_map01\textures.json",
    ROOT / r"Doom64-Retribution\Retribution-RT-Materials\rt\data\textures_statue_eyes.json",
    ROOT / r"Doom64-Retribution\Retribution-RT-Materials\rt\data\scenes\d64rtr_v15_map01\textures.json",
]

# Matches the enemy eyes. An eye is a handful of texels; it needs the multiplier to read
# at all, and 2.0 is the value already settled on for exactly this job.
EMIS = 2.0

# sprite -> (exact art colour to match, full-saturation colour to paint, expected px)
STATUES: dict[str, tuple[tuple[int, int, int], tuple[int, int, int], int]] = {
    "A028A0": ((128, 32, 0), (255, 64, 0), 4),   # dragon — orange
    "A029A0": ((104, 0, 0), (255, 10, 0), 6),    # demon  — blood red, the enemy-eye hex
}

# Belt and braces on the auto-detect: the exact texels the art is known to carry.
ART_GEOMETRY: dict[str, set[tuple[int, int]]] = {
    "A028A0": {(24, 39), (25, 39), (31, 39), (32, 39)},
    "A029A0": {(23, 43), (29, 43), (24, 44), (25, 44), (27, 44), (28, 44)},
}


def wad_lump(name: str) -> bytes:
    with WAD.open("rb") as f:
        _, count, off = struct.unpack("<4sII", f.read(12))
        f.seek(off)
        table = [struct.unpack("<II8s", f.read(16)) for _ in range(count)]
    for o, sz, nm in table:
        if nm.rstrip(b"\0").decode("latin1") == name:
            with WAD.open("rb") as f:
                f.seek(o)
                return f.read(sz)
    raise SystemExit(f"lump {name} not in {WAD.name}")


def build_mask(img: Image.Image, exact: tuple[int, int, int], paint: tuple[int, int, int]):
    """Exact-colour match -> flat full-saturation mask. No dilate, no ramp.

    No intensity ramp because there is nothing to ramp: the art uses ONE colour for the
    whole eye, so every lit texel is equally lit. Dilating would spill the glow onto the
    stone brow, which on a 4-pixel eye is most of the face.
    """
    rgba = img.convert("RGBA")
    w, h = rgba.size
    src = rgba.load()
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    dst = out.load()
    found: set[tuple[int, int]] = set()
    for y in range(h):
        for x in range(w):
            r, g, b, a = src[x, y]
            if a >= 128 and (r, g, b) == exact:
                dst[x, y] = (paint[0], paint[1], paint[2], 255)
                found.add((x, y))
    return out, found


def upsert(path: Path, entries: dict[str, dict]) -> None:
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {"version": 0, "array": []}
    else:
        data = {"version": 0, "array": []}
    by = {e["textureName"]: dict(e) for e in data.get("array", []) if "textureName" in e}
    for name, meta in entries.items():
        row = by.get(name, {})
        row.update(meta)
        row["textureName"] = name
        by[name] = row
    data["array"] = list(by.values())
    data.setdefault("version", 0)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    entries: dict[str, dict] = {}
    for tex, (exact, paint, expect) in STATUES.items():
        img = Image.open(__import__("io").BytesIO(wad_lump(tex)))
        mask, found = build_mask(img, exact, paint)

        want = ART_GEOMETRY[tex]
        if found != want:
            raise SystemExit(
                f"{tex}: eye texels changed — the art is not what this tool was written\n"
                f"  against, so it will NOT guess. expected {sorted(want)}\n"
                f"  found    {sorted(found)}\n"
                f"  Re-measure before touching EXACT/ART_GEOMETRY."
            )
        assert len(found) == expect

        for dest in (MAT / f"{tex}_e.png", MAT_DEV / f"{tex}_e.png", OMAT / f"{tex}_e.png"):
            dest.parent.mkdir(parents=True, exist_ok=True)
            mask.save(dest)
        entries[tex] = {"emissiveMult": EMIS}
        print(f"  {tex}  {img.size[0]}x{img.size[1]}  {len(found)} eye texels  "
              f"art {exact} -> mask #{paint[0]:02x}{paint[1]:02x}{paint[2]:02x}  emis {EMIS}")

    for path in JSON_TARGETS:
        upsert(path, entries)
        print(f"  upserted {len(entries)} entries -> {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
