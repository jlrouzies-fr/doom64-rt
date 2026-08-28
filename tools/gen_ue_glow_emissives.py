"""Emissive masks for the Unseen Evil monsters that have glowing parts.

Covers the Spider Mastermind (red eyes + laser), the Revenant (red eye dots and
shoulder-launcher LEDs) and the Chaingunner (the green backpack).

PURITY, NOT HUE DOMINANCE, IS THE RULE FOR RED, and getting it wrong is the whole
trap. A dominance test (r>=140, r-g>=60, r-b>=60) matches 425..2922 texels per
Mastermind frame -- that is its red-brown BODY, not anything that glows.
Requiring green AND blue both under a cap gives 29 texels on the walk (two eyes)
and 341 on the firing frame. The CAP does the work; the level only decides how
dim a lit texel may be.

The Revenant needs the cap TIGHTER still, at 25. Its LEDs are near-pure --
(135,4,2), (146,17,10), (119,2,1) -- while its bones run a dull desaturated red,
(108,44,44) and (83,43,44). At cap 45 the bones pass and its missile frame goes
from 130 texels to 618: the entire ribcage.

GREEN IS THE OPPOSITE CASE. The Chaingunner's backpack is a dark olive that peaks
at (43,104,27), so a purity test with a low red cap rejects it outright -- r=37
and r=43 fail an r<=25 cap, and the whole backpack scores ZERO. Green needs
dominance (g-r and g-b) with a floor on g, which is exactly the test that would
be wrong for red. One test per monster, named in its config.

FOUR THINGS, ONE COLOUR, SPLIT BY GEOMETRY. Eyes, LEDs and a gun flash are the
same red and cannot be told apart by threshold. Three filters do it:

  min_blob   a connected patch under N texels is a SPECK, not a feature. The
             Mastermind's wind-up carried nine of them (1..3 texels at up 26..59)
             and they rendered as a constellation of dots on a monster that had
             not fired. But the REVENANT'S FLOOR IS 1, and that is not a typo:
             its right shoulder LED is a single texel, (90,4,2), and a floor of 2
             deleted it on every frame it appears on.
  eye_band   on a NON-FIRING frame only the eyes glow, and height is what
             separates them from the gun. The firing frame is exempt -- that is
             when the low red IS the point.
  cluster    keep only blobs within R texels of the largest. The Mastermind's
             firing frame needs this: the same threshold matches four armour
             highlights on the LEGS at lat +-33..+-42, 24 and 25 texels each, big
             enough to outrank real parts of the flash. Size cannot separate them
             and a lateral window cannot either (on side rotations the gun itself
             sits at lat -48). Distance can.

NO CAST LIGHT IS WRITTEN HERE. Anything that should light the room does it
through an analytic light at the blob position (tools/gen_hand_light_offsets.py),
never a textures.json lightIntensity -- RTGL1 pins one of those to the centre of
the billboard quad, which is how the Chaingunner ended up with a warm blob on his
chest and both barrels dark.

    tools\\.venv-ai\\Scripts\\python.exe tools/gen_ue_glow_emissives.py
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

# THE LEVELS ARE REVIEWED, NOT GUESSED -- set in the detection page and read back
# out of it. They are NOT the same number per monster, so a single global constant
# would quietly be wrong for one of them:
#     tools/build_glow_gallery.py
#     https://claude.ai/code/artifact/2af23f42-3173-4bf9-94a8-727c4488a335
MONSTERS = {
    "SPID": {
        "alive": "ABCDEFGHZ",          # I..S is death
        "gun": "H",
        "test": ("red", 112, 40),      # the EYES need this low: 29 texels at 112, ZERO at 180
        # ...but the firing frame needs it HIGH, and this is not a preference. At
        # 112 it takes 1440 texels: the dark red ARMOUR (143,15,14 / 114,15,16 /
        # 173,18,16) passes purity just as the laser does, and the whole chassis
        # reads as neon. 235 keeps 341 -- (236,19,9) and (251,9,0).
        # H ONLY. G is the wind-up, whose gun has NOT fired; raising G left 7
        # texels where its eyes had 25, so the wind-up went dark.
        "level_by_frame": {"H": 235},
        "eye_band": 75.0,              # eyes sit at up 99..103; the gun is all below
        "cluster": {"H": 30.0},        # drops the leg highlights, keeps the muzzle column
        "min_blob": 6,
        "eye_mult": 8.0,               # ~14 texels an eye
        "gun_mult": 3.0,               # ~300 texels -- would blow out at 8
    },
    "SKEL": {
        "alive": "ABCDEFGHIJK",        # L is pain AND the first death frame; excluded
        "gun": "J",                    # the missile launch flare, ~130 texels
        "test": ("red", 70, 25),
        "min_blob": 1,                 # see the module docstring -- a 1-texel LED is real
        # ...but the launch flare is not an LED. A floor of 1 left J at 130 texels
        # in 25 blobs, ~14 of them single specks around a flare whose real parts
        # are 38 and 34. The floor has to be per-frame because the same monster
        # needs both answers.
        "min_blob_by_frame": {"J": 3},
        # No eye_band and no cluster: the eyes (up ~107) and the shoulder LEDs
        # (up ~112..115) are BOTH wanted, they are 5 texels apart in height, and
        # every frame here is small enough that nothing spurious survives cap 25.
        "eye_mult": 10.0,              # dots are 1..4 texels; the Arch-Vile's use 8 at 1..2
        "gun_mult": 3.0,
    },
    "CPOS": {
        "alive": "ABCDEFG",            # H..P is death
        "gun": "",                     # the backpack is not a weapon; one multiplier
        # Dominance, not purity -- the olive peaks at (43,104,27) and a red-style
        # cap would score the whole backpack at zero. Floor on g stops the
        # near-black (8,29,4) shading from joining in.
        "test": ("green", 45, 25, 25),
        "min_blob": 4,
        # PEAK 180, NOT THE DEFAULT 255. Saturating this olive to full range gives
        # (105,255,66) -- a neon, radioactive green that reads nothing like the
        # painted backpack. The ray-traced path uses _e RAW, so whatever is written
        # here IS the emitted colour; 180 keeps it a normal mid green, (74,180,46).
        "peak": 180,
        "eye_mult": 2.5,               # with peak 180 this is ~1/3 the old 255x6
        "gun_mult": 2.5,
    },
}


def hot(px, test) -> bool:
    """One texel against this monster's rule."""
    r, g, b, a = px
    if a < 128:
        return False
    if test[0] == "red":
        _, level, cap = test
        return r >= level and g <= cap and b <= cap
    _, level, dr, db = test          # green dominance
    return g >= level and g - r >= dr and g - b >= db


def serves(name: str, sprite: str) -> list[str]:
    """Frames a lump serves. SPIDA1D1 is frame A rot 1 AND frame D rot 1."""
    rest = name[len(sprite):]
    out = []
    if len(rest) >= 2:
        out.append(rest[0])
    if len(rest) >= 4:
        out.append(rest[2])
    return out


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


def centre(c):
    return (sum(p[0] for p in c) / len(c), sum(p[1] for p in c) / len(c))


def build_e(albedo: Image.Image, test, min_blob: int,
            band: float | None = None, oy: int = 0,
            cluster: float | None = None, peak: int = 255) -> tuple[Image.Image, int]:
    """Glowing texels, hue saturated to full range; everything else transparent.

    NOT the raw albedo: RsWorld.inl multiplies by baseColor again, and squaring
    dark art annihilates the glow. Same reason gen_hand_glow_emissives saturates,
    and the reason the Chaingunner's dim olive can work at all.

    `peak` is how far the saturation goes, and it is a COLOUR decision, not a
    brightness one. The ray-traced path reads _e RAW, so this value IS the emitted
    hue: 255 gave the Chaingunner (105,255,66), a radioactive green nothing like
    the painted backpack. 180 gives (74,180,46). Brightness belongs in the mult.

    See the module docstring for why all three filters exist.
    """
    src = albedo.convert("RGBA")
    w, _ = src.size
    data = list(src.get_flattened_data())
    lit = {(i % w, i // w) for i, p in enumerate(data) if hot(p, test)}
    if band is not None:
        lit = {p for p in lit if (oy - p[1]) > band}

    comps = [c for c in blobs(lit) if len(c) >= min_blob]
    if cluster and comps:
        comps.sort(key=len, reverse=True)
        hx, hy = centre(comps[0])
        comps = [c for c in comps
                 if ((centre(c)[0] - hx) ** 2 + (centre(c)[1] - hy) ** 2) ** 0.5 <= cluster]
    keep = {p for c in comps for p in c}

    out, n = [], 0
    for i, p in enumerate(data):
        if (i % w, i // w) not in keep:
            out.append((0, 0, 0, 0))
            continue
        r, g, b, _ = p
        k = float(peak) / max(r, g, b)
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
            r"tools\.venv-ai\Scripts\python.exe tools/gen_ue_glow_emissives.py")

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
            raw = z.read(lumps[name])
            albedo = Image.open(io.BytesIO(raw)).convert("RGBA")

            test = cfg["test"]
            for f in fr:
                lvl = cfg.get("level_by_frame", {}).get(f)
                if lvl is not None:
                    test = (test[0], lvl) + tuple(test[2:])
            is_gun = any(f in cfg["gun"] for f in fr)
            band = None if is_gun else cfg.get("eye_band")
            cluster = None
            for f in fr:
                cluster = cfg.get("cluster", {}).get(f, cluster)

            floor_n = cfg["min_blob"]
            for f in fr:
                floor_n = cfg.get("min_blob_by_frame", {}).get(f, floor_n)

            e_img, n = build_e(albedo, test, floor_n,
                               band, grab_oy(raw), cluster, cfg.get("peak", 255))
            if n == 0:
                # CLEAR BOTH SIDES. Clearing only the meta leaves the _e PNG from
                # an earlier, looser run sitting on disk, and RTGL1 picks an _e up
                # by filename -- so the frame keeps glowing with no row to explain
                # it. Tightening min_blob on the Revenant's J orphaned exactly one
                # (SKELJ5) and the count mismatch, 87 files against 86 rows, was
                # the only thing that showed it.
                entries[name] = {}
                for d in MAT_DIRS:
                    stale = d / f"{name}_e.png"
                    if stale.exists():
                        stale.unlink()
                        print(f"  removed stale {stale.parent.name}/{stale.name}")
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
        print(f"{sprite}: {eyes} glow lumps x{cfg['eye_mult']}, "
              f"{guns} gun lumps x{cfg['gun_mult']}, {empty} with nothing lit")

    patch_global(entries)
    print(f"  wrote _e into {len(MAT_DIRS)} mat dirs, meta into both textures.json trees")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
