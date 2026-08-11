"""Bake the chosen lava look into material overlays: _e, _n, _h, _orm.

The look is "halo + relief, 0.85" from tools/gen_lava_looks.py --set halo
(middle row, right column). Everything it needs is a per-texel modulation of
the flat that already exists, so none of it needs a shader: RTGL already
multiplies an _e mask by the base colour, already applies a normal map, and
already does parallax from a height map.

That is the whole design decision here. The first pass at this look replaced the
painted crust with a procedural heat ramp and was rejected on sight -- the art
carries per-crack shading, warm/cool variation between plates and hand-placed
hot spots that a mask derived from it cannot reproduce. So the albedo is never
touched. What gets written is:

  _e    GREY, so the hue comes entirely from the art the shader multiplies it
        by. Carries four things: a small crust lift, the relief shading from
        light coming OUT of the cracks, self-emission on the cracks themselves,
        and the wide halo.
  _n    relief normal. Height is 1 - crack mask, so the molten line is the LOW
        point, which is what a crack is.
  _h    the same height, for parallax.
  _orm  rough crust, smoother channels, metallic 0. Lava is not a mirror.

TWO THINGS THAT WILL BREAK THIS IF CHANGED CARELESSLY.

1. Every frame or none. HLAVA1-5 is a 5-frame ANIMDEFS ping-pong and today only
   HLAVA1 has _n/_h/_orm -- so once per cycle the surface gains a normal map and
   a heightmap (which shifts the UVs) and snaps back. That is the same trap the
   water hit; see docs/rt-water.md trap 2.

2. One normalisation for the whole sequence. _e is 8-bit, so it has to be scaled
   into 0..1 and the scale paid back through emissiveMult. Normalising each
   frame on its own max makes the brightest frame and the dimmest frame equally
   bright, i.e. the animation stops animating and starts flickering. The peak is
   taken across the whole group and applied to every member of it.

Usage:
    tools\\.venv-ai\\Scripts\\python.exe tools/gen_lava_material.py           # report
    tools\\.venv-ai\\Scripts\\python.exe tools/gen_lava_material.py --apply
    tools\\.venv-ai\\Scripts\\python.exe tools/gen_lava_material.py --revert
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gen_lava_looks import blur, crack_mask, lit_by_cracks, load_source, relief  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent

# Animation groups. Each is normalised as a unit -- see the header.
GROUPS = [
    [f"HLAVA{i}" for i in range(1, 6)],  # 5-frame ping-pong, 5 tics
    ["D64LAVA1"],  # warp2, no frame siblings
    ["D64LAVA2"],
]

# mat_dev is NOT a scratch folder: TextureOverrides.cpp looks there too
# (TEXTURES_FOLDER_DEV), so a stale overlay left in it is a live overlay. It
# already holds a frame-01-only _n/_h/_orm set for the lava, which is trap 2
# waiting to happen, so it gets written exactly like mat does.
MAT_DIRS = [
    ROOT / "Doom64-Retribution/Retribution-RT-Materials/rt/mat",
    ROOT / "Doom64-Retribution/Retribution-RT-Materials/rt/mat_dev",
    ROOT / "sourcecode/gzdoom-rt/build/RelWithDebInfo/rt/mat",
    ROOT / "sourcecode/gzdoom-rt/build/RelWithDebInfo/rt/mat_dev",
]
TEXJSON = ROOT / "sourcecode/gzdoom-rt/build/RelWithDebInfo/rt/data/textures.json"
BACKUP = ROOT / "tools/_lava_mat_backup"

SUFFIXES = ("_e.png", "_n.png", "_h.png", "_orm.png")

# --- the look, as numbers -----------------------------------------------------
# Straight out of the sweep: halo over relief at 0.85. HALO_STRENGTH is the one
# the choice was made on; the rest are the panel-7 recipe it was swept against.
HALO_STRENGTH = 0.85
HALO_RADIUS = 6
CRUST_AMBIENT = 0.10  # crust lift where no crack is near
CRUST_GAIN = 0.85  # how much the crack light brightens the crust
RELIEF_STRENGTH = 0.035
SELF_EMIT = 1.5  # the cracks are hot rock, not lit rock
SELF_EMIT_GAMMA = 1.3


def build(name: str):
    """-> (unnormalised _e, height, normal_rgb, orm_rgb)"""
    albedo, _authored_e = load_source(name)
    m = crack_mask(albedo)

    h, nx, ny = relief(m, RELIEF_STRENGTH)
    ndl, glow = lit_by_cracks(m, nx, ny)

    # The relief IS the light having a direction: without ndl this is just a
    # blurred glow mask and the plates stay flat.
    shade = glow * (0.30 + 1.7 * ndl)
    wide = blur(m, HALO_RADIUS)

    e = (
        CRUST_AMBIENT
        + CRUST_GAIN * shade
        + SELF_EMIT * (m**SELF_EMIT_GAMMA)
        + HALO_STRENGTH * wide
    )

    # Normal map, tangent space, +Z up. nx/ny already carry the strength.
    inv = 1.0 / np.sqrt(nx * nx + ny * ny + 1.0)
    normal = np.stack([nx * inv, ny * inv, inv], axis=-1) * 0.5 + 0.5

    # Rough crust, smoother where the rock has gone liquid. Metallic 0: lava is
    # not a mirror, which is the whole reason it cannot reuse the water path.
    rough = 0.85 - 0.5 * np.clip(m, 0.0, 1.0)
    orm = np.stack([np.ones_like(rough), rough, np.zeros_like(rough)], axis=-1)

    return e, h, normal, orm


def write_png(path: Path, arr: np.ndarray, as_srgb: bool = False) -> None:
    """as_srgb matters and is not cosmetic.

    TextureManager.cpp loads the five overlays with different Vulkan formats:
    albedo and _e are R8G8B8A8_SRGB, _n and _orm are UNORM, _h is R8_UNORM. So
    the _e bytes get sRGB-DECODED on sample and everything else does not. Writing
    a linear 0.14 into _e as byte 36 lands as 0.017 in the shader -- eight times
    too dark, with no error anywhere. Only _e is encoded.
    """
    a = np.clip(arr, 0.0, 1.0)
    if as_srgb:
        a = np.where(a <= 0.0031308, a * 12.92, 1.055 * a ** (1.0 / 2.4) - 0.055)
    if a.ndim == 2:
        a = np.repeat(a[..., None], 3, axis=2)
    Image.fromarray((np.clip(a, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)).save(path)


def apply(dry: bool) -> int:
    written = 0
    mults: dict[str, float] = {}

    for group in GROUPS:
        built = {n: build(n) for n in group}
        # ONE peak for the whole sequence, or the animation flickers.
        peak = max(float(e.max()) for e, _h, _n, _o in built.values())
        mult = round(peak * 1.5, 3)  # 1.5 is the emissiveMult the lava ships with

        print(f"  {'/'.join(group):28} peak _e {peak:5.2f}  -> emissiveMult {mult}")
        for name, (e, h, normal, orm) in built.items():
            mults[name] = mult
            if dry:
                continue
            for d in MAT_DIRS:
                if not d.exists():
                    continue
                write_png(d / f"{name}_e.png", e / peak, as_srgb=True)
                write_png(d / f"{name}_n.png", normal)
                write_png(d / f"{name}_h.png", h)
                write_png(d / f"{name}_orm.png", orm)
                written += 4
    return written if not dry else 0, mults


def backup(restore: bool) -> int:
    """Keep whatever shipped, so --revert is a real undo and not a regenerate."""
    n = 0
    for d in MAT_DIRS:
        if not d.exists():
            continue
        tag = BACKUP / d.parent.parent.name / d.name
        src_dir, dst_dir = (tag, d) if restore else (d, tag)
        for group in GROUPS:
            for name in group:
                for suf in SUFFIXES:
                    src = src_dir / (name + suf)
                    if not src.exists():
                        continue
                    dst_dir.mkdir(parents=True, exist_ok=True)
                    (shutil.move if restore else shutil.copy2)(str(src), str(dst_dir / src.name))
                    n += 1
    return n


MULT_BACKUP = BACKUP / "emissiveMult.json"


def patch_json(mults: dict[str, float]) -> int:
    if not TEXJSON.exists():
        print(f"  (skipped {TEXJSON.name}: not found -- build gzdoom first)")
        return 0
    data = json.loads(TEXJSON.read_text(encoding="utf-8"))
    entries = data["array"]

    # Record what shipped BEFORE the first overwrite, so --revert is an undo.
    # Without this the second --apply would record its own values as "original".
    if not MULT_BACKUP.exists():
        MULT_BACKUP.parent.mkdir(parents=True, exist_ok=True)
        MULT_BACKUP.write_text(
            json.dumps(
                {
                    e["textureName"]: e.get("emissiveMult")
                    for e in entries
                    if e.get("textureName") in mults
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    seen, changed = set(), 0
    for entry in entries:
        name = entry.get("textureName")
        if name in mults and name not in seen:
            seen.add(name)
            if entry.get("emissiveMult") != mults[name]:
                entry["emissiveMult"] = mults[name]
                changed += 1
    for name, mult in mults.items():
        if name not in seen:
            entries.append({"textureName": name, "emissiveMult": mult, "metallicDefault": 0})
            changed += 1
    TEXJSON.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return changed


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--revert", action="store_true")
    args = ap.parse_args()

    if args.revert:
        n = backup(restore=True)
        print(f"restored {n} file(s) from {BACKUP}")
        if MULT_BACKUP.exists() and TEXJSON.exists():
            old = json.loads(MULT_BACKUP.read_text(encoding="utf-8"))
            data = json.loads(TEXJSON.read_text(encoding="utf-8"))
            for e in data["array"]:
                if e.get("textureName") in old and old[e["textureName"]] is not None:
                    e["emissiveMult"] = old[e["textureName"]]
            TEXJSON.write_text(json.dumps(data, indent=2), encoding="utf-8")
            MULT_BACKUP.unlink()
            print(f"restored {len(old)} emissiveMult value(s)")
        return 0

    print(f"lava material: halo {HALO_STRENGTH} over relief {RELIEF_STRENGTH}")
    if not args.apply:
        apply(dry=True)
        print("\nPass --apply to write them.")
        return 0

    kept = backup(restore=False)
    print(f"  backed up {kept} existing file(s) to {BACKUP}")
    written, mults = apply(dry=False)
    changed = patch_json(mults)
    print(f"\n{written} overlay(s) written, {changed} textures.json entr(ies) updated.")
    print("Relaunch to see it. --revert restores what shipped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
