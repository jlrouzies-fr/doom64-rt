"""Find linedefs/sectors near MAP01 SkyViewpoint for skybox face textures."""
import re
from pathlib import Path

# Repo root, derived from this file so a clone can live anywhere.
PROJ_ROOT = Path(__file__).resolve().parents[1]

text = PROJ_ROOT / r"tools\_map_cmp\MAP01_TEXTMAP.txt".read_text(encoding="utf-8")

verts = []
for m in re.finditer(r"(?ms)^vertex\s*\{(.*?)\}", text):
    b = m.group(1)
    x = float(re.search(r"x\s*=\s*([-\d.]+)", b).group(1))
    y = float(re.search(r"y\s*=\s*([-\d.]+)", b).group(1))
    verts.append((x, y))

sides = []
for m in re.finditer(r"(?ms)^sidedef\s*\{(.*?)\}", text):
    b = m.group(1)
    sec = int(re.search(r"sector\s*=\s*(\d+)", b).group(1))
    tex = {
        k: re.search(rf"texture{k}\s*=\s*\"([^\"]+)\"", b)
        for k in ("top", "bottom", "middle")
    }
    sides.append(
        (
            sec,
            {k: (v.group(1) if v else "-") for k, v in tex.items()},
        )
    )

print("vertices near sky cam (-1728,0):")
near = []
for i, (x, y) in enumerate(verts):
    if abs(x + 1728) < 512 and abs(y) < 512:
        near.append(i)
        print(i, x, y)

# linedefs using those verts
print("\nlinedefs in skybox region:")
for m in re.finditer(r"(?ms)^linedef\s*\{(.*?)\}", text):
    b = m.group(1)
    v1 = int(re.search(r"v1\s*=\s*(\d+)", b).group(1))
    v2 = int(re.search(r"v2\s*=\s*(\d+)", b).group(1))
    if v1 in near or v2 in near:
        sf = int(re.search(r"sidefront\s*=\s*(\d+)", b).group(1))
        sb = re.search(r"sideback\s*=\s*(\d+)", b)
        print(f"v{v1}-v{v2} front={sides[sf]}", end="")
        if sb:
            print(f" back={sides[int(sb.group(1))]}", end="")
        print()

# sector containing sky cam roughly: floors around that area
print("\nsectors with SPACE* ceiling or floor (skybox candidates):")
for i, m in enumerate(re.finditer(r"(?ms)^sector\s*\{(.*?)\}", text)):
    b = m.group(1)
    tf = re.search(r'texturefloor\s*=\s*"([^"]+)"', b).group(1)
    tc = re.search(r'textureceiling\s*=\s*"([^"]+)"', b).group(1)
    if tf.startswith("SPACE") or tc.startswith("SPACE") or "CLOUD" in tf or "CLOUD" in tc:
        hf = re.search(r"heightfloor\s*=\s*([-\d.]+)", b).group(1)
        hc = re.search(r"heightceiling\s*=\s*([-\d.]+)", b).group(1)
        print(f"#{i} floor={tf} ceil={tc} z={hf}..{hc}")
