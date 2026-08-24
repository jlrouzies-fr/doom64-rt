"""Tag the Doom 64 LIQUID flats as water for RTGL1.

Covers all four liquids -- water, nukage, sludge, blood. They are one flat design
in four palettes and share the stylized surface shader; the engine picks the body
colour per liquid from the texture name (rt_main.cpp l_waterflag), this script
only says "liquid".

The WFALL/SFALL/BFALL wall sheets are deliberately NOT tagged (see _FALLS below)
but ARE quarantined, because their frame-01-only overlays are a separate defect.

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
# BOTH copies, and the second one is why this used to look like it never worked.
#
# The build dir is what RTGL1 reads, so it has to be written. But
# build-gzdoom-rt.cmd stages `Retribution-RT-Materials\rt` over `build\...\rt`
# on EVERY build -- so writing only the build copy means the next build silently
# reverts it. That is how frame 01 of all eight liquid families kept its
# roughness 0.8 while frames 02..64 sat at 0.1, through repeated --apply runs
# that each reported success.
#
# First entry is the live one and the one `show` reports.
TARGETS = [
    ROOT / "sourcecode/gzdoom-rt/build/RelWithDebInfo/rt/data/textures.json",
    ROOT / "Doom64-Retribution/Retribution-RT-Materials/rt/data/textures.json",
]
TARGET = TARGETS[0]

# EVERY frame of both sequences, not just the one the map names.
#
# D64W2_01 is frame 1 of a 64-frame ANIMDEFS animation (D64W2_01..D64W2_64, 2
# tics each); the map's sector names frame 1 but GZDoom swaps in a different
# frame every 2 tics, so tagging only "D64W2_01" makes the surface water for
# 2 tics out of ~128 -- a bright flash once per ~3.7s cycle, then nothing.
# D64W1_* is the same, 64 frames. D64WATR1/2 are the source patches (warp2).
#
# All FOUR liquids, not just water: nukage (D64N*), sludge (D64S*) and blood
# (D64B*) are the same 64-frame flat design in a different palette. The engine
# tells them apart by name and picks a body/crest colour per liquid; here they
# are all just "water".
_SEQ = ("D64W1_", "D64W2_", "D64N1_", "D64N2_",
        "D64S1_", "D64S2_", "D64B1_", "D64B2_")

# The WALL sheets. 64-frame sequences exactly like the flats, and they are NOT
# tagged as liquid: RG_MESH_PRIMITIVE_WATER makes a primitive refractive, and
# ASManager then rewrites its TLAS mask to INSTANCE_MASK_REFRACT alone, dropping
# every INSTANCE_MASK_WORLD_* bit. A pool that casts no shadow is survivable; a
# WALL that stops blocking shadow rays is not, and MAP10's falls leaked light
# through the solid lines they are painted on.
#
# They stay in the QUARANTINE list regardless. Frame-01-only overlays are a
# defect of their own -- the surface gains a normal map and a heightmap for two
# tics per cycle and snaps back -- and that is true whether or not anything ever
# tags them as liquid.
_FALLS = ("WFALL", "SFALL", "BFALL")
_PATCHES = ("D64WATR1", "D64WATR2", "D64NUKG1", "D64NUKG2",
            "D64SLDG1", "D64SLDG2", "D64BLOD1", "D64BLOD2")

WATER = tuple(
    f"{p}{i:02d}" for p in _SEQ for i in range(1, 65)
) + _PATCHES

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
# D64WATR1/2 and the other warp2 patches are NOT part of any sequence (separate
# 192x192 textures), so their overlays are consistent and are left alone.
#
# Every liquid family has the same frame-01-only overlays, for the same reason:
# the PBR tooling worked from the names the maps reference.
#
# BLOOD AND SLUDGE ARE EXEMPT, AND MUST STAY EXEMPT. d64r-liquid-art.wad
# redefines all 128 frames of each as one unshifted image and
# tools/gen_liquid_art.py writes _n/_h/_orm for EVERY one of them, so those
# families are materially uniform by construction -- it is the "regenerate for
# 128 frames" this comment rejected for the others, done properly. Quarantining
# frame 01 here would take the overlay off exactly one frame in 64 and recreate
# the defect this list exists to stop. For blood the _h also carries the flow
# direction in .g/.b, so losing it stills the flow; for sludge the _n IS the
# effect (rt_sludge_relief), so losing it puts the water ripple back for 2 tics
# a cycle.
#
# Poison is NOT exempt: the same wad replaces its art, but it gets no relief
# and no flow, so no overlays are written for it and the quarantine stands.
_RELIEF_FAMILIES = ("D64B1_", "D64B2_", "D64S1_", "D64S2_")
FRAME1_ONLY_MATS = tuple(
    f"{p}01" for p in _SEQ + _FALLS if p not in _RELIEF_FAMILIES
)
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
    """One line per FAMILY: 712 frame names is not a report anyone can read."""
    print(f"{TARGET}")
    # first textureName wins in RTGL1's lookup, so only the first matters
    by_name = {}
    for e in entries:
        by_name.setdefault(e.get("textureName"), e)

    for family in _SEQ + _PATCHES:
        names = [n for n in WATER if n.startswith(family)]
        present = [n for n in names if n in by_name]
        tagged = [n for n in present if by_name[n].get("isWater")]
        print(f"  {family:9} {len(tagged):3}/{len(names):3} tagged isWater"
              f"   ({len(names) - len(present)} missing entries)")


def retag(path: Path, mode: str) -> list[tuple[str, str]]:
    """Apply (or revert) the water meta in one textures.json. Returns the changes."""
    data, entries = load(path)

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

    # The falls were tagged for one revision. Untag on every --apply, so a tree
    # that ran the old version converges instead of keeping a leak nobody can
    # see in the source any more.
    fall_names = {f"{p}{i:02d}" for p in _FALLS for i in range(1, 65)}
    for e in entries:
        if e.get("textureName") in fall_names and e.pop("isWater", None) is not None:
            changed.append((e["textureName"], "untagged (wall sheet)"))

    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return changed


def main() -> int:
    if not TARGET.exists():
        print(f"ERROR: {TARGET} not found -- build gzdoom first")
        return 1

    mode = sys.argv[1] if len(sys.argv) > 1 else ""

    if mode not in ("--apply", "--revert"):
        show(load(TARGET)[1])
        print("\nPass --apply to tag them as water, --revert to untag.")
        return 0

    changed = []
    for path in TARGETS:
        if not path.exists():
            print(f"  skip (missing): {path}")
            continue
        c = retag(path, mode)
        changed += c
        print(f"  {len(c):4} entr(ies) -> {path}")

    n = quarantine_frame1_mats(restore=(mode == "--revert"))
    print(f"{n} frame-01-only material overlay(s) moved.")
    print("Relaunch to see it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
