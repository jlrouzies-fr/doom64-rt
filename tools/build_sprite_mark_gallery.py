"""Build the Unseen Evil sprite-marking gallery (an Artifact page).

Two jobs the art cannot answer on its own, in one page:

  EYES for the Arch-Vile, Revenant and Spider Mastermind. Retribution's own eye
  masks come from its authored brightmaps (tools/gen_enemy_eye_emissives.py);
  Unseen Evil ships none, so the eyes have to be found by colour instead. That
  IS viable here -- SKELA1's eyes are 4 texels of pure (128,0,0) in the head
  band, well clear of the body -- but the threshold has to be seen to be
  trusted, and it differs per monster.

  MUZZLE BARRELS for the Chaingunner. Colour cannot find these at all: the
  firing frame's flash is painted into the sprite and bleeds across the whole
  torso (118 saturated texels on CPOSF1), so where the two barrel ends actually
  are is a judgement call. Those get clicked.

WHY THE PAGE JUDGES, NOT JUST HIGHLIGHTS. Every candidate blob is run through
the same rules the project already uses for eyes -- is_valid_eye_mask: 2..70
texels, no taller than h/5, no wider than w/2, centred inside the top 55% of the
OPAQUE body box. Accepted blobs draw cyan, rejected ones grey. A threshold that
lights the whole torso then reads as "one huge rejected blob" rather than as
nothing at all, which is the difference between tuning it and giving up on it.

FRAMES ARE THE LIVING ONES ONLY. Death and gib frames are excluded per monster
by hand below: the gore on these sprites reuses the same palette ramp as the
eyes, so a threshold that is right for a face lights a corpse. That is exactly
why gen_hand_glow_emissives keeps the Baron's I..N out of its table.

    tools\\.venv-ai\\Scripts\\python.exe tools/build_sprite_mark_gallery.py
    -> tools/sprite-mark-gallery.html      (publish as an Artifact)
"""
from __future__ import annotations

import base64
import io
import json
import struct
import zipfile
from pathlib import Path

from PIL import Image

from _smg_page import BOOT, CSS, FONTS, SHELL

PROJ_ROOT = Path(__file__).resolve().parents[1]
PK3 = PROJ_ROOT / "Doom64-Retribution" / "d64r-ue-monsters.pk3"
OUT = PROJ_ROOT / "tools" / "sprite-mark-gallery.html"

# Living frames only -- see the module docstring. Derived from each actor's own
# state table in tools/d64r-ue-monsters/d64rue/monsters.zs.
SECTIONS = [
    {
        "id": "vile-eyes", "sprite": "VILE", "mode": "eyes",
        "title": "Arch-Vile — eyes",
        "blurb": "Walk A–F, cast G–Q, heal Z–^. Death R–Y is excluded: its gore "
                 "reuses the eye ramp.",
        "frames": "ABCDEFGHIJKLMNOPQZ[^",
        "floor": 110, "sat": 45,
    },
    {
        "id": "skel-eyes", "sprite": "SKEL", "mode": "eyes",
        "title": "Revenant — eyes",
        "blurb": "Walk A–F, melee G–I, missile J–K. Its eyes sample as pure red "
                 "(128,0,0), 4 texels on the front idle frame.",
        "frames": "ABCDEFGHIJK",
        "floor": 100, "sat": 60,
    },
    {
        "id": "spid-eyes", "sprite": "SPID", "mode": "eyes",
        "title": "Spider Mastermind — eyes",
        "blurb": "Walk A–F, fire G–H, spawn Z. Death I–S excluded. The head band "
                 "is measured off the opaque body, which matters on a sprite this wide.",
        "frames": "ABCDEFGHZ",
        "floor": 110, "sat": 45,
    },
    {
        "id": "cpos-muzzle", "sprite": "CPOS", "mode": "points",
        "title": "Chaingunner — muzzle and glow",
        "blurb": "Living frames A-G. E and F are the firing pair -- paint the two "
                 "barrel ends there for the muzzle flash positions.",
        "frames": "ABCDEFG",
        "floor": 0, "sat": 0,
    },
]


def read_grab(png: bytes) -> tuple[int, int]:
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


def data_uri(raw: bytes) -> str:
    return "data:image/png;base64," + base64.b64encode(raw).decode("ascii")


def lump_frames(name: str, sprite: str) -> list[tuple[str, str]]:
    """(frame, rotation) pairs a lump serves.

    A Doom sprite lump can serve TWO frames: VILEA2D8 is frame A rotation 2 AND
    frame D rotation 8, one image the engine flips. So a lump must appear in the
    page exactly ONCE even though two frames use it -- listing it under both
    would give the second card the same element key as the first, and painting
    one would silently stop updating the other.
    """
    rest = name[len(sprite):]
    out = []
    if len(rest) >= 2:
        out.append((rest[0], rest[1]))
    if len(rest) >= 4:
        out.append((rest[2], rest[3]))
    return [(f, r) for f, r in out if r in "012345678"]


def collect() -> list[dict]:
    z = zipfile.ZipFile(PK3)
    raws = {n.rsplit("/", 1)[-1].split(".")[0].upper(): n
            for n in z.namelist() if n.startswith("sprites/")}

    out = []
    for sec in SECTIONS:
        sprite, alive = sec["sprite"], sec["frames"]
        # lump -> the frames it serves, restricted to the living ones
        serves: dict[str, list[str]] = {}
        for name in sorted(raws):
            if not name.startswith(sprite):
                continue
            fr = [f for f, _r in lump_frames(name, sprite) if f in alive]
            if fr:
                serves[name] = sorted(set(fr))

        # Each lump is filed under the FIRST living frame it serves, so it is
        # drawn once; the card says if a second frame shares it.
        groups: dict[str, list[dict]] = {}
        for name, frames in serves.items():
            raw = z.read(raws[name])
            im = Image.open(io.BytesIO(raw))
            ox, oy = read_grab(raw)
            groups.setdefault(frames[0], []).append({
                "lump": name, "w": im.size[0], "h": im.size[1],
                "ox": ox, "oy": oy, "shared": frames[1:], "sprite": data_uri(raw),
            })

        ordered = []
        for frame in alive:
            if frame in groups:
                ordered.append({"frame": frame,
                                "lumps": sorted(groups[frame], key=lambda d: d["lump"])})
        out.append({"id": sec["id"], "sprite": sprite, "title": sec["title"],
                    "blurb": sec["blurb"], "groups": ordered})
    return out


def main() -> None:
    sections = collect()
    boot = BOOT.replace("__FONTS__", json.dumps(FONTS))
    # SEED FROM THE COMMITTED GENERATOR, not from an empty dict. The page saves
    # into the artifact, but the artifact is not the record -- the generator is,
    # and a republish from this file would otherwise wipe what was drawn. (It
    # did once.) Anything already accepted into gen_vile_glow_emissives.EYES
    # reloads here, so painting continues from where it stopped.
    seed: dict[str, list[int]] = {}
    try:
        from gen_vile_glow_emissives import EYES
        seed.update({k: list(v) for k, v in EYES.items()})
    except Exception as exc:                       # generator absent or mid-edit
        print(f"  (no eye seed: {exc})")
    state = {"masks": seed}
    s, e = "<" + "script", "<" + "/" + "script>"
    nl = "\n"

    # Body content only: the Artifact tool wraps this in doctype/head/body. The
    # page's own Save rebuilds a COMPLETE document from these same static source
    # elements plus the new state -- never by serializing the live DOM.
    OUT.write_text(nl.join([
        "<title>Unseen Evil Emissive Masks</title>",
        FONTS,
        '<style id="css">' + CSS + "</style>",
        '<template id="shell">' + SHELL + "</template>",
        '<div class="wrap" id="app"></div>',
        s + ' id="data" type="application/json">' + json.dumps(sections) + e,
        s + ' id="state" type="application/json">' + json.dumps(state) + e,
        s + ' id="boot">' + boot + e,
        "",
    ]), encoding="utf-8")

    print(f"{OUT.relative_to(PROJ_ROOT)}  {OUT.stat().st_size / 1024:.0f} KB")
    for sec in sections:
        n = sum(len(g["lumps"]) for g in sec["groups"])
        print(f"  {sec['sprite']:5s} {len(sec['groups']):3d} frames  {n:4d} lumps")


if __name__ == "__main__":
    main()
