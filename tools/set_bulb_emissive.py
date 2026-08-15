"""Set emissiveMult on the Doom 64 bulb-array textures.

Why this exists as a script rather than an edit: rt/data/textures.json under
build/ is gitignored and rewritten by the PBR tooling (apply_all_category_pbr.py
and friends), so a hand edit is neither recorded nor durable. Re-run this after
any of those.

What it is for. A bulb panel needs to *look* like a large glowing fixture while
a single small analytic light at its centre does the shadow casting. Those are
different mechanisms and only one of them costs shadow quality:

  - Source RADIUS makes the light physically bigger, which widens the penumbra.
    At 0.35m (11.2 map units) it erases the shadow of a fence wire a few units
    thick. It is NOT the way to make a fixture look big.
  - EMISSION makes the surface itself glow across its whole area. Section 12:
    emission is collected only on indirect bounces, never through
    processDirectIllumination, so it can never cast a pool of light or a shadow
    at any strength -- which means raising it cannot blur or fill a shadow edge.

So: keep the analytic light small and dim, and let emission carry the fixture's
apparent size and brightness.

The limit, from section 12 and section 16: at 1 spp indirect, emission is weak,
noisy and directionless, and too much of it gives the "uniformly bright and
directionless" look. Raise it in steps and judge, do not jump to a large value.

Usage:
    python tools/set_bulb_emissive.py            # show current values
    python tools/set_bulb_emissive.py 3.0        # set the bulb panels to 3.0
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT / "sourcecode/gzdoom-rt/build/RelWithDebInfo/rt/data/textures.json"

# The bulb arrays only. SPACEAZ is the wall-mounted 4x4 grid, SFLATAQ the 4x4
# flat, SFLATAS the 2x2. Deliberately NOT SFLATAP -- that is a recessed grille,
# not a lamp, and the original game does not light it.
BULBS = ("SFLATAQ", "SFLATAS", "SPACEAZ")


def main() -> int:
    if not TARGET.exists():
        print(f"ERROR: {TARGET} not found -- build gzdoom first")
        return 1

    data = json.loads(TARGET.read_text(encoding="utf-8"))
    # RTGL1's schema is {"version": N, "array": [ {...}, ... ]}.
    entries = data["array"] if isinstance(data, dict) and "array" in data else None
    if entries is None:
        print("ERROR: unexpected textures.json shape; expected {'version':N,'array':[...]}")
        return 1

    if len(sys.argv) < 2:
        print(f"{TARGET}")
        for e in entries:
            if e.get("textureName") in BULBS:
                print(f"  {e['textureName']:10} emissiveMult={e.get('emissiveMult')}")
        print("\nPass a value to set, e.g.  python tools/set_bulb_emissive.py 3.0")
        return 0

    value = float(sys.argv[1])
    changed = []
    seen = set()
    for e in entries:
        name = e.get("textureName")
        if name in BULBS:
            seen.add(name)
            if e.get("emissiveMult") != value:
                changed.append((name, e.get("emissiveMult"), value))
                e["emissiveMult"] = value

    for name in BULBS:
        if name not in seen:
            entries.append({"textureName": name, "emissiveMult": value})
            changed.append((name, None, value))

    TARGET.write_text(json.dumps(data, indent=2), encoding="utf-8")
    for name, old, new in changed:
        print(f"  {name:10} {old} -> {new}")
    print(f"\n{len(changed)} entr(ies) written to {TARGET.name}. Relaunch to see it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
