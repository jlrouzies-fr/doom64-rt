import io
import struct
from pathlib import Path

from PIL import Image

# Repo root, derived from this file so a clone can live anywhere.
PROJ_ROOT = Path(__file__).resolve().parents[1]

p = PROJ_ROOT / r"Doom64-Retribution\D64RTR_v15.WAD"
d = p.read_bytes()
n, o = struct.unpack_from("<II", d, 4)
mat = PROJ_ROOT / r"sourcecode\gzdoom-rt\build\RelWithDebInfo\rt\mat"
omat = PROJ_ROOT / r"Doom64-Retribution\Retribution-RT-Materials\rt\mat"
mat.mkdir(parents=True, exist_ok=True)
omat.mkdir(parents=True, exist_ok=True)

for i in range(n):
    off, sz, name = struct.unpack_from("<II8s", d, o + i * 16)
    nm = name.split(b"\0")[0].decode("ascii", "replace")
    if not nm.startswith("BAR1"):
        continue
    data = d[off : off + sz]
    print(nm, sz, data[:16])
    try:
        img = Image.open(io.BytesIO(data)).convert("RGBA")
        print(" ", img.format, img.size)
        # green-biased emissive: keep green/bright pixels
        out = []
        for r, g, b, a in img.getdata():
            if a < 40:
                out.append((0, 0, 0, 0))
                continue
            if g > r + 10 and g > b:
                out.append((min(255, int(r * 0.4)), min(255, int(g * 1.6)), min(255, int(b * 0.4)), a))
            elif r + g + b > 380:
                out.append((min(255, int(r * 0.3)), min(255, int(g * 1.3)), min(255, int(b * 0.3)), a))
            else:
                out.append((0, 0, 0, 0))
        e = Image.new("RGBA", img.size)
        e.putdata(out)
        e.save(mat / f"{nm}_e.png")
        e.save(omat / f"{nm}_e.png")
        img.save(PROJ_ROOT / r"tools\_map_isol" / f"{nm}.png")
        print("  wrote _e")
    except Exception as ex:
        print("  fail", ex)
