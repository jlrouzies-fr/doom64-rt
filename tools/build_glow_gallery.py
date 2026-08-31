"""Build the Unseen Evil glow-detection gallery (an Artifact page).

Three monsters whose emissives CAN be found by colour, unlike the Arch-Vile's
eyes, which had to be painted (tools/build_sprite_mark_gallery.py). Measured
before this was written, on the shipped sprites:

  CHAINGUNNER   green back lines cluster at (24,72,0) and appear ONLY on
                rotations 4/5/6 -- the rear views, which is where his back is.
                The muzzle runs cool white (216,216,240) to violet (192,168,240)
                and lands almost entirely on CPOSF, the firing frame.

  MASTERMIND    eyes 13..26 texels on the front rotations of the walk; the guns
                light up on H -- 1187 texels on H1, 844 on H2H8.

  REVENANT      eye dots are 1..4 texels on nearly every frame; the launcher
                elements light on J -- 82 on J1, 34 on J2, 25 on J8.

PURITY, NOT HUE, IS THE DISCRIMINATOR, and getting this wrong is the whole trap:
a plain "reddish" test (r>=140, r-g>=60, r-b>=60) matches 425..2922 texels per
Mastermind frame, which is its red-brown BODY. Requiring green and blue both
under a cap gives the numbers above. The `cap` slider therefore does more work
than `level`.

ONE FAMILY CAN MEAN TWO THINGS. The Mastermind's eyes and its firing parts are
the same red, told apart by which frame they appear on, not by colour -- so they
are one family here and the generator splits them by frame. Same for the
Revenant's eye dots and its launchers on J.

LIVING FRAMES ONLY, per monster. Death and gib frames reuse the same palette
ramps, so a threshold that is right for an eye lights a corpse -- the reason
gen_hand_glow_emissives keeps the Baron's I..N out of its table.

    tools\\.venv-ai\\Scripts\\python.exe tools/build_glow_gallery.py
    -> tools/glow-gallery.html      (publish as an Artifact)
"""
from __future__ import annotations

import base64
import io
import json
import zipfile
from pathlib import Path

from PIL import Image

from _cpg_page import BOOT, CSS, FONTS, SHELL

PROJ_ROOT = Path(__file__).resolve().parents[1]
PK3 = PROJ_ROOT / "Doom64-Retribution" / "d64r-ue-monsters.pk3"
OUT = PROJ_ROOT / "tools" / "glow-gallery.html"

# Slider ranges per rule kind. `cap` leads on the pure rules because it is the
# term that separates a glow from flesh.
PURE = {
    "cap": {"name": "Cap g/b", "min": 5, "max": 120},
    "level": {"name": "Min level", "min": 60, "max": 240},
}
DOMINANT = {
    "level": {"name": "Min level", "min": 30, "max": 200},
    "sep": {"name": "Separation", "min": 5, "max": 90},
}
COOL = {
    "bright": {"name": "Min bright", "min": 120, "max": 255},
    "floor": {"name": "Min channel", "min": 30, "max": 200},
    "cool": {"name": "Blue over red", "min": -60, "max": 40},
}

SECTIONS = [
    {
        "id": "cpos", "sprite": "CPOS", "title": "Chaingunner", "frames": "ABCDEFG",
        "blurb": "Green lines on his back — rear rotations 4/5/6 only. The muzzle is the "
                 "white-to-violet flash on the F frame, which never lit because no CPOS "
                 "sprite had an _e at all.",
        "families": [
            {"id": "green", "label": "Green", "kind": "dominant", "ch": "g",
             "color": "--grn", "params": {"level": 70, "sep": 25}, "sliders": DOMINANT},
            {"id": "muzzle", "label": "Muzzle", "kind": "cool",
             "color": "--mzl", "params": {"bright": 190, "floor": 90, "cool": -20},
             "sliders": COOL},
        ],
    },
    {
        "id": "spid", "sprite": "SPID", "title": "Spider Mastermind", "frames": "ABCDEFGHZ",
        "blurb": "Eyes on the front rotations of the walk (13–26 texels); the firing parts "
                 "light up on H — 1187 texels on H1. Same red, split by frame.",
        "families": [
            {"id": "red", "label": "Red", "kind": "pure", "ch": "r",
             "color": "--red", "params": {"level": 120, "cap": 40}, "sliders": PURE},
        ],
    },
    {
        "id": "skel", "sprite": "SKEL", "title": "Revenant", "frames": "ABCDEFGHIJK",
        "blurb": "Eye dots are 1–4 texels on nearly every frame; the launcher elements "
                 "light on J — 82 texels on J1. Same red, split by frame.",
        "families": [
            {"id": "red", "label": "Red", "kind": "pure", "ch": "r",
             "color": "--red", "params": {"level": 120, "cap": 40}, "sliders": PURE},
        ],
    },
]


def data_uri(raw: bytes) -> str:
    return "data:image/png;base64," + base64.b64encode(raw).decode("ascii")


def collect() -> list[dict]:
    z = zipfile.ZipFile(PK3)
    raws = {}
    for n in z.namelist():
        if not n.startswith("sprites/"):
            continue
        raws[n.rsplit("/", 1)[-1].split(".")[0].upper()] = n

    out = []
    for sec in SECTIONS:
        sprite, alive = sec["sprite"], sec["frames"]
        frames = []
        for name in sorted(raws):
            if not name.startswith(sprite):
                continue
            rest = name[len(sprite):]
            # A lump can serve two frames (SPIDA1D1 is A rot 1 and D rot 1), so
            # both positions are checked -- and it is emitted ONCE.
            served = []
            if len(rest) >= 2:
                served.append(rest[0])
            if len(rest) >= 4:
                served.append(rest[2])
            if not any(f in alive for f in served):
                continue
            raw = z.read(raws[name])
            im = Image.open(io.BytesIO(raw))
            frames.append({"lump": name, "w": im.size[0], "h": im.size[1],
                           "sprite": data_uri(raw)})
        out.append({**{k: v for k, v in sec.items() if k != "frames"}, "frames": frames})
    return out


def main() -> None:
    sections = collect()
    boot = BOOT.replace("__FONTS__", json.dumps(FONTS))
    s, e = "<" + "script", "<" + "/" + "script>"
    nl = "\n"

    # Body content only: the Artifact tool wraps this in doctype/head/body. The
    # page's own Save rebuilds a complete document from these same static source
    # elements plus the new state -- never by serializing the live DOM.
    OUT.write_text(nl.join([
        "<title>Unseen Evil Glow Families</title>",
        FONTS,
        '<style id="css">' + CSS + "</style>",
        '<template id="shell">' + SHELL + "</template>",
        '<div class="wrap" id="app"></div>',
        s + ' id="data" type="application/json">' + json.dumps(sections) + e,
        s + ' id="state" type="application/json">' + json.dumps({"t": {}}) + e,
        s + ' id="boot">' + boot + e,
        "",
    ]), encoding="utf-8")

    print(f"{OUT.relative_to(PROJ_ROOT)}  {OUT.stat().st_size / 1024:.0f} KB")
    for sec in sections:
        fams = " + ".join(f["label"] for f in sec["families"])
        print(f"  {sec['sprite']:5s} {len(sec['frames']):3d} lumps   {fams}")


if __name__ == "__main__":
    main()
