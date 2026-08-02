from pathlib import Path
import re

t = Path(
    r"G:\AI\Doom64-RT\sourcecode\gzdoom-rt\build\RelWithDebInfo\rt\data\textures.json"
).read_text(encoding="utf-8")
for n in [
    "BAR1A0",
    "BAR1B0",
    "BEXPC0",
    "BAL1A0",
    "BAL7A1A5",
    "RBALA1",
    "TRCRA1",
    "PLSSA0",
    "MANFA1",
    "PISFA0",
    "GFLMA0",
]:
    m = re.search(rf'"textureName"\s*:\s*"{n}"[^}}]+}}', t)
    print(m.group(0) if m else "MISSING " + n)
mat = Path(r"G:\AI\Doom64-RT\sourcecode\gzdoom-rt\build\RelWithDebInfo\rt\mat")
print("BAR1 _e:", list(mat.glob("BAR1*_e.png")))
