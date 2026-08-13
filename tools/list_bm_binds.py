import re
import zipfile
from collections import Counter
from pathlib import Path

# Repo root, derived from this file so a clone can live anywhere.
PROJ_ROOT = Path(__file__).resolve().parents[1]

bm = PROJ_ROOT / r"Doom64-Retribution\D64RTR_BRIGHTMAPS.PK3"
with zipfile.ZipFile(bm) as z:
    t = z.read("GLDEFS").decode("latin1", "replace")
PROJ_ROOT / r"tools\_map_isol\brightmaps_gldefs.txt".write_text(t, encoding="utf-8")
binds = re.findall(
    r'brightmap\s+sprite\s+"([^"]+)"\s*\{\s*map\s+"([^"]+)"', t, re.I
)
print("binds", len(binds))
print(Counter(b[0][:4] for b in binds).most_common(40))
mon_pref = {
    "SARG",
    "TROO",
    "FATT",
    "BOS2",
    "BOSS",
    "CYBR",
    "BSPI",
    "HEAD",
    "SKEL",
    "POSS",
    "SPOS",
    "CPOS",
    "VILE",
    "SPID",
    "SKUL",
    "PAIN",
    "SSWV",
    "PLAY",
    "SMON",
}
mon = [b for b in binds if b[0][:4] in mon_pref]
print("monster binds", len(mon))
for b in mon:
    print(b[0], "->", b[1])
