"""Prefix histogram for high emissiveMult in global textures.json."""
from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

# Repo root, derived from this file so a clone can live anywhere.
PROJ_ROOT = Path(__file__).resolve().parents[2]

p = PROJ_ROOT / r"sourcecode\gzdoom-rt\build\RelWithDebInfo\rt\data\textures.json"
prefs: Counter[str] = Counter()
for line in p.read_text(encoding="utf-8").splitlines():
    s = line.split("//", 1)[0]
    m = re.search(r'"textureName"\s*:\s*"([^"]+)".*"emissiveMult"\s*:\s*([0-9.]+)', s)
    if not m:
        continue
    name, val = m.group(1).upper(), float(m.group(2))
    if val < 0.01:
        continue
    pref_m = re.match(r"[A-Z]+", name)
    prefs[pref_m.group(0) if pref_m else name] += 1
for k, v in prefs.most_common(50):
    print(f"{v:4d}  {k}")
