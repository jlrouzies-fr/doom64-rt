"""Red eye emissives for the C307 demon-face wall.

C307 is a 64x64 face carved into the wall whose EYES LIGHT UP over an ANIMDEFS
sequence: C307 has them dark, C307B and C307B1 are a dim red, and B2..B5 ramp up
to a white-hot core. Not one of the seven frames had an `_e`, so in the path
tracer the eyes never lit at all -- the animation played and nothing happened.

THE MASK IS DERIVED, NOT TYPED. C307B and C307B5 are the same wall with the eyes
at their dimmest and brightest, so differencing them isolates exactly the texels
the artist animated: 40 of them, two blobs of 20, at x 19..44 / y 28..33 either
side of the face. Hand-listing a rectangle would have taken the brow ridge with
it, and a colour threshold cannot see the dim frames at all -- the eyes there are
(32,0,8), darker than plenty of the surrounding stone.

Doing it that way also means the mask cannot drift from the art: if the texture is
ever redrawn, this recomputes rather than lying.

THE `_e` CARRIES THE FRAME'S OWN COLOUR, RAW. The ray-traced path uses `_e`
directly as the emitted colour (only the rasterized path multiplies by baseColor),
so copying each frame's actual eye pixels is what preserves the ramp the artist
drew -- dim red through to white. Normalising every frame to one bright red and
moving the mult per frame would light the whole sequence evenly, which is the one
thing this texture is not.

THE ROWS ALREADY HAVE PBR AND MUST KEEP IT. Every C307 row carries
metallicDefault 1.0 / roughnessDefault 0.8, and patch_global HARD REPLACES rather
than merges -- so the existing meta is read and carried forward here. Writing just
the emissiveMult would quietly turn a metal wall into a dielectric one.

IT NEEDS ITS OWN OVERLAY. gen_world_emissives.scrub_stock_world_emis strips every
emissiveMult whose textureName is not in the authored keep set, and that set is
built from the overlay JSONs in rt/data. Without textures_c307_eyes.json listed in
_authored_emis_keep(), the next run of that generator would delete all of this
again -- silently, which is AGENTS pitfall 13.

    tools\\.venv-ai\\Scripts\\python.exe tools/gen_c307_eye_emissives.py
"""
from __future__ import annotations

import io
import json
import struct
import sys
from pathlib import Path

from PIL import Image

PROJ_ROOT = Path(__file__).resolve().parents[1]
WAD = PROJ_ROOT / "Doom64-Retribution" / "D64RTR_v15.WAD"

BUILD = PROJ_ROOT / "sourcecode" / "gzdoom-rt" / "build" / "RelWithDebInfo" / "rt"
SHIP = PROJ_ROOT / "Doom64-Retribution" / "Retribution-RT-Materials" / "rt"
MAT_DIRS = [BUILD / "mat_dev", BUILD / "mat", SHIP / "mat_dev", SHIP / "mat"]
OVERLAY = SHIP / "data" / "textures_c307_eyes.json"

# The two frames that differ ONLY in how lit the eyes are.
DIM, BRIGHT = "C307B", "C307B5"
# Every frame that should glow. C307 is deliberately absent: its eyes are drawn
# dark, and a frame the artist turned off must not be turned back on here.
LIT = ["C307B", "C307B1", "C307B2", "C307B3", "C307B4", "C307B5"]
DARK = ["C307"]

# Between CFACE's 1 and the SMON monitors' 2.8. These are 40 texels on a large
# dark wall, and the ramp itself lives in the art rather than in this number.
EMIS_MULT = 2.5


def wad_lumps(path: Path) -> dict[str, bytes]:
    d = path.read_bytes()
    n, o = struct.unpack_from("<II", d, 4)
    out: dict[str, bytes] = {}
    for i in range(n):
        off, sz, name = struct.unpack_from("<II8s", d, o + i * 16)
        nm = name.split(b"\0")[0].decode("ascii", "replace")
        if sz > 0:
            out[nm.upper()] = d[off:off + sz]
    return out


def main() -> int:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    try:
        from gen_enemy_eye_emissives import patch_global
    except ModuleNotFoundError as exc:
        raise SystemExit(
            f"{exc} -- run with the project venv: "
            r"tools\.venv-ai\Scripts\python.exe tools/gen_c307_eye_emissives.py")

    lumps = wad_lumps(WAD)
    missing = [n for n in LIT + DARK if n not in lumps]
    if missing:
        raise SystemExit(f"not in {WAD.name}: {missing}")

    def pixels(name: str):
        im = Image.open(io.BytesIO(lumps[name])).convert("RGBA")
        return im.size, list(im.get_flattened_data())

    (w, h), dim = pixels(DIM)
    _, bright = pixels(BRIGHT)
    eye = [i for i in range(len(dim)) if dim[i][:3] != bright[i][:3]]
    if not eye:
        raise SystemExit(f"{DIM} and {BRIGHT} are identical -- the mask cannot be derived")
    xs = [i % w for i in eye]
    ys = [i // w for i in eye]
    print(f"eye mask: {len(eye)} texels  x {min(xs)}..{max(xs)}  y {min(ys)}..{max(ys)}")

    # Carry the existing PBR meta forward -- patch_global replaces the whole row.
    authored = json.loads((SHIP / "data" / "textures.json").read_text(encoding="utf-8"))
    existing = {e["textureName"]: e for e in authored.get("array", [])
                if e.get("textureName", "").startswith("C307")}

    entries: dict[str, dict] = {}
    overlay_rows = []
    for name in LIT:
        _, px = pixels(name)
        out = [(0, 0, 0, 0)] * (w * h)
        for i in eye:
            r, g, b, _a = px[i]
            out[i] = (r, g, b, 255)
        img = Image.new("RGBA", (w, h))
        img.putdata(out)
        for d in MAT_DIRS:
            d.mkdir(parents=True, exist_ok=True)
            img.save(d / f"{name}_e.png")

        keep = {k: v for k, v in existing.get(name, {}).items() if k != "textureName"}
        keep.pop("emissiveMult", None)
        entries[name] = {"emissiveMult": EMIS_MULT} | keep
        overlay_rows.append({"emissiveMult": EMIS_MULT, "textureName": name})
        peak = max((px[i][:3] for i in eye), key=sum)
        print(f"  {name:<8} peak {peak}  keeps {sorted(keep)}")

    # The eyes-off frame keeps its PBR and loses any emissive, both in the meta
    # and on disk -- an _e left from an earlier run would light a dark frame.
    for name in DARK:
        keep = {k: v for k, v in existing.get(name, {}).items() if k != "textureName"}
        keep.pop("emissiveMult", None)
        entries[name] = keep
        for d in MAT_DIRS:
            stale = d / f"{name}_e.png"
            if stale.exists():
                stale.unlink()
                print(f"  removed stale {stale.parent.name}/{stale.name}")
        print(f"  {name:<8} eyes drawn dark -> no emissive")

    OVERLAY.parent.mkdir(parents=True, exist_ok=True)
    OVERLAY.write_text(
        json.dumps({"version": 0, "array": overlay_rows}, indent=2) + "\n",
        encoding="utf-8")
    patch_global(entries)
    print(f"wrote _e into {len(MAT_DIRS)} mat dirs, {OVERLAY.name}, and both textures.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
