from pathlib import Path
import re

mat = Path(r"G:\AI\Doom64-RT\sourcecode\gzdoom-rt\build\RelWithDebInfo\rt\mat")
prefs = (
    "SARG",
    "TROO",
    "POSS",
    "SPOS",
    "CPOS",
    "HEAD",
    "BOSS",
    "BOS2",
    "SKEL",
    "FATT",
    "BSPI",
    "SPID",
    "CYBR",
    "PAIN",
    "SKUL",
    "VILE",
    "SSWV",
)
files = list(mat.glob("*_e.png"))
print("total _e", len(files))
for p in prefs:
    n = len([f for f in files if f.name.startswith(p)])
    if n:
        print(f"  {p}: {n}")

t = (mat.parent / "data" / "textures.json").read_text(encoding="utf-8")
for n in [
    "SARGA1",
    "TROOA1",
    "HEADA1",
    "BOS2A1",
    "BOSSA1",
    "CYBRA1",
    "SKELA1",
    "FATTA1",
    "VILEA1",
    "SPIDA1",
]:
    m = re.search(rf'"textureName"\s*:\s*"{n}"[^}}]+}}', t)
    print(n, m.group(0) if m else "MISSING")
