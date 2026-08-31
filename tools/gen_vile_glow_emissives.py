"""Flame-glow emissive masks for the Unseen Evil Arch-Vile (RTGL1).

The Baron family's fist glow (tools/gen_hand_glow_emissives.py) is masked from
the mod's OWN authored brightmaps -- the artists drew where the fire is and the
tool just reads it. Unseen Evil ships no monster brightmaps at all: its 49
brightmap lumps are wall and switch textures. So the mask here comes from the
art itself, by colour, at a threshold chosen PER FRAME by eye.

THE THRESHOLDS ARE REVIEWED, NOT GUESSED. One floor cannot serve the whole cast:
the wind-up is a thin rim of fire and the peak is a wall of it, so a value that
reads H correctly floods J. FLOORS below was set frame by frame in the review
page and read back out of it:

    tools/build_vile_glow_gallery.py
    https://claude.ai/code/artifact/4c64fc5a-3d12-473a-98d7-1e92616e125d

Four frames are deliberately EMPTY and must stay that way. G is the wind-up
before the fire exists, and Z/[/^ are the resurrection gesture, which is not a
flame at all -- all four were set to the maximum, selecting nothing. A generator
that "helpfully" lit them would be inventing fire the artist never drew.

NO lightIntensity IS WRITTEN, and any found is REMOVED. RTGL1 pins a sprite's
attached light to the centre of the billboard quad (VulkanDevice.cpp: center =
average of the 4 quad verts), so a lightIntensity on a frame whose fire is in
the raised hands puts the light in the chest -- and with two hands, both average
into one point between them. That is the reported "the light doesn't match where
the flames are". The cast light belongs on per-flame analytic lights, the way
RT_UploadHandGlowLights does it for the Baron; this file writes only the glow.

Outputs (all four mat dirs, or the change is inert -- developerMode reads
mat_dev, and the build xcopies the shipped tree over the build one):
  rt/mat[_dev]/<FRAME>_e.png
  rt/data/textures.json   (both trees, via patch_global)
"""
from __future__ import annotations

import io
import sys
import zipfile
from pathlib import Path

from PIL import Image

PROJ_ROOT = Path(__file__).resolve().parents[1]
PK3 = PROJ_ROOT / "Doom64-Retribution" / "d64r-ue-monsters.pk3"

BUILD = PROJ_ROOT / "sourcecode" / "gzdoom-rt" / "build" / "RelWithDebInfo" / "rt"
SHIP = PROJ_ROOT / "Doom64-Retribution" / "Retribution-RT-Materials" / "rt"
MAT_DIRS = [BUILD / "mat_dev", BUILD / "mat", SHIP / "mat_dev", SHIP / "mat"]

# Read back from the review page, frame by frame. 300 means "nothing here".
FLOORS = {
    "G": 300, "H": 182, "I": 190, "J": 206, "K": 231,
    "L": 202, "M": 231, "N": 257, "O": 195, "P": 170,
    "Z": 300, "[": 300, "^": 300,
}

# The Baron's value. emissiveMult is what makes the masked texels glow; it does
# NOT light the room on its own.
EMISSIVE_MULT = 4.0
LIGHT_KEYS = ("lightIntensity", "lightColorHEX", "lightEvenOnDynamic")

# --- eyes ------------------------------------------------------------------
#
# THE EYES ARE DRAWN, NOT DETECTED, and they live here rather than in a second
# generator ON PURPOSE: this file writes the whole VILE _e set, so a separate
# eye pass would be silently erased by the next flame run. One owner, one image.
#
# Threshold detection was tried and rejected on the evidence -- the Revenant's
# eyes are 4 texels of pure (128,0,0) and separate cleanly, but the Arch-Vile's
# gave ONE texel at the same settings, and a floor low enough to catch it also
# catches the body. So they were painted by hand, one or two texels each, in:
#     tools/build_sprite_mark_gallery.py
#     https://claude.ai/code/artifact/8401f74e-1309-43c6-8448-9597a541b66c
#
# Only 26 of the 127 living lumps carry an eye, and that is the artist's call,
# not an omission: the eye is only visible on the front-ish rotations (1,2,3,7,8)
# of the walk, on the cast's tail, and on the heal. Rear rotations have none.
#
# Yellow-orange, not the ff0a00 red gen_enemy_eye_emissives uses for
# Retribution's monsters -- asked for explicitly, and it keeps the Arch-Vile
# distinct from every other lit eye in the game.
EYE_HEX = "ffc040"
# 4x the EMIS=2.0 that file uses for Retribution's eyes. Those are clusters;
# this is ONE TEXEL, and it has to read as a hot point at gameplay distance.
# This is the knob if it is too much.
EYE_EMISSIVE_MULT = 8.0

# lump -> pixel indices (y * width + x), straight from the painter.
EYES = {
    "VILEA1D1": [973, 979],
    "VILEA2D8": [1591, 1683],
    "VILEA3D7": [1698],
    "VILEA7D3": [1748],
    "VILEA8D2": [1250, 1254],
    "VILEB1E1": [1168, 1174],
    "VILEB2E8": [1178, 1182],
    "VILEB3E7": [1181],
    "VILEB7E3": [1275],
    "VILEB8E2": [970],
    "VILEC1F1": [1172, 1179],
    "VILEC2F8": [737, 741],
    "VILEC3F7": [1236],
    "VILEC7F3": [1174],
    "VILEC8F2": [1426, 1430],
    "VILEP8": [1588, 1592],
    "VILEQ1": [1053, 1059],
    "VILEQ2": [1155, 1230],
    "VILEQ3": [1243],
    "VILEQ7": [1267],
    "VILEQ8": [1240, 1244],
    "VILEZ1": [583, 589],
    "VILEZ2Z8": [543],
    "VILE[1": [1508, 1514],
    "VILE[2[8": [1369, 1374],
    "VILE[3[7": [923],
}


def hot(px, floor: int) -> bool:
    r, g, b, a = px
    if a < 128:
        return False
    # Same test as the review page, including the clamp: red saturates at 255, so
    # past that the floor keeps biting through colour purity and total brightness
    # instead of going dead.
    return r >= min(floor, 255) and r - b >= floor * 0.4 and r + g + b >= floor * 1.8


def build_e(albedo: Image.Image, floor: int) -> tuple[Image.Image, int]:
    """Masked texels, hue saturated to full range; everything else transparent.

    NOT the raw albedo: RsWorld.inl multiplies by baseColor again, and squaring
    dark art annihilates the glow (same reason gen_hand_glow_emissives saturates).
    Intensity ramps with the texel's own luminance, which is the only ramp there
    is here -- the Baron gets its ramp from the brightmap.
    """
    data = list(albedo.convert("RGBA").get_flattened_data())
    lums = [max(p[0], p[1], p[2]) for p in data if hot(p, floor)]
    top = max(lums) if lums else 0
    out, peak = [], 0
    for p in data:
        if not hot(p, floor) or top == 0:
            out.append((0, 0, 0, 0))
            continue
        r, g, b, _ = p
        t = 0.55 + 0.45 * (max(r, g, b) / top)          # never dimmer than ~55%
        k = (255.0 / max(r, g, b)) * min(1.0, t)
        q = (min(255, int(r * k)), min(255, int(g * k)), min(255, int(b * k)), 255)
        peak = max(peak, q[0], q[1], q[2])
        out.append(q)
    img = Image.new("RGBA", albedo.size)
    img.putdata(out)
    return img, peak


def paint_eyes(img: Image.Image, lump: str) -> int:
    """Burn the hand-painted eye texels into an _e, over whatever is there.

    Written at FULL intensity in EYE_HEX rather than the texel's own hue: the
    eye is one or two texels of fairly ordinary skin colour in the art, so
    saturating what is there gives a dull dot. The glow is authored.
    """
    px = EYES.get(lump)
    if not px:
        return 0
    r = int(EYE_HEX[0:2], 16), int(EYE_HEX[2:4], 16), int(EYE_HEX[4:6], 16)
    w, h = img.size
    data = list(img.get_flattened_data())
    n = 0
    for i in px:
        if 0 <= i < w * h:
            data[i] = (r[0], r[1], r[2], 255)
            n += 1
    img.putdata(data)
    return n


def main() -> int:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    try:
        from gen_enemy_eye_emissives import patch_global
    except ModuleNotFoundError as exc:
        raise SystemExit(
            f"{exc} -- run with the project venv: "
            r"tools\.venv-ai\Scripts\python.exe tools/gen_vile_glow_emissives.py")

    z = zipfile.ZipFile(PK3)
    lumps = {n.rsplit("/", 1)[-1].split(".")[0].upper(): n
             for n in z.namelist() if n.startswith("sprites/VILE")}

    entries: dict[str, dict] = {}
    written = skipped = 0

    # Every lump that needs an _e: the flame frames AND every lump carrying a
    # painted eye. The two sets barely overlap -- the eye is on the walk, the
    # cast's tail and the heal, the flame on G..P -- so iterating only FLOORS
    # would drop most of the eyes, and iterating only EYES would drop the flame.
    todo: dict[str, int] = {}
    for frame, floor in FLOORS.items():
        for n in lumps:
            if len(n) > 4 and n[4] == frame and not (len(n) > 6 and n[6] != frame):
                todo[n] = floor
    for n in EYES:
        todo.setdefault(n, 300)          # eye-only lump: no flame at any floor

    eyed = 0
    for tex in sorted(todo):
        floor = todo[tex]
        if tex not in lumps:
            print(f"  {tex}: painted but no such lump -- skipped")
            continue
        albedo = Image.open(io.BytesIO(z.read(lumps[tex]))).convert("RGBA")
        e_img, peak = build_e(albedo, floor)
        eye_n = paint_eyes(e_img, tex)
        eyed += 1 if eye_n else 0

        if peak == 0 and eye_n == 0:
            # Deliberate for G and the heal frames. Still clear any stale light
            # keys so an earlier run cannot leave a chest light behind.
            entries[tex] = {}
            skipped += 1
            continue

        for d in MAT_DIRS:
            d.mkdir(parents=True, exist_ok=True)
            e_img.save(d / f"{tex}_e.png")
        # A lump with both takes the HIGHER multiplier -- they share one, and a
        # one-texel eye needs far more than the flame does. Only the tail of the
        # cast is ever in both.
        mult = EYE_EMISSIVE_MULT if eye_n else EMISSIVE_MULT
        entries[tex] = {"emissiveMult": mult}
        written += 1

    patch_global(entries)
    lit = {f for f, v in FLOORS.items() if v < 300}
    eye_frames = sorted({n[4] for n in EYES if len(n) > 4})
    print(f"VILE glow: {written} lumps masked, {skipped} deliberately empty")
    print(f"  flame frames {''.join(sorted(lit))}")
    print(f"  eye lumps    {eyed} at {EYE_HEX} x{EYE_EMISSIVE_MULT}, frames {''.join(eye_frames)}")
    print(f"  no flame     {''.join(f for f in FLOORS if f not in lit)}  (wind-up + heal)")
    print(f"  wrote _e into {len(MAT_DIRS)} mat dirs, meta into both textures.json trees")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
