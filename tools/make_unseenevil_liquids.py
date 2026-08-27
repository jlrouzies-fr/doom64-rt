"""Give Doom 64: Unseen Evil Retribution's liquids -- the same construction, by name.

WHAT WAS FOUND (2026-08-27, data only). Of the 74 Doom 64 texture names Unseen
Evil can put on a wall or floor, all 74 are pixel-identical to Retribution's, so
wall and flat art is already at parity. The liquids are not, and the reason is
NAMES. UE maps DOOM II's liquid flats onto its own two-frame flats:

    FWATER1..4  -> WATERA          NUKAGE1..3 -> SLIMEB       BLOOD1..3 -> BLOODB
    SLIME01..08 -> SLUDGEB/A       LAVA1..4   -> textures/pepy/d64_lava.png

The engine's liquid SHADER already knows those names (RT_LiquidIdOfName), so UE
water ripples. Everything else Retribution's liquids get is keyed on
Retribution's names and never fires:

  * the per-frame relief maps -- rt/mat has 64 x _h/_n/_orm for D64B1_/D64B2_/
    D64S1_/D64S2_ and ZERO for BLOODA/B, SLUDGEA/B. docs/rt-blood-pools.md:
    "rt_blood_relief / rt_sludge_relief were the entire difference between a
    coagulated pool and water with red paint on it".
  * lava. RT_IsLavaFlat matches HLAVA*/D64LAVA* only; UE's pepy png gets no
    emissiveMult 4.5, no lightIntensity 140, no rt_lava_* lights/flow/GI, and
    d64r-lava-fx.pk3's sprays never spawn.
  * the poison bubbles: d64r-poison-fx.pk3 keys on the D64N prefix.
  * the animation itself: a 64-frame warp scroll at 2 tics against a 2-frame
    flip at 8.

SO USE RETRIBUTION'S NAMES. This overlay ships the construction Retribution's
own WAD uses, verbatim, and make_unseenevil_texfix.py retargets the mod's mapping
onto it:

    FWATER*  -> D64W1_01     NUKAGE* -> D64N1_01     BLOOD*  -> D64B2_01
    SLIME01..08 -> D64S1_01  LAVA*   -> HLAVA1

The picks are Retribution's most-used family of each kind (floor census over its
34 maps: D64N1_ 142, D64B2_ 96, D64W2_ 120 / D64W1_ 61, D64S1_ 7, HLAVA1 8).

WHAT IS IN THE PK3, all copied from D64RTR_v15.WAD:

  textures/D64WATR1..D64LAVA2.png    the ten 192x192 warp source patches
  textures/HLAVA1..5.png             the lava flat's five frames
  TEXTURES                           the 576 D64[WNBSL]n_nn frame composites
                                     (two shifted layers of a warp patch, Alpha
                                     0.5 Translucent; lava Alpha 0.75 Add), the
                                     four warp-patch textures and HLAVA1..5
  ANIMDEFS.d64rtliquids              the nine 64-frame sequences and HLAVA's
                                     ping-pong, verbatim

THE LOAD ORDER IS THE MECHANISM, exactly as it is for Retribution. After this
overlay the launcher loads d64r-liquid-art.wad -- the coagulated blood / poison /
sludge art, which REDEFINES every D64B/N/S frame as one unshifted copy so the
authored relief is legal -- and then d64r-poison-fx.pk3 and d64r-lava-fx.pk3.
All three are self-contained (no Retribution actor classes; checked), so they
run on DOOM II the moment the names match.

    py -3 tools/make_unseenevil_liquids.py            # census, writes nothing
    py -3 tools/make_unseenevil_liquids.py --write    # build the overlay pk3
"""

from __future__ import annotations

import argparse
import re
import struct
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "Doom64-UnseenEvil" / "d64ue-retribution-liquids.pk3"
WAD = ROOT / "Doom64-Retribution" / "D64RTR_v15.WAD"

PATCHES = [
    "D64WATR1", "D64WATR2", "D64NUKG1", "D64NUKG2", "D64SLDG1", "D64SLDG2",
    "D64BLOD1", "D64BLOD2", "D64LAVA1", "D64LAVA2",
    "HLAVA1", "HLAVA2", "HLAVA3", "HLAVA4", "HLAVA5",
]
FRAME_RE = re.compile(r"^D64[WNBSL]\d_\d\d$")
STILL = {"D64WATR1", "D64WATR2", "D64LAVA1", "D64LAVA2",
         "HLAVA1", "HLAVA2", "HLAVA3", "HLAVA4", "HLAVA5"}
ANIM_HEADS = re.compile(r"^(D64[WNBSL]\d_01|HLAVA1)$")


def read_wad():
    b = WAD.read_bytes()
    _, n, off = struct.unpack("<4sii", b[:12])
    lumps = {}
    for i in range(n):
        fo, sz, nm = struct.unpack("<ii8s", b[off + i * 16 : off + i * 16 + 16])
        lumps.setdefault(nm.rstrip(b"\0").decode("latin1"), b[fo : fo + sz])
    return lumps


def texture_blocks(text: str):
    """(name, verbatim block) for every top-level `Texture NAME, w, h { ... }`.

    Brace-matched by hand: the frame composites nest `{ Alpha .. Style .. }`
    inside each Patch, so a non-greedy regex to the first `}` would truncate
    every one of them.
    """
    out = []
    for m in re.finditer(r"(?im)^[ \t]*(?:Wall)?Texture\s+([A-Za-z0-9_]+)\s*,", text):
        name = m.group(1).upper()
        i = text.find("{", m.end())
        if i < 0:
            continue
        depth, j = 0, i
        while j < len(text):
            c = text[j]
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        out.append((name, text[m.start() : j + 1].strip() + "\n"))
    return out


def animdef_blocks(text: str):
    """Verbatim `texture NAME` + its pic lines, for the liquid heads."""
    blocks, cur = [], False
    for ln in text.splitlines():
        w = ln.split()
        if not w:
            continue
        if w[0].lower() in ("texture", "flat") and len(w) >= 2:
            cur = bool(ANIM_HEADS.match(w[1].upper()))
            if cur:
                blocks.append(f"\ntexture {w[1]}\n")
        elif cur and w[0].lower() in ("pic", "allowdecals", "oscillate", "random"):
            blocks.append("    " + " ".join(w) + "\n")
        else:
            cur = False
    return "".join(blocks)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    lumps = read_wad()
    for p in PATCHES:
        if lumps.get(p, b"")[:8] != b"\x89PNG\r\n\x1a\n":
            raise SystemExit(f"{p}: not a PNG lump in {WAD.name}")

    blocks = [(n, t) for n, t in texture_blocks(lumps["TEXTURES"].decode("latin1"))
              if FRAME_RE.match(n) or n in STILL]
    names = {n for n, _ in blocks}
    frames = sorted(n for n in names if FRAME_RE.match(n))
    refs = {p.upper() for _, t in blocks for p in re.findall(r"(?i)\bPatch\s+([A-Za-z0-9_]+)", t)}
    missing = refs - set(PATCHES)
    if missing:
        raise SystemExit(f"TEXTURES references patches this overlay does not ship: {sorted(missing)}")

    anim = animdef_blocks(lumps["ANIMDEFS"].decode("latin1"))
    pics = {p.upper() for p in re.findall(r"(?im)^\s*pic\s+(\w+)", anim)}
    undefined = pics - names
    if undefined:
        raise SystemExit(f"ANIMDEFS names frames TEXTURES does not define: {sorted(undefined)[:8]}")

    fam = {}
    for n in frames:
        fam[n[:5]] = fam.get(n[:5], 0) + 1
    print("Retribution's liquids for Unseen Evil, by name")
    print(f"  patches   {len(PATCHES)} PNG lumps")
    print(f"  TEXTURES  {len(frames)} frame composites {fam} + {len(names) - len(frames)} stills")
    print(f"  ANIMDEFS  {anim.count('texture ')} sequences, {len(pics)} frames, every one defined")
    if not args.write:
        print(f"\n(census only -- pass --write to build {OUT.name})")
        return

    textures = (
        "// Doom64-RT: Retribution's liquid construction, copied verbatim from\n"
        "// D64RTR_v15.WAD so UE's liquids carry the names every RT liquid system\n"
        "// keys on. d64r-liquid-art.wad loads AFTER this and redefines the blood,\n"
        "// poison and sludge frames -- last definition wins, as in Retribution.\n\n"
        + "\n".join(t for _, t in blocks)
    )
    animdefs = (
        "// Doom64-RT: Retribution's liquid ANIMDEFS, verbatim. Nine 64-frame warp\n"
        "// scrolls at 2 tics and HLAVA's five-frame ping-pong.\n"
        + anim
    )
    with ZipFile(OUT, "w", ZIP_DEFLATED) as z:
        for p in PATCHES:
            z.writestr(f"textures/{p}.png", lumps[p])
        z.writestr("TEXTURES", textures)
        z.writestr("ANIMDEFS.d64rtliquids", animdefs)
    with ZipFile(OUT) as z:
        back = z.namelist()
        assert len([x for x in back if x.startswith("textures/")]) == len(PATCHES)
        assert z.read("TEXTURES").decode() == textures
    print(f"\nwrote {OUT} ({OUT.stat().st_size} bytes, {len(back)} entries)")


if __name__ == "__main__":
    main()
