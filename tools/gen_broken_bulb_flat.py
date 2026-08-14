"""Install the BROKEN-BULB SFLATAS: three dead bulbs, one working, one light.

    python tools/gen_broken_bulb_flat.py

    reads   screen/SFLATAS_broken.png          the hand-painted albedo
    writes  Doom64-Retribution/d64r-sflatas-broken.wad   (TX_ override)
            <4 material dirs>/SFLATAS_e.png    ONLY the working bulb glows
            <4 material dirs>/SFLATAS_{n,h,orm}.png  restored to AUTHORED

WHY THIS APPROACH, AND WHY THE LAST ONE IS GONE.

The problem is the MAP01 cage: a chain-link grating under a lamp pane casts no
readable shadow. Measured in the shadow lab (MAP93, the fixture alone in a dark
room), the cause is not occlusion and not the renderer -- it is that SFLATAS
paints FOUR bulbs 32 map units apart while the grating's openings are about 16,
so each bulb lays down an offset copy of the mesh shadow that fills in the
previous one's gaps and the pattern cancels. One compact light casts crisply;
four cast a trace; sixteen cast nothing at any source radius.

The previous attempt rebuilt the art as a single bulb in the centre of the tile.
That works optically and was a mess in practice, because moving painted geometry
means moving it in the albedo AND in _n/_h/_orm AND keeping the light on top of
it AND panning every pane so a wall does not slice the one remaining bulb.

THIS approach gets the same optics for none of that cost: the bulbs all stay
exactly where they were painted, and three of them are simply BROKEN -- dark,
shattered glass. Nothing moves. So:

  * _n / _h / _orm are the AUTHORED maps, untouched. All four housings still
    physically exist, so the relief is still correct for all four. This is the
    entire class of bug that produced "the new texture is drawn on top of the
    old one" -- it cannot happen here, and this script actively RESTORES those
    three maps in case an earlier run rearranged them.
  * No flat panning. The art keeps its original tiling and alignment, so no
    sector needs an offset and no light has to chase one.
  * One light, at the working bulb, via SoloBulbTextures in
    rt_lights_fixtures.cpp -- the only engine change this needs.

MATERIALS EXIST IN FOUR PLACES, and the game reads the one that is easiest to
forget. rt/RTGL1.json sets developerMode:true, which makes RTGL1 prefer
rt/mat_dev over rt/mat; and tools/build-gzdoom-rt.cmd:124 xcopies the tracked
Retribution-RT-Materials\rt tree over the build tree on EVERY build. So writing
three of the four dirs holds only until the next build, and the symptom is old
art ghosting through new art with no obvious cause. Write all four. Always.
"""

import struct
import sys
from pathlib import Path

try:
    from PIL import Image
except ModuleNotFoundError:
    sys.exit("needs Pillow -- run with py -3.13, not the bare `python` on PATH")

ROOT = Path(__file__).resolve().parent.parent
MODS = ROOT / "Doom64-Retribution"

TEX = "SFLATAS"
TILE = 64
SRC_ART = ROOT / "screen" / "SFLATAS_broken.png"
OUT_WAD = MODS / "d64r-sflatas-broken.wad"

# The authored four-blob emissive mask, kept beside this script precisely because
# this script WRITES the mask it would otherwise read. A generator whose input is
# its own output is not idempotent; it is a ratchet, and the previous tool walked
# its bulb across the tile on the second run before this snapshot existed.
SRC_MASK = ROOT / "tools" / "_sflatas_e_authored.png"
# Authored _n/_h/_orm, snapshotted for the same reason.
SRC_SIDE = ROOT / "tools" / "_sflatas_authored"
SIDE_MAPS = ("_n", "_h", "_orm")

# All four, and see the module docstring for why leaving one out is invisible
# until the next build.
MAT_DIRS = [
    ROOT / "sourcecode/gzdoom-rt/build/RelWithDebInfo/rt/mat",
    ROOT / "sourcecode/gzdoom-rt/build/RelWithDebInfo/rt/mat_dev",
    MODS / "Retribution-RT-Materials/rt/mat",
    MODS / "Retribution-RT-Materials/rt/mat_dev",
]


def write_wad(items):
    body, directory, offset = b"", b"", 12
    for name, data in items:
        directory += struct.pack(
            "<II8s", offset, len(data), name.encode("ascii")[:8].ljust(8, b"\0")
        )
        body += data
        offset += len(data)
    return struct.pack("<4sII", b"PWAD", len(items), 12 + len(body)) + body + directory


def png_bytes(im: Image.Image) -> bytes:
    import io

    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


def blobs(im: Image.Image, thr: int):
    """Connected components above `thr`, as (cx, cy, area) in IMAGE coords."""
    w, h = im.size
    px = im.load()
    seen = [[False] * w for _ in range(h)]
    out = []
    for y in range(h):
        for x in range(w):
            if px[x, y] < thr or seen[y][x]:
                continue
            stack, pts = [(x, y)], []
            seen[y][x] = True
            while stack:
                cx, cy = stack.pop()
                pts.append((cx, cy))
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nx, ny = cx + dx, cy + dy
                    if 0 <= nx < w and 0 <= ny < h and not seen[ny][nx] and px[nx, ny] >= thr:
                        seen[ny][nx] = True
                        stack.append((nx, ny))
            if len(pts) >= 4:
                out.append(
                    (
                        sum(p[0] for p in pts) / len(pts) + 0.5,
                        sum(p[1] for p in pts) / len(pts) + 0.5,
                        len(pts),
                    )
                )
    return sorted(out, key=lambda c: (c[1], c[0]))


def main() -> None:
    if not SRC_ART.exists():
        sys.exit(f"{SRC_ART} missing -- that is the hand-painted albedo")
    if not SRC_MASK.exists():
        sys.exit(f"{SRC_MASK} missing -- the authored 4-blob emissive snapshot")

    art = Image.open(SRC_ART).convert("RGBA")
    if art.size != (TILE, TILE):
        sys.exit(f"{SRC_ART} is {art.size}, expected ({TILE}, {TILE})")

    mask = Image.open(SRC_MASK).convert("L")
    cand = blobs(mask, 128)
    if len(cand) != 4:
        sys.exit(
            f"{SRC_MASK} has {len(cand)} blob(s), expected 4 -- it is probably "
            "already a generated mask. Restore it from git."
        )

    # WHICH BULB IS THE WORKING ONE is measured off the new art, not assumed and
    # not read off a screenshot: for each authored bulb position, the mean
    # luminance of the albedo in a window around it. A working bulb is a bright
    # intact lens; a broken one is a dark hole with a few glass shards, so the
    # separation is large and unambiguous (156 against 53/64/94 as painted).
    lum = art.convert("L")
    lpx = lum.load()
    scored = []
    for (bx, by, _area) in cand:
        vals = [
            lpx[int(x) % TILE, int(y) % TILE]
            for y in range(int(by) - 6, int(by) + 7)
            for x in range(int(bx) - 6, int(bx) + 7)
        ]
        scored.append((sum(vals) / len(vals), bx, by))
    scored.sort(reverse=True)
    best, wx, wy = scored[0]
    runner = scored[1][0]
    if best < runner * 1.25:
        sys.exit(
            "cannot tell which bulb is lit: brightest window "
            f"{best:.0f} vs next {runner:.0f}. Repaint so the working bulb is "
            "clearly the brightest, or set it by hand."
        )

    # The emissive mask keeps ONLY the working bulb's blob. Three dead bulbs must
    # not glow -- if they do, the pane still reads as four sources and the whole
    # point (one compact source, so the grating's shadow survives) is lost.
    e_new = Image.new("L", (TILE, TILE), 0)
    src = mask.load()
    dst = e_new.load()
    kept = 0
    for y in range(TILE):
        for x in range(TILE):
            if src[x, y] < 128:
                continue
            # nearest authored bulb centre, with wrap
            def wrapd(a, b):
                d = abs(a - b)
                return min(d, TILE - d)

            near = min(cand, key=lambda c: wrapd(x + 0.5, c[0]) ** 2 + wrapd(y + 0.5, c[1]) ** 2)
            if near[0] == wx and near[1] == wy:
                dst[x, y] = src[x, y]
                kept += 1

    OUT_WAD.write_bytes(
        write_wad([("TX_START", b""), (TEX, png_bytes(art)), ("TX_END", b"")])
    )

    # Restore the AUTHORED side maps. All four bulb housings still exist in the
    # new art -- only the glass is broken -- so the authored relief is still the
    # correct relief, and any rearranged copy left by the previous single-bulb
    # tool is now actively wrong.
    restored = []
    for suffix in SIDE_MAPS:
        snap = SRC_SIDE / f"{TEX}{suffix}.png"
        if not snap.exists():
            print(f"  WARNING: no authored {TEX}{suffix}.png snapshot -- left as is")
            continue
        im = Image.open(snap)
        for d in MAT_DIRS:
            if d.exists():
                im.save(d / f"{TEX}{suffix}.png")
        restored.append(suffix)

    for d in MAT_DIRS:
        if d.exists():
            e_new.save(d / f"{TEX}_e.png")

    # README before/after. "Before" is the stock flat as it ships, taken from the
    # game's own wad rather than from any material dir -- those get overwritten by
    # this very script, so reading one back would show the new art as the old.
    docs = ROOT / "docs" / "img" / "features"
    docs.mkdir(parents=True, exist_ok=True)
    stock = None
    for wad in ("D64RTR_v15.WAD",):
        p = MODS / wad
        if not p.exists():
            continue
        blob = p.read_bytes()
        n, off = struct.unpack("<II", blob[4:12])
        for i in range(n):
            o, sz, nm = struct.unpack("<II8s", blob[off + i * 16 : off + i * 16 + 16])
            if nm.rstrip(b"\0").decode("latin1") == TEX and sz > 8:
                import io

                try:
                    stock = Image.open(io.BytesIO(blob[o : o + sz])).convert("RGB")
                except Exception:
                    stock = None
    if stock is not None:
        stock.resize((256, 256), Image.NEAREST).save(docs / "sflatas-before.png")
    art.convert("RGB").resize((256, 256), Image.NEAREST).save(docs / "sflatas-after.png")

    print(f"wrote {OUT_WAD.name}  ({OUT_WAD.stat().st_size} bytes)")
    print(f"  albedo from {SRC_ART.relative_to(ROOT)}")
    print(f"  working bulb: image ({wx:.1f}, {wy:.1f})  mean luminance {best:.0f}")
    print("  broken bulbs: " + ", ".join(
        f"({b:.1f},{c:.1f}) {a:.0f}" for a, b, c in scored[1:]))
    print(f"  _e keeps {kept} px, the working bulb only")
    print(f"  restored authored {', '.join(restored)} in "
          f"{sum(1 for d in MAT_DIRS if d.exists())} material dir(s)")
    # A CEILING FLAT'S Y IS FLIPPED against the image it is painted in: the world
    # position of a texel is ( img_x, TileSize - img_y ). Measured on 2026-08-14 in
    # the MAP93 lab by standing under the pane and subtracting a lights-off capture
    # from a lights-on one -- the light at image (16,48) landed LEFT, at (48,48)
    # landed BOTTOM, so the bulb the image draws at (16,48) lives at world (16,16).
    # X is NOT flipped. Do not "fix" this by symmetry: the authored lattice
    # BulbLatticeAS = {15.5, 47.5} is symmetric and therefore proves nothing.
    ex, ey = wx, TILE - wy
    print()
    print("  rt_lights_fixtures.cpp, SoloBulbTextures -- the light for this art:")
    print(f'      {{ "SFLATAS", {ex:.1f}, {ey:.1f}, /*verySmall*/ false }},')
    print(f"  (world y is TileSize - image y; image ({wx:.1f}, {wy:.1f}) is world "
          f"({ex:.1f}, {ey:.1f}))")
    print()
    print("  VERIFY, do not assume -- the two captures must put the lit patch and")
    print("  the emissive bulb on the same pixels:")
    print('      tools\\shot.ps1 -Map map93 -WarpTo "96 96" -Pitch 40 \\')
    print('          -ExtraFiles "d64rshadowlab.wad,d64r-sflatas-broken.wad" \\')
    print('          -Extra "+rt_solo_lamps 1 +rt_solo_lamp_radius 0.02 ..."')
    print('      ...and again with +rt_solo_lamps 0, then subtract the two.')


if __name__ == "__main__":
    main()
