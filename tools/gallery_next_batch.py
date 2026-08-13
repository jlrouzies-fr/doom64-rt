"""Find next booth index needing review; optionally reset blocked -> unreviewed."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

# Repo root, derived from this file so a clone can live anywhere.
PROJ_ROOT = Path(__file__).resolve().parents[1]

ROOT = PROJ_ROOT
MD = ROOT / "texture-status.md"
BOOTHS = ROOT / r"tools\_gallery\booths.json"


def statuses() -> dict[str, str]:
    t = MD.read_text(encoding="utf-8")
    out = {}
    for m in re.finditer(r"^\|\s*`([^`]+)`\s*\|\s*[^|]+\|\s*([^|]+)\|", t, re.M):
        name = m.group(1).strip()
        if name == "texture":
            continue
        st = m.group(2).strip().split()[0] if m.group(2).strip() else "?"
        out[name] = st
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset-blocked", action="store_true")
    ap.add_argument("--count", type=int, default=30)
    args = ap.parse_args()
    booths = json.loads(BOOTHS.read_text(encoding="utf-8"))["booths"]
    st = statuses()

    if args.reset_blocked:
        text = MD.read_text(encoding="utf-8")
        for name, s in list(st.items()):
            if s in ("blocked", "?"):
                text = re.sub(
                    rf"^\|\s*`{re.escape(name)}`\s*\|\s*([^|]+)\|\s*[^|]+\|\s*[^|]+\|",
                    rf"| `{name}` | \1| unreviewed | pending re-capture |",
                    text,
                    count=1,
                    flags=re.M,
                )
                st[name] = "unreviewed"
        MD.write_text(text, encoding="utf-8")
        print("reset blocked/? -> unreviewed")

    need = []
    for b in booths:
        s = st.get(b["texture"], "unreviewed")
        if s in ("unreviewed", "blocked", "?", "auto"):
            need.append(b["index"])
    if not need:
        print("NEXT none (all done/skip)")
        return
    start = need[0]
    # contiguous run from start up to count
    end = start
    for i in range(start, min(start + args.count, len(booths))):
        s = st.get(booths[i]["texture"], "unreviewed")
        if s in ("done", "skip") and i != start:
            break
        end = i
    print(f"NEXT_START {start}")
    print(f"NEXT_COUNT {end - start + 1}")
    print(f"NEXT_RANGE {start}-{end}")
    print("need_total", len(need))


if __name__ == "__main__":
    main()
