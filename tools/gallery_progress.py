import re
from collections import Counter
from pathlib import Path

# Repo root, derived from this file so a clone can live anywhere.
PROJ_ROOT = Path(__file__).resolve().parents[1]

t = PROJ_ROOT / r"texture-status.md".read_text(encoding="utf-8")
c = Counter()
for m in re.finditer(r"^\|\s*`([^`]+)`\s*\|\s*([^|]+)\|\s*([^|]+)\|", t, re.M):
    name, cat, st = m.group(1).strip(), m.group(2).strip(), m.group(3).strip()
    if name == "texture":
        continue
    token = st.split()[0] if st.split() else "?"
    c[token] += 1
print(dict(c))
print("total", sum(c.values()))
dirs = sorted(p.name for p in PROJ_ROOT / r"tools\_gallery".glob("batch_*"))
print("batch dirs", len(dirs), "last", dirs[-5:] if dirs else [])
