from pathlib import Path
import re

t = Path(
    r"G:\AI\Doom64-RT\sourcecode\gzdoom-rt\build\RelWithDebInfo\rt\data\textures.json"
).read_text(encoding="utf-8")
for n in ["BEXPC0", "BEXPF0", "MISLB0", "MISLE0"]:
    m = re.search(rf'"textureName"\s*:\s*"{n}"[^}}]+}}', t)
    print(m.group(0) if m else f"MISSING {n}")
