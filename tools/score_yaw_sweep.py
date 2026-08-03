"""Score MAP99 yaw/orbit-sweep PNGs for directional emission *wash*.

Distinguishes:
  - White-bloom wash (high bright-pixel fraction / very high mean)  → FAIL
  - Normal dark gallery with some yaws seeing lit panels (moderate mean
    swing, near-zero bright_frac) → PASS

Scores the lower 55% of the frame (floor / pillars) so a sky strip in the
upper FOV cannot dominate the mean — orbit stops near aisles otherwise
false-fail.

Usage:
  python tools/score_yaw_sweep.py [dir]
  python tools/score_yaw_sweep.py screen/yaw_sweep --max-delta 45 --max-mean 70
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

from PIL import Image


def score_dir(d: Path) -> list[dict]:
    rows: list[dict] = []
    for p in sorted(d.glob("yaw_*.png")):
        im = Image.open(p).convert("RGB")
        w, h = im.size
        # Drop window chrome / HUD; keep lower FOV (pillars + floor), not sky.
        left, right = w // 8, w * 7 // 8
        top = int(h * 0.38)
        bottom = int(h * 0.88)
        crop = im.crop((left, top, right, bottom))
        px = list(crop.getdata())
        luma = [(0.2126 * r + 0.7152 * g + 0.0722 * b) for r, g, b in px]
        mean = sum(luma) / len(luma)
        bright = sum(1 for v in luma if v > 200) / len(luma)
        hot = sum(1 for v in luma if v > 120) / len(luma)
        p95 = sorted(luma)[int(len(luma) * 0.95)]
        rows.append(
            {
                "file": p.name,
                "mean": round(mean, 2),
                "bright_frac": round(bright, 4),
                "hot_frac": round(hot, 4),
                "p95": round(p95, 2),
            }
        )
        print(
            f"{p.name}: mean={mean:.1f} p95={p95:.1f} "
            f"hot%>120={hot * 100:.2f}% bright%>200={bright * 100:.2f}%"
        )
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "dir",
        nargs="?",
        default=r"G:\AI\Doom64-RT\screen\yaw_sweep",
    )
    ap.add_argument(
        "--max-delta",
        type=float,
        default=45.0,
        help="Fail if (max_mean - min_mean) exceeds this (default 45)",
    )
    ap.add_argument(
        "--max-mean",
        type=float,
        default=70.0,
        help="Fail if any frame mean luma exceeds this (default 70)",
    )
    ap.add_argument(
        "--max-bright-frac",
        type=float,
        default=0.03,
        help="Fail if any frame bright>200 fraction exceeds this (default 0.03)",
    )
    ap.add_argument(
        "--max-p95",
        type=float,
        default=160.0,
        help="Fail if any frame 95th-percentile luma exceeds this (default 160)",
    )
    ap.add_argument(
        "--baseline-json",
        default="",
        help="Optional boost=0 yaw_score.json — fail if delta grows a lot vs baseline",
    )
    ap.add_argument(
        "--max-delta-vs-baseline",
        type=float,
        default=40.0,
        help="With --baseline-json, fail if delta_now - delta_base exceeds this",
    )
    ap.add_argument("--json-out", default="")
    args = ap.parse_args()
    d = Path(args.dir)
    rows = score_dir(d)
    if not rows:
        print("FAIL: no yaw_*.png found")
        return 2

    means = [r["mean"] for r in rows]
    delta = max(means) - min(means)
    med = statistics.median(means)
    suspects = [
        r["file"]
        for r in rows
        if r["mean"] > args.max_mean
        or r["bright_frac"] > args.max_bright_frac
        or r["p95"] > args.max_p95
    ]

    report = {
        "dir": str(d),
        "frames": rows,
        "min_mean": min(means),
        "max_mean": max(means),
        "median_mean": med,
        "delta": round(delta, 2),
        "suspect_frames": suspects,
        "thresholds": {
            "max_delta": args.max_delta,
            "max_mean": args.max_mean,
            "max_bright_frac": args.max_bright_frac,
            "max_p95": args.max_p95,
            "max_delta_vs_baseline": args.max_delta_vs_baseline,
        },
        "pass": True,
        "reasons": [],
    }

    print(
        f"range mean {min(means):.1f}..{max(means):.1f}  delta={delta:.1f}  median={med:.1f}"
    )

    if delta > args.max_delta:
        report["pass"] = False
        report["reasons"].append(f"delta {delta:.1f} > max_delta {args.max_delta}")
    if max(means) > args.max_mean:
        report["pass"] = False
        report["reasons"].append(f"max mean {max(means):.1f} > max_mean {args.max_mean}")
    if any(r["bright_frac"] > args.max_bright_frac for r in rows):
        report["pass"] = False
        report["reasons"].append(
            f"bright_frac > {args.max_bright_frac} in {suspects}"
        )
    if any(r["p95"] > args.max_p95 for r in rows):
        report["pass"] = False
        report["reasons"].append(f"p95 > {args.max_p95} in {suspects}")

    if args.baseline_json:
        base = json.loads(Path(args.baseline_json).read_text(encoding="utf-8"))
        base_delta = float(base.get("delta", 0))
        growth = delta - base_delta
        report["baseline_delta"] = base_delta
        report["delta_growth"] = round(growth, 2)
        print(f"vs baseline delta {base_delta:.1f} -> growth {growth:.1f}")
        if growth > args.max_delta_vs_baseline:
            report["pass"] = False
            report["reasons"].append(
                f"delta growth {growth:.1f} > {args.max_delta_vs_baseline} vs boost=0"
            )

    if report["pass"]:
        print("PASS: no emission-wash signature")
        code = 0
    else:
        print("FAIL:", "; ".join(report["reasons"]))
        if suspects:
            print("SUSPECT frames:", ", ".join(suspects))
        code = 2

    out = Path(args.json_out) if args.json_out else d / "yaw_score.json"
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("report ->", out)
    return code


if __name__ == "__main__":
    sys.exit(main())
