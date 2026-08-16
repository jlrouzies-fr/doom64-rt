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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    with zipfile.ZipFile(MOD) as z:
        raw = z.read(LUMP).decode("latin-1")

    out_lines = []
    changed = []
    for line in raw.splitlines(keepends=True):
        stripped = line.strip()
        if ":" in stripped and not stripped.startswith(("//", "#")):
            src, _, dst = stripped.partition(":")
            src = src.strip()
            if src in RETARGET:
                old, new = RETARGET[src]
                if dst.strip() == old:
                    line = line.replace(f"{src}:{old}", f"{src}:{new}")
                    changed.append(f"{src}: {old} -> {new}")
        out_lines.append(line)

    if not changed:
        raise SystemExit(
            "nothing to change -- the mod's mapping is not what this tool expects; "
            "re-read resources/d64ue_textures.txt before assuming it is a no-op"
        )
    for c in changed:
        print("  ", c)

    # Prove the lamp mappings that SHOULD stay are still intact.
    kept = [l.strip() for l in out_lines if "SFLATAS" in l]
    print("   still mapped to the lamp flat (correct):", ", ".join(kept) or "none")

    if not args.write:
        print("\ncensus only; pass --write to build", OUT.name)
        return

    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(LUMP, "".join(out_lines))
    print(f"\nwrote {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
