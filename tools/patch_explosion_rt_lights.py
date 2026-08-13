"""
Make barrel / rocket explosion sprites emit real RT analytic lights.

Stock gzdoom-rt textures.json only gives BEXP*/MISL* emissiveMult (sprite glow).
Path-traced lights come from lightIntensity (+ color) on texture meta — RTGL1
attaches a spherical light to the sprite quad.

Retribution: 64ExplosiveBarrel uses BEXP A-E then spawns 64BarrelExplosion (MISL B-F).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

# Repo root, derived from this file so a clone can live anywhere.
PROJ_ROOT = Path(__file__).resolve().parents[1]

ROOT = PROJ_ROOT
RT_DATA = ROOT / r"sourcecode\gzdoom-rt\build\RelWithDebInfo\rt\data"
GLOBAL_JSON = RT_DATA / "textures.json"
SCENE_JSON = RT_DATA / r"scenes\d64rtr_v15_map01\textures.json"
OVERLAY_GLOBAL = ROOT / r"Doom64-Retribution\Retribution-RT-Materials\rt\data\textures_explosions.json"
OVERLAY_SCENE = (
    ROOT / r"Doom64-Retribution\Retribution-RT-Materials\rt\data\scenes\d64rtr_v15_map01\textures.json"
)

# Prefer tools/gen_fx_emissives.py for the full FX set.
# Kept for quick barrel-only retunes: toxic green BEXP, fire MISL.
EXPLOSIONS: dict[str, dict] = {
    "BAR1A0": {"emissiveMult": 1.2, "noShadow": True, "lightIntensity": 180, "lightColorHEX": "3dff4a"},
    "BAR1B0": {"emissiveMult": 1.0, "noShadow": True, "lightIntensity": 140, "lightColorHEX": "2ecc40"},
    "BEXPA0": {"emissiveMult": 0.4, "noShadow": True, "lightIntensity": 900, "lightColorHEX": "66ff44"},
    "BEXPB0": {"emissiveMult": 0.5, "noShadow": True, "lightIntensity": 1500, "lightColorHEX": "77ff55"},
    "BEXPC0": {"emissiveMult": 0.55, "noShadow": True, "lightIntensity": 2200, "lightColorHEX": "66ff44"},
    "BEXPD0": {"emissiveMult": 0.45, "noShadow": True, "lightIntensity": 1800, "lightColorHEX": "55dd33"},
    "BEXPE0": {"emissiveMult": 0.35, "noShadow": True, "lightIntensity": 1200, "lightColorHEX": "44aa22"},
    "BEXPF0": {"emissiveMult": 0.5, "noShadow": True, "lightIntensity": 2400, "lightColorHEX": "66ff44"},
    "BEXPG0": {"emissiveMult": 0.45, "noShadow": True, "lightIntensity": 1800, "lightColorHEX": "55dd33"},
    "BEXPH0": {"emissiveMult": 0.3, "noShadow": True, "lightIntensity": 1000, "lightColorHEX": "338818"},
    "BEXPI0": {"emissiveMult": 0.2, "noShadow": True, "lightIntensity": 600, "lightColorHEX": "226611"},
    "MISLB0": {"emissiveMult": 0.5, "noShadow": True, "lightIntensity": 2500, "lightColorHEX": "ffb380"},
    "MISLC0": {"emissiveMult": 0.45, "noShadow": True, "lightIntensity": 2000, "lightColorHEX": "ff8c4d"},
    "MISLD0": {"emissiveMult": 0.35, "noShadow": True, "lightIntensity": 1400, "lightColorHEX": "cc6633"},
    "MISLE0": {"emissiveMult": 0.25, "noShadow": True, "lightIntensity": 900, "lightColorHEX": "994422"},
    "MISLF0": {"emissiveMult": 0.15, "noShadow": True, "lightIntensity": 500, "lightColorHEX": "662211"},
}


def upsert_entries(path: Path, entries: dict[str, dict], replace_file: bool = False) -> None:
    if path.exists() and not replace_file:
        data = json.loads(path.read_text(encoding="utf-8"))
    else:
        data = {"version": 0, "array": []}

    by_name = {e["textureName"]: e for e in data.get("array", []) if "textureName" in e}
    for name, meta in entries.items():
        cur = by_name.get(name, {"textureName": name})
        cur.update(meta)
        cur["textureName"] = name
        by_name[name] = cur

    data["version"] = data.get("version", 0)
    data["array"] = list(by_name.values())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {path} ({len(entries)} explosion metas upserted, {len(data['array'])} total)")


def patch_global_inline(path: Path, entries: dict[str, dict]) -> None:
    """Keep stock file formatting for existing keys; append missing ones before closing.]"""
    text = path.read_text(encoding="utf-8")
    for name, meta in entries.items():
        # compact one-liner like stock
        parts = [f'"textureName":"{name}"']
        for k, v in meta.items():
            if isinstance(v, bool):
                parts.append(f'"{k}":{"true" if v else "false"}')
            elif isinstance(v, float) and v == int(v):
                parts.append(f'"{k}":{int(v)}')
            elif isinstance(v, (int, float)):
                parts.append(f'"{k}":{v}')
            else:
                parts.append(f'"{k}":"{v}"')
        line = "    ,   { " + "  ,".join(parts) + " }"

        pat = re.compile(
            rf'^[ \t]*,?[ \t]*\{{[ \t]*"textureName"[ \t]*:[ \t]*"{re.escape(name)}".*$',
            re.M,
        )
        if pat.search(text):
            text = pat.sub(line, text, count=1)
        else:
            # insert before final closing of array
            text = re.sub(r"\n(\s*\]\s*\}\s*)$", "\n" + line + r"\n\1", text, count=1)

    path.write_text(text, encoding="utf-8")
    print(f"patched inline {path}")


def main() -> None:
    patch_global_inline(GLOBAL_JSON, EXPLOSIONS)
    upsert_entries(SCENE_JSON, EXPLOSIONS, replace_file=False)
    upsert_entries(OVERLAY_GLOBAL, EXPLOSIONS, replace_file=True)
    if OVERLAY_SCENE.exists():
        upsert_entries(OVERLAY_SCENE, EXPLOSIONS, replace_file=False)
    else:
        # scene overlay may only have map mats; still write explosion upserts into a copy
        upsert_entries(OVERLAY_SCENE, EXPLOSIONS, replace_file=False)


if __name__ == "__main__":
    main()
