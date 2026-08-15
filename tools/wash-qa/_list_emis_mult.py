"""List textures.json emissiveMult values (comment-tolerant)."""
from __future__ import annotations

import re
from pathlib import Path

# Repo root, derived from this file so a clone can live anywhere.
PROJ_ROOT = Path(__file__).resolve().parents[2]

p = PROJ_ROOT / r"sourcecode\gzdoom-rt\build\RelWithDebInfo\rt\data\textures.json"
high = []
low = []
for line in p.read_text(encoding="utf-8").splitlines():
    s = line.split("//", 1)[0]
    m = re.search(r'"textureName"\s*:\s*"([^"]+)".*"emissiveMult"\s*:\s*([0-9.]+)', s)
    if not m:
        continue
    name, val = m.group(1), float(m.group(2))
    (high if val >= 0.01 else low).append((val, name))
high.sort(reverse=True)
print(f"emissiveMult>=0.01: {len(high)}")
for v, n in high[:40]:
    print(f"  {v:8.4f}  {n}")
print(f"emissiveMult<0.01: {len(low)} (authored-ish)")
for v, n in sorted(low)[:15]:
    print(f"  {v:8.4f}  {n}")
