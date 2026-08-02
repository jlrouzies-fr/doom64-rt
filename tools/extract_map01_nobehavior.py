"""Extract Retribution MAP01 as a PWAD without BEHAVIOR/ACS."""
import struct
from pathlib import Path

src = Path(r"G:\AI\Doom64-RT\Doom64-Retribution\D64RTR_v15.WAD")
d = src.read_bytes()
n, o = struct.unpack_from("<II", d, 4)
lumps = []
for i in range(n):
    off, sz, name = struct.unpack_from("<II8s", d, o + i * 16)
    name = name.split(b"\0")[0].decode("ascii", "replace")
    lumps.append((name, off, sz))

# Find MAP01..next map marker
start = None
end = None
for i, (name, off, sz) in enumerate(lumps):
    if name == "MAP01":
        start = i
        continue
    if start is not None and (name.startswith("MAP") or name == "BEHAVIOR"):
        # continue collecting until next MAPxx (not BEHAVIOR)
        pass
    if start is not None and i > start and name.startswith("MAP") and name != "MAP01":
        end = i
        break
if start is None:
    raise SystemExit("MAP01 not found")
if end is None:
    end = len(lumps)

wanted = []
skip = {"BEHAVIOR", "SCRIPTS", "DIALOGUE", "ZNODES", "SSECTORS", "SEGS", "NODES", "BLOCKMAP", "REJECT"}
for name, off, sz in lumps[start:end]:
    if name in skip:
        print("skip", name, sz)
        continue
    wanted.append((name, d[off : off + sz]))
    print("keep", name, sz)

def wad(items):
    body = b""
    directory = b""
    offset = 12
    for name, data in items:
        directory += struct.pack("<II8s", offset, len(data), name.encode("ascii")[:8].ljust(8, b"\0"))
        body += data
        offset += len(data)
    header = struct.pack("<4sII", b"PWAD", len(items), 12 + len(body))
    return header + body + directory

out = Path(r"G:\AI\Doom64-RT\tools\map01_nobehavior.wad")
out.write_bytes(wad(wanted))
print("wrote", out, "lumps", len(wanted))
