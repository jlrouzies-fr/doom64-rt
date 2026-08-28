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
MONSTERS = [
    ("BOS2", "BOS2", "RT_HAND_HELLKNIGHT", "Hell Knight", "bm"),
    ("BOSS", "BOS2", "RT_HAND_BARON", "Baron of Hell", "bm"),
    ("VILE", None, "RT_HAND_ARCHVILE", "Arch-Vile (Unseen Evil)", "fire"),
]

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
MIN_BLOB = 8  # texels; the eye dots are ~2 and must not become lights
MAX_HANDS = 2


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
    with zipfile.ZipFile(UE_PK3) as z:
        ue = {n.rsplit("/", 1)[-1].split(".")[0].upper(): z.read(n)
              for n in z.namelist() if n.startswith("sprites/VILE")}

    for sprite, donor, tag, label, kind in MONSTERS:
        src = "brightmap " + str(donor) if kind == "bm" else "reviewed colour floors"
        print(f"=== {label} ({sprite}, mask from {src}) ===")
        rows: list[list[tuple[float, float]]] = []
        lit_all: list[tuple[int, int, int]] = []

        for letter in FRAMES:
            tex = f"{sprite}{letter}1"
            if kind == "fire":
                floor = VILE_FLOORS.get(letter)
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
            if kind == "fire":
                lit = {(i % w, i // w) for i, px in enumerate(ap) if vile_hot(px, floor)}
            else:
                mp = list(m.get_flattened_data())
                lit = {
                    (i % w, i // w)
                    for i, (r, g, b, a) in enumerate(mp)
                    if a >= 24 and max(r, g, b) >= 40 and ap[i][3] >= 20
                }
            lit_all += [ap[y * w + x][:3] for (x, y) in lit]

            comps = [c for c in blobs(lit) if len(c) >= MIN_BLOB][:MAX_HANDS]
            hands = []
            for c in comps:
                cx = sum(p[0] for p in c) / len(c)
                cy = sum(p[1] for p in c) / len(c)
                hands.append((cx - xoff, yoff - cy))  # lateral (+right), up from feet

            desc = ", ".join(f"(lat{lat:+.1f}, up{up:.1f})" for lat, up in hands) or "none"
            print(f"  {letter}: {w}x{h} grAb=({xoff},{yoff})  {len(comps)} blob(s)  {desc}")
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
        "};",
        "",
        "struct RtHandFrame",
        "{",
        "    int        count;",
        "    RtHandPos  hands[ 2 ];",
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
            parts = ", ".join(f"{{ {lat:.1f}f, {up:.1f}f, 0.0f }}" for lat, up in hands)
            pad = ", ".join(["{ 0.0f, 0.0f, 0.0f }"] * (MAX_HANDS - len(hands)))
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
