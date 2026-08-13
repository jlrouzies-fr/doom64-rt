"""
Sanitize gallery/MAP scene emissives to an allowlist.

Root cause of yaw-dependent white wash:
  rt_emis_mapboost multiplies ALL surface emission in the view.
  False or oversized emitters (solid stub _e, loose albedo masks, leftover
  OUTTEX/FALL) dominate when those faces face the camera.

This keeps authored world emitters, zeros emission on everything else in the
gallery scene, and deletes non-allowlisted _e maps (never touches enemy/FX
sprite _e prefixes).

Usage:
  python tools/sanitize_gallery_emissives.py
"""
from __future__ import annotations

import json
import re
from pathlib import Path

# Repo root, derived from this file so a clone can live anywhere.
PROJ_ROOT = Path(__file__).resolve().parents[1]

ROOT = PROJ_ROOT
WORLD = ROOT / r"Doom64-Retribution\Retribution-RT-Materials\rt\data\textures_world_emis.json"
SCENES = [
    ROOT / r"sourcecode\gzdoom-rt\build\RelWithDebInfo\rt\data\scenes\d64rtexg_map99\textures.json",
    ROOT / r"Doom64-Retribution\Retribution-RT-Materials\rt\data\scenes\d64rtexg_map99\textures.json",
    ROOT / r"sourcecode\gzdoom-rt\build\RelWithDebInfo\rt\data\scenes\d64rtr_v15_map01\textures.json",
    ROOT / r"Doom64-Retribution\Retribution-RT-Materials\rt\data\scenes\d64rtr_v15_map01\textures.json",
]
MAT_DIRS = [
    ROOT / r"sourcecode\gzdoom-rt\build\RelWithDebInfo\rt\mat",
    ROOT / r"sourcecode\gzdoom-rt\build\RelWithDebInfo\rt\mat_dev",
    ROOT / r"Doom64-Retribution\Retribution-RT-Materials\rt\mat",
]

# Sprite / FX _e owned by other generators — never delete
KEEP_E_RE = re.compile(
    r"^(POSS|SPOS|CPOS|PLAY|SSWV|TROO|TRO2|SARG|SAR2|SKUL|HEAD|BOSS|PAIN|"
    r"BAR1|BEXP|MISL|MISF|BAL|RBAL|TRCR|RECT|MANF|APLS|APBX|PLSS|PLSE|"
    r"PUFF|BLUD|TFOG|IFOG|BFG|LAS|SAWG|PUNG|SHT|CHGG|ROCK|PLAS|BFGG|"
    r"BON|SOUL|MEGA|ARM|STIM|MEDI|PSTR|PINV|PINS|PMAP|PVIS|CLIP|AMMO|"
    r"ROCK|BROK|CELL|CELP|SHEL|SBOX|BPAK|BFUG|MGUN|CSAW|LAUN|PLAS|SHOT|"
    r"FIRE|FCAN|FSKU|SMBT|SMGT|SMRT|TRE\d|COL\d|CAND|CBRA|POL|POB|FSKU|"
    r"TLMP|TLP|LANT|RT_|MZL)",
    re.I,
)

EMIS_KEYS = (
    "emissiveMult",
    "lightIntensity",
    "lightColor",
    "lightColorHEX",
    "lightEvenOnDynamic",
    "attachedLightIntensity",
    "attachedLightColor",
)


def load_allow() -> set[str]:
    doc = json.loads(WORLD.read_text(encoding="utf-8"))
    return {e["textureName"].upper() for e in doc.get("array", []) if "textureName" in e}


def sanitize_scene(path: Path, allow: set[str]) -> tuple[int, int]:
    if not path.exists():
        return 0, 0
    doc = json.loads(path.read_text(encoding="utf-8"))
    cleared = kept = 0
    for e in doc.get("array", []):
        name = str(e.get("textureName", "")).upper()
        if name in allow or KEEP_E_RE.match(name):
            kept += 1
            continue
        changed = False
        for k in EMIS_KEYS:
            if k in e:
                del e[k]
                changed = True
        if changed:
            cleared += 1
    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return cleared, kept


def sanitize_mats(allow: set[str]) -> int:
    removed = 0
    for d in MAT_DIRS:
        if not d.exists():
            continue
        for p in d.glob("*_e.png"):
            stem = p.name[: -len("_e.png")].upper()
            if stem in allow or KEEP_E_RE.match(stem):
                continue
            p.unlink()
            removed += 1
    return removed


def main() -> None:
    if not WORLD.exists():
        raise SystemExit(f"missing {WORLD} — run gen_world_emissives.py first")
    allow = load_allow()
    print(f"allowlist {len(allow)}")
    for scene in SCENES:
        cleared, kept = sanitize_scene(scene, allow)
        print(f"  scene {scene.parent.name}: cleared emis meta {cleared}, kept {kept}")
    removed = sanitize_mats(allow)
    print(f"removed non-allowlist _e.png: {removed}")


if __name__ == "__main__":
    main()
