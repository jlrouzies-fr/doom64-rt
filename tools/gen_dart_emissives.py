"""Dark-red glow for the DART projectile — the trap darts and the nailgun's nails.

`DART` is used by two actors in D64RTR_v15's DECORATE:

    ACTOR 64Dart          Spawn: DART A 1     trap darts (thing 896, "Dart")
    ACTOR 64NailShot      Spawn: DART AA 1    the nailgun's nail, FastProjectile

Neither state is `BRIGHT`, and the art is almost black — the whole sprite is a grey
ramp of (8,8,8)..(56,56,56) with a dark red head painted in exactly two shades. In a
dark room the thing is invisible until it hits you, which is the report this fixes.

WHY EXACT-COLOUR AUTO-DETECT IS SAFE HERE
-----------------------------------------
Same argument as `tools/gen_statue_eye_emissives.py`, and it holds even more tightly:
there is no red *range* on this sprite to get wrong. Every non-red texel in all five
lumps is a pure grey (r == g == b), and the red is two exact palette entries:

    DARTA1     16x12    (40,0,0) x8    (56,0,0) x4
    DARTA2A8   32x11    (40,0,0) x9    (56,0,0) x7
    DARTA3A7   32x11    (40,0,0) x12   (56,0,0) x3
    DARTA4A6   32x11    (40,0,0) x5    (56,0,0) x3
    DARTA5     16x10    none                          <- rear view, no red at all

`ART_COUNTS` asserts those numbers on every run, so if the WAD is ever swapped for one
whose dart is painted differently this fails loudly instead of quietly inventing a glow.
`DARTA5` is deliberately in the table with zeros and gets no mask and no meta: the back
of a dart has no red head to light, and writing an empty `_e` would only give the
hygiene checker a stray to trip over.

COLOUR — "dark red" is the HUE, not a dim mask
----------------------------------------------
Painting the mask at the art's own (56,0,0) is the mistake `docs/sprite-illumination.md`
Mechanism 3 exists to prevent: under RT the primary emission is the RAW `_e` sample, so a
mask painted 0.22 renders at 0.22 and stays invisible — which is the bug. The mask is
therefore painted at full range in a deep red, `e01000`, the same "true red" pinned for
BOSS in Case 4 for exactly this reason (a dark red normalised to peak 255 across all three
channels comes out orange; a pinned deep red does not). The art's two shades survive as a
two-step ramp — (56,0,0) at the peak, (40,0,0) at 40/56 of it — so the head keeps its
shading instead of becoming a flat blob.

NO CAST LIGHT
-------------
`emissiveMult` only. A nail is a FastProjectile the nailgun fires in bursts, and a
sprite's attached light anchors at the billboard centre (Mechanism 2) — a stream of them
would each drop a light into the scene for the length of their flight. The ask is
visibility, and on-screen emission is what delivers it. If a dart should later throw a
red pool onto the wall it passes, that is an engine-side light on the `RT_FLAME_KINDS`
pattern, not a number here.

Output:
    rt/mat/<LUMP>_e.png  (+ mat_dev, + the Retribution-RT-Materials overlay)
    textures.json        emissiveMult only, upserted into the four live targets
"""
from __future__ import annotations

import io
import json
import struct
from pathlib import Path

from PIL import Image

# Repo root, derived from this file so a clone can live anywhere.
ROOT = Path(__file__).resolve().parents[1]

WAD = ROOT / r"Doom64-Retribution\D64RTR_v15.WAD"
MAT = ROOT / r"sourcecode\gzdoom-rt\build\RelWithDebInfo\rt\mat"
MAT_DEV = ROOT / r"sourcecode\gzdoom-rt\build\RelWithDebInfo\rt\mat_dev"
OMAT = ROOT / r"Doom64-Retribution\Retribution-RT-Materials\rt\mat"

JSON_TARGETS = [
    ROOT / r"sourcecode\gzdoom-rt\build\RelWithDebInfo\rt\data\textures.json",
    ROOT / r"sourcecode\gzdoom-rt\build\RelWithDebInfo\rt\data\scenes\d64rtr_v15_map01\textures.json",
    ROOT / r"Doom64-Retribution\Retribution-RT-Materials\rt\data\textures_dart.json",
    ROOT / r"Doom64-Retribution\Retribution-RT-Materials\rt\data\scenes\d64rtr_v15_map01\textures.json",
]

# The enemy-eye / statue-eye house value. A dart head is 8-16 texels; without the
# multiplier the indirect half contributes nothing at all.
EMIS = 2.0

# Deep red, full range. See the COLOUR note above — do not "fix" this to ff0000 or to
# a saturation-normalised sample of the art.
RED = (224, 16, 0)

# art colour -> fraction of RED to paint. Brightest art shade lands on RED itself.
LEVELS = {
    (56, 0, 0): 1.0,
    (40, 0, 0): 40 / 56,
}

# lump -> {art colour: expected texel count}. Asserted on every run.
ART_COUNTS: dict[str, dict[tuple[int, int, int], int]] = {
    "DARTA1":   {(40, 0, 0): 8,  (56, 0, 0): 4},
    "DARTA2A8": {(40, 0, 0): 9,  (56, 0, 0): 7},
    "DARTA3A7": {(40, 0, 0): 12, (56, 0, 0): 3},
    "DARTA4A6": {(40, 0, 0): 5,  (56, 0, 0): 3},
    "DARTA5":   {},  # rear view: no red head visible, no mask written
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


def build_mask(img: Image.Image) -> tuple[Image.Image, dict[tuple[int, int, int], int]]:
    """Exact-colour lookup -> two-step full-range red ramp. No dilate, no halo."""
    rgba = img.convert("RGBA")
    w, h = rgba.size
    src = rgba.load()
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    dst = out.load()
    found: dict[tuple[int, int, int], int] = {}
    for y in range(h):
        for x in range(w):
            r, g, b, a = src[x, y]
            if a < 128:
                continue
            scale = LEVELS.get((r, g, b))
            if scale is None:
                continue
            dst[x, y] = (
                round(RED[0] * scale),
                round(RED[1] * scale),
                round(RED[2] * scale),
                255,
            )
            found[(r, g, b)] = found.get((r, g, b), 0) + 1
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
    for lump, want in ART_COUNTS.items():
        img = Image.open(io.BytesIO(wad_lump(lump)))
        mask, found = build_mask(img)

        if found != want:
            raise SystemExit(
                f"{lump}: red texels changed — the art is not what this tool was written\n"
                f"  against, so it will NOT guess. expected {want}\n"
                f"  found    {found}\n"
                f"  Re-measure before touching ART_COUNTS / LEVELS."
            )
        if not want:
            print(f"  {lump}  {img.size[0]}x{img.size[1]}  no red head — skipped")
            continue

        peak = mask.convert("RGB").getextrema()[0][1]
        assert peak == RED[0], f"{lump}: mask peaked at {peak}, expected {RED[0]}"

        for dest in (MAT / f"{lump}_e.png", MAT_DEV / f"{lump}_e.png", OMAT / f"{lump}_e.png"):
            dest.parent.mkdir(parents=True, exist_ok=True)
            mask.save(dest)
        entries[lump] = {"emissiveMult": EMIS}
        print(f"  {lump}  {img.size[0]}x{img.size[1]}  {sum(want.values())} red texels  "
              f"-> #{RED[0]:02x}{RED[1]:02x}{RED[2]:02x} ramp  emis {EMIS}")

    for path in JSON_TARGETS:
        upsert(path, entries)
        print(f"  upserted {len(entries)} entries -> {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
