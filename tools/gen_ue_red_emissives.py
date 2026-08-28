"""Red emissive masks for the Unseen Evil monsters that glow red.

Covers the Spider Mastermind now; the Revenant slots into MONSTERS unchanged
when its turn comes (its eye dots are 1..4 texels on nearly every frame and its
launcher elements light on J -- 82 texels on J1).

PURITY, NOT REDNESS, IS THE RULE, and getting it wrong is the whole trap. A
dominance test (r>=140, r-g>=60, r-b>=60) matches 425..2922 texels per Mastermind
frame -- that is its red-brown BODY, not anything that glows. Requiring green and
blue both under a cap gives 29 texels on the walk (two eyes at lat +-13) and 1440
on the firing frame, at the reviewed level of 112. The CAP does the work; moving
the level from 120 to 112 added 7 texels to an eye and 253 to the flash.

TWO THINGS, ONE COLOUR, SPLIT BY FRAME. The eyes and the gun flash are the same
red and cannot be told apart by threshold. They are told apart by which frame
they appear on, which also decides how hot each gets: an eye is ~14 texels and
needs a high multiplier to read at all, while the gun flash is a hundred times
the area and would blow out at the same value.

NO CAST LIGHT IS WRITTEN HERE. Eyes never cast -- gen_enemy_eye_emissives keeps
EYE_LIGHT at 0 for exactly this reason, and a walking spider with two red lamps
for eyes is the failure it avoids. The gun flash DOES cast, but through an
analytic light at the flash position (tools/gen_hand_light_offsets.py, frame H),
not a textures.json lightIntensity -- RTGL1 pins one of those to the centre of
the billboard quad, which is how the Chaingunner ended up with a warm blob on his
chest and both barrels dark.

    tools\\.venv-ai\\Scripts\\python.exe tools/gen_ue_red_emissives.py
"""
from __future__ import annotations

import io
import struct
import sys
import zipfile
from pathlib import Path

from PIL import Image

PROJ_ROOT = Path(__file__).resolve().parents[1]
PK3 = PROJ_ROOT / "Doom64-Retribution" / "d64r-ue-monsters.pk3"

BUILD = PROJ_ROOT / "sourcecode" / "gzdoom-rt" / "build" / "RelWithDebInfo" / "rt"
SHIP = PROJ_ROOT / "Doom64-Retribution" / "Retribution-RT-Materials" / "rt"
MAT_DIRS = [BUILD / "mat_dev", BUILD / "mat", SHIP / "mat_dev", SHIP / "mat"]

# sprite -> living frames, the frames whose red is a GUN rather than an eye, and
# the two multipliers. Death frames are excluded per monster: the gore reuses the
# same palette ramp, so a threshold right for an eye lights a corpse.
# THE LEVELS ARE REVIEWED, NOT GUESSED. Set per monster in the detection page and
# read back out of it -- they are NOT the same number, so a single global constant
# would quietly be wrong for one of them:
#     tools/build_glow_gallery.py
#     https://claude.ai/code/artifact/2af23f42-3173-4bf9-94a8-727c4488a335
MONSTERS = {
    "SPID": {
        "alive": "ABCDEFGHZ",       # I..S is death
        "gun": "H",
        "level": 112, "cap": 40,    # reviewed: the EYES need this low -- they are 29
                                    # texels at 112 and ZERO at 180.
        # ...but the firing frames need it high, and this is not a preference.
        # At 112 the firing frame takes 1440 texels: the Mastermind's dark red
        # ARMOUR (143,15,14 / 114,15,16 / 173,18,16) passes the purity test just
        # as its laser does, and build_e then saturates every one of them to full
        # red -- the whole chassis reads as neon. 235 keeps 341, dropping the
        # armour and keeping (236,19,9) and (251,9,0).
        # H ONLY. G is the wind-up: its gun has not fired, and raising G too
        # left 7 texels where its EYES had 25, so the wind-up went dark.
        "level_by_frame": {"H": 235},
        # ON A NON-FIRING FRAME, ONLY THE EYES GLOW. Height is what separates
        # them: the eyes sit at up ~99..103 and everything the gun contributes is
        # below. Without this the wind-up frame kept three mid-sized red patches
        # low on the chassis -- a constellation of dots under the eyes on a spider
        # that had not fired yet. The firing frame is exempt: that is when the low
        # red IS the point.
        "eye_band": 75.0,
        "eye_mult": 8.0,            # ~14 texels; same value the Arch-Vile's eyes use
        "gun_mult": 3.0,            # 1440 texels -- would blow out at 8
    },
}


def red_hot(px, level: int, cap: int) -> bool:
    r, g, b, a = px
    return a >= 128 and r >= level and g <= cap and b <= cap


def serves(name: str, sprite: str) -> list[str]:
    """Frames a lump serves. SPIDA1D1 is frame A rot 1 AND frame D rot 1."""
    rest = name[len(sprite):]
    out = []
    if len(rest) >= 2:
        out.append(rest[0])
    if len(rest) >= 4:
        out.append(rest[2])
    return out


# Texels a connected red patch needs to survive. Below this it is a SPECK, not a
# feature: the wind-up frame carried nine of them, 1..3 texels each scattered at
# up 26..59, and they rendered as a constellation of dots under the eyes on a
# spider that was not even firing yet. An eye is 13..16 texels; a laser blob is
# dozens. Nothing real is this small.
MIN_BLOB = 6


def blobs(lit: set[tuple[int, int]]) -> list[list[tuple[int, int]]]:
    """8-connected components of the mask."""
    seen: set[tuple[int, int]] = set()
    out = []
    for start in lit:
        if start in seen:
            continue
        stack, cells = [start], []
        seen.add(start)
        while stack:
            x, y = stack.pop()
            cells.append((x, y))
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    p = (x + dx, y + dy)
                    if p in lit and p not in seen:
                        seen.add(p)
                        stack.append(p)
        out.append(cells)
    return out


def grab_oy(png: bytes) -> int:
    """The sprite's feet row, from grAb -- heights are measured from it."""
    i = 8
    while i + 8 <= len(png):
        ln, typ = struct.unpack(">I4s", png[i:i + 8])
        if typ == b"grAb":
            return struct.unpack(">ii", png[i + 8:i + 16])[1]
        if typ == b"IEND":
            break
        i += 12 + ln
    return 0


def build_e(albedo: Image.Image, level: int, cap: int,
            band: float | None = None, oy: int = 0) -> tuple[Image.Image, int]:
    """Red texels, hue saturated to full range; everything else transparent.

    NOT the raw albedo: RsWorld.inl multiplies by baseColor again, and squaring
    dark art annihilates the glow. Same reason gen_hand_glow_emissives saturates.

    Specks are dropped -- see MIN_BLOB. A per-texel threshold has no notion of
    "is this a thing", so without it every stray red pixel on the sprite becomes
    a glowing dot.
    """
    src = albedo.convert("RGBA")
    w, h = src.size
    data = list(src.get_flattened_data())
    lit = {(i % w, i // w) for i, p in enumerate(data) if red_hot(p, level, cap)}
    if band is not None:
        lit = {p for p in lit if (oy - p[1]) > band}
    keep = {p for c in blobs(lit) if len(c) >= MIN_BLOB for p in c}

    out, n = [], 0
    for i, p in enumerate(data):
        if (i % w, i // w) not in keep:
            out.append((0, 0, 0, 0))
            continue
        r, g, b, _ = p
        k = 255.0 / max(r, g, b)
        out.append((min(255, int(r * k)), min(255, int(g * k)), min(255, int(b * k)), 255))
        n += 1
    img = Image.new("RGBA", src.size)
    img.putdata(out)
    return img, n


def main() -> int:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    try:
        from gen_enemy_eye_emissives import patch_global
    except ModuleNotFoundError as exc:
        raise SystemExit(
            f"{exc} -- run with the project venv: "
            r"tools\.venv-ai\Scripts\python.exe tools/gen_ue_red_emissives.py")

    z = zipfile.ZipFile(PK3)
    lumps = {n.rsplit("/", 1)[-1].split(".")[0].upper(): n
             for n in z.namelist() if n.startswith("sprites/")}

    entries: dict[str, dict] = {}
    for sprite, cfg in MONSTERS.items():
        eyes = guns = empty = 0
        for name in sorted(lumps):
            if not name.startswith(sprite):
                continue
            fr = [f for f in serves(name, sprite) if f in cfg["alive"]]
            if not fr:
                continue
            albedo = Image.open(io.BytesIO(z.read(lumps[name]))).convert("RGBA")
            lvl = cfg["level"]
            for f in fr:
                lvl = cfg.get("level_by_frame", {}).get(f, lvl)
            is_gun = any(f in cfg["gun"] for f in fr)
            band = None if is_gun else cfg.get("eye_band")
            e_img, n = build_e(albedo, lvl, cfg["cap"], band, grab_oy(z.read(lumps[name])))
            if n == 0:
                entries[name] = {}          # clear any stale meta
                empty += 1
                continue
            for d in MAT_DIRS:
                d.mkdir(parents=True, exist_ok=True)
                e_img.save(d / f"{name}_e.png")
            entries[name] = {"emissiveMult": cfg["gun_mult"] if is_gun else cfg["eye_mult"]}
            if is_gun:
                guns += 1
            else:
                eyes += 1
        print(f"{sprite}: {eyes} eye lumps x{cfg['eye_mult']}, "
              f"{guns} gun lumps x{cfg['gun_mult']}, {empty} with no red")

    patch_global(entries)
    print(f"  wrote _e into {len(MAT_DIRS)} mat dirs, meta into both textures.json trees")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
