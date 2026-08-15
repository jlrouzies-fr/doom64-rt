"""Check PLAY / FX keep overlap after scrub."""
from __future__ import annotations

import json
import re
from pathlib import Path

fx = json.loads(
    Path(r"Doom64-Retribution/Retribution-RT-Materials/rt/data/textures_fx.json").read_text(
        encoding="utf-8"
    )
)
names = [e["textureName"].upper() for e in fx["array"]]
for pref in ["PLAY", "POSS", "BAL", "PUF", "MISL", "ART", "FIRE", "SKUL"]:
    hits = [n for n in names if n.startswith(pref)]
    print(pref, len(hits), hits[:8])

text = Path(
    r"sourcecode/gzdoom-rt/build/RelWithDebInfo/rt/data/textures.json"
).read_text(encoding="utf-8")
plays = []
for line in text.splitlines():
    s = line.split("//", 1)[0]
    m = re.search(
        r'"textureName"\s*:\s*"(PLAY[^"]*)".*"emissiveMult"\s*:\s*([0-9.]+)', s
    )
    if m:
        plays.append((m.group(1), float(m.group(2))))
print("global PLAY with mult count", len(plays))
print(plays[:25])
