import json
import re
import struct
from collections import Counter
from pathlib import Path

# Repo root, derived from this file so a clone can live anywhere.
PROJ_ROOT = Path(__file__).resolve().parents[2]

p = PROJ_ROOT / r"Doom64-Retribution/d64rtexg01.wad"
d = p.read_bytes()
n, o = struct.unpack_from("<II", d, 4)
t = ""
for i in range(n):
    off, sz, name = struct.unpack_from("<II8s", d, o + i * 16)
    if name.split(b"\0")[0] == b"TEXTMAP":
        t = d[off : off + sz].decode("utf-8")
        break

secs = len(re.findall(r"^sector$", t, re.M))
mids = re.findall(r'texturemiddle = "([^"]+)";', t)
c = Counter(mids)
pillar_tex = [k for k in c if k not in ("STONE2", "-")]
g = json.loads(
    PROJ_ROOT / r"tools/_gallery/batches/batch_01.json".read_text(encoding="utf-8")
)["grid"]
print("sectors", secs, "(expect 102 = hall+solid+100 pillars)")
print("pillar face textures", len(pillar_tex), "sample", pillar_tex[:6])
print("grid", g)
print(
    "at spawn: one 480u face at 200u fills FOV; neighbors are",
    g["cell"],
    "u sideways — look left/right or fly up to see the grid",
)
