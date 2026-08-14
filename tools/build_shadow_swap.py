"""Swap a map's lamp-pane CEILING flats to a single-bulb texture, in an overlay wad.

    python tools/build_shadow_swap.py                 MAP01, SFLATAS+SFLATAQ -> SFLATCH
    python tools/build_shadow_swap.py --map MAP07
    python tools/build_shadow_swap.py --from SFLATAS --to SFLATDE

    -> Doom64-Retribution/d64r-shadow-swap.wad

WHY. The shadow lab (MAP93) measured that a grating shadow needs ONE COMPACT LIGHT
per fixture, and that "one light per painted bulb" can never deliver it because
Doom 64 paints its bulbs a metre or more apart -- further apart than the mesh
openings they are supposed to cast through, so the copies interleave and cancel.

SFLATCH is already the single-bulb flat in this game: SoloBulbTextures in
rt_lights_fixtures.cpp puts its bulb at (32.0, 32.0), dead centre of the 64-unit
tile. So swapping a lamp pane to it is the "repaint the texture as one bulb" idea
WITHOUT any repainting -- and it changes the LIGHT FAMILY too, from the bulb
lattice (rt_ceiling_bulb_*) to the solo path (rt_solo_lamp_*), which is the half
that actually matters.

NOTHING PERMANENT. This writes a separate PWAD that only tools/ab-texswap.cmd
loads, so the shipping game is untouched and the comparison is one flag.

TWO THINGS THAT MAKE THIS SAFE, both learned the hard way in this repo:

  * It reads the map from whichever loaded wad WINS, not from the IWAD. MAP01 is
    replaced by d64r-3dfloor-rtfix.wad and again by d64r-seqlight-fix.wad; building
    from D64RTR_v15.WAD would silently revert both of those fixes the moment this
    overlay loaded last.
  * CEILINGS ONLY. SFLATAS is used as a floor as well, and a floor is not a lamp
    pane -- swapping it would move light to places the art never had it.
"""

import argparse
import re
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODS = ROOT / "Doom64-Retribution"
OUT = MODS / "d64r-shadow-swap.wad"

# The -file order tools/launch-retribution-rt.cmd and tools/shot.ps1 use. Later
# entries win, so the map is taken from the LAST one that carries it.
LOAD_ORDER = [
    "D64RTR_v15.WAD", "d64r-3dfloor-rtfix.wad", "d64r-seqlight-fix.wad",
    "d64r-bulb-textures.wad", "d64r-ctel-fix.wad",
]


def read_wad(path: Path):
    d = path.read_bytes()
    if d[:4] not in (b"PWAD", b"IWAD"):
        return None, []
    n, off = struct.unpack("<II", d[4:12])
    lumps = []
    for i in range(n):
        o, sz, nm = struct.unpack("<II8s", d[off + i * 16 : off + i * 16 + 16])
        lumps.append((nm.rstrip(b"\0").decode("latin1"), o, sz))
    return d, lumps


def write_wad(items):
    body, directory, offset = b"", b"", 12
    for name, data in items:
        directory += struct.pack(
            "<II8s", offset, len(data), name.encode("ascii")[:8].ljust(8, b"\0")
        )
        body += data
        offset += len(data)
    return struct.pack("<4sII", b"PWAD", len(items), 12 + len(body)) + body + directory


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--map", default="MAP01")
    ap.add_argument("--from", dest="src", default="SFLATAS,SFLATAQ",
                    help="comma-separated ceiling flats to replace")
    ap.add_argument("--to", default="SFLATCH",
                    help="single-bulb flat to use (SFLATCH or SFLATDE -- these are "
                         "the only two the solo light path knows)")
    args = ap.parse_args()
    srcs = [s.strip().upper() for s in args.src.split(",") if s.strip()]

    # Whichever loaded wad carries this map LAST is the one in play.
    src_wad, blob, lumps = None, None, None
    for name in LOAD_ORDER:
        f = MODS / name
        if not f.exists():
            continue
        d, L = read_wad(f)
        if d and args.map in [x[0] for x in L]:
            src_wad, blob, lumps = f, d, L
    if not src_wad:
        raise SystemExit(f"{args.map} not found in any loaded wad")

    names = [x[0] for x in lumps]
    i = names.index(args.map)
    # A UDMF map is its marker through ENDMAP; copy every lump so nothing an
    # earlier fix wad added (BEHAVIOR, ZNODES) is dropped on the floor.
    end = i
    while end < len(names) and names[end] != "ENDMAP":
        end += 1
    block = lumps[i : end + 1]

    out, changed = [], 0
    for nm, o, sz in block:
        data = blob[o : o + sz]
        if nm == "TEXTMAP":
            txt = data.decode("latin1")
            for s in srcs:
                # CEILINGS ONLY -- textureceiling, never texturefloor.
                txt, k = re.subn(
                    r'(textureceiling\s*=\s*)"' + re.escape(s) + r'"',
                    r'\1"' + args.to + '"', txt)
                changed += k
                print(f"  {s:8} -> {args.to}: {k} ceiling(s)")
            data = txt.encode("latin1")
        out.append((nm, data))

    if not changed:
        raise SystemExit("nothing to swap -- check --from against the map")

    OUT.write_bytes(write_wad(out))
    print(f"\nwrote {OUT}  ({OUT.stat().st_size} bytes)")
    print(f"  {args.map} taken from {src_wad.name} (last loaded wad that has it)")
    print(f"  {changed} ceiling(s) swapped; floors untouched")
    print(f"  load it LAST, and expect rt_ceiling_edge_debug to report the panes")
    print(f"  under \"solo N flat(s)\" instead of \"bulb lattice(s)\".")


if __name__ == "__main__":
    main()
