"""MAP01 RT fixes: try surgical edits around the 3D floor / sky control sector."""
import re
import struct
from pathlib import Path

# Repo root, derived from this file so a clone can live anywhere.
PROJ_ROOT = Path(__file__).resolve().parents[1]

SRC = PROJ_ROOT / r"tools\_map_cmp\MAP01_TEXTMAP.txt"
OUT = PROJ_ROOT / r"Doom64-Retribution"


def wad(items):
    body = b""
    directory = b""
    offset = 12
    for name, data in items:
        directory += struct.pack(
            "<II8s", offset, len(data), name.encode("ascii")[:8].ljust(8, b"\0")
        )
        body += data
        offset += len(data)
    return struct.pack("<4sII", b"PWAD", len(items), 12 + len(body)) + body + directory


def write_map(name: str, text: str):
    path = OUT / name
    path.write_bytes(
        wad([("MAP01", b""), ("TEXTMAP", text.encode("utf-8")), ("ENDMAP", b"")])
    )
    print("wrote", path, "len", len(text))


text = SRC.read_text(encoding="utf-8")

# A: keep 3D floor, replace control sector sky ceiling with normal flat
skyfix = text
# only sector id=18 ceiling sky
skyfix = re.sub(
    r"(sector\s*\{[^{}]*?textureceiling\s*=\s*)\"F_SKY1\"([^{}]*?id\s*=\s*18\s*;)",
    r'\1"FLAT1"\2',
    skyfix,
    count=1,
    flags=re.S,
)
# fallback if order differs (id before ceiling)
if skyfix == text:
    def fix_sec(m):
        b = m.group(1)
        if re.search(r"(?m)^\s*id\s*=\s*18\s*;", b):
            b = re.sub(r'textureceiling\s*=\s*"F_SKY1";', 'textureceiling = "FLAT1";', b)
        return "sector\n{" + b + "}"

    skyfix = re.sub(r"(?ms)^sector\s*\{(.*?)\}", fix_sec, text)

write_map("d64r-map01-sky3dfix.wad", skyfix)

# B: disable 3D floor special only (known good)
def no3d(m):
    b = m.group(1)
    if re.search(r"special\s*=\s*160\s*;", b):
        b = re.sub(r"(?m)^\s*special\s*=\s*\d+;\s*\n", "", b)
        b = re.sub(r"(?m)^\s*arg\d+\s*=\s*-?\d+;\s*\n", "", b)
    return "linedef\n{" + b + "}"


no3d_text = re.sub(r"(?ms)^linedef\s*\{(.*?)\}", no3d, text)
write_map("d64r-map01-rtfix.wad", no3d_text)
