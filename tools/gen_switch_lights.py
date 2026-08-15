"""Emit the switch-face light table for RT_UploadSwitchLights (rt_main.cpp).

Doom 64 Retribution's switches light up when thrown: SWXC's demon face gains red eyes,
SWXSG's panel gains a pink gem. Under RTGL1 an emissive surface is not a light source
(see rt_wall_strips), so tools/gen_world_emissives.py makes those eyes GLOW and they
still light nothing. This table is the other half: one analytic light per lit switch
face, so a thrown switch actually reddens the wall it is set into.

WHERE THE NUMBERS COME FROM
---------------------------
Nothing here is authored. Every row is measured from the `_e.png` mask that
gen_world_emissives.py already wrote for that texture, which is itself derived from the
mod's own artwork. So the cast light cannot disagree with the on-screen glow: they are
the same texels.

  position  centroid of the lit texels, in texel space, from the top-left of the texture
  colour    saturation-normalised average of those texels (same treatment as
            RT_HAND_COLOR in gen_hand_light_offsets.py)
  weight    lit texel count, so the engine can scale a 7-texel pair of eyes differently
            from a 40-texel gem without a second table

Using the mask centroid rather than the switch patch's centre is deliberate and is what
makes "centre of the switch face" cheap: it is one point per texture, needs no TEXTURES
parsing at runtime, and it already sits on the lit part rather than the middle of a
mostly-dark plate.

BOTH FORMS ARE IN THE TABLE. A switch face exists as a bare 32x32 texture AND stamped
into CMPSW* wall panels, and the engine names whichever one the mapper used — 41 bare
uses against 54 composite ones for SWXC alone. Emitting only the patches is precisely
the bug this table's sibling fix repaired (see fea95ec).

WHICH FRAME IS "ON" IS NOT THE LETTER. SWXC lights on B; SWXCL and SWXCKL light on A —
their eyes go OUT when pressed. The mask set is the authority: a texture has an `_e`
only if that frame is the lit one, so walking rt/mat gets this right for free and a
letter rule would light two families backwards.

Output: sourcecode/gzdoom-rt/src/common/rendering/rt/rt_switch_lights.h
Run gen_world_emissives.py FIRST — this reads the masks it writes.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from PIL import Image

# Repo root, derived from this file so a clone can live anywhere.
PROJ_ROOT = Path(__file__).resolve().parents[1]

ROOT = PROJ_ROOT
MAT = ROOT / r"sourcecode\gzdoom-rt\build\RelWithDebInfo\rt\mat"
OVERLAY = ROOT / r"Doom64-Retribution\Retribution-RT-Materials\rt\data\textures_world_emis.json"
OUT = ROOT / r"sourcecode\gzdoom-rt\src\common\rendering\rt\rt_switch_lights.h"

# The lit frames, by patch. Mirrors SWITCH_ON_EMIS in gen_world_emissives.py — the two
# must agree, because that tool writes the masks this one measures. Note the A-forms.
LIT_PATCHES = {
    "SWXCB",    # demon face      — eyes red when ON
    "SWXCKB",
    "SWXCKLA",  # INVERTED: lit on A, dark when pressed
    "SWXCLA",   # INVERTED: lit on A, dark when pressed
    "SWXS4B",
    "SWXSAB",
    "SWXSCB",
    "SWXSDB",
    "SWXSEB",
    "SWXSFB",
    "SWXSGB",   # panel gem, not eyes
}

# A composite is one of ours if it carries a mask and its name is CMPSW<nn><A|B>. The
# composite masks are produced only by the switch expansion in gen_world_emissives.py,
# so their existence already means "this panel embeds a lit switch".
COMPOSITE_RE = re.compile(r"^CMPSW\d+[AB]$", re.I)


def lit_texels(img: Image.Image) -> list[tuple[int, int, tuple[int, int, int]]]:
    px = img.convert("RGBA").load()
    out = []
    for y in range(img.height):
        for x in range(img.width):
            r, g, b, a = px[x, y]
            if a > 0 and (r or g or b):
                out.append((x, y, (r, g, b)))
    return out


def normalised_hex(texels: list[tuple[int, int, tuple[int, int, int]]]) -> str:
    """Average the lit colour, then lift to full saturation.

    Same reasoning as the fist lights: an average taken over a dim ramp is dim, and a dim
    light colour under a path tracer reads as grey rather than as red. The HUE is the
    measurement; the level belongs to the intensity cvar.
    """
    n = len(texels)
    r = sum(t[2][0] for t in texels) / n
    g = sum(t[2][1] for t in texels) / n
    b = sum(t[2][2] for t in texels) / n
    m = max(r, g, b)
    if m <= 0:
        return "ffffff"
    k = 255.0 / m
    return f"{int(min(255, r * k)):02x}{int(min(255, g * k)):02x}{int(min(255, b * k)):02x}"


def main() -> None:
    if not MAT.exists():
        raise SystemExit(f"missing {MAT} — run gen_world_emissives.py first")

    allowed = set()
    if OVERLAY.exists():
        for e in json.loads(OVERLAY.read_text(encoding="utf-8")).get("array", []):
            allowed.add(str(e.get("textureName", "")).upper())

    rows = []
    for p in sorted(MAT.glob("*_e.png")):
        name = p.name[: -len("_e.png")].upper()
        if name not in LIT_PATCHES and not COMPOSITE_RE.match(name):
            continue
        if COMPOSITE_RE.match(name) and name not in allowed:
            # A CMPSW mask that the emissive overlay does not vouch for is not ours.
            continue
        img = Image.open(p)
        tex = lit_texels(img)
        if not tex:
            continue
        cx = sum(t[0] for t in tex) / len(tex) + 0.5
        cy = sum(t[1] for t in tex) / len(tex) + 0.5
        rows.append((name, img.width, img.height, cx, cy, len(tex), normalised_hex(tex)))

    if not rows:
        raise SystemExit("no switch masks found — did gen_world_emissives.py run?")

    lines = [
        "// GENERATED by tools/gen_switch_lights.py — do not edit by hand.",
        "//",
        "// One row per LIT switch face: the bare 32x32 patch and every CMPSW* wall panel",
        "// that stamps it. Position is the centroid of the texture's own emissive mask in",
        "// TEXEL space from the top-left; colour is that mask's hue at full saturation, so",
        "// the cast light and the on-screen glow are measured from the same pixels.",
        "//",
        "// `lit` is the mask's texel count: a pair of eyes is ~7, a panel gem ~40. The",
        "// engine uses it to scale intensity, so one cvar covers both without a per-family",
        "// table to keep in step.",
        "//",
        "// Which frame is lit is NOT the A/B letter — SWXCL and SWXCKL light on A. The rows",
        "// come from which textures actually have a mask, so that is handled by construction.",
        "#pragma once",
        "",
        "struct RtSwitchLight",
        "{",
        "    const char* tex;   // texture name as the engine sees it, UPPERCASE",
        "    float       tw, th; // texture size in texels",
        "    float       cx, cy; // lit centroid, texels from the TOP-left",
        "    int         lit;    // lit texel count",
        "    unsigned    rgb;    // 0xRRGGBB",
        "};",
        "",
        f"constexpr int RT_SWITCH_LIGHT_COUNT = {len(rows)};",
        "",
        "constexpr RtSwitchLight RT_SWITCH_LIGHTS[ RT_SWITCH_LIGHT_COUNT ] = {",
    ]
    for name, w, h, cx, cy, lit, hexcol in rows:
        lines.append(
            f'    {{ "{name}", {w}.f, {h}.f, {cx:.2f}f, {cy:.2f}f, {lit}, 0x{hexcol}u }},'
        )
    lines += ["};", ""]

    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {OUT}  ({len(rows)} rows)")
    fam = {}
    for name, *_rest in rows:
        key = "CMPSW*" if COMPOSITE_RE.match(name) else name
        fam[key] = fam.get(key, 0) + 1
    print("   ", fam)


if __name__ == "__main__":
    main()
