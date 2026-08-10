"""Tag the Doom 64 water flats as water for RTGL1.

Why this exists as a script rather than an edit: rt/data/textures.json under
build/ is gitignored and rewritten by the PBR tooling (apply_all_category_pbr.py
and friends), so a hand edit is neither recorded nor durable. Re-run this after
any of those, and after a clean build checkout.

What it does. RTGL1 only runs its water path on primitives carrying
RG_MESH_PRIMITIVE_WATER, and the only way world geometry gets that flag is the
"isWater" key in the JSON meta (TextureMeta.cpp). Without it D64W2_01 is just
another rough dark surface -- which is what it was until now: it is nearly black
(mean luminance 8/255) so under path tracing it reads as a hole in the floor.

Tagging it turns on the STYLIZED water shader (rt_water_style, on by default):
opaque deep-blue body carrying the flat's own caustic veins, plus a
Fresnel-weighted mirror reflection. It deliberately does NOT enable refraction
-- these are floor flats, there is no sector underneath them to see into. See
deps/RTGL Shaders/RaygenPrimary.inl :: getStylizedWaterAlbedo.

roughnessDefault is low so the surface half gets a tight specular sheen from
lights; the shader overrides roughness for the water surface anyway, but the
JSON value is what reflections OF the water use.

Usage:
    python tools/set_water_meta.py           # show current state
    python tools/set_water_meta.py --apply   # tag + quarantine frame-01 mats
    python tools/set_water_meta.py --revert  # undo both
"""

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT / "sourcecode/gzdoom-rt/build/RelWithDebInfo/rt/data/textures.json"

# EVERY frame of both sequences, not just the one the map names.
#
# D64W2_01 is frame 1 of a 64-frame ANIMDEFS animation (D64W2_01..D64W2_64, 2
# tics each); the map's sector names frame 1 but GZDoom swaps in a different
# frame every 2 tics, so tagging only "D64W2_01" makes the surface water for
# 2 tics out of ~128 -- a bright flash once per ~3.7s cycle, then nothing.
# D64W1_* is the same, 64 frames. D64WATR1/2 are the source patches (warp2).
WATER = (
    tuple(f"D64W1_{i:02d}" for i in range(1, 65))
    + tuple(f"D64W2_{i:02d}" for i in range(1, 65))
    + ("D64WATR1", "D64WATR2")
)

META = {
    "isWater": True,
    "roughnessDefault": 0.1,
    "metallicDefault": 0.0,
}

# Material overlays that exist for FRAME 01 ONLY.
#
# The PBR tooling generated D64W1_01_n/_orm/_h and D64W2_01_n/_orm/_h because
# frame 01 is the name the maps reference -- but frames 02..64 got nothing. So
# once per ~3.7s animation cycle the surface gains an authored normal map and a
# heightmap (parallax shifts the UVs), then snaps back 2 tics later: the water's
# reflections and waves visibly JUMP on a regular beat.
#
# A 64-frame animation must be materially uniform. The stylized water builds its
# own wave normal (getWaterNormal) and the shader writes roughness/metallic
# explicitly, so these overlays are unwanted regardless -- quarantine, not
# regenerate-for-128-frames.
#
# D64WATR1/2 are NOT part of either sequence (separate 192x192 warp textures),
# so their overlays are consistent and are left alone.
FRAME1_ONLY_MATS = ("D64W1_01", "D64W2_01")
MAT_SUFFIXES = ("_n.png", "_orm.png", "_h.png")

MAT_DIRS = [
    ROOT / "sourcecode/gzdoom-rt/build/RelWithDebInfo/rt/mat",
    ROOT / "sourcecode/gzdoom-rt/build/RelWithDebInfo/rt/mat_dev",
    ROOT / "Doom64-Retribution/Retribution-RT-Materials/rt/mat",
    ROOT / "Doom64-Retribution/Retribution-RT-Materials/rt/mat_dev",
]


def quarantine_frame1_mats(restore: bool = False) -> int:
    """Move (or restore) the frame-01-only overlays. Returns files moved."""
    moved = 0
    for d in MAT_DIRS:
        if not d.exists():
            continue
        q = d.parent / (d.name + "_quarantine_water")
        src_dir, dst_dir = (q, d) if restore else (d, q)
        for base in FRAME1_ONLY_MATS:
            for suf in MAT_SUFFIXES:
                src = src_dir / (base + suf)
                if not src.exists():
                    continue
                dst_dir.mkdir(parents=True, exist_ok=True)
                shutil.move(str(src), str(dst_dir / src.name))
                print(f"  {'restored' if restore else 'quarantined'}: {src}")
                moved += 1
    return moved


def load(path: Path):
    data = json.loads(path.read_text(encoding="utf-8"))
    entries = data["array"] if isinstance(data, dict) and "array" in data else None
    if entries is None:
        raise SystemExit("ERROR: unexpected textures.json shape; expected {'version':N,'array':[...]}")
    return data, entries


def show(entries) -> None:
    print(f"{TARGET}")
    for name in WATER:
        # first textureName wins in RTGL1's lookup, so only the first matters
        hit = next((e for e in entries if e.get("textureName") == name), None)
        if hit is None:
            print(f"  {name:10} (no entry)")
        else:
            print(f"  {name:10} isWater={hit.get('isWater')} "
                  f"rough={hit.get('roughnessDefault')} metal={hit.get('metallicDefault')}")


def main() -> int:
    if not TARGET.exists():
        print(f"ERROR: {TARGET} not found -- build gzdoom first")
        return 1

    data, entries = load(TARGET)
    mode = sys.argv[1] if len(sys.argv) > 1 else ""

    if mode not in ("--apply", "--revert"):
        show(entries)
        print("\nPass --apply to tag them as water, --revert to untag.")
        return 0

    changed = []
    seen = set()
    for e in entries:
        name = e.get("textureName")
        if name not in WATER:
            continue
        seen.add(name)
        if mode == "--apply":
            before = dict(e)
            e.update(META)
            if e != before:
                changed.append((name, "updated"))
        else:
            if e.pop("isWater", None) is not None:
                changed.append((name, "untagged"))

    if mode == "--apply":
        for name in WATER:
            if name not in seen:
                entries.append({"textureName": name, **META})
                changed.append((name, "added"))

    TARGET.write_text(json.dumps(data, indent=2), encoding="utf-8")
    for name, what in changed:
        print(f"  {name:10} {what}")
    print(f"\n{len(changed)} entr(ies) written to {TARGET.name}.")

    n = quarantine_frame1_mats(restore=(mode == "--revert"))
    print(f"{n} frame-01-only material overlay(s) moved.")
    print("Relaunch to see it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
