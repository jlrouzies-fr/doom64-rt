"""
Fist-glow emissive masks for the Baron family (RTGL1).

Covers:
  BOS2  Hell Knight     green fists
  BOSS  Baron of Hell   red fists   ("the red hell knight")

Why this is separate from gen_enemy_eye_emissives.py:
  That script is an EYE generator. is_valid_eye_mask() rejects any mask that is
  >70 texels, taller than h/5, wider than w/2, or outside the head band. These
  monsters' glow is on the FISTS -- mid-body and wide apart -- so 39 of the 40
  living frames were rejected. The one that slipped through (BOS2F4F6) is the
  attack-windup pose, where the raised fist happens to land inside the head band
  and look eye-shaped to the validator. That accident is why exactly one frame
  glowed.

Mask source is the mod's own brightmaps (D64RTR_BRIGHTMAPS.PK3, brightmaps/bd64/
BOS2*B.png). Those exist for precisely the 40 living frames A1..H5 and for NONE
of the death frames I0..N0 -- the mod authors already drew the line, and the
death frames must stay dark because the gibs reuse the same palette ramp as the
hand glow. BOSS ships no brightmaps of its own, but it is the same artwork
palette-swapped (12/12 frames verified pixel-identical in silhouette), so the
BOS2 masks transfer.

emissiveMult alone cannot light a room -- RTGL1 only collects emission on an
indirect bounce, never through processDirectIllumination (see the rt_wall_strips
comment in rt_main.cpp). The cast light is NOT declared here: RTGL1 pins a
sprite's attached light to the centre of the billboard quad, which put the glow
in the torso and merged both fists into one point. RT_UploadHandGlowLights in
rt_main.cpp uploads one analytic sphere per fist instead
(rt_hand_light_* cvars, offsets + colour from tools/gen_hand_light_offsets.py).

Outputs (all four, or the change is inert):
  rt/mat/<FRAME>_e.png                x3  (build mat + mat_dev + shipped materials)
  rt/data/textures.json                   (live file RTGL1 actually reads)
  rt/data/textures_enemy_eyes.json        (overlay source of record)
"""

from __future__ import annotations

import io
import json
import struct
import zipfile
from pathlib import Path

from PIL import Image

# Repo root, derived from this file so a clone can live anywhere.
PROJ_ROOT = Path(__file__).resolve().parents[1]

ROOT = PROJ_ROOT
WAD = ROOT / r"Doom64-Retribution\D64RTR_v15.WAD"
BM = ROOT / r"Doom64-Retribution\D64RTR_BRIGHTMAPS.PK3"

MAT = ROOT / r"sourcecode\gzdoom-rt\build\RelWithDebInfo\rt\mat"
# mat_dev is the raw-PNG folder the dev image loader reads. gen_enemy_eye_emissives
# writes here too, and it had left a RED eye-style BOS2F4F6_e.png behind -- write the
# hand mask to all three so no stale variant can win depending on loader.
MAT_DEV = ROOT / r"sourcecode\gzdoom-rt\build\RelWithDebInfo\rt\mat_dev"
OMAT = ROOT / r"Doom64-Retribution\Retribution-RT-Materials\rt\mat"
GLOBAL = ROOT / r"sourcecode\gzdoom-rt\build\RelWithDebInfo\rt\data\textures.json"
OVERLAY = ROOT / r"Doom64-Retribution\Retribution-RT-Materials\rt\data\textures_enemy_eyes.json"

# (sprite, brightmap donor, flat tint or None)
#
# TINT is the same aesthetic override as COLOR_OVERRIDE in gen_hand_light_offsets.py and
# must agree with it, or the fists render a different colour from the light they cast.
#
# BOSS is pinned: per-texel saturation of its albedo yields orange, because normalising a
# dark red average (93,28,2) to peak 255 scales GREEN by the same 2.7x as red. The art is
# red; only the normalisation made it orange.
#
# BOS2 is left None (per-texel hue): green dominates its ramp hard enough that normalising
# cannot shift the hue, and the sampled result was accepted in play.
MONSTERS = [
    ("BOS2", "BOS2", None),
    ("BOSS", "BOS2", (0xE0, 0x10, 0x00)),
]

# How bright the fists RENDER. Doubled from the 2.0 enemy-glow house value on request.
# This cannot change how much they light the room -- that is rt_hand_light_intensity.
EMISSIVE_MULT = 4.0

# The cast light is no longer declared in textures.json; strip any that a previous run
# wrote, or the old billboard-centre light stacks on top of the new per-fist ones.
LIGHT_KEYS = ("lightIntensity", "lightColorHEX", "lightEvenOnDynamic")


def wad_lumps() -> dict[str, bytes]:
    d = WAD.read_bytes()
    n, o = struct.unpack_from("<II", d, 4)
    out: dict[str, bytes] = {}
    for i in range(n):
        off, sz, name = struct.unpack_from("<II8s", d, o + i * 16)
        nm = name.split(b"\0")[0].decode("ascii", "replace")
        if sz > 0:
            out[nm] = d[off : off + sz]
    return out


def brightmaps(prefix: str) -> dict[str, bytes]:
    out: dict[str, bytes] = {}
    with zipfile.ZipFile(BM) as z:
        for info in z.infolist():
            stem = Path(info.filename).stem.upper()
            if stem.startswith(prefix):
                out[stem] = z.read(info)
    return out


def build_mask(
    bm_img: Image.Image, albedo: Image.Image, tint: tuple[int, int, int] | None
) -> tuple[Image.Image, int]:
    """Brightmap + albedo -> _e image, and the peak channel actually written.

    Intensity always comes from the brightmap ramp. Colour is either a flat tint or the
    texel's own hue saturated to full range -- never the raw albedo, because RsWorld.inl
    multiplies by baseColor again and squaring dark art annihilates the glow.
    """
    m = bm_img.convert("RGBA")
    if m.size != albedo.size:
        m = m.resize(albedo.size, Image.Resampling.NEAREST)
    ap = list(albedo.convert("RGBA").get_flattened_data())

    pixels: list[tuple[int, int, int, int]] = []
    peak = 0
    for i, (r, g, b, a) in enumerate(m.get_flattened_data()):
        lum = max(r, g, b)
        # Unlit in the brightmap, or mask bleeding over transparent canvas.
        if a < 24 or lum < 40 or ap[i][3] < 20:
            pixels.append((0, 0, 0, 0))
            continue
        t = min(1.0, lum / 220.0)
        if tint is not None:
            sr, sg, sb = tint
            k = t
        else:
            sr, sg, sb, _ = ap[i]
            p = max(sr, sg, sb)
            k = (255.0 / p) * t if p else 0.0
        px = (min(255, int(sr * k)), min(255, int(sg * k)), min(255, int(sb * k)), 255)
        peak = max(peak, px[0], px[1], px[2])
        pixels.append(px)

    out = Image.new("RGBA", albedo.size)
    out.putdata(pixels)
    return out, peak


def upsert(entries: list[dict], name: str, payload: dict) -> None:
    for e in entries:
        if e.get("textureName") == name:
            e.update(payload)
            # dict.update alone would leave a previously written lightIntensity in place,
            # stacking the torso light this design exists to remove.
            for k in LIGHT_KEYS:
                e.pop(k, None)
            return
    entries.append({"textureName": name, **payload})


def main() -> None:
    lumps = wad_lumps()
    written: list[str] = []

    for sprite, donor, tint in MONSTERS:
        bms = brightmaps(donor)
        label = f"{sprite} (mask from {donor}, {'flat %02x%02x%02x' % tint if tint else 'per-texel hue'})"
        print(f"=== {label} ===")
        count = 0
        peak_seen = 0

        for stem in sorted(bms):
            frame = stem[:-1] if stem.endswith("B") else stem  # BOS2A1B -> BOS2A1
            tex = sprite + frame[len(donor) :]  # retarget donor mask onto this sprite
            if tex not in lumps:
                print(f"  SKIP {tex}: no sprite lump")
                continue

            albedo = Image.open(io.BytesIO(lumps[tex])).convert("RGBA")
            e_img, peak = build_mask(Image.open(io.BytesIO(bms[stem])), albedo, tint)
            if peak == 0:
                print(f"  SKIP {tex}: mask empty after albedo gate")
                continue

            for d in (MAT, MAT_DEV, OMAT):
                d.mkdir(parents=True, exist_ok=True)
                e_img.save(d / f"{tex}_e.png")

            written.append(tex)
            peak_seen = max(peak_seen, peak)
            count += 1

        # A mask that never reaches its intended range is the bug this generator exists to
        # avoid. The target is the tint's own peak, not a blanket 255: a deliberately deep
        # tint like the Baron's e01000 tops out at 224 by design.
        target = max(tint) if tint is not None else 255
        if count and peak_seen < target:
            raise SystemExit(
                f"{sprite}: masks peak at {peak_seen}, expected {target} — would render dim"
            )
        print(f"  {count} frame(s), peak channel {peak_seen}/{target}\n")

    if not written:
        raise SystemExit("no frames written — aborting before touching json")

    payload = {"emissiveMult": EMISSIVE_MULT}
    for path in (GLOBAL, OVERLAY):
        doc = json.loads(path.read_text(encoding="utf-8"))
        for tex in written:
            upsert(doc["array"], tex, dict(payload))
        path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
        print(f"updated {path}")

    print(f"\n{len(written)} frames glow; death frames untouched. Cast light is engine-side.")


if __name__ == "__main__":
    main()
