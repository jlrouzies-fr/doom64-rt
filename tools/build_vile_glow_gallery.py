"""Build the Arch-Vile flame-glow review gallery (an Artifact page).

WHY THIS EXISTS. The Baron family's fist glow is masked from the mod's OWN
authored brightmaps (D64RTR_BRIGHTMAPS.PK3, brightmaps/bd64/BOS2*B.png) -- the
artists already drew where the fire is, and tools/gen_hand_glow_emissives.py just
reads it. Unseen Evil ships no monster brightmaps at all: its 49 brightmap lumps
are all wall and switch textures. So for the Arch-Vile there is no authored
source saying which texels are flame, and the alternative to guessing is asking.

This page shows every BRIGHT frame of the cast, runs the flame detection LIVE at
an adjustable threshold, and lets the reviewer click to place light points. It
emits the coordinates in BOTH spaces:

  * sprite pixels, for the _e mask
  * offsets from the sprite's grAb origin, which is what an analytic light needs
    -- the same body-relative form gen_hand_light_offsets.py emits for the Baron.

DETECTION RUNS IN THE PAGE, NOT HERE. One threshold does not fit every frame:
the wind-up frames are a thin rim of fire and the peak frames are a wall of it,
so a floor that reads G correctly floods J. The page therefore carries only the
sprites, and thresholds live behind a global slider plus a per-frame override.
Keeping the detector in one place (the browser) also means there is no second
Python copy of it here to drift out of step with what the reviewer actually saw.

THE POINT OF THE OFFSETS. RTGL1 pins a sprite's attached light to the CENTRE of
the billboard quad (VulkanDevice.cpp: center = average of the 4 quad verts). The
Arch-Vile's fire is in its raised hands, so a textures.json lightIntensity lands
in its chest -- and with two hands, both average into one point between them.
That is the reported "the light doesn't match where the flames are". The fix is
one analytic light per flame, which needs a real per-frame offset, which is what
the reviewer's clicks produce.

A Doom sprite's origin is (leftoffset, topoffset) from grAb: the actor's centre
column and its FEET row. Assuming w/2 and the image bottom bakes in a per-frame
error, because these sprites are not symmetrically padded (G is 121x136 with
origin 60,136; K is 62x119 with origin 30,119).

    tools\\.venv-ai\\Scripts\\python.exe tools/build_vile_glow_gallery.py
    -> tools/vile-glow-gallery.html      (publish as an Artifact)
"""
from __future__ import annotations

import base64
import io
import json
import struct
import zipfile
from pathlib import Path

from PIL import Image

PROJ_ROOT = Path(__file__).resolve().parents[1]
PK3 = PROJ_ROOT / "Doom64-Retribution" / "d64r-ue-monsters.pk3"
OUT = PROJ_ROOT / "tools" / "vile-glow-gallery.html"

# The BRIGHT frames of the Missile state (the cast) and of Heal.
ATTACK_FRAMES = "GHIJKLMNOP"
HEAL_FRAMES = "Z[^"


def read_grab(png: bytes) -> tuple[int, int]:
    """Doom draw offset from the PNG's grAb chunk; (0,0) if absent."""
    i = 8
    while i + 8 <= len(png):
        ln, typ = struct.unpack(">I4s", png[i:i + 8])
        if typ == b"grAb":
            x, y = struct.unpack(">ii", png[i + 8:i + 16])
            return x, y
        if typ == b"IEND":
            break
        i += 12 + ln
    return 0, 0


def data_uri(im: Image.Image) -> str:
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def collect() -> list[dict]:
    z = zipfile.ZipFile(PK3)
    by_frame: dict[str, str] = {}
    for name in z.namelist():
        if not name.startswith("sprites/VILE"):
            continue
        base = name.rsplit("/", 1)[-1].split(".")[0].upper()
        if len(base) < 6:
            continue
        frame, rot = base[4], base[5]
        if frame not in ATTACK_FRAMES + HEAL_FRAMES:
            continue
        # Front rotation only: its horizontal axis IS the actor's left-right
        # axis, which is what a lateral offset means. A single-rotation frame
        # (rot 0) is the whole frame, so it wins outright.
        if rot == "0":
            by_frame[frame] = name
        elif rot == "1" and frame not in by_frame:
            by_frame[frame] = name

    out = []
    for frame in ATTACK_FRAMES + HEAL_FRAMES:
        name = by_frame.get(frame)
        if not name:
            continue
        raw = z.read(name)
        im = Image.open(io.BytesIO(raw)).convert("RGBA")
        w, h = im.size
        ox, oy = read_grab(raw)
        out.append({
            "frame": frame,
            "lump": name.rsplit("/", 1)[-1].split(".")[0].upper(),
            "w": w, "h": h, "ox": ox, "oy": oy,
            "kind": "heal" if frame in HEAL_FRAMES else "cast",
            "sprite": data_uri(im),
        })
    return out



from _vgg_page import BOOT, CSS, FONTS, SHELL


def main() -> None:
    frames = collect()
    if not frames:
        raise SystemExit("no VILE attack frames found -- build the pk3 first")

    boot = BOOT.replace("__FONTS__", json.dumps(FONTS))
    state = {"picks": {}, "floors": {}, "tuned": {}, "globalFloor": 170}
    s, e = "<" + "script", "<" + "/" + "script>"
    nl = "\n"

    # Body content only: the Artifact tool wraps this in doctype/head/body at
    # publish time. The page's own Save rebuilds a COMPLETE document from these
    # same static source elements (#css, #shell, #boot, #data) plus the new
    # state -- rendering from the page's canonical source, never by serializing
    # the live DOM, which would capture viewer-session state and the runtime's
    # own injected scripts.
    doc = nl.join([
        "<title>Arch-Vile Flame Map</title>",
        FONTS,
        '<style id="css">' + CSS + "</style>",
        '<template id="shell">' + SHELL + "</template>",
        '<div class="wrap" id="app"></div>',
        s + ' id="data" type="application/json">' + json.dumps(frames) + e,
        s + ' id="state" type="application/json">' + json.dumps(state) + e,
        s + ' id="boot">' + boot + e,
        "",
    ])
    OUT.write_text(doc, encoding="utf-8")
    print(f"{OUT.relative_to(PROJ_ROOT)}  {len(frames)} frames, "
          f"{OUT.stat().st_size / 1024:.0f} KB")
    for f in frames:
        print(f"  {f['frame']:2s} {f['lump']:10s} {f['w']:3d}x{f['h']:3d} "
              f"origin {f['ox']:3d},{f['oy']:3d}")


if __name__ == "__main__":
    main()
