from pathlib import Path
import re

mat = Path(r"G:\AI\Doom64-RT\sourcecode\gzdoom-rt\build\RelWithDebInfo\rt\mat")
files = sorted(mat.glob("SARG*_e.png"))
print("mat exists", mat.exists(), "count", len(files))
for f in files[:8]:
    print(" ", f.name, f.stat().st_size)
t = (mat.parent / "data" / "textures.json").read_text(encoding="utf-8")
m = re.search(r'"textureName"\s*:\s*"SARGA1"[^}]+}', t)
print("meta", m.group(0) if m else "MISSING")
