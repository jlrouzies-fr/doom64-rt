"""Strip enemy eye _e.png maps and eye emissiveMult (for before shots)."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# Repo root, derived from this file so a clone can live anywhere. It MUST be
# defined before the import below: a portability pass left it further down the
# file, after its own first use, and `python tools/clear_enemy_eye_emissives.py`
# has died on NameError ever since -- so the recovery path AGENTS.md documents
# for enemy emissives was not runnable at all. Found 2026-08-15 while tracing the
# glowing Baron; ast.parse() passes on it, which is why nothing caught it.
PROJ_ROOT = Path(__file__).resolve().parents[1]

ROOT = PROJ_ROOT
sys.path.insert(0, str(ROOT / "tools"))
from gen_enemy_eye_emissives import (  # noqa: E402
    ENEMY_GALLERY_SCENE,
    GLOBAL,
    MAT,
    MAT_DEV,
    MONSTER_PREFIXES,
    OMAT,
    OVERLAY,
    SCENE,
)

DIRS = (MAT, MAT_DEV, OMAT)


def is_monster_tex(name: str) -> bool:
    return any(name.upper().startswith(p) for p in MONSTER_PREFIXES)


# MONSTER EMISSIVES THAT ARE NOT EYES, AND MUST SURVIVE A CLEAR.
#
# This script is named for eyes but swept every *_e.png whose name began with a
# MONSTER_PREFIXES entry, because that was the only test it had. On 2026-08-13
# that deleted all 79 BOSS*/BOS2*_e.png -- the Baron's and Hell Knight's HAND
# FIRE, ~2% coverage across the upper body, nothing to do with eyes -- while
# leaving their "emissiveMult": 4.0 behind. RTGL falls back to
# `emission = albedo * emissiveMult` when a material has no _e, so both monsters
# rendered at 4x their own albedo (screen/baronHellBright.png).
#
# SKUL is here for a different reason: pack_lostsoul_rt.py owns the Lost Soul's
# flame and attaches a REAL light to it (lightIntensity 450 + lightColorHEX
# ff9028 + lightEvenOnDynamic, frames A-F). That is a shadow-caster, not a glow,
# and it must not be swept up as an eye mask either. Same one-owner rule
# AGENTS.md states for gen_fx_emissives' PREFIX_RULES.
#
# If a family here ever genuinely grows eye masks, clear those by name rather
# than by widening this sweep.
NON_EYE_PREFIXES = (
    "BOSS",  # baron -- hand fire
    "BOS2",  # hell knight -- hand fire
    "SKUL",  # lost soul -- flame, owned by pack_lostsoul_rt.py
)


def is_eye_clearable(name: str) -> bool:
    """A monster texture whose _e/meta this script is actually allowed to remove."""
    if not is_monster_tex(name):
        return False
    return not name.upper().startswith(NON_EYE_PREFIXES)


# The AUTHORED copy of the global meta. GLOBAL (imported from
# gen_enemy_eye_emissives) points only at the gitignored BUILD tree, and
# build-gzdoom-rt.cmd xcopies Retribution-RT-Materials/rt over that tree on every
# build -- so stripping GLOBAL alone is undone by the next build, silently.
#
# That is not hypothetical. Commit 25737b8 deleted all 79 BOSS*/BOS2*_e.png masks
# from BOTH trees (OMAT is in DIRS) but stripped the meta from the build tree
# only. The authored file kept "emissiveMult": 4.0 for every one of them, the
# next build copied it back over the stripped one, and RTGL does
#     emission = h.albedo * tr.emissiveMult          (HitInfo.inl)
# whenever a material has no _e -- so the whole Baron and Hell Knight emitted at
# 4x their own albedo (screen/baronHellBright.png). Two days passed before it was
# connected to a mask deletion, because a REBUILD was needed to surface it.
#
# Same hard rule as AGENTS.md's textures.json note: the authored tree and the
# build tree are both part of the sync, and a generator that writes only one of
# them will be undone by the other.
AUTHORED_GLOBAL = (
    PROJ_ROOT / "Doom64-Retribution/Retribution-RT-Materials/rt/data/textures.json"
)


def strip_global_emis() -> int:
    return sum(_strip_one(p) for p in (GLOBAL, AUTHORED_GLOBAL))


def _strip_one(target: Path) -> int:
    if not target.exists():
        return 0
    text = target.read_text(encoding="utf-8")
    n = 0

    def repl(m: re.Match[str]) -> str:
        nonlocal n
        block = m.group(0)
        name_m = re.search(r'"textureName"\s*:\s*"([^"]+)"', block)
        if not name_m or not is_eye_clearable(name_m.group(1)):
            return block
        touched = False
        if "emissiveMult" in block:
            block = re.sub(r',?\s*"emissiveMult"\s*:\s*[0-9.]+', "", block)
            touched = True
        # Drop eye/fire attached lights we authored (keep other FX fields if any remain)
        if '"lightColorHEX":"ff241c"' in block or '"lightColorHEX": "ff241c"' in block:
            block = re.sub(r',?\s*"lightIntensity"\s*:\s*[0-9.]+', "", block)
            block = re.sub(r',?\s*"lightColorHEX"\s*:\s*"[^"]+"', "", block)
            block = re.sub(r',?\s*"noShadow"\s*:\s*true', "", block)
            touched = True
        if not touched:
            return block
        n += 1
        block = re.sub(r"\{\s*,", "{ ", block)
        block = re.sub(r",\s*,", ", ", block)
        block = re.sub(r",\s*\}", " }", block)
        return block

    new = re.sub(r'\{[^{}]*"textureName"[^{}]*\}', repl, text)
    if n:
        target.write_text(new, encoding="utf-8")
    return n


def clear_json_array(path: Path) -> None:
    if not path.exists():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        data = {"version": 0, "array": []}
    data["array"] = [
        e
        for e in data.get("array", [])
        if not is_eye_clearable(str(e.get("textureName", "")))
    ]
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    n = 0
    for d in DIRS:
        if not d.exists():
            continue
        for p in d.glob("*_e.png"):
            tex = p.name[: -len("_e.png")]
            if is_eye_clearable(tex):
                p.unlink()
                n += 1
    # FILTER the overlay, do not blank it. It used to be truncated to an empty
    # array, which threw away every non-eye entry living in it -- and the Lost
    # Soul's frames do live in it. Same keep-list as everything else here.
    clear_json_array(OVERLAY)
    clear_json_array(SCENE)
    clear_json_array(ENEMY_GALLERY_SCENE)
    g = strip_global_emis()
    print(f"cleared {n} enemy _e.png; stripped {g} global emissiveMult; reset overlays")


if __name__ == "__main__":
    main()
