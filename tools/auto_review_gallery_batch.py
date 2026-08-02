"""
Mark gallery booth shots in texture-status.md after a capture batch.

Valid shot (not near-black) + category heuristics -> status `done`
Failed/black shot -> `blocked`
ISUCK / known dummies -> `skip`
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from PIL import Image

ROOT = Path(r"G:\AI\Doom64-RT")
MD = ROOT / "texture-status.md"
BOOTHS = ROOT / r"tools\_gallery\booths.json"


def category(name: str) -> str:
    u = name.upper()
    if name.upper() in ("ISUCK",):
        return "skip"
    if any(x in u for x in ("LAVA", "FIRE", "NUKE", "SLIME", "WATER", "BLOOD")):
        return "liquid"
    if u.startswith("SPACE") or u.startswith("METAL") or u.startswith("STEEL"):
        return "metal"
    if any(x in u for x in ("COMP", "MONIT", "TECH", "LIGHT", "LITE", "GLOW", "SWITCH")):
        return "tech"
    if u.startswith("SFLAT") or u.startswith("FLAT") or u.startswith("FLOOR"):
        return "floor"
    if u.startswith("CEIL") or u.startswith("SDFLT"):
        return "ceiling"
    if "DOOR" in u or "GATE" in u:
        return "door"
    if u.startswith("HELL"):
        return "hell"
    if re.match(r"^C\d", u):
        return "industrial"
    return "industrial"


def shot_ok(path: Path) -> tuple[bool, str]:
    if not path.exists() or path.stat().st_size < 8000:
        return False, "missing/tiny shot"
    try:
        im = Image.open(path).convert("RGB")
    except Exception as e:
        return False, f"unreadable ({e})"
    # sample center band (ignore HUD text)
    w, h = im.size
    crop = im.crop((int(w * 0.15), int(h * 0.2), int(w * 0.85), int(h * 0.85)))
    hist = crop.resize((64, 64)).getdata()
    mean = sum(sum(p) for p in hist) / (64 * 64 * 3)
    vals = [sum(p) / 3 for p in hist]
    var = sum((v - mean) ** 2 for v in vals) / len(vals)
    if mean < 18:
        return False, f"too dark mean={mean:.1f}"
    # Inside-geometry mush is near-flat; real booth shots can be fairly uniform.
    if var < 25:
        return False, f"low detail var={var:.0f} mean={mean:.1f}"
    return True, f"ok mean={mean:.1f} var={var:.0f}"


def patch_md_row(text: str, name: str, status: str, note: str) -> str:
    pat = re.compile(
        rf"(\|\s*`{re.escape(name)}`\s*\|\s*)([^|]+)(\|\s*)([^|]+)(\|\s*)([^|]*)(\|)",
        re.M,
    )

    def repl(m: re.Match) -> str:
        cat = m.group(2).strip()
        return f"| `{name}` | {cat} | {status} | {note} |"

    # full row replace keeping uses/maps from end — original has 6 cols
    pat2 = re.compile(
        rf"^\|\s*`{re.escape(name)}`\s*\|\s*([^|]+)\|\s*([^|]+)\|\s*([^|]+)\|\s*([^|]+)\|\s*([^|]+)\|",
        re.M,
    )

    def repl2(m: re.Match) -> str:
        return (
            f"| `{name}` | {m.group(1).strip()} | {status} | {note} | "
            f"{m.group(4).strip()} | {m.group(5).strip()} |"
        )

    text2, n = pat2.subn(repl2, text, count=1)
    return text2 if n else text


def refresh_summary(text: str) -> str:
    counts: dict[str, int] = {}
    for m in re.finditer(
        r"^\|\s*`[^`]+`\s*\|\s*[^|]+\|\s*([^|]+)\|", text, re.M
    ):
        st = m.group(1).strip()
        if not st or st == "status" or st.startswith("---"):
            continue
        # first token only
        st0 = st.split()[0]
        if st0 in ("category",):
            continue
        counts[st0] = counts.get(st0, 0) + 1
    block = ["| status | count |", "|---|---|"]
    for st, n in sorted(counts.items(), key=lambda x: (-x[1], x[0])):
        block.append(f"| `{st}` | {n} |")
    return re.sub(
        r"\| status \| count \|\n\|---\|---\|\n(?:\|[^\n]+\n)*",
        "\n".join(block) + "\n",
        text,
        count=1,
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--start", type=int, required=True)
    ap.add_argument("--count", type=int, required=True)
    args = ap.parse_args()
    out = Path(args.outdir)
    booths = json.loads(BOOTHS.read_text(encoding="utf-8"))["booths"]
    manifest_path = out / "manifest.json"
    if manifest_path.exists():
        rows = json.loads(manifest_path.read_text(encoding="utf-8"))
    else:
        rows = []
        for i in range(args.count):
            idx = args.start + i
            rows.append(
                {
                    "index": idx,
                    "texture": booths[idx]["texture"] if idx < len(booths) else None,
                    "shot": f"{idx:04d}.png",
                }
            )

    reviews = {}
    text = MD.read_text(encoding="utf-8")
    for row in rows:
        name = row.get("texture")
        if not name:
            continue
        cat = category(name)
        if cat == "skip" or name.upper() == "ISUCK":
            st, note = "skip", "sky dummy / non-material"
        else:
            # Prefer after-PBR shot, then plain, then before.
            idx = int(row["index"])
            candidates = [
                row.get("shot"),
                row.get("shot_after"),
                f"{idx:04d}_after.png",
                f"{idx:04d}.png",
                row.get("shot_before"),
                f"{idx:04d}_before.png",
            ]
            shot = None
            for c in candidates:
                if not c:
                    continue
                p = out / c
                if p.exists():
                    shot = p
                    break
            if shot is None:
                shot = out / f"{idx:04d}_after.png"
            ok, why = shot_ok(shot)
            if ok:
                st = "done"
                note = f"gallery bulk ({cat}); {why}"
            else:
                st = "blocked"
                note = f"gallery bulk failed; {why}"
        reviews[name] = {"status": st, "notes": note}
        text = patch_md_row(text, name, st, note)

    text = refresh_summary(text)
    MD.write_text(text, encoding="utf-8")
    (out / "auto_review.json").write_text(json.dumps(reviews, indent=2) + "\n", encoding="utf-8")
    done = sum(1 for r in reviews.values() if r["status"] == "done")
    blocked = sum(1 for r in reviews.values() if r["status"] == "blocked")
    skipped = sum(1 for r in reviews.values() if r["status"] == "skip")
    print(f"reviewed {len(reviews)}: done={done} blocked={blocked} skip={skipped}")


if __name__ == "__main__":
    main()
