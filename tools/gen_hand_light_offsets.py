"""
Derive fist positions + glow colour for the Baron family, for RT_UploadHandGlowLights.

Covers:
  BOS2  Hell Knight     green fists
  BOSS  Baron of Hell   red fists   ("the red hell knight")

Why this exists: RTGL1 attaches a sprite's light at the CENTRE of the billboard quad
(VulkanDevice.cpp, `center = average of the 4 quad verts`, radius 0.1). The glow is on the
fists, so the light came out of the torso, and the two fists averaged into a single point
between them. This emits real body-relative offsets so rt_main.cpp can upload one analytic
light per fist instead.

Mask geometry comes from the mod's authored brightmaps. BOSS ships NONE of its own — but
BOSS and BOS2 are the same artwork with a palette swap (verified: 12/12 frames have a
pixel-identical silhouette), so the BOS2 brightmaps transfer exactly. Each sprite is still
resolved against its OWN `grAb` origin, because those are not identical: BOSSA5 is (29,94)
where BOS2A5 is (29,93).

A Doom sprite's origin is (leftoffset, topoffset): the actor's centre column and its FEET
row. Assuming w/2 and the image bottom would bake in a per-frame error, since these
sprites are not symmetrically padded.

Only the front rotation (`1`) is used. Its horizontal axis is the actor's left-right axis,
which is what a lateral offset means; the forward axis is not observable there, so `fwd`
stays 0.

Eyes are in the brightmap too and must not become hand lights — they are dropped by the
MIN_BLOB texel floor, which they fall far below.

This file is the SINGLE SOURCE of the light colour used by the engine. gen_hand_glow_emissives.py
writes only emissiveMult, so the two cannot drift.

Output: sourcecode/gzdoom-rt/src/common/rendering/rt/rt_hand_lights.h (generated)
"""

from __future__ import annotations

import io
import struct
import zipfile
from collections import deque
from typing import NamedTuple
from pathlib import Path

from PIL import Image

# Repo root, derived from this file so a clone can live anywhere.
PROJ_ROOT = Path(__file__).resolve().parents[1]

ROOT = PROJ_ROOT
WAD = ROOT / r"Doom64-Retribution\D64RTR_v15.WAD"
# D64RTR_BRIGHTMAPS.PK3 is not in every checkout of Doom64-Retribution/ -- it is
# a shipped Retribution asset, and this tree only carries it under ReleaseTest/.
# Same file either way; fall back rather than fail, so the Baron rows can still be
# regenerated alongside the Arch-Vile's.
_BM_CANDIDATES = [
    ROOT / r"Doom64-Retribution\D64RTR_BRIGHTMAPS.PK3",
    ROOT / r"ReleaseTest\Doom64-RT\Doom64-Retribution\D64RTR_BRIGHTMAPS.PK3",
]
BM = next((p for p in _BM_CANDIDATES if p.is_file()), _BM_CANDIDATES[0])
OUT = ROOT / r"sourcecode\gzdoom-rt\src\common\rendering\rt\rt_hand_lights.h"

# (sprite, brightmap donor, C++ enum tag, human name, mask source)
#
# "bm"   -- the mod's authored brightmaps. The artists drew the glow.
# "fire" -- colour threshold at a per-frame floor reviewed by eye, for art that
#           ships NO brightmap. Unseen Evil is that case: all 49 of its brightmap
#           lumps are wall and switch textures, so the Arch-Vile has no authored
#           source and the floors come out of the review page instead (see
#           tools/gen_vile_glow_emissives.py, which shares them).
# "muzzle" -- the cool white-to-violet flash painted into the Chaingunner's two
#             barrels. Same reason as "fire": no brightmap exists. It needs its
#             own rule rather than the fire one because the flash is BLUE-biased
#             and the fire test is red-dominant, so the fire rule finds nothing
#             here and a red-dominant threshold loose enough to catch it would
#             take his skin instead.
MONSTERS = [
    ("BOS2", "BOS2", "RT_HAND_HELLKNIGHT", "Hell Knight", "bm"),
    ("BOSS", "BOS2", "RT_HAND_BARON", "Baron of Hell", "bm"),
    ("VILE", None, "RT_HAND_ARCHVILE", "Arch-Vile (Unseen Evil)", "fire"),
    ("CPOS", None, "RT_HAND_CHAINGUNNER", "Chaingunner (Unseen Evil)", "muzzle"),
    ("SPID", None, "RT_HAND_MASTERMIND", "Spider Mastermind (Unseen Evil)", "red"),
    ("SKEL", None, "RT_HAND_REVENANT", "Revenant (Unseen Evil)", "red"),
]

# Frames allowed to carry a LIGHT, where the mask alone would say yes to more.
#
# The Mastermind's eyes and its gun flash are the SAME RED -- 2 blobs of 9..12
# texels at lat +-13, up ~89..101 on the walk, against 1187 texels low and wide
# on H. Colour cannot separate them; the frame can. Without this gate the eyes
# become two analytic lamps on a walking spider, which is the exact failure
# gen_enemy_eye_emissives avoids by keeping EYE_LIGHT at 0.
LIGHT_ONLY_FRAMES = {}

# EYE BAND, in map units above the sprite's feet, per sprite.
#
# The Mastermind's eyes and its laser are the same red and the same frames, so
# neither colour nor frame can separate them -- but HEIGHT can. On the firing
# frame the eyes are still up at lat +-9, up 82 while all 1313 texels of laser
# sit below 75. Split there and the eyes get their own light on every frame,
# which is what they could not have while the mask was one blob.
#
# A frame keeps only TWO lights (RtHandPos hands[2]), so on the firing frame the
# gun wins: it is 1313 texels against 127, and losing a dim eye light for one
# frame is not visible. Every other frame is eyes.
EYE_BAND = {"SPID": 75.0}

# Keep only blobs within R texels of the LARGEST blob, per sprite and frame.
# The Mastermind's firing frame is why: its muzzle is three blobs clustered at
# lat ~-1, up 27..55, but the same threshold also matches four armour highlights
# on the LEGS (lat +-33..+-42) and a row under the ribcage (up 72..77). Those are
# 25 and 24 texels, big enough to outrank real parts of the flash, so a size rule
# cannot separate them -- distance can. A lateral window cannot either: on the
# side rotations the gun itself sits at lat -48 or -65.
CLUSTER_RADIUS = {"SPID": {"H": 30.0}}

# Intensity multiplier per frame kind. Eyes are a soft glow, a gun flash is not,
# and one cvar has to serve both -- so the table carries the ratio.
EYE_SCALE = 0.10


# Reviewed per monster in the detection page, same source as
# gen_ue_red_emissives.MONSTERS -- keep the two in step or the light will sit at
# the centroid of a mask different from the one that glows.
RED_LEVEL = {"SPID": (112, 40), "SKEL": (70, 25)}
# SKEL's cap is TIGHT on purpose. Its LEDs are near-pure -- (135,4,2), (146,17,10),
# (119,2,1) -- while its bones run a dull desaturated red, (108,44,44) / (83,43,44).
# A cap of 45 lets the bones through and frame J goes from 130 texels to 618: the
# whole ribcage. The cap does the discriminating; the level only sets how dim an
# LED may be, and 70 is what recovers the eyes on frames B, E and F.

# Per-frame override, mirroring gen_ue_red_emissives.level_by_frame. The light
# must sit at the centroid of the SAME texels that glow -- at 112 the firing
# frame's mask is mostly armour, so the light would be placed by the armour.
RED_LEVEL_BY_FRAME = {"SPID": {"H": 235}}


def red_hot(px, level: int, cap: int) -> bool:
    """A texel of a red glow -- eye or gun.

    PURITY, not redness. A dominance test (r>=140, r-g>=60, r-b>=60) matches
    425..2922 texels per Mastermind frame, which is its red-brown BODY. Requiring
    green and blue both near zero gives 29 on the walk and 1440 on the firing frame.
    """
    r, g, b, a = px
    return a >= 128 and r >= level and g <= cap and b <= cap


def ue_lump(ue: dict, sprite: str, letter: str) -> str | None:
    """The pk3 lump holding this frame's FRONT rotation.

    A lump can serve two frames -- SPIDA1D1 is frame A rotation 1 AND frame D
    rotation 1 -- so "<sprite><letter>1" finds only the single-frame ones. Looking
    just there silently dropped every walk frame of the Mastermind, which is where
    its eyes are.
    """
    direct = f"{sprite}{letter}1"
    if direct in ue:
        return direct
    for name in sorted(ue):
        if not name.startswith(sprite):
            continue
        rest = name[len(sprite):]
        if len(rest) == 4 and rest[1] == "1" and rest[3] == "1":
            if rest[0] == letter or rest[2] == letter:
                return name
    return None


def muzzle_hot(px) -> bool:
    """A texel of the Chaingunner's muzzle flash.

    Bright, no channel dark, and never warm: the flash runs cool white
    (216,216,240) to violet (192,168,240), so blue must not fall far below red.
    That last term is what keeps his orange-lit skin and the red jacket out.
    """
    r, g, b, a = px
    return a >= 128 and max(r, g, b) >= 190 and min(r, g, b) >= 90 and (b - r) >= -20

# Our Arch-Vile sprites live in the add-on pk3, not the Retribution WAD.
UE_PK3 = ROOT / r"Doom64-Retribution\d64r-ue-monsters.pk3"

# Aesthetic override of the sampled colour, per sprite.
#
# BOSS: sampling gives ff4c06, which reads ORANGE and was rejected. That is an artefact of
# saturation-normalising, not of the art: the Baron's lit average is (93,28,2), and scaling
# it to peak 255 multiplies GREEN by the same 2.7x as red, so a dark red becomes orange.
# Pinning a true red instead. "Darker" is better expressed through rt_hand_light_intensity
# than by dimming the hue, since the hue is what tints the room.
#
# BOS2 is not overridden: green dominates its ramp so hard that normalising cannot shift
# the hue, and the sampled 08ff5e was accepted in play.
# BOS2 is pinned to the exact value that was accepted in play. Left unpinned it samples
# to 09ff4b here, because this script averages only the front rotations while the value
# in play came from all 40 frames — a small shift, but not one worth making silently.
#
# VILE: pinned to ff9028, which is Retribution's OWN flame light -- the colour its
# Lost Soul fire already casts (the SKUL rows in textures.json). Sampling the art
# would land somewhere near it anyway, and matching the game's existing flame
# exactly is worth more than a second, slightly different orange.
COLOR_OVERRIDE = {
    "BOSS": "e01000",
    "BOS2": "08ff5e",
    "VILE": "ff9028",
}

# A..P. The Baron family only ever fills A..H -- it has no brightmap past that and
# I..N are its death/gib frames, which must stay dark because the gore reuses the
# hand glow's palette ramp. The range runs to P for the Arch-Vile, whose cast is
# frames G..P. Its own death frames R..Y fall outside the table and so cannot light.
FRAMES = "ABCDEFGHIJKLMNOP"
# Texels a blob needs to become a light, per sprite. The Baron's floor of 8 exists
# to keep its EYE dots out; the Revenant's red IS eyes and shoulder launchers, at
# 2..5 texels each, so the same floor would reject every one of them.
MIN_BLOB_DEFAULT = 8
# SKEL is 1, and that is not a typo. Its right shoulder LED is a SINGLE texel on
# frame A -- (90,4,2) at lat +20, up 115 -- and on frame B the artist drew that
# same spot unlit, cool grey (93,94,113). So a floor of 2 deleted the only frame
# the LED ever appears on, and it cast no light on ANY frame while the 4-texel
# left LED lit fine. That is the whole "one launcher works, the other doesn't".
MIN_BLOB_BY_SPRITE = {"SKEL": 1}

# FOUR, not two. The Revenant wants both eyes AND both shoulder launchers lit at
# their own positions; two slots can only ever show half of that.
MAX_HANDS = 4


class Hand(NamedTuple):
    lat: float
    up: float
    fwd: float
    scale: float
    colour: str | None   # hex, None = inherit the monster's
    eye: bool


# A SECOND SOURCE ON THE SAME MONSTER. The Chaingunner's backpack indicator is
# green on a monster whose muzzle light is white-blue, so it cannot ride the
# monster colour, and it is lit whether or not he is firing, so it cannot ride
# the muzzle frames either.
#
# IT IS POSITIONED FROM THE BACK VIEW, and it has to be: the table is keyed by
# frame letter and built from rotation 1, and a backpack is INVISIBLE from the
# front -- rotation 1 has zero green texels on every frame. Rotation 5 is the one
# that shows it. Screen-x mirrors on a back view (the monster's right appears on
# your left), hence the negated lateral, and fwd is negative because the pack sits
# behind the body axis. That is also why fwd exists at all; every other source
# here leaves it 0 because a front view cannot show forward extension.
EXTRA_SOURCE = {
    "CPOS": {
        "rot": "5",
        "test": "green",
        "fwd": -10.0,
        "scale": 0.45,
        "colour": "45b42c",   # the TONED green, matching the _e -- not a saturated sample
        "reserve": [1],       # one slot held back from the muzzle blobs
    },
}


# Monsters whose only light is their EYES, positioned from the eye masks that
# gen_enemy_eye_emissives already wrote into rt/mat. Deriving from the _e rather
# than re-thresholding the albedo is what guarantees the light lands exactly where
# the glow is -- the cross-check AGENTS.md asks for cannot fail if there is only
# one source of truth.
#
# POSS / SPOS / SSWV / HEAD / PAIN have NO _e at all, so there is no eye glow to
# match and they are absent on purpose, not by oversight.
EYE_MONSTERS = [
    ("TROO", "RT_HAND_IMP", "Imp"),
    ("TRO2", "RT_HAND_NIGHTMAREIMP", "Nightmare Imp"),
    ("SARG", "RT_HAND_PINKY", "Pinky"),
    ("SAR2", "RT_HAND_SPECTRE", "Spectre"),
    ("FATT", "RT_HAND_MANCUBUS", "Mancubus"),
    ("BSPI", "RT_HAND_ARACHNOTRON", "Arachnotron"),
    ("CYBR", "RT_HAND_CYBERDEMON", "Cyberdemon"),
]

OMAT = PROJ_ROOT / "Doom64-Retribution" / "Retribution-RT-Materials" / "rt" / "mat"


def extra_hands(sprite, letter, cfg, lumps, ue):
    """The Chaingunner's backpack: one light, from the BACK rotation."""
    name = f"{sprite}{letter}{cfg['rot']}"
    raw = ue.get(name) or lumps.get(name)
    if raw is None:
        return []
    im = Image.open(io.BytesIO(raw)).convert("RGBA")
    w, _ = im.size
    px = list(im.get_flattened_data())
    lit = [(i % w, i // w) for i, q in enumerate(px)
           if q[3] >= 128 and q[1] >= 45 and q[1] - q[0] >= 25 and q[1] - q[2] >= 25]
    if not lit:
        return []
    g = read_grab(raw) or (w // 2, im.size[1])
    cx = sum(q[0] for q in lit) / len(lit)
    cy = sum(q[1] for q in lit) / len(lit)
    return [Hand(-(cx - g[0]), g[1] - cy, cfg["fwd"], cfg["scale"], cfg["colour"], False)]


def eye_rows(sprite, lumps):
    """Per-frame eye positions read straight out of the sprite's own _e masks.

    A frame whose eyes GLOW must get a light, and rotation 1 is not always the
    lump that carries the mask: TROO's F and BSPI's B and D have an _e on other
    rotations only. Left alone those frames go dark mid-walk while the glow stays
    on -- the same defect as the Revenant's missing LED, arrived at differently.
    Eyes sit at a fixed point on a head, so carrying the last measured position
    forward is accurate; inventing one from a 45-degree rotation's screen-x would
    not be, because that axis is not the body's lateral axis.

    A frame with NO _e on any rotation is left dark on purpose -- nothing glows
    there, so there is nothing for a light to sit under.
    """
    rows, lit_all = [], []
    glows = {n.stem[len(sprite):-2][0] for n in OMAT.glob(f"{sprite}*_e.png")}
    last: list = []
    for letter in FRAMES:
        f = OMAT / f"{sprite}{letter}1_e.png"
        raw = lumps.get(f"{sprite}{letter}1")
        if not f.exists() or raw is None:
            if letter in glows and last:
                rows.append(last)
                print(f"  {letter}: no rot-1 mask, carried forward from the previous frame")
            else:
                rows.append([])
            continue
        im = Image.open(f).convert("RGBA")
        w, _ = im.size
        px = list(im.get_flattened_data())
        lit = {(i % w, i // w) for i, q in enumerate(px) if q[3] > 0}
        if not lit:
            rows.append([])
            continue
        lit_all += [px[y * w + x][:3] for (x, y) in lit]
        # grAb comes from the WAD sprite: the _e is written by PIL, which DROPS
        # grAb, so the mask itself cannot say where the feet are.
        g = read_grab(raw) or (w // 2, im.size[1])
        comps = [c for c in blobs(lit) if len(c) >= 2][:2]
        hands = []
        for c in comps:
            cx = sum(q[0] for q in c) / len(c)
            cy = sum(q[1] for q in c) / len(c)
            hands.append(Hand(cx - g[0], g[1] - cy, 0.0, 1.0, None, True))
        rows.append(hands)
        if hands:
            last = hands
        print(f"  {letter}: {len(hands)} eye(s)  " +
              ", ".join(f"(lat{h.lat:+.1f}, up{h.up:.1f})" for h in hands))
    return rows, lit_all


def wad_lumps() -> dict[str, bytes]:
    d = WAD.read_bytes()
    n, o = struct.unpack_from("<II", d, 4)
    out: dict[str, bytes] = {}
    for i in range(n):
        off, sz, name = struct.unpack_from("<II8s", d, o + i * 16)
        nm = name.split(b"\0")[0].decode("ascii", "replace")
        if sz > 0:
            out[nm] = d[off : off + sz]
    return out


def read_grab(png: bytes) -> tuple[int, int] | None:
    """Doom sprite origin from the PNG grAb chunk: (leftoffset, topoffset)."""
    off = 8
    while off < len(png):
        ln = struct.unpack_from(">I", png, off)[0]
        if png[off + 4 : off + 8] == b"grAb":
            x, y = struct.unpack_from(">ii", png, off + 8)
            return x, y
        off += 8 + ln + 4
    return None


def blobs(lit: set[tuple[int, int]]) -> list[list[tuple[int, int]]]:
    """8-connected components, largest first."""
    out: list[list[tuple[int, int]]] = []
    seen: set[tuple[int, int]] = set()
    for p in lit:
        if p in seen:
            continue
        comp: list[tuple[int, int]] = []
        q = deque([p])
        seen.add(p)
        while q:
            x, y = q.popleft()
            comp.append((x, y))
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    nb = (x + dx, y + dy)
                    if nb in lit and nb not in seen:
                        seen.add(nb)
                        q.append(nb)
        out.append(comp)
    out.sort(key=len, reverse=True)
    return out


def saturated_hex(colors: list[tuple[int, int, int]]) -> str:
    """Average the lit texels, renormalised so the light keeps its saturation."""
    n = len(colors)
    r = sum(c[0] for c in colors) / n
    g = sum(c[1] for c in colors) / n
    b = sum(c[2] for c in colors) / n
    scale = 255.0 / max(r, g, b, 1.0)
    return "{:02x}{:02x}{:02x}".format(
        min(255, int(r * scale)), min(255, int(g * scale)), min(255, int(b * scale))
    )


def main() -> None:
    lumps = wad_lumps()
    with zipfile.ZipFile(BM) as z:
        bms = {Path(i.filename).stem.upper(): z.read(i) for i in z.infolist()}

    per_monster: list[tuple[str, str, str, list[list[tuple[float, float]]], str]] = []

    from gen_vile_glow_emissives import FLOORS as VILE_FLOORS, hot as vile_hot

    # LIGHT-ONLY floor overrides. The emissive floor is the reviewer's call and
    # is not touched here -- G is 300 there, meaning "no fire is DRAWN on this
    # frame", and that stands. But G is the wind-up, and the cast now holds it
    # for 2 seconds so the light rises before the flame lands; a light needs a
    # POSITION, and at 170 G resolves to 39 texels spanning x 17..101, y 5..32 --
    # both raised hands, near the top of a 136-tall sprite. So the light is
    # placed from the art even where nothing is drawn as burning yet.
    LIGHT_FLOOR = {"G": 170}
    with zipfile.ZipFile(UE_PK3) as z:
        ue = {n.rsplit("/", 1)[-1].split(".")[0].upper(): z.read(n)
              for n in z.namelist() if n.startswith("sprites/")}

    for sprite, donor, tag, label, kind in MONSTERS:
        src = "brightmap " + str(donor) if kind == "bm" else "reviewed colour floors"
        print(f"=== {label} ({sprite}, mask from {src}) ===")
        rows: list[list[tuple[float, float]]] = []
        lit_all: list[tuple[int, int, int]] = []

        for letter in FRAMES:
            tex = f"{sprite}{letter}1"
            if kind in ("muzzle", "red"):
                only = LIGHT_ONLY_FRAMES.get(sprite)
                if only is not None and letter not in only:
                    print(f"  {letter}: not a firing frame -> no lights")
                    rows.append([])
                    continue
                found = ue_lump(ue, sprite, letter)
                spr = ue.get(found) if found else None
                if spr is None:
                    print(f"  {letter}: no lump -> no lights")
                    rows.append([])
                    continue
            elif kind == "fire":
                floor = LIGHT_FLOOR.get(letter, VILE_FLOORS.get(letter))
                spr = ue.get(tex)
                if spr is None or floor is None or floor >= 300:
                    # >=300 is the reviewer saying "no fire on this frame" -- the
                    # wind-up and the heal gesture. Not a failure.
                    print(f"  {letter}: no fire -> no lights")
                    rows.append([])
                    continue
            else:
                stem = f"{donor}{letter}1B"
                if tex not in lumps or stem not in bms:
                    print(f"  {letter}: MISSING ({tex}/{stem}) -> no lights")
                    rows.append([])
                    continue
                spr = lumps[tex]

            al = Image.open(io.BytesIO(spr)).convert("RGBA")
            w, h = al.size
            if kind == "bm":
                m = Image.open(io.BytesIO(bms[stem])).convert("RGBA")
                if m.size != al.size:
                    m = m.resize(al.size, Image.Resampling.NEAREST)

            grab = read_grab(spr)
            if grab is None:
                grab = (w // 2, h)
                print(f"  {letter}: WARNING no grAb, assuming {grab}")
            xoff, yoff = grab

            ap = list(al.get_flattened_data())
            if kind == "red":
                lvl, cap = RED_LEVEL.get(sprite, (120, 40))
                lvl = RED_LEVEL_BY_FRAME.get(sprite, {}).get(letter, lvl)
                lit = {(i % w, i // w) for i, px in enumerate(ap) if red_hot(px, lvl, cap)}
            elif kind == "muzzle":
                lit = {(i % w, i // w) for i, px in enumerate(ap) if muzzle_hot(px)}
            elif kind == "fire":
                lit = {(i % w, i // w) for i, px in enumerate(ap) if vile_hot(px, floor)}
            else:
                mp = list(m.get_flattened_data())
                lit = {
                    (i % w, i // w)
                    for i, (r, g, b, a) in enumerate(mp)
                    if a >= 24 and max(r, g, b) >= 40 and ap[i][3] >= 20
                }
            lit_all += [ap[y * w + x][:3] for (x, y) in lit]

            band = EYE_BAND.get(sprite)
            frame_scale = 1.0
            if band is not None:
                hi = {p for p in lit if (yoff - p[1]) > band}
                lo = lit - hi
                # The gun wins only when it CLEARLY dominates. A bare "more texels
                # low" made it 33-vs-25 on the wind-up frame, handing that frame to
                # the gun and leaving the eyes dark for no visible reason.
                if len(lo) > len(hi) * 3:
                    lit = lo
                else:
                    lit = hi
                    frame_scale = EYE_SCALE

            floor_n = MIN_BLOB_BY_SPRITE.get(sprite, MIN_BLOB_DEFAULT)
            comps = [c for c in blobs(lit) if len(c) >= floor_n]

            radius = CLUSTER_RADIUS.get(sprite, {}).get(letter)
            if radius and comps:
                comps.sort(key=len, reverse=True)
                hx, hy = (sum(q[0] for q in comps[0]) / len(comps[0]),
                          sum(q[1] for q in comps[0]) / len(comps[0]))
                near = []
                for c in comps:
                    cx = sum(q[0] for q in c) / len(c)
                    cy = sum(q[1] for q in c) / len(c)
                    if ((cx - hx) ** 2 + (cy - hy) ** 2) ** 0.5 <= radius:
                        near.append(c)
                if len(near) != len(comps):
                    print(f"  {letter}: cluster r={radius:.0f} kept {len(near)}/{len(comps)} blobs")
                comps = near

            # ONE PER SIDE, not simply the two biggest. A spread flame breaks into
            # many blobs, and "largest two" then picks two parts of the SAME arm:
            # the Arch-Vile's H came out (-49.7, -40.3) and its I (+42.4, +33.7),
            # both lights stacked on one hand with nothing on the other -- on the
            # two frames right after the cast starts, which is where the light was
            # reported missing. Fall back to the two largest only when one side
            # genuinely has no blob (arms down and the fire central, K..P).
            def centre(c):
                return (sum(p[0] for p in c) / len(c), sum(p[1] for p in c) / len(c))

            room = MAX_HANDS - len(EXTRA_SOURCE.get(sprite, {}).get("reserve", []))
            if len(comps) > room:
                # One per side FIRST, then fill by size. The side rule alone is
                # what stops a spread flame putting both lights on one arm (the
                # Arch-Vile's H and I did exactly that); filling afterwards is
                # what lets a Revenant show two shoulders AND two eyes.
                left = [c for c in comps if centre(c)[0] < xoff]
                right = [c for c in comps if centre(c)[0] >= xoff]
                picked = []
                if left and right:
                    picked = [left[0], right[0]]
                for c in comps:
                    if len(picked) >= room:
                        break
                    if c not in picked:
                        picked.append(c)
                comps = picked
            else:
                comps = comps[:room]

            hands = []
            for c in comps:
                cx, cy = centre(c)
                # lateral (+right), up from feet, fwd, scale, colour(None=monster), eye?
                hands.append(Hand(cx - xoff, yoff - cy, 0.0, frame_scale, None, False))

            extra = EXTRA_SOURCE.get(sprite)
            if extra is not None:
                hands += extra_hands(sprite, letter, extra, lumps, ue)

            desc = ", ".join(f"(lat{h.lat:+.1f}, up{h.up:.1f})" for h in hands) or "none"
            # NOT `kind` -- that is the monster's mask type and shadowing it here
            # silently sent every frame after the first down the brightmap branch.
            band_label = "eyes" if frame_scale != 1.0 else "gun/hands"
            print(f"  {letter}: {w}x{h} grAb=({xoff},{yoff})  {len(hands)} blob(s)  "
                  f"{band_label} x{frame_scale}  {desc}")
            rows.append(hands)

        if not lit_all:
            raise SystemExit(f"{sprite}: no lit texels found — aborting")
        sampled = saturated_hex(lit_all)
        hexcol = COLOR_OVERRIDE.get(sprite, sampled)
        if hexcol != sampled:
            print(f"  -> light colour {hexcol}  (override; sampled {sampled})\n")
        else:
            print(f"  -> light colour {hexcol}\n")
        per_monster.append((sprite, tag, label, rows, hexcol))

    # EYES LAST, so the existing RT_HAND_* indices keep their values. The enum is
    # generated from this order and the ini archives nothing about it, but a stale
    # object file compiled against the old numbering would silently light the wrong
    # monster -- appending is the change that cannot do that.
    for sprite, tag, label in EYE_MONSTERS:
        print(f"=== {label} ({sprite}, eyes from the authored _e masks) ===")
        rows, lit_all = eye_rows(sprite, lumps)
        if not lit_all:
            raise SystemExit(f"{sprite}: no eye texels found -- aborting")
        # Sampled, never hardcoded: the Nightmare Imp's eyes are a cold blue-violet
        # while every other monster here is red, and that difference lives in the
        # mask. A literal would drift the cast light off the glow on the next retune.
        hexcol = COLOR_OVERRIDE.get(sprite, saturated_hex(lit_all))
        print(f"  -> eye colour {hexcol}\n")
        per_monster.append((sprite, tag, label, rows, hexcol))

    lines = [
        "// GENERATED by tools/gen_hand_light_offsets.py -- do not edit by hand.",
        "//",
        "// Body-relative fist positions for the Baron family, in MAP UNITS:",
        "//   lateral = +right of the actor's facing, up = above the actor's feet (Z()).",
        "// Rotated by the actor's yaw at upload time by RT_UploadHandGlowLights.",
        "//",
        "// Geometry comes from the mod's authored brightmaps. BOSS ships none of its own,",
        "// but BOSS and BOS2 are the same artwork palette-swapped (12/12 frames verified",
        "// pixel-identical in silhouette), so the BOS2 masks transfer. Each sprite is still",
        "// resolved against its OWN grAb: BOSSA5 is (29,94) where BOS2A5 is (29,93).",
        "//",
        "// fwd is intentionally 0: the front rotation cannot show forward extension, so a",
        "// value here would be invented.",
        "//",
        "// Frames I..N (death/gib) are absent on purpose: the gore reuses the same palette",
        "// ramp as the hand glow, so lighting them would make corpses flare.",
        "#pragma once",
        "",
        "struct RtHandPos",
        "{",
        "    float lateral;",
        "    float up;",
        "    float fwd;",
        "    // Intensity multiplier for THIS HAND, not this frame. One monster can",
        "    // carry sources of different strengths at once -- the Chaingunner has a",
        "    // muzzle flash AND a backpack indicator, and the Mastermind's eyes sit",
        "    // at 0.10 of its gun. A per-frame scalar could not express either.",
        "    float lightScale;",
        "    // 0 = inherit RT_HAND_COLOR[monster]. Set when a hand's colour differs",
        "    // from the rest of the monster: the Chaingunner's backpack is green on a",
        "    // monster whose light is white-blue.",
        "    unsigned colour;",
        "    // Eyes draw from rt_eye_light_* instead of the monster's own cvars. They",
        "    // are a different ORDER of light -- a hint on the face, not a source that",
        "    // lights a room -- and sharing a monster cvar makes one of the two wrong.",
        "    bool  isEye;",
        "};",
        "",
        "struct RtHandFrame",
        "{",
        "    int        count;",
        "    RtHandPos  hands[ 4 ];",
        "};",
        "",
        "enum RtHandMonster",
        "{",
    ]
    for i, (_s, tag, label, _r, _c) in enumerate(per_monster):
        lines.append(f"    {tag} = {i},  // {label}")
    lines += [
        f"    RT_HAND_MONSTER_COUNT = {len(per_monster)},",
        "};",
        "",
        "// Indexed by sprite frame letter: A=0 .. H=7.",
        f"constexpr int RT_HAND_FRAME_COUNT = {len(FRAMES)};",
        "",
        "constexpr RtHandFrame RT_HAND_FRAMES[ RT_HAND_MONSTER_COUNT ][ RT_HAND_FRAME_COUNT ] = {",
    ]
    for sprite, tag, label, rows, _c in per_monster:
        lines.append(f"    // {label} ({sprite})")
        lines.append("    {")
        for letter, hands in zip(FRAMES, rows):
            parts = ", ".join(
                "{{ {:.1f}f, {:.1f}f, {:.1f}f, {:.2f}f, {}u, {} }}".format(
                    h.lat, h.up, h.fwd, h.scale,
                    f"0x{h.colour}" if h.colour else "0",
                    "true" if h.eye else "false")
                for h in hands)
            pad = ", ".join(["{ 0.0f, 0.0f, 0.0f, 1.00f, 0u, false }"] * (MAX_HANDS - len(hands)))
            both = ", ".join(x for x in (parts, pad) if x)
            lines.append(f"        {{ {len(hands)}, {{ {both} }} }},  // {letter}")
        lines.append("    },")
    lines += [
        "};",
        "",
        "// Saturation-normalised average of each monster's own lit texels, so the cast light",
        "// agrees with the sprite glow. 0xRRGGBB.",
        "constexpr unsigned RT_HAND_COLOR[ RT_HAND_MONSTER_COUNT ] = {",
    ]
    for sprite, tag, label, _r, hexcol in per_monster:
        lines.append(f"    0x{hexcol}u,  // {label} ({sprite})")
    lines += ["};", ""]

    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
