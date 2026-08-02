"""Apply a batch review JSON into texture-status.md + optional scene meta tweaks."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(r"G:\AI\Doom64-RT")
MD = ROOT / "texture-status.md"
SCENE = ROOT / r"sourcecode\gzdoom-rt\build\RelWithDebInfo\rt\data\scenes\d64rtexg_map99\textures.json"
OVERLAY = (
    ROOT / r"Doom64-Retribution\Retribution-RT-Materials\rt\data\scenes\d64rtexg_map99\textures.json"
)


def patch_md(reviews: dict[str, dict]) -> None:
    text = MD.read_text(encoding="utf-8")
    for name, rev in reviews.items():
        st = rev["status"]
        note = rev.get("notes", "").replace("|", "/")
        pat = re.compile(
            rf"(\|\s*`{re.escape(name)}`\s*\|\s*[^|]+\|\s*)([^|]+)(\|\s*)([^|]*)(\|)",
            re.M,
        )

        def repl(m: re.Match) -> str:
            return f"{m.group(1)}{st} {m.group(3)}{note} {m.group(5)}"

        text2, n = pat.subn(repl, text, count=1)
        if n:
            text = text2
        else:
            print("MD miss", name)
    # refresh summary counts
    counts = {}
    for m in re.finditer(r"^\|\s*`[^`]+`\s*\|\s*[^|]+\|\s*([^|]+)\|", text, re.M):
        st = m.group(1).strip().split()[0] if m.group(1).strip() else "?"
        if st in ("status", "---`"):
            continue
        counts[st] = counts.get(st, 0) + 1
    block = ["| status | count |", "|---|---|"]
    for st, n in sorted(counts.items(), key=lambda x: -x[1]):
        block.append(f"| `{st}` | {n} |")
    text = re.sub(
        r"\| status \| count \|\n\|---\|---\|\n(?:\|.*\|\n)*",
        "\n".join(block) + "\n",
        text,
        count=1,
    )
    MD.write_text(text, encoding="utf-8")
    print("updated", MD, counts)


def patch_scene(meta_patches: dict[str, dict]) -> None:
    for path in (SCENE, OVERLAY):
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        by = {e["textureName"]: e for e in data["array"]}
        for name, patch in meta_patches.items():
            if name not in by:
                by[name] = {"textureName": name}
            by[name].update(patch)
            by[name]["textureName"] = name
        data["array"] = list(by.values())
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        print("patched", path)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("review_json")
    args = ap.parse_args()
    doc = json.loads(Path(args.review_json).read_text(encoding="utf-8"))
    patch_md(doc.get("reviews", {}))
    if doc.get("meta"):
        patch_scene(doc["meta"])


if __name__ == "__main__":
    main()
