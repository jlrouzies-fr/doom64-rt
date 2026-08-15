"""Flatten the CTEL panel's CENTRE element, keeping its rotating ring.

CTEL1..CTEL8 (ANIMDEFS, 4 tics each) is a telemetry panel whose red elements
animate. Measured per gem cluster, that animation is TWO different things
overlaid, and only one of them is a defect:

  ROTATION -- eight 4-pixel clusters around the rim, at (6,22) (6,40) (22,6)
  (22,56) (42,6) (42,56) (56,22) (56,40). Every one carries the SAME luminance
  set, 359/172/150/77/71/28/20/14, cyclically shifted by one frame, so the bright
  spot walks around the panel. Their combined output is 891 in every single
  frame -- dead constant. This is a chase light turning around, it is motion
  rather than lighting, and it is the thing worth keeping.

  FADE -- one 13-pixel blob dead centre at (31,31), running 44 at its darkest to
  1166 at its brightest, a 26x swing with no rotation in it whatsoever. This one
  cluster IS the whole brightness envelope of the texture (2.20x peak/trough
  across the tile; take it out and the remainder is flat). It is a light fading
  in and out, painted into the artwork, and under a path tracer in a dark room it
  reads as exactly what it is: a surface lighting itself with nothing casting it.

So the repair is not to freeze the animation -- that was tried and it threw away
the rotation to fix the fade (2026-08-10). It is to hold the CENTRE blob at its
darkest frame across all eight, and leave every other pixel of every frame alone.
The ring keeps turning, the panel stops pulsing, and the alcove's real
PointLightPulse supplies the brightness.

The centre is pinned to its DIM state, not a mid or bright one, for the same
reason albedo should always describe unlit material: any residual painted glow is
light the renderer did not cast.

Output is a TX_ wad, the same mechanism and namespace tools/make_bulb_textures.py
uses to replace SFLATC/SPACECE.

Needs Pillow, which on this machine is only in Python 3.13:

    C:\\Users\\Winter\\AppData\\Local\\Programs\\Python\\Python313\\python.exe \\
        tools/make_ctel_static_center.py
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))

from make_map_3dfloor_rtfix import OUT, WAD, read_wad_lumps, write_wad

OUTWAD = OUT / "d64r-ctel-fix.wad"
FRAMES = [f"CTEL{i}" for i in range(1, 9)]

# A pixel belongs to a red element if red dominates this much. Low enough that the
# same pixels are selected in every frame regardless of how lit they currently are.
RED_DOMINANCE = 15

# The centre blob is identified by geometry, not by a hardcoded pixel list: it is
# the cluster containing the tile's centre.
CENTRE = (31, 31)


def clusters(px, size, thresh: int) -> list[list[tuple[int, int]]]:
    w, h = size
    sel = {
        (x, y)
        for y in range(h)
        for x in range(w)
        if px[x, y][0] - max(px[x, y][1], px[x, y][2]) > thresh
    }
    out = []
    while sel:
        seed = sel.pop()
        comp, stack = {seed}, [seed]
        while stack:
            x, y = stack.pop()
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    q = (x + dx, y + dy)
                    if q in sel:
                        sel.discard(q)
                        comp.add(q)
                        stack.append(q)
        out.append(sorted(comp))
    return out


def luma(px, pts) -> float:
    return sum(
        0.2126 * px[x, y][0] + 0.7152 * px[x, y][1] + 0.0722 * px[x, y][2]
        for x, y in pts
    )


def main() -> None:
    by_name: dict[str, bytes] = {}
    for name, blob in read_wad_lumps(WAD):
        u = name.upper()
        if u in FRAMES and u not in by_name:
            by_name[u] = blob

    missing = [f for f in FRAMES if f not in by_name]
    if missing:
        raise SystemExit(f"missing frames in {WAD}: {missing}")

    imgs = {f: Image.open(io.BytesIO(by_name[f])).convert("RGB") for f in FRAMES}
    ref = imgs[FRAMES[0]]

    groups = clusters(ref.load(), ref.size, RED_DOMINANCE)
    centre = [g for g in groups if CENTRE in g]
    if len(centre) != 1:
        raise SystemExit(
            f"expected exactly one red cluster containing {CENTRE}, found "
            f"{len(centre)} — art changed, refusing to patch blind"
        )
    centre_px = centre[0]
    ring = [g for g in groups if g is not centre[0]]
    print(f"centre cluster: {len(centre_px)} px at {CENTRE}")
    print(f"ring clusters : {len(ring)} x {sorted({len(g) for g in ring})} px")

    # The frame whose centre is darkest is the state every frame will be pinned to.
    darkest = min(FRAMES, key=lambda f: luma(imgs[f].load(), centre_px))
    src = imgs[darkest].load()
    print(f"pinning centre to {darkest} (its darkest state)\n")

    print(f"{'frame':7}{'centre before':>15}{'centre after':>14}{'ring (kept)':>13}")
    items: list[tuple[str, bytes]] = [("TX_START", b"")]
    for f in FRAMES:
        im = imgs[f].copy()
        p = im.load()
        before = luma(imgs[f].load(), centre_px)
        for x, y in centre_px:
            p[x, y] = src[x, y]
        after = luma(p, centre_px)
        ringl = sum(luma(p, g) for g in ring)
        print(f"{f:7}{before:15.0f}{after:14.0f}{ringl:13.0f}")

        buf = io.BytesIO()
        im.save(buf, format="PNG")
        items.append((f, buf.getvalue()))
    items.append(("TX_END", b""))

    write_wad(OUTWAD, items)
    print(f"\nwrote {OUTWAD} lumps={[nm for nm, _ in items]}")
    print("Add it to the launcher's -file list AFTER D64RTR_v15.WAD.")


if __name__ == "__main__":
    main()
