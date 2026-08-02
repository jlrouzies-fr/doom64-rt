"""Apply (or reset) category PBR for a gallery index range."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(r"G:\AI\Doom64-RT")
sys.path.insert(0, str(ROOT / "tools"))
from apply_all_category_pbr import OVERLAY, SCENE, classify  # noqa: E402

BOOTHS = ROOT / r"tools\_gallery\booths.json"


def neutral(name: str) -> dict:
    """Baseline stub — dull diffuse, for before shots."""
    return {
        "textureName": name,
        "roughnessDefault": 0.9,
        "metallicDefault": 0.0,
    }


def patch(names: list[str], mode: str) -> None:
    for path in (SCENE, OVERLAY):
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            by = {e["textureName"]: e for e in data.get("array", [])}
        else:
            data = {"version": 0, "array": []}
            by = {}
        for n in names:
            by[n] = classify(n) if mode == "pbr" else neutral(n)
        data["array"] = list(by.values())
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {path} mode={mode} n={len(names)} total={len(by)}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, required=True)
    ap.add_argument("--count", type=int, required=True)
    ap.add_argument("--mode", choices=("pbr", "neutral"), default="pbr")
    args = ap.parse_args()
    booths = json.loads(BOOTHS.read_text(encoding="utf-8"))["booths"]
    names = [booths[i]["texture"] for i in range(args.start, args.start + args.count)]
    patch(names, args.mode)
    print("textures:", ", ".join(names))


if __name__ == "__main__":
    main()
