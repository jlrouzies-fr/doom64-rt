"""
The fire-impact flavour's two pieces of DATA: the flame sheet the quads wear,
and the four colour ramps they cool through.

WHY THE ART IS EXTRACTED AND NOT DRAWN. The barrel plate settled this: a
procedural generator does not arrive at art that reads, because what makes it
read is that someone drew it. So the flame is the game's OWN five-frame `FIRE`
animation (64BigFire's bonfire), lifted out of D64RTR_v15.WAD, desaturated to a
white-hot luminance sheet and laid out as a flipbook strip. The internal shading
-- bright core, dark edges -- survives; only the HUE is left for the renderer to
supply per projectile, which is exactly what rt_fire's prim.color tint does.

The WAD itself proves the idea: it ships the same flame shape recoloured four
times already (GFLM green, RFLM red, BFLM blue, YFLM yellow).

WHY THE RAMPS COME FROM THE PROJECTILE'S OWN DEATH SPRITE. Same rule as every
other ramp in rt_sparks_internal.h -- PUFF's for sparks, PLSE's for the plasma
arc, MISL's for rocket embers. Reading the artist's palette rather than picking
colours is the single decision that made those stop needing tuning.

Usage:
    py -3 tools/gen_fire_impact_art.py            # write the sheet
    py -3 tools/gen_fire_impact_art.py --ramps    # print the C++ ramp tables
    py -3 tools/gen_fire_impact_art.py --pretint  # ALSO write four tinted sheets

--pretint is the FALLBACK PATH and is not needed unless the prim.color tint is
refuted in play. See docs/rt-impact-fx.md; RTGL1's HitInfo.inl multiplies
layerColors[0] into the sampled texel, so one white sheet should be enough.
"""
from __future__ import annotations

import argparse
import io
import struct
import sys
from pathlib import Path

from PIL import Image

PROJ_ROOT = Path(__file__).resolve().parents[1]
WAD = PROJ_ROOT / "Doom64-Retribution" / "D64RTR_v15.WAD"

# BOTH AUTHORED TREES AND BOTH BUILD TREES, and all four are load-bearing.
# developerMode makes RTGL1 read rt/mat_dev in preference to rt/mat, so a sheet
# in only one of them resolves to the 1x1 transparent placeholder -- which an
# alpha-tested quad discards ENTIRELY, with no error anywhere. That cost an
# afternoon on the barrel coals. And the build xcopies the authored tree over
# the build one, so writing only the build copy is undone by the next build.
OUT_DIRS = [
    PROJ_ROOT / "Doom64-Retribution" / "Retribution-RT-Materials" / "rt" / "mat" / "d64rt" / "fire",
    PROJ_ROOT / "Doom64-Retribution" / "Retribution-RT-Materials" / "rt" / "mat_dev" / "d64rt" / "fire",
    PROJ_ROOT / "sourcecode" / "gzdoom-rt" / "build" / "RelWithDebInfo" / "rt" / "mat" / "d64rt" / "fire",
    PROJ_ROOT / "sourcecode" / "gzdoom-rt" / "build" / "RelWithDebInfo" / "rt" / "mat_dev" / "d64rt" / "fire",
]

# The flipbook. Five frames because that is what the artist drew; the renderer
# reads the cell count off the sheet's aspect, so changing this needs no code.
FIRE_FRAMES = ["FIREA0", "FIREB0", "FIREC0", "FIRED0", "FIREE0"]

# THE RAMP SOURCES -- each projectile's OWN death frames.
#
# Note BAL1/BAL3 run D..I and BAL7/BAL8 run C..H: the bruiser balls spend their
# first death frame at full brightness before A_FadeOut starts, so their ladder
# begins one letter earlier. Taken from the DECORATE, not guessed.
RAMP_SOURCES = {
    "RT_FIRE_ORANGE_RAMP": ("BAL1", "DEFGHI", "0", "64DoomImpBall -- the imp's fireball"),
    "RT_FIRE_VIOLET_RAMP": ("BAL3", "DEFGHI", "0", "64NightmareImpBall -- the nightmare imp's"),
    "RT_FIRE_GREEN_RAMP": ("BAL7", "CDEFGH", "0", "64BaronBall -- the HELL KNIGHT's, not the baron's"),
    "RT_FIRE_RED_RAMP": ("BAL8", "CDEFGH", "0", "64BaronBall2 -- the BARON OF HELL's"),
}

RAMP_N = 10  # like the ember and laser ramps: a mark held for seconds bands.

# Tints for --pretint only, from each projectile's GLDEFS pointlight.
PRETINTS = {
    "orange": (1.00, 0.60, 0.00),
    "violet": (0.45, 0.25, 1.00),
    "green": (0.10, 1.00, 0.10),
    "red": (1.00, 0.15, 0.05),
}


def read_lumps() -> dict:
    d = WAD.read_bytes()
    n, o = struct.unpack_from("<II", d, 4)
    out = {}
    for i in range(n):
        off, sz, name = struct.unpack_from("<II8s", d, o + i * 16)
        nm = name.split(b"\0")[0].decode("ascii", "replace")
        if sz:
            out[nm] = d[off : off + sz]
    return out


def lum(rgb) -> float:
    r, g, b = rgb
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def ramp_for(lumps: dict, code: str, frames: str, rot: str) -> list:
    """Every colour the death animation actually paints, brightest first,
    resampled to RAMP_N.

    Read off the PIXELS rather than straight off the PLTE: a palette may carry
    entries the art never uses, and an unused near-black would push the real
    ladder up and make the ramp end brighter than the sprite ever does."""
    seen = {}
    for f in frames:
        nm = f"{code}{f}{rot}"
        raw = lumps.get(nm)
        if raw is None:
            raise SystemExit(f"gen_fire_impact_art: lump {nm} not in {WAD.name}")
        im = Image.open(io.BytesIO(raw)).convert("RGBA")
        px = im.load()
        for y in range(im.height):
            for x in range(im.width):
                r, g, b, a = px[x, y]
                if a < 128:
                    continue
                seen[(r, g, b)] = seen.get((r, g, b), 0) + 1

    # Drop colours that appear on almost nothing -- a handful of stray texels
    # would otherwise get an equal say with the body of the flame.
    total = sum(seen.values())
    keep = [c for c, n in seen.items() if n >= max(2, total // 400)]
    keep.sort(key=lum, reverse=True)
    if len(keep) < 2:
        raise SystemExit(f"gen_fire_impact_art: {code} gave only {len(keep)} colours")

    out = []
    for i in range(RAMP_N):
        j = round(i * (len(keep) - 1) / (RAMP_N - 1))
        out.append((keep[j][0] << 16) | (keep[j][1] << 8) | keep[j][2])
    return out


def print_ramps(lumps: dict) -> None:
    print("// GENERATED by tools/gen_fire_impact_art.py --ramps. Do not hand-edit;")
    print("// re-run it if the sprite art ever changes.")
    for name, (code, frames, rot, note) in RAMP_SOURCES.items():
        vals = ramp_for(lumps, code, frames, rot)
        print(f"\n// {code} {frames[0]}0-{frames[-1]}0 -- {note}")
        print(f"constexpr uint32_t {name}[] = {{")
        for i in range(0, RAMP_N, 5):
            row = ", ".join(f"0x{v:06X}" for v in vals[i : i + 5])
            print(f"    {row},")
        print("};")
        print(f"constexpr int {name}_N = int( std::size( {name} ) );")


def build_sheet(lumps: dict) -> Image.Image:
    frames = []
    for nm in FIRE_FRAMES:
        raw = lumps.get(nm)
        if raw is None:
            raise SystemExit(f"gen_fire_impact_art: lump {nm} not in {WAD.name}")
        frames.append(Image.open(io.BytesIO(raw)).convert("RGBA"))

    # SQUARE CELLS, and that is not tidiness -- it is what makes the frame count
    # recoverable from the file. The renderer infers it as round(width / height)
    # rather than being told twice, and that only works if a cell is as wide as
    # it is tall. The first version packed cells at the art's own 32x52 and a
    # five-frame strip measured 160/52 = 3.08, so the game animated three frames
    # and stepped through fragments of its neighbours -- which on screen reads as
    # bad art rather than as a mismatch, exactly the failure the inference was
    # supposed to avoid. The transparent margin costs nothing.
    cell = max(max(f.width for f in frames), max(f.height for f in frames))
    cw = ch = cell
    sheet = Image.new("RGBA", (cw * len(frames), ch), (0, 0, 0, 0))

    # BOTTOM-ALIGNED, and it matters: the renderer plants the quad's FOOT on the
    # surface, so a frame centred in its cell would leave the flame floating a
    # few pixels off the wall on the shorter frames only -- a wobble that reads
    # as the effect being loose rather than as the flame moving.
    for i, f in enumerate(frames):
        sheet.paste(f, (i * cw + (cw - f.width) // 2, ch - f.height))

    # WHITE-HOT: luminance, normalised so the core reaches full. The tint is a
    # MULTIPLY (HitInfo.inl:90), so anything short of 255 in the core makes the
    # brightest part of the flame darker than the colour it is supposed to be.
    px = sheet.load()
    peak = 1
    for y in range(sheet.height):
        for x in range(sheet.width):
            r, g, b, a = px[x, y]
            if a:
                peak = max(peak, int(lum((r, g, b))))
    for y in range(sheet.height):
        for x in range(sheet.width):
            r, g, b, a = px[x, y]
            if not a:
                px[x, y] = (0, 0, 0, 0)
                continue
            v = min(255, int(lum((r, g, b)) * 255.0 / peak + 0.5))
            px[x, y] = (v, v, v, a)
    return sheet


def tinted(sheet: Image.Image, rgb) -> Image.Image:
    out = sheet.copy()
    px = out.load()
    for y in range(out.height):
        for x in range(out.width):
            v, _, _, a = px[x, y]
            if not a:
                continue
            px[x, y] = (
                min(255, int(v * rgb[0] + 0.5)),
                min(255, int(v * rgb[1] + 0.5)),
                min(255, int(v * rgb[2] + 0.5)),
                a,
            )
    return out


def write_all(img: Image.Image, stem: str) -> None:
    for d in OUT_DIRS:
        d.mkdir(parents=True, exist_ok=True)
        p = d / f"{stem}.png"
        img.save(p)
        print(f"  wrote {p.relative_to(PROJ_ROOT)}  {img.width}x{img.height}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ramps", action="store_true", help="print the C++ ramp tables and exit")
    ap.add_argument("--pretint", action="store_true", help="also write four pre-tinted sheets")
    a = ap.parse_args()

    if not WAD.exists():
        raise SystemExit(f"gen_fire_impact_art: {WAD} not found")
    lumps = read_lumps()

    if a.ramps:
        print_ramps(lumps)
        return 0

    sheet = build_sheet(lumps)
    print(
        f"fire sheet: {len(FIRE_FRAMES)} frames, cell "
        f"{sheet.width // len(FIRE_FRAMES)}x{sheet.height}"
    )
    write_all(sheet, "fire")

    if a.pretint:
        for nm, rgb in PRETINTS.items():
            write_all(tinted(sheet, rgb), f"fire_{nm}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
