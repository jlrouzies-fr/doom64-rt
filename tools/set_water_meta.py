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
    python tools/set_water_meta.py --apply   # write the tags
    python tools/set_water_meta.py --revert  # remove them (back to plain PBR)
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT / "sourcecode/gzdoom-rt/build/RelWithDebInfo/rt/data/textures.json"

# The composites the maps actually place (MAP10, MAP11, MAP34 for D64W2_01;
# MAP08/14/15/16/22/23/30/34 for D64W1_01), plus the source patches they are
# built from, so a direct placement is covered too.
WATER = ("D64W2_01", "D64W1_01", "D64WATR1", "D64WATR2")

META = {
    "isWater": True,
    "roughnessDefault": 0.1,
    "metallicDefault": 0.0,
}


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
    print(f"\n{len(changed)} entr(ies) written to {TARGET.name}. Relaunch to see it.")
    show(*load(TARGET)[1:])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
