"""
Extract the Doom 64 main-menu patches out of D64RTR_v15.WAD into rt-wad-overlay/.

Why this exists
---------------
gzdoom-rt mounts its own `rt/wad` directory AFTER every `-file` PWAD
(`GetCmdLineFiles`, d_main.cpp:1963), and it ships plain-Doom-font
`graphics/M_LOADG.png`, `M_SAVEG.png` and `M_QUITG.png`. Those beat
Retribution's D64 patches, which is why LOAD / SAVE / QUIT were the only main
menu entries not in the Doom 64 font (RT ships no M_NGAME / M_OPTION, so those
two stayed D64).

The fix is precedence, not art: copy the mod's own patches into the tracked
`rt-wad-overlay/graphics/`, which `tools/sync-rt-wad.py` mirrors into the real
`rt/wad` trees, replacing RT's versions in place.

The lumps are already PNG, so they are copied BYTE FOR BYTE. Do not round-trip
them through PIL - it drops the `grAb` chunk that carries the patch offset.

Usage:
    py -3 tools/extract_d64_menu_gfx.py
    py -3 tools/extract_d64_menu_gfx.py --check    # report drift, write nothing
"""

import argparse
import os
import struct

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WAD = os.path.join(ROOT, "Doom64-Retribution", "D64RTR_v15.WAD")
OUTDIR = os.path.join(ROOT, "rt-wad-overlay", "graphics")

LUMPS = ["M_LOADG", "M_SAVEG", "M_QUITG"]

PNG_SIG = b"\x89PNG\r\n\x1a\n"


def read_wad_lumps(path, wanted):
    """Return {name: bytes} for the LAST occurrence of each wanted lump name."""
    with open(path, "rb") as f:
        data = f.read()

    magic, numlumps, infotableofs = struct.unpack_from("<4sii", data, 0)
    if magic not in (b"IWAD", b"PWAD"):
        raise SystemExit(f"{path}: not a wad (magic {magic!r})")

    found = {}
    for i in range(numlumps):
        filepos, size, raw = struct.unpack_from("<ii8s", data, infotableofs + i * 16)
        name = raw.split(b"\0")[0].decode("ascii", "replace").upper()
        if name in wanted:
            found[name] = data[filepos:filepos + size]
    return found


def png_size(blob):
    # IHDR width/height live at bytes 16..24 of a PNG.
    w, h = struct.unpack_from(">II", blob, 16)
    return w, h


def has_grab(blob):
    return b"grAb" in blob[:512]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="report drift without writing")
    args = ap.parse_args()

    if not os.path.isfile(WAD):
        raise SystemExit(f"missing wad: {WAD}")

    found = read_wad_lumps(WAD, set(LUMPS))
    missing = [n for n in LUMPS if n not in found]
    if missing:
        raise SystemExit(f"{WAD}: lump(s) not found: {', '.join(missing)}")

    if not args.check:
        os.makedirs(OUTDIR, exist_ok=True)

    drift = 0
    for name in LUMPS:
        blob = found[name]
        if not blob.startswith(PNG_SIG):
            raise SystemExit(f"{name}: not a PNG lump (starts {blob[:8]!r})")
        w, h = png_size(blob)
        dst = os.path.join(OUTDIR, name + ".png")

        same = os.path.exists(dst) and open(dst, "rb").read() == blob
        note = "grAb" if has_grab(blob) else "no grAb"
        if same:
            print(f"  ok    {name}.png  {w}x{h}  {len(blob)} bytes  ({note})")
            continue

        drift += 1
        if args.check:
            print(f"  DRIFT {name}.png  {w}x{h}  {len(blob)} bytes  ({note})")
        else:
            with open(dst, "wb") as f:
                f.write(blob)
            print(f"  WROTE {name}.png  {w}x{h}  {len(blob)} bytes  ({note})  -> {dst}")

    if args.check:
        print(f"\n{drift} file(s) differ from the wad")
        raise SystemExit(1 if drift else 0)

    print(f"\nextracted {len(LUMPS)} lump(s) into {OUTDIR}")
    print("now run:  py -3 tools/sync-rt-wad.py")


if __name__ == "__main__":
    main()
