"""Score MAP97 emis-iso room screenshots; rank which batch rooms wash.

Usage:
  python tools/score_emis_iso.py [dir]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(r"G:\AI\Doom64-RT")
ROOMS_JSON = ROOT / r"tools\_emis_iso\rooms.json"


def score_png(path: Path) -> dict:
    im = Image.open(path).convert("RGB")
    w, h = im.size
    crop = im.crop((w // 8, int(h * 0.28), w * 7 // 8, int(h * 0.88)))
    px = list(crop.getdata())
    luma = [(0.2126 * r + 0.7152 * g + 0.0722 * b) for r, g, b in px]
    mean = sum(luma) / len(luma)
    bright = sum(1 for v in luma if v > 200) / len(luma)
    hot = sum(1 for v in luma if v > 120) / len(luma)
    p95 = sorted(luma)[int(len(luma) * 0.95)]
    return {
        "file": path.name,
        "mean": round(mean, 2),
        "p95": round(p95, 2),
        "hot_frac": round(hot, 4),
        "bright_frac": round(bright, 4),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("dir", nargs="?", default=str(ROOT / "screen" / "emis_iso"))
    ap.add_argument("--json-out", default="")
    args = ap.parse_args()
    d = Path(args.dir)
    rooms_meta = []
    if ROOMS_JSON.exists():
        rooms_meta = json.loads(ROOMS_JSON.read_text(encoding="utf-8"))["rooms"]

    rows = []
    shots = sorted(d.glob("room_*.png"))
    if not shots:
        shots = sorted(d.glob("Screenshot_*.png"))
    for i, p in enumerate(shots):
        s = score_png(p)
        # Prefer id from filename room_00_CONTROL.png
        rid = p.stem
        note = ""
        if rid.startswith("room_") and "_" in rid[5:]:
            parts = rid.split("_", 2)
            if len(parts) >= 3:
                rid = parts[2]
        if i < len(rooms_meta):
            if rid.startswith("room") or rid.isdigit():
                rid = rooms_meta[i]["id"]
            note = rooms_meta[i].get("note", "")
            # match by id when possible
            for rm in rooms_meta:
                if rm["id"] == rid:
                    note = rm.get("note", "")
                    break
        s["room"] = rid
        s["note"] = note
        s["index"] = i
        rows.append(s)
        print(
            f"[{i}] {rid:12} mean={s['mean']:6.1f} p95={s['p95']:6.1f} "
            f"hot%={s['hot_frac']*100:5.2f} bright%={s['bright_frac']*100:5.2f}  {note}"
        )

    if not rows:
        print("FAIL: no screenshots")
        return 2

    control = next((r for r in rows if r["room"] == "CONTROL"), rows[0])
    ranked = sorted(rows, key=lambda r: r["mean"], reverse=True)
    print("--- ranked by mean (hottest first) ---")
    for r in ranked:
        delta = r["mean"] - control["mean"]
        flag = " <== HOT" if delta > 15 or r["bright_frac"] > 0.02 else ""
        print(f"  {r['room']:12} mean={r['mean']:6.1f}  vs_control={delta:+6.1f}{flag}")

    report = {
        "dir": str(d),
        "control_mean": control["mean"],
        "frames": rows,
        "hottest": ranked[0]["room"],
        "hot_rooms": [
            r["room"]
            for r in ranked
            if r["room"] != "CONTROL"
            and (r["mean"] - control["mean"] > 15 or r["bright_frac"] > 0.02)
        ],
    }
    out = Path(args.json_out) if args.json_out else d / "emis_iso_score.json"
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"report -> {out}")
    print(f"hot_rooms: {report['hot_rooms'] or '(none vs control)'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
