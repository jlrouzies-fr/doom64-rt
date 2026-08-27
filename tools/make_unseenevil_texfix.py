"""Retarget Unseen Evil's FLAT2 mapping away from Doom 64's lamp flat.

THE PROBLEM. resources/d64ue_textures.txt maps three stock DOOM flats onto Doom 64's
inset-lamp flat SFLATAS:

    TLITE6_5:SFLATAS      correct -- TLITE6_* ARE ceiling light flats
    TLITE6_6:SFLATAS      correct
    FLAT2:SFLATAS         not correct for RT

FLAT2 is an ordinary grey ceiling/floor flat that DOOM II uses over very large areas
-- MAP02's main ceiling is one. Under the rasterizer that mapping is harmless: the
lamp art simply tiles. Under RT it is not, because SFLATAS is a FIXTURE to two
separate systems that Retribution authored around it:

  * rt/data/textures.json gives SFLATAS emissiveMult 20.0, so the surface glows
  * rt_lights_fixtures.cpp treats SFLATAS as a ceiling inset lamp and places real
    analytic lights across every plane wearing it (RT_IsCeilingInsetLampTexture)

So an entire ceiling becomes a light. That is the "red light coming from nowhere":
no light thing, no sector light, no emissive setting of ours -- the ceiling itself
was classified as a lamp.

THE FIX is one character of intent: send FLAT2 to SFLATAP instead. Same tech-ceiling
family and the closest visual match, but it is a recessed GRILLE rather than a bulb
array -- and the engine excludes it from the lamp list deliberately, with a comment
saying so ("it is a recessed grille, not a lamp, and the original game does not light
it"). It carries no material emissive either. Verified against rt/data/textures.json
and the fixture tables rather than chosen by eye.

TLITE6_5/6 KEEP THEIR SFLATAS MAPPING. They are real light flats, so being treated
as lamps is correct and wanted -- that is the mod's ceiling lights working.

Delivered as an overlay pk3 holding one file at the mod's own path, so load order is
the whole mechanism and the mod pk3 is never touched.

    py -3 tools/make_unseenevil_texfix.py            # report the edit, write nothing
    py -3 tools/make_unseenevil_texfix.py --write
"""

import argparse
import zipfile
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
MOD = PROJ / "Doom64-UnseenEvil" / "D64UnseenEvil-v1.0.3.pk3"
OUT = PROJ / "Doom64-UnseenEvil" / "d64ue-texfix.pk3"

LUMP = "resources/d64ue_textures.txt"

# from -> to, applied to the mapping's TARGET only, and only on these source flats.
RETARGET = {
    "FLAT2": ("SFLATAS", "SFLATAP"),
}

# THE LIQUIDS, 2026-08-27. UE's own two-frame flats reach the engine's liquid
# shader by name, and nothing else: the per-frame relief maps, the lava emissive
# and lights, the poison bubbles and the lava sprays are all keyed on
# Retribution's names. d64ue-retribution-liquids.pk3 (make_unseenevil_liquids.py)
# ships that construction; these lines point the mod at it. Targets are
# Retribution's most-used family of each kind, from a floor census of its maps.
_LAVA_PNG = "textures/pepy/d64_lava.png"
RETARGET.update({
    **{f"FWATER{i}": ("WATERA", "D64W1_01") for i in (1, 2, 3, 4)},
    **{f"NUKAGE{i}": ("SLIMEB", "D64N1_01") for i in (1, 2, 3)},
    **{f"BLOOD{i}": ("BLOODB", "D64B2_01") for i in (1, 2, 3)},
    **{f"SLIME0{i}": ("SLUDGEB", "D64S1_01") for i in (1, 2, 3, 4)},
    **{f"SLIME0{i}": ("SLUDGEA", "D64S1_01") for i in (5, 6, 7, 8)},
    **{f"LAVA{i}": (_LAVA_PNG, "HLAVA1") for i in (1, 2, 3, 4)},
})

# PIXEL-IDENTICAL TWINS, 2026-08-27. Seventeen of the mod's path-named PNGs are
# byte-for-byte the same picture as a Retribution DTWMD* lump. A path-named PNG
# reaches the renderer NAMELESS (GZDoom names only 8-char basenames), so nothing
# in rt/mat or textures.json can ever match it; the Retribution name carries the
# authored metallic/roughness meta and, for three of them, full _h/_n/_orm
# relief. Same picture on screen, Retribution's material underneath.
_TWINS = {
    "textures/cage/d64_bigbrick1.png": ("DTWMD25", ["BIGBRIK1"]),
    "textures/cage/d64_bigbrick2.png": ("DTWMD23", ["BIGBRIK2"]),
    "textures/cage/d64_bigbrick3.png": ("DTWMD26", ["BIGBRIK3"]),
    "textures/cage/d64_brickedup.png": ("DTWMD35", ["ROCK1", "ROCK2", "ROCK3"]),
    "textures/cage/d64_brownwall.png": ("DTWMD14", ["BROWN96", "BROVINE2"]),
    "textures/cage/d64_cement.png": ("DTWMD07", [f"CEMENT{i}" for i in range(1, 7)]),
    "textures/cage/d64_fleshpanels.png": ("DTWMD31", ["SKINSYMB"]),
    "textures/cage/d64_hexes.png": ("DTWMD10", ["METAL1"]),
    "textures/cage/d64_metalsupport.png": ("DTWMD04", ["SUPPORT3"]),
    "textures/cage/d64_starstruct_red.png": ("DTWMD17", ["STARTAN1", "STARTAN2", "STARBR2"]),
    "textures/cage/d64_starstruct_tan.png": ("DTWMD18", ["STARGR1", "STARGR2"]),
    "textures/cage/d64_stonewall.png": ("DTWMD32", ["STONE4", "STONE5"]),
    "textures/cage/d64_support2.png": ("DTWMD05", ["SUPPORT2"]),
    "textures/cage/d64_tekgreen.png": ("DTWMD02", ["TEKGREN2", "TEKGREN4", "TEKGREN5"]),
    "textures/cage/d64_tekgreen2.png": ("DTWMD03", ["TEKGREN1"]),
    "textures/cage/d64_tekwall2.png": ("DTWMD01", ["TEKWALL2"]),
    "textures/cage/edits/d64_talldooralpha_0.png": ("DTWMD20", ["SPCDOOR3"]),
}
for _png, (_d64, _srcs) in _TWINS.items():
    RETARGET.update({src: (_png, _d64) for src in _srcs})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    # EVERY mapping file, not just the .txt. The liquid lines are in the .txt, but
    # the twins are in the .bricks/.metal/.stone/.doors/.flesh includes, and an
    # include the overlay does not carry keeps the mod's own copy -- so a retarget
    # that lands in one of those was silently a no-op until this walked them all.
    # Only files that actually change are written, so the mod's untouched
    # includes stay the mod's.
    with zipfile.ZipFile(MOD) as z:
        files = {n: z.read(n).decode("latin-1")
                 for n in z.namelist() if n.lower().startswith("resources/d64ue_textures.")}
    if LUMP not in files:
        raise SystemExit(f"{LUMP} not in {MOD.name}")

    outputs = {}
    changed = []
    seen = set()
    for name, raw in sorted(files.items()):
        out_lines = []
        touched = False
        for line in raw.splitlines(keepends=True):
            stripped = line.strip()
            if ":" in stripped and not stripped.startswith(("//", "#")):
                src, _, dst = stripped.partition(":")
                src = src.strip()
                if src in RETARGET:
                    old, new = RETARGET[src]
                    if dst.strip() == old:
                        line = line.replace(f"{src}:{old}", f"{src}:{new}")
                        changed.append(f"{name.split('.')[-1]:8} {src}: {old} -> {new}")
                        seen.add(src)
                        touched = True
            out_lines.append(line)
        if touched:
            outputs[name] = "".join(out_lines)

    if not changed:
        raise SystemExit(
            "nothing to change -- the mod's mapping is not what this tool expects; "
            "re-read resources/d64ue_textures.* before assuming it is a no-op"
        )
    for c in changed:
        print("  ", c)
    missed = sorted(set(RETARGET) - seen)
    if missed:
        print("   NOT FOUND with the expected old target (check the mod's table):", ", ".join(missed))

    # Prove the lamp mappings that SHOULD stay are still intact.
    kept = [l.strip() for l in outputs.get(LUMP, files[LUMP]).splitlines() if "SFLATAS" in l]
    print("   still mapped to the lamp flat (correct):", ", ".join(kept) or "none")
    print(f"   files rewritten: {', '.join(n.split('/')[-1] for n in outputs)}")

    if not args.write:
        print("\ncensus only; pass --write to build", OUT.name)
        return

    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        for name, text in outputs.items():
            z.writestr(name, text)
    print(f"\nwrote {OUT} ({OUT.stat().st_size} bytes, {len(outputs)} mapping file(s))")


if __name__ == "__main__":
    main()
