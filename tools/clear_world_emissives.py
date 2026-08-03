"""Temporarily strip world _e maps + emis meta for A/B (mapboost stay 200).

Does NOT touch enemy/FX/sprite _e. Restore with:
  python tools/gen_world_emissives.py
"""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

ROOT = Path(r"G:\AI\Doom64-RT")
WORLD = ROOT / r"Doom64-Retribution\Retribution-RT-Materials\rt\data\textures_world_emis.json"
WORLD_BAK = WORLD.with_suffix(".json.bak")

MAT_DIRS = [
    ROOT / r"sourcecode\gzdoom-rt\build\RelWithDebInfo\rt\mat",
    ROOT / r"Doom64-Retribution\Retribution-RT-Materials\rt\mat",
]
SCENES = [
    ROOT / r"sourcecode\gzdoom-rt\build\RelWithDebInfo\rt\data\scenes\d64rtexg_map99\textures.json",
    ROOT / r"Doom64-Retribution\Retribution-RT-Materials\rt\data\scenes\d64rtexg_map99\textures.json",
    ROOT / r"sourcecode\gzdoom-rt\build\RelWithDebInfo\rt\data\scenes\d64rtr_v15_map01\textures.json",
    ROOT / r"Doom64-Retribution\Retribution-RT-Materials\rt\data\scenes\d64rtr_v15_map01\textures.json",
]
GLOBAL = ROOT / r"sourcecode\gzdoom-rt\build\RelWithDebInfo\rt\data\textures.json"

EMIS_KEYS = (
    "emissiveMult",
    "lightIntensity",
    "lightColor",
    "lightColorHEX",
    "lightEvenOnDynamic",
    "attachedLightIntensity",
    "attachedLightColor",
)


def load_world_names() -> set[str]:
    if not WORLD.exists() and WORLD_BAK.exists():
        doc = json.loads(WORLD_BAK.read_text(encoding="utf-8"))
    elif WORLD.exists():
        doc = json.loads(WORLD.read_text(encoding="utf-8"))
    else:
        raise SystemExit(f"missing {WORLD} (and no .bak)")
    return {e["textureName"].upper() for e in doc.get("array", []) if "textureName" in e}


def strip_scene(path: Path, names: set[str]) -> int:
    if not path.exists():
        return 0
    doc = json.loads(path.read_text(encoding="utf-8"))
    n = 0
    for e in doc.get("array", []):
        name = str(e.get("textureName", "")).upper()
        if name not in names:
            continue
        changed = False
        for k in EMIS_KEYS:
            if k in e:
                del e[k]
                changed = True
        if changed:
            n += 1
    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return n


def strip_global(names: set[str]) -> int:
    if not GLOBAL.exists():
        return 0
    text = GLOBAL.read_text(encoding="utf-8")
    n = 0

    def repl(m: re.Match[str]) -> str:
        nonlocal n
        block = m.group(0)
        name_m = re.search(r'"textureName"\s*:\s*"([^"]+)"', block)
        if not name_m or name_m.group(1).upper() not in names:
            return block
        orig = block
        for k in EMIS_KEYS:
            block = re.sub(rf',?\s*"{k}"\s*:\s*(?:\[[^\]]*\]|"[^"]*"|[0-9.eE+-]+|true|false)', "", block)
        block = re.sub(r"\{\s*,", "{", block)
        block = re.sub(r",\s*}", "}", block)
        block = re.sub(r",\s*,", ",", block)
        if block != orig:
            n += 1
        return block

    text2 = re.sub(r"\{[^{}]*\"textureName\"[^{}]*\}", repl, text)
    if n:
        GLOBAL.write_text(text2, encoding="utf-8")
    return n


def main() -> None:
    names = load_world_names()
    print(f"world names: {len(names)}")

    # Backup overlay once, then empty it so nothing re-merges expectantly
    if WORLD.exists() and not WORLD_BAK.exists():
        shutil.copy2(WORLD, WORLD_BAK)
        print(f"backed up -> {WORLD_BAK.name}")
    if WORLD.exists() or WORLD_BAK.exists():
        WORLD.write_text('{\n  "array": []\n}\n', encoding="utf-8")
        print(f"cleared {WORLD.name}")

    removed = 0
    for d in MAT_DIRS:
        if not d.exists():
            continue
        for name in names:
            p = d / f"{name}_e.png"
            if p.exists():
                p.unlink()
                removed += 1
    print(f"deleted _e.png: {removed}")

    for scene in SCENES:
        c = strip_scene(scene, names)
        print(f"  scene {scene.parent.name}: stripped meta {c}")

    g = strip_global(names)
    print(f"global textures.json stripped: {g}")
    print("done — launch gallery and check wall blotches at mapboost 200")
    print("restore: python tools/gen_world_emissives.py")


if __name__ == "__main__":
    main()
