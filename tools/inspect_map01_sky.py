import re
import struct
from pathlib import Path
from collections import Counter

# Repo root, derived from this file so a clone can live anywhere.
PROJ_ROOT = Path(__file__).resolve().parents[1]

text = PROJ_ROOT / r"tools\_map_cmp\MAP01_TEXTMAP.txt".read_text(encoding="utf-8")

print("=== sky-related things ===")
for m in re.finditer(r"(?ms)^thing\s*\{(.*?)\}", text):
    b = m.group(1)
    t = re.search(r"type\s*=\s*(\d+)", b)
    if not t:
        continue
    typ = int(t.group(1))
    if typ in (9080, 9081, 9082, 9025, 9070, 9071, 9072, 9001) or "sky" in b.lower():
        print("--- type", typ)
        print(b.strip()[:400])

print("\n=== F_SKY1 sectors (ceilings) ===")
for i, m in enumerate(re.finditer(r"(?ms)^sector\s*\{(.*?)\}", text)):
    b = m.group(1)
    if 'textureceiling = "F_SKY1"' in b:
        flats = re.findall(r'texture\w+\s*=\s*"[^"]+"', b)
        ids = re.findall(r"(?m)^\s*id\s*=\s*\d+", b)
        print(f"sector#{i}", flats, ids, "light", re.search(r"lightlevel\s*=\s*(\d+)", b).group(1) if re.search(r"lightlevel\s*=\s*(\d+)", b) else "?")

print("\n=== SPACE*/cloud-ish floor/ceil textures ===")
tex = Counter()
for m in re.finditer(r'texture(?:floor|ceiling|middle|top|bottom)\s*=\s*"([^"]+)"', text):
    name = m.group(1)
    if any(x in name.upper() for x in ("SPACE", "CLOUD", "SKY", "ISUCK")):
        tex[name] += 1
print(tex)

# Decode ISUCK PNG palette roughly
data = PROJ_ROOT / r"tools\_map_isol\ISUCK.bin".read_bytes()
assert data[:8] == b"\x89PNG\r\n\x1a\n"
# find PLTE
i = 8
colors = []
while i < len(data):
    ln = int.from_bytes(data[i : i + 4], "big")
    typ = data[i + 4 : i + 8]
    chunk = data[i + 8 : i + 8 + ln]
    if typ == b"PLTE":
        for j in range(0, len(chunk), 3):
            colors.append(tuple(chunk[j : j + 3]))
        print("ISUCK palette", colors)
    if typ == b"IEND":
        break
    i += 12 + ln
