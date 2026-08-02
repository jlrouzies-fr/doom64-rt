"""Apply stronger category PBR defaults to all gallery scene textures (preserve hand patches)."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(r"G:\AI\Doom64-RT")
SCENE = ROOT / r"sourcecode\gzdoom-rt\build\RelWithDebInfo\rt\data\scenes\d64rtexg_map99\textures.json"
OVERLAY = (
    ROOT / r"Doom64-Retribution\Retribution-RT-Materials\rt\data\scenes\d64rtexg_map99\textures.json"
)
INV = ROOT / r"tools\_gallery\texture_inventory.json"


def classify(name: str) -> dict:
    u = name.upper()
    meta: dict = {"textureName": name, "roughnessDefault": 0.75, "metallicDefault": 0.2}
    if u == "ISUCK":
        return {**meta, "emissiveMult": 0.0, "roughnessDefault": 1.0, "metallicDefault": 0.0}
    if any(x in u for x in ("LAVA", "FIRE")):
        return {
            **meta,
            "emissiveMult": 2.0,
            "roughnessDefault": 0.35,
            "metallicDefault": 0.1,
            "lightIntensity": 80,
            "lightColor": [255, 90, 20],
        }
    if any(x in u for x in ("NUKE", "SLIME")):
        return {
            **meta,
            "emissiveMult": 1.2,
            "isAcid": True,
            "roughnessDefault": 0.25,
            "metallicDefault": 0.2,
            "lightIntensity": 40,
            "lightColor": [40, 255, 40],
        }
    if "WATER" in u or "BLOOD" in u:
        return {
            **meta,
            "isMirror": True,
            "isWater": "WATER" in u,
            "metallicDefault": 1.0,
            "roughnessDefault": 0.05,
        }
    if u.startswith("SPACE") or u.startswith("METAL") or u.startswith("STEEL"):
        return {
            **meta,
            "metallicDefault": 0.8,
            "roughnessDefault": 0.34,
            "isMirrorIfSmooth": True,
        }
    if any(x in u for x in ("COMP", "MONIT", "TECH", "LIGHT", "LITE", "GLOW", "SWITCH")):
        return {
            **meta,
            "metallicDefault": 0.55,
            "roughnessDefault": 0.4,
            "emissiveMult": 0.7,
            "lightIntensity": 35,
            "lightColor": [180, 220, 255],
        }
    if u.startswith("SFLAT") or u.startswith("FLAT") or u.startswith("FLOOR"):
        return {**meta, "roughnessDefault": 0.92, "metallicDefault": 0.05}
    if u.startswith("CEIL") or u.startswith("SDFLT"):
        return {**meta, "roughnessDefault": 0.85, "metallicDefault": 0.12}
    if "DOOR" in u or "GATE" in u:
        return {
            **meta,
            "metallicDefault": 0.65,
            "roughnessDefault": 0.45,
            "emissiveMult": 0.15 if "GATE" in u else 0.0,
        }
    if u.startswith("HELL"):
        return {**meta, "roughnessDefault": 0.7, "metallicDefault": 0.25, "emissiveMult": 0.1}
    if u.startswith("C") and u[1:2].isdigit():
        return {**meta, "roughnessDefault": 0.8, "metallicDefault": 0.3}
    return meta


def main() -> None:
    names = json.loads(INV.read_text(encoding="utf-8"))["textures"]
    # Keep any existing tuned fields that are richer? For bulk we replace with classify.
    array = [classify(n) for n in names]
    # Preserve prior hand patches from batch_0000_0011 review.json if present
    hand = ROOT / r"tools\_gallery\batch_0000_0011\review.json"
    if hand.exists():
        meta = json.loads(hand.read_text(encoding="utf-8")).get("meta", {})
        by = {e["textureName"]: e for e in array}
        for k, v in meta.items():
            if k in by:
                by[k].update(v)
                by[k]["textureName"] = k
        array = list(by.values())

    doc = {"version": 0, "array": array}
    for path in (SCENE, OVERLAY):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
        print("wrote", path, len(array))


if __name__ == "__main__":
    main()
