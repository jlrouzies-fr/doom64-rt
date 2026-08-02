"""Pair gallery screenshot files with texture names from tour log / booths.json."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(r"G:\AI\Doom64-RT")
BOOTHS = ROOT / r"tools\_gallery\booths.json"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--count", type=int, default=24)
    ap.add_argument("--tag", default="", help="before | after | empty for plain 0000.png")
    args = ap.parse_args()
    out = Path(args.outdir)
    booths = json.loads(BOOTHS.read_text(encoding="utf-8"))["booths"]
    tag = (args.tag or "").strip()
    log = out / (f"stdout_{tag}.txt" if tag else "stdout.txt")
    from_log: dict[int, str] = {}
    if log.exists():
        for m in re.finditer(
            r"D64RtGalleryTour:\s+(\d+)\s+(\S+)", log.read_text(encoding="utf-8", errors="replace")
        ):
            from_log[int(m.group(1))] = m.group(2)

    # Merge into existing manifest if present (so before+after coexist).
    manifest_path = out / "manifest.json"
    by_idx: dict[int, dict] = {}
    if manifest_path.exists():
        for row in json.loads(manifest_path.read_text(encoding="utf-8")):
            by_idx[int(row["index"])] = row

    for i in range(args.count):
        idx = args.start + i
        name = from_log.get(idx)
        if not name and idx < len(booths):
            name = booths[idx]["texture"]
        row = by_idx.get(idx, {"index": idx, "texture": name})
        row["texture"] = name or row.get("texture")
        if tag:
            shot = out / f"{idx:04d}_{tag}.png"
            row[f"shot_{tag}"] = shot.name if shot.exists() else None
            row[f"exists_{tag}"] = shot.exists()
            row[f"size_{tag}"] = shot.stat().st_size if shot.exists() else 0
            # Prefer after as primary shot for reviewers/auto tools.
            if tag == "after" and shot.exists():
                row["shot"] = shot.name
                row["exists"] = True
                row["size"] = shot.stat().st_size
            elif tag == "before" and not row.get("shot"):
                row["shot"] = shot.name if shot.exists() else None
                row["exists"] = shot.exists()
                row["size"] = shot.stat().st_size if shot.exists() else 0
        else:
            shot = out / f"{idx:04d}.png"
            row["shot"] = shot.name if shot.exists() else None
            row["exists"] = shot.exists()
            row["size"] = shot.stat().st_size if shot.exists() else 0
        by_idx[idx] = row

    rows = [by_idx[i] for i in sorted(by_idx) if args.start <= i < args.start + args.count]
    # Also keep any other indices already in manifest outside this range
    for idx, row in sorted(by_idx.items()):
        if idx < args.start or idx >= args.start + args.count:
            rows.append(row)
    rows.sort(key=lambda r: int(r["index"]))
    manifest_path.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    print(f"manifest {len(rows)} -> {manifest_path} tag={tag or 'plain'}")


if __name__ == "__main__":
    main()
