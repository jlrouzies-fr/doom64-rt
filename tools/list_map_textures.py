"""List unique textures used in a UDMF TEXTMAP extract."""
import argparse
import re
from collections import Counter
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("textmap", type=Path)
    ap.add_argument("-n", type=int, default=0, help="show top N (0=all)")
    args = ap.parse_args()
    text = args.textmap.read_text(encoding="utf-8", errors="replace")
    tex = Counter()
    for m in re.finditer(
        r'texture(?:floor|ceiling|middle|top|bottom)\s*=\s*"([^"]+)"', text
    ):
        name = m.group(1)
        if name not in ("-", "F_SKY1"):
            tex[name] += 1
    items = tex.most_common(args.n or None)
    print(f"unique={len(tex)}")
    for name, c in items:
        print(f"{c:4} {name}")


if __name__ == "__main__":
    main()
