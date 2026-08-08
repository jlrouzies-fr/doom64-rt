"""
Light the bulb sockets in SFLATC and SPACECE, so the faux panel lights have
something in the art to come from.

The problem this solves. rt_faux_lamps puts analytic lights on these two
textures, but the textures show UNLIT sockets: a regular lattice of small dark
recesses in a rusty plate. A light with no visible source in the surface it
comes from reads as exactly what it is -- an invention. Painting the sockets as
lit bulbs gives the light a fixture.

The lattices are DETECTED from the art, not assumed, and assuming cost a pass:
both are 64x64 and the socket centres come out as

  SFLATC   4x4, x and y both at 7.5, 23.5, 39.5, 55.5   (period 16)
  SPACECE  3x3, x at 10.1, 31.1, 52.1 but y at 9.0, 30.0, 51.0

SPACECE's axes do not share an offset. Painting it from one guessed lattice put
every bulb low in its housing with a dark crescent above it, which is why the
centres are now found by flood-filling the dark blobs and taking their centroids,
with the count asserted against the grid we expect.

Both sockets are small and steep: the radial luminance profile drops to 37 at
the centre and 42 one pixel out, and is back to the plate's 59 by two pixels
out. SPACECE additionally has a bright rim at r=2 (66), the lip of the housing.
So only r<=1 is recoloured and the rim is left alone -- widening the disc would
paint over the socket lip and the bulb would lose its housing.

Two outputs, because a brighter albedo alone does not glow under a path tracer:

  d64r-bulb-textures.wad   replacement SFLATC/SPACECE lumps, sockets repainted
                           as lit bulbs. Wrapped in TX_START/TX_END because
                           that is the namespace they live in in D64RTR_v15.WAD.
  <name>_e.png             emissive masks in rt/mat, the same mechanism the 291
                           existing _e maps use, so the painted bulbs actually
                           emit instead of merely looking pale.

Written to BOTH rt/mat locations: the build's copy is what runs, and
Retribution-RT-Materials is the source that survives a rebuild (build-gzdoom-rt.cmd
only stages rt/ when the folder is missing, so the live copy is not regenerated).

Needs Pillow, which on this machine is only in Python 3.13:

    C:\\Users\\Winter\\AppData\\Local\\Programs\\Python\\Python313\\python.exe \\
        tools/make_bulb_textures.py

    ... --preview   also write 8x previews next to the wad for eyeballing
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from make_map_3dfloor_rtfix import OUT, WAD, read_wad_lumps, write_wad

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    raise SystemExit(
        "Pillow not found. Run this with Python 3.13:\n"
        r"  C:\Users\Winter\AppData\Local\Programs\Python\Python313\python.exe "
        "tools/make_bulb_textures.py"
    )

ROOT = Path(__file__).resolve().parent.parent
OUTWAD = OUT / "d64r-bulb-textures.wad"
MAT_DIRS = [
    ROOT / "Doom64-Retribution/Retribution-RT-Materials/rt/mat",
    ROOT / "sourcecode/gzdoom-rt/build/RelWithDebInfo/rt/mat",
]

# Bulb colour. Cool white core falling to the same blue-grey the analytic lights
# use (rt_faux_lamp_color 6E7F94), so the painted fixture and the light it casts
# are obviously the same object rather than two different colours of lie.
CORE = (232, 240, 250)
EDGE = (143, 166, 190)

# radius, in pixels, of the repainted disc. See the module docstring: the socket
# is back to plate luminance by r=2, so 1.5 covers the dark core and stops at the lip.
BULB_R = 1.5

# Expected socket count per axis, used only as an assertion on what detection finds.
PANELS = {"SFLATC": 4, "SPACECE": 3}


def centres(img: Image.Image, name: str) -> list[tuple[float, float]]:
    """Find the socket centres in the art instead of assuming a perfect lattice.

    Assuming one was wrong for SPACECE: its columns sit at 10.5/31.5/52.5 but its
    rows at 9/30/51, so a single shared offset painted every bulb low in its
    housing and left a dark crescent above. The sockets are the only strongly
    dark blobs in either plate, so a threshold plus a flood fill finds them
    exactly, and the count is asserted against the grid we expect to see.
    """
    w, h = img.size
    px = img.convert("RGB").load()
    lum = lambda p: p[0] * 0.299 + p[1] * 0.587 + p[2] * 0.114
    vals = [lum(px[x, y]) for y in range(h) for x in range(w)]
    mean = sum(vals) / len(vals)
    # The radial profile bottoms out around 37 against a plate mean of 59, so a
    # threshold midway between the two separates socket from plate cleanly.
    thr = mean - 11.0

    seen = [[False] * w for _ in range(h)]
    found: list[tuple[float, float]] = []
    for sy in range(h):
        for sx in range(w):
            if seen[sy][sx] or lum(px[sx, sy]) >= thr:
                continue
            # Flood fill with wraparound: the lattice tiles, so a socket may be cut
            # by the edge and its two halves must count as one blob.
            stack, blob = [(sx, sy)], []
            seen[sy][sx] = True
            while stack:
                x, y = stack.pop()
                blob.append((x, y))
                for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                    nx %= w
                    ny %= h
                    if not seen[ny][nx] and lum(px[nx, ny]) < thr:
                        seen[ny][nx] = True
                        stack.append((nx, ny))
            if len(blob) < 3:
                continue  # dirt speck in the rust, not a socket
            # Centroid in wrapped space: anchor on the first pixel and take the
            # shortest offset to each other, so a blob straddling the seam averages
            # to the right place instead of to the middle of the texture.
            ax, ay = blob[0]
            ox = sum(((x - ax + w // 2) % w) - w // 2 for x, _ in blob) / len(blob)
            oy = sum(((y - ay + h // 2) % h) - h // 2 for _, y in blob) / len(blob)
            found.append(((ax + ox) % w, (ay + oy) % h))

    n = PANELS[name]
    if len(found) != n * n:
        raise SystemExit(
            f"{name}: detected {len(found)} sockets, expected {n * n}. "
            f"Threshold or art changed — inspect before trusting this."
        )
    found.sort(key=lambda c: (round(c[1]), round(c[0])))
    return found


def paint(img: Image.Image, name: str, spots: list, emissive: bool) -> Image.Image:
    w, h = img.size
    out = img.convert("RGB").copy()
    if emissive:
        out = Image.new("RGB", (w, h), (0, 0, 0))
    px = out.load()

    for cx, cy in spots:
        rad = int(BULB_R) + 1
        for dy in range(-rad, rad + 1):
            for dx in range(-rad, rad + 1):
                d = (dx * dx + dy * dy) ** 0.5
                if d > BULB_R:
                    continue
                x = int(round(cx + dx)) % w
                y = int(round(cy + dy)) % h
                # Radial falloff so the bulb has a hot centre instead of reading as
                # a flat sticker. t=0 at the centre, 1 at the edge of the disc.
                t = d / BULB_R if BULB_R > 0 else 0.0
                col = tuple(
                    int(round(CORE[k] + (EDGE[k] - CORE[k]) * t)) for k in range(3)
                )
                px[x, y] = col
    return out


def png_bytes(img: Image.Image) -> bytes:
    import io

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def main() -> None:
    preview = "--preview" in sys.argv
    lumps = read_wad_lumps(WAD)
    by_name = {nm.upper(): blob for nm, blob in lumps}

    items: list[tuple[str, bytes]] = [("TX_START", b"")]
    for name in PANELS:
        blob = by_name.get(name)
        if blob is None:
            raise SystemExit(f"{name} not found in {WAD}")
        if blob[:8] != b"\x89PNG\r\n\x1a\n":
            raise SystemExit(f"{name} is not a PNG lump — unexpected, aborting")

        import io

        src = Image.open(io.BytesIO(blob))
        if src.size != (64, 64):
            raise SystemExit(f"{name} is {src.size}, expected 64x64 — lattice would be wrong")

        spots = centres(src, name)
        lit = paint(src, name, spots, emissive=False)
        items.append((name, png_bytes(lit)))

        emis = paint(src, name, spots, emissive=True)
        for d in MAT_DIRS:
            if not d.is_dir():
                print(f"  skip (missing) {d}")
                continue
            p = d / f"{name}_e.png"
            p.write_bytes(png_bytes(emis))
            print(f"  wrote {p}")

        if preview:
            for tag, im in (("lit", lit), ("emis", emis), ("src", src.convert("RGB"))):
                q = OUT / f"_preview_{name}_{tag}.png"
                im.resize((512, 512), Image.NEAREST).save(q)
                print(f"  preview {q}")

        n = PANELS[name]
        xs = sorted({round(c[0], 1) for c in spots})
        ys = sorted({round(c[1], 1) for c in spots})
        print(f"{name}: {n}x{n} bulbs detected, radius {BULB_R}")
        print(f"    x centres {xs}")
        print(f"    y centres {ys}")

    items.append(("TX_END", b""))
    write_wad(OUTWAD, items)
    print(f"\nwrote {OUTWAD} lumps={[nm for nm, _ in items]}")


if __name__ == "__main__":
    main()
