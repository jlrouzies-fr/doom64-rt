"""Build the per-map Doom 64 sky textures the RT sky path needs.

Why this exists
---------------
Retribution does NOT set a sky in MAPINFO. Every map says `sky1 = "ISUCK"` -- a
64x64 dummy -- and the real sky is a **sector skybox room**: a ring of sectors
parked off the side of the map with a SkyViewpoint (thing 9080) in it, the cloud
layer as its ceiling flat and the mountain silhouette as a masked MIDDLE texture
on the ring walls. F_SKY1 ceilings in the level show that room.

Under RT sector skybox rooms are never drawn (HWSkyboxPortal geometry is not
submitted -- the white/black bug), so rt_sky_always fills every F_SKY1 opening
with the flat sky dome instead. That left d64r-rt-sky forcing ONE flat sky,
MOONSKY, onto all 34 maps: the fire skies of the hell maps, the brown mountains
of MAP10/16, the purple weather of MAP12/14/30 and the void of MAP25/26/31 all
came out as the same starfield.

This script bakes the skybox rooms that need baking into single dome textures,
one per family. Three families need nothing generated and are wired straight to
the WAD's own textures in ZSCRIPT:

    fire maps  -> FRSKYNRM / FRSKYGRN, the WAD's 100-frame ANIMDEFS fire skies.
                  hw_sky.cpp fetches the sky with GetGameTexture(tex, true), so
                  the animation runs on the dome. The art is already black at
                  the top and bright at the bottom, which is the orientation the
                  dome wants: fire at the horizon, black above, and the dome's
                  cap takes the top row -- black.
    void maps  -> VOIDSKY, a flat dark teal. Nothing to bake.
    star maps  -> MOONSKY, unchanged (tools/gen_moon_sky.py).

Nothing here is eyeballed
-------------------------
Every angle is measured off the skybox rooms themselves, per map, and averaged
over the maps a given sky serves (--report prints the table). The room is a
drum: a ring of MOUNT* walls of known radius around a SkyViewpoint at a known
height, under a cloud flat at a known ceiling. That fixes, without guessing:

  - where the mountain peaks sit    -- atan((ceiling - eye) / ring radius)
  - how far down the silhouette runs -- the middle texture is 128 units tall and
    hangs from the ceiling, so its bottom edge is 128 below that
  - how big the clouds are          -- the flat is 512 units across and sits
    (ceiling - eye) above you, so one tile spans that many plane-heights

MAP10, for instance: eye at z=40 in a 192-radius ring 104 tall, so its peaks top
out 18.4 degrees up and its cloud tile spans 8 plane-heights. MAP02's ring is
176 tall and its eye is at z=8, so its mountains reach 40 degrees -- twice as
tall a horizon, which is why one set of numbers for all of them would be wrong.

Output shape
------------
Everything is 1024x128, deliberately the same shape as MOONSKY:

  - 1024 wide because hw_skydome picks `xscale = texw < 1024 ? floor(1024/texw)
    : 1`. At 1024 the sky wraps exactly once and what is painted is what you
    see; anything narrower repeats and the composition repeats with it.
  - 128 tall because that is the `texh <= 128 && tiled` branch of SetupMatrices,
    the one MOONSKY is already tuned against. A 256-tall sky takes a different
    branch with a different vertical translate and scale, which would move the
    horizon out from under the moon and the rt_sun aim that agrees with it.

The CLOUD layer is not pasted flat. In the room it is a horizontal PLANE over
the viewer, so it is projected here the way the eye sees it: an output row is an
altitude, and the plane is sampled at r = cot(altitude) plane-heights from
directly overhead. Clouds come out large and slow overhead and crowd into
streaks towards the horizon, which is why the original reads as weather rather
than wallpaper. A haze fade towards the tile's mean colour takes over as r
grows, both because that is what distance does and because without it the
horizon rows alias into confetti.

MAP11 and MAP14 get flat backgrounds with no painted cloud at all. Those two are
the RT_CLOUD_PRESETS maps (rt_main.cpp): they already get the volumetric cloud
DECK drawn as geometry over the sky, and painting cloud into the dome as well
would show two unrelated cloud layers at once. Their sky is the dark purple the
deck is meant to sit against.

Usage
-----
    tools\\.venv-ai\\Scripts\\python.exe tools/gen_d64_skies.py --report
    tools\\.venv-ai\\Scripts\\python.exe tools/gen_d64_skies.py --preview
    tools\\.venv-ai\\Scripts\\python.exe tools/pack_rt_sky.py

The per-map wiring lives in tools/d64r-rt-sky/ZSCRIPT. Adding a sky here without
adding it there changes nothing in game.
"""

from __future__ import annotations

import argparse
import io
import math
import re
import sys
from pathlib import Path

from PIL import Image

try:
    import numpy as np
except ModuleNotFoundError:  # pragma: no cover
    raise SystemExit(
        "gen_d64_skies needs numpy for the cloud-plane projection.\n"
        "Run it with the repo venv, which has it:\n"
        "  tools\\.venv-ai\\Scripts\\python.exe tools/gen_d64_skies.py"
    )

sys.path.insert(0, str(Path(__file__).resolve().parent))

from make_map_3dfloor_rtfix import WAD, read_wad_lumps  # noqa: E402

HERE = Path(__file__).resolve().parent
OUTDIR = HERE / "d64r-rt-sky" / "textures"

# Same as MOONSKY, and for the reasons in the module docstring. Do not change one
# without the other: the point is that every sky in the game takes the same
# branch of SetupMatrices, so the horizon does not move from map to map.
SKY_WIDTH = 1024
SKY_HEIGHT = 128

# maxSideAngle in SkyVertexDoom -- the dome covers +/-60 degrees of altitude over
# the texture's height, not a full hemisphere.
DOME_MAX_ALTITUDE = 60.0

# Doom middle textures are 1 texel per map unit vertically and hang from the
# ceiling on these rings, so the silhouette's bottom edge is this far below it.
MOUNT_TEX_HEIGHT = 128

# A flat is 1 texel per map unit too, so the cloud tile is this many units across.
CLOUD_FLAT_UNITS = 512

# How far out the cloud plane is sampled before it is entirely haze, in units of
# the plane's own height above the viewer.
HAZE_START = 2.0
HAZE_FULL = 14.0

# Mountain tiles around the full 360 degrees. The rings measure ~1230 units of
# perimeter against a 256-wide tile, so the originals repeat about 4.8 times; 4
# is the nearest count that divides 1024 without seaming the ring, and 15% wider
# peaks is not a visible error.
MOUNT_REPEATS = 4


# -- what each generated sky is, and which maps it serves ---------------------
#
# The map list is not documentation: the angles and the cloud scale are measured
# off exactly these maps and averaged. Keep it in step with the table in ZSCRIPT.
#
# background: ("cloud", FLAT) | ("stars", FLAT) | ("flat", FLAT, dim)
SKIES = {
    "SKYMTNA": {
        "maps": ["MAP02", "MAP04", "MAP05", "MAP34"],
        "bg": ("stars", "SPACE"),
        "mtn": "MOUNTA",
        "note": "Starfield behind a tall grey-blue mountain ring. These rooms are "
                "176 units tall against 104 elsewhere, so the horizon is the "
                "highest in the game.",
    },
    "SKYMTNB": {
        "maps": ["MAP10", "MAP16"],
        "bg": ("cloud", "CLOUDBRN"),
        "mtn": "MOUNTB",
        "note": "Burnt orange overcast over red rock.",
    },
    "SKYMTNC": {
        "maps": ["MAP12", "MAP30"],
        "bg": ("cloud", "CLOUDPRP"),
        "mtn": "MOUNTC",
        "note": "Purple weather over violet peaks.",
    },
    "SKYMTNCD": {
        "maps": ["MAP14"],
        "bg": ("flat", "CLOUDPRP", 0.35),
        "mtn": "MOUNTC",
        "note": "Same peaks as SKYMTNC, but MAP14 is in RT_CLOUD_PRESETS -- its "
                "cloud is the RT deck drawn as geometry, so the dome carries "
                "none of its own or you see two skies at once.",
    },
    "SKYCLDPK": {
        "maps": ["MAP09", "MAP15", "MAP18", "MAP19", "MAP20"],
        "bg": ("cloud", "CLOUDPNK"),
        "mtn": None,
        "note": "Pink overcast. No mountain ring in these rooms -- the cloud "
                "flat is the whole sky.",
    },
    "SKYCLDBR": {
        "maps": ["MAP17", "MAP27"],
        "bg": ("cloud", "CLOUDBRN"),
        "mtn": None,
        "note": "Brown overcast, no mountain ring.",
    },
    "SKYSTORM": {
        "maps": ["MAP11"],
        "bg": ("flat", "CLOUDPRP", 0.30),
        "mtn": None,
        "note": "The storm map. Dark purple for the RT cloud deck and the "
                "lightning to sit against; painting cloud here would double it.",
    },
}


# -- reading the skybox rooms out of the WAD ---------------------------------

def _blocks(text: str, kind: str) -> list[dict]:
    out = []
    for m in re.finditer(r"(?ms)^" + kind + r"\s*\n\{\n(.*?)\n\}", text):
        out.append(dict(re.findall(r"(\w+) = ([^;]+);", m.group(1))))
    return out


def _textmaps() -> dict[str, str]:
    """{MAPxx: TEXTMAP text}. Retribution is all UDMF."""
    maps, pending = {}, None
    for name, blob in read_wad_lumps(WAD):
        if re.fullmatch(r"MAP\d\d|TITLEMAP", name):
            pending = name
        elif name == "TEXTMAP" and pending:
            maps[pending] = blob.decode("latin1")
            pending = None
        elif name == "ENDMAP":
            pending = None
    return maps


class Room:
    """The measurements a skybox room hands us, in degrees and plane-heights."""

    def __init__(self, mapname: str, text: str):
        self.map = mapname
        verts = _blocks(text, "vertex")
        sides = _blocks(text, "sidedef")
        lines = _blocks(text, "linedef")
        secs = _blocks(text, "sector")

        vp = [t for t in _blocks(text, "thing") if t.get("type") == "9080"]
        # UDMF `height` is the offset above the sector floor.
        self.eye_above_floor = float(vp[0].get("height", 0)) if vp else 0.0

        # The mountain ring: every wall carrying a MOUNT* middle texture. Its
        # perimeter gives the radius, which is what turns heights into angles.
        perim, ring_sector = 0.0, None
        for ln in lines:
            for side in ("sidefront", "sideback"):
                if side not in ln:
                    continue
                sd = sides[int(ln[side])]
                if sd.get("texturemiddle", "").strip('"').upper().startswith("MOUNT"):
                    a, b = verts[int(ln["v1"])], verts[int(ln["v2"])]
                    perim += math.hypot(float(a["x"]) - float(b["x"]),
                                        float(a["y"]) - float(b["y"]))
                    ring_sector = int(sd["sector"])

        self.mtn_top_deg = self.mtn_span_deg = None
        if ring_sector is not None and perim > 0:
            sec = secs[ring_sector]
            floor, ceil = float(sec["heightfloor"]), float(sec["heightceiling"])
            radius = perim / (2.0 * math.pi)
            eye = floor + self.eye_above_floor
            # The silhouette hangs from the ceiling and is MOUNT_TEX_HEIGHT tall.
            # Where it runs below the room's floor it is simply not drawn, but we
            # keep the unclipped span here -- the dome texture clips it at the
            # horizon by itself, which is the same cut.
            self.mtn_top_deg = math.degrees(math.atan2(ceil - eye, radius))
            bottom = math.degrees(
                math.atan2(ceil - MOUNT_TEX_HEIGHT - eye, radius))
            self.mtn_span_deg = self.mtn_top_deg - bottom

        # The cloud plane: the room's own ceiling, however high above the eye.
        self.cloud_span = None
        for sec in secs:
            if ("CLOUD" in sec.get("textureceiling", "").upper()
                    and "ALLBLACK" in sec.get("texturefloor", "").upper()):
                height = (float(sec["heightceiling"])
                          - float(sec["heightfloor"]) - self.eye_above_floor)
                if height > 0:
                    self.cloud_span = CLOUD_FLAT_UNITS / height
                break


def measure(skyname: str, spec: dict, rooms: dict[str, Room]) -> dict:
    """Average the rooms of the maps this sky serves."""
    got = [rooms[m] for m in spec["maps"] if m in rooms]
    if not got:
        raise SystemExit(f"{skyname}: none of {spec['maps']} found in {WAD.name}")

    def mean(attr, default):
        vals = [getattr(r, attr) for r in got if getattr(r, attr) is not None]
        return sum(vals) / len(vals) if vals else default

    return {
        "rooms": got,
        # 6.8 and the 20/30 degrees below are only reached if a room is missing
        # the feature entirely; they are the measured averages of the ones that
        # have it, so a fallback still lands somewhere sane.
        "cloud_span": mean("cloud_span", 6.8),
        "mtn_top_deg": mean("mtn_top_deg", 20.0),
        "mtn_span_deg": mean("mtn_span_deg", 30.0),
    }


# -- painting ----------------------------------------------------------------

def wad_lump(name: str) -> Image.Image:
    for lump, blob in read_wad_lumps(WAD):
        if lump.upper() == name.upper():
            return Image.open(io.BytesIO(blob))
    raise SystemExit(f"{WAD}: no {name} lump")


def tile_to_width(src: Image.Image, width: int) -> Image.Image:
    """Repeat a texture horizontally. Refuses to produce a seam."""
    if width % src.width:
        raise SystemExit(
            f"{src.width}px does not divide {width} -- tiling would seam.")
    out = Image.new(src.mode, (width, src.height))
    for i in range(width // src.width):
        out.paste(src, (i * src.width, 0))
    return out


def project_cloud_plane(tile: Image.Image, width: int, height: int,
                        span: float) -> Image.Image:
    """Look up at an infinite plane papered with `tile`, and paint what you see.

    Row y is an altitude (top = the dome's 60 degrees, bottom = the horizon);
    column x is an azimuth. A ray at altitude a meets a plane one unit overhead
    at radius cot(a), so the whole projection is that one identity, scaled by
    `span` -- how many plane-heights one tile covers, measured off the room --
    plus a haze term to keep the horizon from aliasing into confetti.
    """
    src = np.asarray(tile.convert("RGB")).astype(np.float32)
    th, tw = src.shape[:2]
    mean = src.reshape(-1, 3).mean(axis=0)

    alt = np.deg2rad(DOME_MAX_ALTITUDE * (1.0 - (np.arange(height) + 0.5) / height))
    # Floor the altitude rather than the radius: at the horizon cot() runs away
    # and the sample point stops meaning anything, but haze has already taken the
    # pixel over by then anyway.
    alt = np.maximum(alt, np.deg2rad(0.75))
    r = (1.0 / np.tan(alt))[:, None]                       # (H,1) plane-heights

    az = 2.0 * math.pi * (np.arange(width) + 0.5) / width  # (W,)
    px = r * np.cos(az)[None, :] * (tw / span)
    py = r * np.sin(az)[None, :] * (th / span)

    # Bilinear, wrapped. Nearest sampling turns the overhead rows -- where one
    # texel covers several degrees -- into visible blocks.
    x0 = np.floor(px).astype(np.int64)
    y0 = np.floor(py).astype(np.int64)
    fx = (px - x0)[..., None]
    fy = (py - y0)[..., None]
    x0m, x1m = x0 % tw, (x0 + 1) % tw
    y0m, y1m = y0 % th, (y0 + 1) % th
    top = src[y0m, x0m] * (1 - fx) + src[y0m, x1m] * fx
    bot = src[y1m, x0m] * (1 - fx) + src[y1m, x1m] * fx
    out = top * (1 - fy) + bot * fy

    haze = np.clip((r - HAZE_START) / (HAZE_FULL - HAZE_START), 0.0, 1.0)[..., None]
    out = out * (1 - haze) + mean[None, None, :] * haze

    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), "RGB")


def flat_background(tile: Image.Image, width: int, height: int,
                    dim: float) -> Image.Image:
    """The tile's mean colour, dimmed. For maps whose cloud is RT geometry."""
    src = np.asarray(tile.convert("RGB")).astype(np.float32)
    mean = np.clip(src.reshape(-1, 3).mean(axis=0) * dim, 0, 255)
    return Image.new("RGB", (width, height), tuple(int(round(c)) for c in mean))


def paste_mountains(sky: Image.Image, mtn: Image.Image,
                    top_deg: float, span_deg: float, repeats: int) -> None:
    """Composite the silhouette ring at the altitude the room puts it at.

    The art is placed by its measured top and span rather than bottom-aligned,
    because the two families differ: the 104-tall rings hang their peaks 18-24
    degrees up and run off the bottom of the dome, while the 176-tall rings of
    MAP02/04/05/34 put theirs at 40 and stop well above the horizon. Below the
    art's bottom edge its last row is extended down to the horizon -- in the room
    that gap is the far side of the ring and the black floor, i.e. more of the
    same rock, and leaving the background showing there would float the mountains
    in mid-air.
    """
    if mtn.mode != "RGBA":
        mtn = mtn.convert("RGBA")
    px_per_deg = sky.height / DOME_MAX_ALTITUDE
    band = max(1, int(round(span_deg * px_per_deg)))
    y_top = int(round(sky.height - top_deg * px_per_deg))

    tile_w = sky.width // repeats
    scaled = mtn.resize((tile_w, band), Image.LANCZOS)
    strip = Image.new("RGBA", (sky.width, band), (0, 0, 0, 0))
    for i in range(repeats):
        strip.paste(scaled, (i * tile_w, 0))

    # Carry the art's last row down to the horizon, fading it to black. Straight
    # repetition of that row streaks -- it is one line of rock detail stretched
    # over tens of pixels -- and what the room actually shows down there is the
    # far side of the ring falling into its own shadow over the black floor.
    fill_h = sky.height - (y_top + band)
    if fill_h > 0:
        tail = np.asarray(
            strip.crop((0, band - 1, sky.width, band)).convert("RGBA")
        ).astype(np.float32)                                   # (1,W,4)
        tail = np.repeat(tail, fill_h, axis=0)
        # Fade over a short run and hold black for the rest. Fading across the
        # whole fill leaves that one row of rock detail legible as vertical
        # streaks all the way to the horizon; 8 rows is enough to read as the
        # foot of the mountain and short enough that nothing repeats visibly.
        fade = np.zeros(fill_h, dtype=np.float32)
        run = min(fill_h, 8)
        fade[:run] = np.linspace(1.0, 0.0, run, dtype=np.float32)
        tail[..., :3] *= fade[:, None, None]                   # to black, keep alpha
        full = Image.new("RGBA", (sky.width, band + fill_h), (0, 0, 0, 0))
        full.paste(strip, (0, 0))
        full.paste(Image.fromarray(tail.astype(np.uint8), "RGBA"), (0, band))
        strip = full

    sky.paste(strip, (0, y_top), strip)


def main() -> None:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--width", type=int, default=SKY_WIDTH)
    p.add_argument("--height", type=int, default=SKY_HEIGHT)
    p.add_argument("--mtn-scale", type=float, default=1.0,
                   help="multiply the measured mountain height. 1.0 is what the "
                        "rooms say; the one knob to reach for if the ring reads "
                        "too tall or too low on the dome in game")
    p.add_argument("--cloud-scale", type=float, default=1.0,
                   help="multiply the measured cloud tile span. Above 1 makes "
                        "the clouds smaller and busier")
    p.add_argument("--report", action="store_true",
                   help="print what each room measured, per map, and stop")
    p.add_argument("--preview", action="store_true",
                   help="also write *_preview.png brightened x2.5 -- these skies "
                        "are dark and near-unreadable on a monitor. NOT packed.")
    p.add_argument("--only", action="append", default=None,
                   help="build just this sky (repeatable)")
    args = p.parse_args()

    if args.width % MOUNT_REPEATS:
        raise SystemExit(f"width {args.width} is not divisible by "
                         f"{MOUNT_REPEATS} mountain tiles; the ring would seam.")

    texts = _textmaps()
    rooms = {m: Room(m, texts[m])
             for spec in SKIES.values() for m in spec["maps"] if m in texts}

    if args.report:
        print(f"{'map':7s} {'eye':>4s} {'peaks':>7s} {'span':>7s} {'cloud tile':>11s}")
        for name, spec in SKIES.items():
            print(f"-- {name}: {', '.join(spec['maps'])}")
            for m in spec["maps"]:
                r = rooms.get(m)
                if not r:
                    print(f"{m:7s}   (not in {WAD.name})")
                    continue
                top = f"{r.mtn_top_deg:6.1f}d" if r.mtn_top_deg is not None else "     --"
                span = f"{r.mtn_span_deg:6.1f}d" if r.mtn_span_deg is not None else "     --"
                cs = f"{r.cloud_span:9.2f}h" if r.cloud_span is not None else "       --"
                print(f"{m:7s} {r.eye_above_floor:4.0f} {top} {span} {cs}")
            av = measure(name, spec, rooms)
            print(f"{'  avg':7s} {'':4s} {av['mtn_top_deg']:6.1f}d "
                  f"{av['mtn_span_deg']:6.1f}d {av['cloud_span']:9.2f}h")
        return

    OUTDIR.mkdir(parents=True, exist_ok=True)
    for name, spec in SKIES.items():
        if args.only and name not in args.only:
            continue
        av = measure(name, spec, rooms)
        kind, lump = spec["bg"][0], spec["bg"][1]
        tile = wad_lump(lump)

        if kind == "cloud":
            span = av["cloud_span"] * args.cloud_scale
            sky = project_cloud_plane(tile, args.width, args.height, span)
            how = (f"{lump} {tile.width}x{tile.height} projected as a cloud "
                   f"plane, 1 tile = {span:.2f} plane-heights")
        elif kind == "stars":
            # Tiled, not projected: a starfield is at infinity, so it has no
            # perspective to give. This is byte-for-byte what MOONSKY is.
            sky = tile_to_width(tile.convert("RGB"), args.width)
            if sky.height != args.height:
                sky = sky.resize((args.width, args.height), Image.LANCZOS)
            how = f"{lump} tiled x{args.width // tile.width}"
        else:
            sky = flat_background(tile, args.width, args.height, spec["bg"][2])
            how = (f"flat {lump} mean x{spec['bg'][2]:g} = "
                   f"#{'%02X%02X%02X' % sky.getpixel((0, 0))}")

        if spec["mtn"]:
            top = av["mtn_top_deg"] * args.mtn_scale
            span = av["mtn_span_deg"] * args.mtn_scale
            paste_mountains(sky, wad_lump(spec["mtn"]), top, span, MOUNT_REPEATS)
            how += (f" + {spec['mtn']} x{MOUNT_REPEATS}, peaks {top:.1f} deg up, "
                    f"{span:.1f} deg tall")

        out = OUTDIR / f"{name}.png"
        sky.save(out)
        print(f"wrote {out.name} {sky.width}x{sky.height} "
              f"[{', '.join(spec['maps'])}]")
        print(f"    {how}")
        print(f"    {spec['note']}")

        if args.preview:
            from PIL import ImageEnhance
            prev = ImageEnhance.Brightness(sky).enhance(2.5)
            prev.save(OUTDIR / f"{name}_preview.png")
            print(f"    preview: {name}_preview.png (x2.5, not packed)")

    print("\nnext: tools\\.venv-ai\\Scripts\\python.exe tools/pack_rt_sky.py")


if __name__ == "__main__":
    main()
