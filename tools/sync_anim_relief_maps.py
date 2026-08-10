"""Give every frame of an animated texture the same _h / _n / _orm maps.

RTGL1 resolves auxiliary maps per texture NAME, and an ANIMDEFS animation is a
run of separate names (CTEL1..CTEL8, SMONAA..SMONAD, HLAVA1..HLAVA5). So if only
the first frame ships an `_h.png`, the surface is parallax-displaced on that
frame and flat on all the others, and the animation cycles the relief in and out
several times a second.

That does not look like a missing map. It looks like the TEXTURE MOVING UP AND
DOWN, which is how it was reported on MAP13's CTEL panel (2026-08-10) -- and it
sends you looking at scrollers, lifts and sector specials, none of which are
involved.

Sharing frame 1's maps is only correct when the frames are the same surface with
something small changing on it. That is checked, not assumed: a frame is only
given frame 1's maps if it is pixel-identical to frame 1 outside a small
fraction of the tile. CTEL is 45 differing pixels of 4096 (1.1%) -- the gems --
with the stone byte-identical. A genuinely different frame fails the check and
is reported, because it needs its own maps rather than a copy.

  python tools/sync_anim_relief_maps.py             # report + fix CTEL
  python tools/sync_anim_relief_maps.py --dry-run   # report only
  python tools/sync_anim_relief_maps.py SMONA       # some other base
"""

from __future__ import annotations

import io
import shutil
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))

from make_map_3dfloor_rtfix import WAD, read_wad_lumps

ROOT = Path(r"G:\AI\Doom64-RT")
MAT = ROOT / r"sourcecode\gzdoom-rt\build\RelWithDebInfo\rt\mat"
MAT_DEV = ROOT / r"sourcecode\gzdoom-rt\build\RelWithDebInfo\rt\mat_dev"
OMAT = ROOT / r"Doom64-Retribution\Retribution-RT-Materials\rt\mat"
DIRS = (MAT, MAT_DEV, OMAT)

SUFFIXES = ("_h", "_n", "_orm")

# Above this share of differing pixels the frames are not "the same surface with
# a detail changing" and must not share relief maps.
MAX_DIFF_FRAC = 0.05


def frames_for(base: str) -> list[str]:
    lumps = read_wad_lumps(WAD)
    seen: dict[str, bytes] = {}
    for name, blob in lumps:
        u = name.upper()
        if u.startswith(base) and u[len(base):].isdigit() and u not in seen:
            seen[u] = blob
    return sorted(seen, key=lambda n: int(n[len(base):]))


def diff_frac(a: Image.Image, b: Image.Image) -> float:
    if a.size != b.size:
        return 1.0
    ap, bp = a.load(), b.load()
    w, h = a.size
    n = sum(1 for y in range(h) for x in range(w) if ap[x, y] != bp[x, y])
    return n / float(w * h)


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    dry = "--dry-run" in sys.argv
    bases = args or ["CTEL"]

    for base in bases:
        lumps = {n.upper(): b for n, b in read_wad_lumps(WAD)}
        names = frames_for(base)
        if len(names) < 2:
            print(f"{base}: not an animation ({len(names)} frame(s)) — skipped")
            continue

        first, rest = names[0], names[1:]
        img0 = Image.open(io.BytesIO(lumps[first])).convert("RGB")
        print(f"{base}: {len(names)} frames, reference {first}")

        for suf in SUFFIXES:
            src = OMAT / f"{first}{suf}.png"
            if not src.exists():
                print(f"  {suf}: {first} has none — nothing to share")
                continue
            for nm in rest:
                frac = diff_frac(img0, Image.open(io.BytesIO(lumps[nm])).convert("RGB"))
                if frac > MAX_DIFF_FRAC:
                    print(f"  {suf}: {nm} differs from {first} on {frac:.1%} of the "
                          f"tile — needs its OWN map, not a copy")
                    continue
                for d in DIRS:
                    dst = d / f"{nm}{suf}.png"
                    if dst.exists():
                        continue
                    if dry:
                        print(f"  would write {dst}")
                    else:
                        dst.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copyfile(src, dst)
            if not dry:
                print(f"  {suf}: shared with {len(rest)} frame(s)")


if __name__ == "__main__":
    main()
