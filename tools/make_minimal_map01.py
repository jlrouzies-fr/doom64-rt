"""Build a tiny UDMF MAP01 WAD for isolation testing."""
import struct
from pathlib import Path

TEXTMAP = r"""namespace = "zdoom";
thing
{
x = 0.000;
y = 0.000;
type = 1;
coop = true;
dm = true;
single = true;
skill1 = true;
skill2 = true;
skill3 = true;
skill4 = true;
skill5 = true;
}
vertex { x = -256.000; y = -256.000; }
vertex { x = 256.000; y = -256.000; }
vertex { x = 256.000; y = 256.000; }
vertex { x = -256.000; y = 256.000; }
linedef { v1 = 0; v2 = 1; sidefront = 0; blocking = true; }
linedef { v1 = 1; v2 = 2; sidefront = 1; blocking = true; }
linedef { v1 = 2; v2 = 3; sidefront = 2; blocking = true; }
linedef { v1 = 3; v2 = 0; sidefront = 3; blocking = true; }
sidedef { sector = 0; texturemiddle = "STARTAN2"; }
sidedef { sector = 0; texturemiddle = "STARTAN2"; }
sidedef { sector = 0; texturemiddle = "STARTAN2"; }
sidedef { sector = 0; texturemiddle = "STARTAN2"; }
sector
{
heightfloor = 0;
heightceiling = 128;
texturefloor = "FLOOR0_1";
textureceiling = "CEIL1_1";
lightlevel = 160;
}
"""

def wad(lumps):
    # lumps: list[(name:str, data:bytes)]
    body = b""
    directory = b""
    offset = 12
    for name, data in lumps:
        directory += struct.pack("<II8s", offset, len(data), name.encode("ascii")[:8].ljust(8, b"\0"))
        body += data
        offset += len(data)
    header = struct.pack("<4sII", b"PWAD", len(lumps), 12 + len(body))
    return header + body + directory

out = Path(r"G:\AI\Doom64-RT\tools\map01_minimal.wad")
data = wad([
    ("MAP01", b""),
    ("TEXTMAP", TEXTMAP.encode("utf-8")),
    ("ENDMAP", b""),
])
out.write_bytes(data)
print("wrote", out, "size", len(data))
