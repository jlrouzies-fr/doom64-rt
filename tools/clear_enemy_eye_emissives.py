"""Strip enemy eye _e.png maps and eye emissiveMult (for before shots)."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(r"G:\AI\Doom64-RT")
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


def strip_global_emis() -> int:
    if not GLOBAL.exists():
        return 0
    text = GLOBAL.read_text(encoding="utf-8")
    n = 0

    def repl(m: re.Match[str]) -> str:
        nonlocal n
        block = m.group(0)
        name_m = re.search(r'"textureName"\s*:\s*"([^"]+)"', block)
        if not name_m or not is_monster_tex(name_m.group(1)):
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
        GLOBAL.write_text(new, encoding="utf-8")
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
        if not is_monster_tex(str(e.get("textureName", "")))
    ]
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    n = 0
    for d in DIRS:
        if not d.exists():
            continue
        for p in d.glob("*_e.png"):
            tex = p.name[: -len("_e.png")]
            if is_monster_tex(tex):
                p.unlink()
                n += 1
    OVERLAY.write_text('{"version": 0, "array": []}\n', encoding="utf-8")
    clear_json_array(SCENE)
    clear_json_array(ENEMY_GALLERY_SCENE)
    g = strip_global_emis()
    print(f"cleared {n} enemy _e.png; stripped {g} global emissiveMult; reset overlays")


if __name__ == "__main__":
    main()
