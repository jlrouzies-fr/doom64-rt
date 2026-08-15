import struct, re
from pathlib import Path

# Repo root, derived from this file so a clone can live anywhere.
PROJ_ROOT = Path(__file__).resolve().parents[1]

p = PROJ_ROOT / r"Doom64-Retribution\D64RTR_v15.WAD"
d = p.read_bytes()
n, o = struct.unpack_from("<II", d, 4)
lumps = []
for i in range(n):
    off, sz, name = struct.unpack_from("<II8s", d, o + i * 16)
    name = name.split(b"\0")[0].decode("ascii", "replace")
    lumps.append((name, off, sz))


def get_map_lump(mapname, lumpname):
    idx = next(i for i, l in enumerate(lumps) if l[0].upper() == mapname)
    for j in range(idx, min(idx + 40, len(lumps))):
        nm, off, sz = lumps[j]
        if j > idx and nm.upper().startswith("MAP") and len(nm) == 5 and nm[3:].isdigit():
            break
        if nm.upper() == lumpname:
            return d[off : off + sz]
    return None


out = PROJ_ROOT / r"tools\_map_cmp"
out.mkdir(exist_ok=True)

for m in ["MAP01", "MAP02"]:
    for ln in ["SCRIPTS", "TEXTMAP"]:
        data = get_map_lump(m, ln)
        (out / f"{m}_{ln}.txt").write_bytes(data)
        print(m, ln, len(data))

for m in ["MAP01", "MAP02"]:
    t = (out / f"{m}_TEXTMAP.txt").read_text("latin1", "replace")
    print(f"\n=== {m} TEXTMAP feature counts ===")
    for pat, label in [
        (r"^thing\b", "things"),
        (r"^sector\b", "sectors"),
        (r"^linedef\b", "linedefs"),
        (r"^sidedef\b", "sidedefs"),
        (r"^vertex\b", "vertices"),
        (r"portal", "portal"),
        (r"polyobject|polyobj", "polyobj"),
        (r"3dmidtex|3dfloor|Sector_Set3dFloor", "3d"),
        (r"mirror|Line_Mirror|Line_Horizon", "mirror/horizon"),
        (r"Transfer_Heights|transferheights", "transferheights"),
        (r"skybox|Skybox", "skybox"),
        (r"script\s*=", "script="),
        (r"special\s*=\s*80", "special80"),
        (r"lightlevel\s*=\s*0", "light0"),
        (r"fade\s*=", "fade"),
        (r"colormap\s*=", "colormap"),
        (r"alpha\s*=", "alpha"),
        (r"renderstyle\s*=", "renderstyle"),
        (r"softwareslope|slope", "slope"),
    ]:
        c = len(re.findall(pat, t, re.I | re.M))
        print(f"  {label:18} {c}")

for m in ["MAP01", "MAP02"]:
    s = (out / f"{m}_SCRIPTS.txt").read_text("latin1", "replace")
    print(f"\n=== {m} SCRIPTS ===")
    headers = re.findall(r"^(script\s+[^\n{]+)", s, re.I | re.M)
    print("  headers:")
    for h in headers:
        print("   ", h.strip())
    for kw in [
        "ENTER",
        "OPEN",
        "RESPAWN",
        "FadeTo",
        "SetHudSize",
        "Delay",
        "Polyobj",
        "ChangeCamera",
        "SetPlayerProperty",
        "Thing_Spawn",
        "Sector_SetColor",
        "Light_Fade",
        "terminat",
        "while(",
        "for(",
    ]:
        print(f"  {kw:22} {s.lower().count(kw.lower())}")
    # first 80 lines
    print("--- head ---")
    print("\n".join(s.splitlines()[:80]))
