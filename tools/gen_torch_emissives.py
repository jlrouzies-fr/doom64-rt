"""
Generate RT emissive masks + attached-light meta for the Retribution standing torches.

Covers the eight TL*/TS* families (long/short torch x blue/green/red/yellow), 5 frames
each = 40 sprites that carried **no RT meta at all** — no light, no emission.

Why these need their own tool instead of a PREFIX_RULES entry in gen_fx_emissives.py:

  * They are NOT drawn BRIGHT. `64TorchLongBlue` etc. run `TLBL ABCDE 4` with no BRIGHT
    flag, unlike the wall torches (`A030`/`A031`/`A032`/`GTCH`, all `ABCDE 4 BRIGHT`).
    The mod deliberately shades the stone pole.
  * The pole is most of the sprite — ~180 flame texels out of ~970 opaque on a TL frame.
    A blanket `emissiveMult` would make an 82%-grey-stone brazier self-illuminate, which
    is the PLSG/BFGG whole-gun-body failure documented in gen_fx_emissives.py.
  * gen_fx_emissives.make_emissive_png() cannot separate them: it keeps any texel with
    sum >= 200, and the stone reads (176,168,168) = 512.

So the mask here is gated on **saturation**, not brightness: the flame is the only
coloured thing on the sprite. Per Mechanism 3 in docs/sprite-illumination.md the mask is
then repainted at FULL saturation (the shader already multiplies by baseColor; sampling
the albedo back into the mask squares it and kills the glow), taking only the intensity
ramp from the source texel.

Light colours are the shared flame palette also used by BFLM/GFLM/RFLM/YFLM, which sits
within 10 deg of every measured flame and matches the mod's own GLDEFS intent
(TORCHLONG*/TORCHSHORT*, color 0.0 0.2 1.0 / 0.0 1.0 0.0 / 1.0 0.1 0.1 / 1.0 0.9 0.0)
without GLDEFS' fully-primary saturation.

Writes:
  build/RelWithDebInfo/rt/data/textures.json            (live global)
  build/RelWithDebInfo/rt/data/scenes/d64rtr_v15_map01/textures.json
  Doom64-Retribution/.../rt/data/textures_fx.json       (overlay source-of-record)
  Doom64-Retribution/.../rt/data/scenes/d64rtr_v15_map01/textures.json
  {build/RelWithDebInfo/rt/mat, .../rt/mat_dev, Retribution-RT-Materials/rt/mat}/<NAME>_e.png
"""
from __future__ import annotations

import io
import json
import struct
from pathlib import Path

from PIL import Image

ROOT = Path(r"G:\ai\Doom64-RT")
WAD = ROOT / r"Doom64-Retribution\D64RTR_v15.WAD"
RT_DATA = ROOT / r"sourcecode\gzdoom-rt\build\RelWithDebInfo\rt\data"
MAT_DIRS = [
    ROOT / r"sourcecode\gzdoom-rt\build\RelWithDebInfo\rt\mat",
    ROOT / r"sourcecode\gzdoom-rt\build\RelWithDebInfo\rt\mat_dev",
    ROOT / r"Doom64-Retribution\Retribution-RT-Materials\rt\mat",
]
JSON_TARGETS = [
    RT_DATA / "textures.json",
    RT_DATA / r"scenes\d64rtr_v15_map01\textures.json",
    ROOT / r"Doom64-Retribution\Retribution-RT-Materials\rt\data\textures_fx.json",
    ROOT / r"Doom64-Retribution\Retribution-RT-Materials\rt\data\scenes\d64rtr_v15_map01\textures.json",
    ROOT / r"sourcecode\gzdoom-rt\build\WashScratch\rt\data\scenes\d64rtr_v15_map01\textures.json",
]

# Shared flame palette — same hexes as BFLM/GFLM/RFLM/YFLM in gen_fx_emissives.py.
FLAME_BLUE = "4488ff"
FLAME_GREEN = "44ff66"
FLAME_RED = "ff4020"
FLAME_YELLOW = "ffcc33"

# No attached light. These are lit by the engine instead — RT_UploadFlameLights in
# rt_main.cpp, table RT_FLAME_KINDS, cvar rt_flame_light_on — because texture meta cannot
# express either thing a torch needs:
#   * the GLDEFS offset (80u for TL*, 64u for TS*). RTGL1 pins a sprite light to the
#     CENTRE of the billboard quad, so a 100-unit torch lit itself from the midriff.
#   * flicker. Meta is static per frame, and every torch spawns at map load, so driving
#     intensity off the A..E animation would pulse the whole level in lockstep.
# emissiveMult stays at 1.0: the flame still has to glow on screen, and the mask below is
# what makes that safe on a sprite that is 82% grey stone.
# Keep INTENSITY = 0 unless you also delete the TL*/TS* rows from RT_FLAME_KINDS — two
# lights on one flame, at two different heights, is worse than the bug this replaced.
INTENSITY = 0  # was 900, matching the GLDEFS size 40/48 vs the wall torches' 28/32
EMISSIVE_MULT = 1.0

FAMILIES = {
    "TLBL": FLAME_BLUE,
    "TLGR": FLAME_GREEN,
    "TLRD": FLAME_RED,
    "TLYL": FLAME_YELLOW,
    "TSBL": FLAME_BLUE,
    "TSGR": FLAME_GREEN,
    "TSRD": FLAME_RED,
    "TSYL": FLAME_YELLOW,
}

# Flame gate. The stone sconce is neutral grey (max-min == 0..8); the dimmest flame texel
# still carries a strong channel split.
MIN_SATURATION = 45
MIN_SUM = 150


def wad_images(path: Path) -> dict[str, bytes]:
    d = path.read_bytes()
    n, o = struct.unpack_from("<II", d, 4)
    out: dict[str, bytes] = {}
    for i in range(n):
        off, sz, name = struct.unpack_from("<II8s", d, o + i * 16)
        nm = name.split(b"\0")[0].decode("ascii", "replace")
        if sz > 0:
            out.setdefault(nm, d[off : off + sz])
    return out


def flame_texels(img: Image.Image) -> list[tuple[int, int]]:
    """Indices of flame texels + their intensity (0..255), skipping the grey pole."""
    out = []
    for i, (r, g, b, a) in enumerate(img.convert("RGBA").getdata()):
        if a < 40 or r + g + b < MIN_SUM:
            continue
        if max(r, g, b) - min(r, g, b) < MIN_SATURATION:
            continue
        out.append((i, max(r, g, b)))
    return out


def make_mask(img: Image.Image, hex_color: str) -> tuple[Image.Image, int]:
    """Full-saturation flame mask; intensity ramp from the source, hue from a constant."""
    cr, cg, cb = (int(hex_color[i : i + 2], 16) for i in (0, 2, 4))
    flame = flame_texels(img)
    peak = max((v for _, v in flame), default=1)

    px = [(0, 0, 0, 0)] * (img.width * img.height)
    for i, v in flame:
        k = v / peak  # normalize so the hottest flame texel paints at full range
        px[i] = (int(cr * k), int(cg * k), int(cb * k), 255)

    out = Image.new("RGBA", img.size)
    out.putdata(px)
    written_peak = max((max(p[:3]) for p in px), default=0)
    return out, written_peak


def upsert(path: Path, entries: dict[str, dict]) -> tuple[int, int]:
    """Insert/replace entries, keeping the file's exact json.dumps(indent=2) formatting."""
    doc = json.loads(path.read_text(encoding="utf-8"))
    key = next(k for k, v in doc.items() if isinstance(v, list))
    arr = doc[key]
    by_name = {t.get("textureName"): i for i, t in enumerate(arr) if isinstance(t, dict)}

    added = replaced = 0
    # keep the torch block together: land new entries after the last GTCH frame if present
    anchor = max((i for n, i in by_name.items() if n and n.startswith("GTCH")), default=None)
    pending = []
    for name, meta in entries.items():
        if name in by_name:
            arr[by_name[name]] = meta
            replaced += 1
        else:
            pending.append(meta)
            added += 1
    if pending:
        at = anchor + 1 if anchor is not None else len(arr)
        arr[at:at] = pending

    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return added, replaced


def main() -> None:
    lumps = wad_images(WAD)
    entries: dict[str, dict] = {}
    masks = 0

    for prefix, hex_color in FAMILIES.items():
        names = sorted(n for n in lumps if n.startswith(prefix))
        if not names:
            print(f"  !! {prefix}: no lumps in {WAD.name}")
            continue
        for name in names:
            img = Image.open(io.BytesIO(lumps[name])).convert("RGBA")
            mask, peak = make_mask(img, hex_color)
            if peak < 255:
                print(f"  !! {name}: mask peaks at {peak}, expected 255")
            for d in MAT_DIRS:
                d.mkdir(parents=True, exist_ok=True)
                mask.save(d / f"{name}_e.png")
            masks += 1

            entries[name] = {
                "textureName": name,
                "emissiveMult": EMISSIVE_MULT,
                "lightColorHEX": hex_color,
                "lightIntensity": INTENSITY,
                "noShadow": True,
            }
        n_flame = len(flame_texels(Image.open(io.BytesIO(lumps[names[0]])).convert("RGBA")))
        print(f"  {prefix}: {len(names)} frames, {hex_color} @ {INTENSITY}, "
              f"{n_flame} flame texels on {names[0]}")

    print(f"\ntorch metas: {len(entries)}   _e.png written: {masks} x {len(MAT_DIRS)} dirs")
    for path in JSON_TARGETS:
        if not path.exists():
            print(f"  skip (missing) {path}")
            continue
        added, replaced = upsert(path, entries)
        print(f"  +{added} new / {replaced} replaced  {path}")


if __name__ == "__main__":
    main()
