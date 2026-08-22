"""Give the SMONF indicator panels a real light, the way Retribution wires the rest.

WHY A LIGHT THING AND NOT A BRIGHTER TEXTURE. The panel's `_e` mask covers 111-157
texels of a 64x64 tile -- about 3%. A path tracer will happily bounce light off it,
which is the faint blue glow that IS visible, but an emitter that small cannot light
a room by radiance alone without looking blown out. `rt_emis_mapboost` can force it,
but that uniform is GLOBAL to every emissive in the game: at 2000 the panel reads
right and everything else in the level is ruined. Reported 2026-08-22.

Retribution already solved this everywhere else: a 9801/9802 light thing a few units
off the panel face, never texture metadata. Measured over the WAD, SMONAA is 88/88
wired that way, SMONDA 25/27, SMONCA 19/21, SMONEA 6/6 -- but SMONF was skipped, and
only 13 of its 125 walls game-wide have a light near them. This adds the missing ones.

WHAT IT PLACES. PointLightPulse (9801), not PointLightFlicker (9802):

  * The SMONF art is a smooth ramp -- the bulb fades up F1->F4 and back down, a
    PULSE. 9802 Flicker is binary, re-rolled every tic (a_dynlight.cpp), which is
    the TV-static look the SMONB panels want and this one does not.
  * FDynamicLight::Activate reads `specialf1 / TICRATE` as the pulse period in
    seconds, and specialf1 is the thing's ANGLE in degrees. Our re-timed blink is
    25 tics (tools/fix_smon_emissives.py), so angle=25 gives 25/35 s -- the light
    breathes on the same period as the texture it sits on.
  * Radii 20 and 16. Kept inside 16-20 deliberately: past rt_dynlight_rsoft a
    LARGER radius is DIMMER, so a big number here would darken the fixture and can
    invert the pulse. Radius is falloff, not brightness.
  * Colour 50,80,255 -- the blue of the repaired mask, so the bounce matches the
    surface it comes off rather than announcing itself as a separate effect.

PLACEMENT. The panel is an UPPER texture on a two-sided line (MAP06 sector 152:
`texturetop = "SMONF1"`), so it hangs from the ceiling of the sector you view it
from, not from the floor. The bulb's centroid measured 20 texels down from the top
of the tile, so the light sits at (top of the texture's span) - 20, pushed 8 units
off the face along the sidedef's outward normal. Thing `height` is UDMF's offset
above that sector's floor, so it is written as Z - heightfloor.

LAYERING. Maps already carried by d64r-seqlight-fix.wad are read FROM it, not from
the stock WAD -- it loads earlier and would otherwise hand back the un-patched map,
the same trap documented in tools/make_seqlight_fix.py. Everything else comes from
D64RTR_v15.WAD.

  python tools/add_smonf_lights.py --dry-run   # report placements, write nothing
  python tools/add_smonf_lights.py             # build the wad
"""

from __future__ import annotations

import math
import re
import struct
import sys
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from make_map_3dfloor_rtfix import (
    decode_textmap,
    is_map_marker,
    map_lump_range,
    read_wad_lumps,
    write_wad,
)

PROJ_ROOT = Path(__file__).resolve().parents[1]
WAD = PROJ_ROOT / r"Doom64-Retribution\D64RTR_v15.WAD"
SEQL = PROJ_ROOT / r"Doom64-Retribution\d64r-seqlight-fix.wad"
OUTWAD = PROJ_ROOT / r"Doom64-Retribution\d64r-smonf-lights.wad"

LIGHT_TYPE = 9801          # PointLightPulse
LIGHT_ANGLE = 25           # pulse period in tics; matches the re-timed blink
# 50% more saturated than the first pass's (50,80,255): pulling R and G down is
# what saturates a blue, since saturation is (max-min)/max and blue is already
# pinned at 255. Requested 2026-08-22.
LIGHT_RGB = (25, 40, 255)
LIGHT_R1 = 20              # see rt_dynlight_rsoft -- bigger is DIMMER, keep 16..20
LIGHT_R2 = 16
FACE_OFFSET = 8.0          # units off the wall face
BULB_FROM_TOP = 20.0       # measured centroid of the lit texels
NEAR_EXISTING = 96.0       # skip a wall that already has a light this close

LIGHT_TYPES = {"9800", "9801", "9802", "9803", "9804"}


def blocks(text: str, kind: str) -> list[tuple[dict, re.Match]]:
    out = []
    for m in re.finditer(r"(?ms)^" + kind + r"\s*\{(.*?)\}", text):
        d = {}
        for kv in re.finditer(
            r'(\w+)\s*=\s*("(?:[^"\\]|\\.)*"|-?[0-9]+\.?[0-9]*|true|false);', m.group(1)
        ):
            k, v = kv.group(1), kv.group(2)
            d[k] = v[1:-1] if v.startswith('"') else v
        out.append((d, m))
    return out


def fnum(d: dict, key: str, dflt: float = 0.0) -> float:
    try:
        return float(d[key])
    except (KeyError, TypeError, ValueError):
        return dflt


def seg_dist(px, py, x1, y1, x2, y2) -> float:
    dx, dy = x2 - x1, y2 - y1
    L = dx * dx + dy * dy
    t = 0.0 if L == 0 else max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / L))
    return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))


def thing_block(x: float, y: float, height: float) -> str:
    r, g, b = LIGHT_RGB
    return (
        "thing\n{\n"
        f"x = {x:.3f};\n"
        f"y = {y:.3f};\n"
        f"height = {height:.3f};\n"
        f"angle = {LIGHT_ANGLE};\n"
        f"type = {LIGHT_TYPE};\n"
        f"arg0 = {r};\narg1 = {g};\narg2 = {b};\n"
        f"arg3 = {LIGHT_R1};\narg4 = {LIGHT_R2};\n"
        # Without the skill/class/mode flags a UDMF thing spawns in NO game mode.
        # Cloned from Retribution's own 9802 blocks rather than invented.
        "skill1 = true;\nskill2 = true;\nskill3 = true;\nskill4 = true;\nskill5 = true;\n"
        "single = true;\ncoop = true;\n"
        "class1 = true;\nclass2 = true;\nclass3 = true;\nclass4 = true;\nclass5 = true;\n"
        "}\n"
    )


def plan_for_map(text: str) -> tuple[list[tuple[float, float, float, str]], list[str]]:
    """Return (placements, notes). Placement = (x, y, height, why)."""
    sides = blocks(text, "sidedef")
    lines = blocks(text, "linedef")
    verts = blocks(text, "vertex")
    secs = blocks(text, "sector")
    things = blocks(text, "thing")

    existing = [
        (fnum(t, "x"), fnum(t, "y"))
        for t, _ in things
        if str(t.get("type")) in LIGHT_TYPES
    ]

    out: list[tuple[float, float, float, str]] = []
    notes: list[str] = []

    for li, (ld, _) in enumerate(lines):
        for key, slotsign in (("sidefront", 1.0), ("sideback", -1.0)):
            si = ld.get(key)
            if si is None:
                continue
            sd = sides[int(si)][0]
            slot = None
            for s in ("texturetop", "texturemiddle", "texturebottom"):
                if str(sd.get(s, "")).upper().startswith("SMONF"):
                    slot = s
                    break
            if slot is None:
                continue

            v1 = verts[int(ld["v1"])][0]
            v2 = verts[int(ld["v2"])][0]
            x1, y1 = fnum(v1, "x"), fnum(v1, "y")
            x2, y2 = fnum(v2, "x"), fnum(v2, "y")
            mx, my = (x1 + x2) / 2, (y1 + y2) / 2
            dx, dy = x2 - x1, y2 - y1
            L = math.hypot(dx, dy) or 1.0
            # front side is to the RIGHT of v1->v2
            nx, ny = (dy / L) * slotsign, (-dx / L) * slotsign

            this_sec = secs[int(sd["sector"])][0]
            other_si = ld.get("sideback" if key == "sidefront" else "sidefront")
            other_sec = (
                secs[int(sides[int(other_si)][0]["sector"])][0]
                if other_si is not None
                else None
            )

            fl = fnum(this_sec, "heightfloor")
            ce = fnum(this_sec, "heightceiling")
            if slot == "texturetop" and other_sec is not None:
                # Upper: fills from the far ceiling up to this one, pegged top.
                span_top = ce
            elif slot == "texturebottom" and other_sec is not None:
                span_top = fnum(other_sec, "heightfloor")
            elif other_sec is not None:
                # Two-sided MIDTEX hangs in the OPENING, not floor-to-ceiling of
                # either side -- its top is the lower of the two ceilings.
                span_top = min(ce, fnum(other_sec, "heightceiling"))
            else:
                span_top = ce  # one-sided middle: pegged to the ceiling
            z = span_top - BULB_FROM_TOP

            px, py = mx + nx * FACE_OFFSET, my + ny * FACE_OFFSET
            near = min(
                (seg_dist(lx, ly, x1, y1, x2, y2) for lx, ly in existing),
                default=float("inf"),
            )
            if near <= NEAR_EXISTING:
                notes.append(f"    line {li}: already lit ({near:.0f}u) -- skipped")
                continue
            # A light outside the sector it sits in lights nothing. Catch it here
            # rather than discovering it as a dark panel in play.
            if not (fl < z < ce):
                notes.append(
                    f"    line {li}: z={z:.0f} outside sector [{fl:.0f},{ce:.0f}]"
                    f" -- SKIPPED, needs a look"
                )
                continue
            out.append((px, py, z - fl, f"line {li} {slot}={sd[slot]} z={z:.0f}"))
    return out, notes


def main() -> None:
    dry = "--dry-run" in sys.argv
    lumps = read_wad_lumps(WAD)
    seq = read_wad_lumps(SEQL) if SEQL.exists() else []
    seq_maps = {nm.upper() for i, (nm, _) in enumerate(seq) if is_map_marker(seq, i)}

    combined: list[tuple[str, bytes]] = []
    total = 0
    for i, (nm, _) in enumerate(lumps):
        if not is_map_marker(lumps, i):
            continue
        mapname = nm.upper()
        src, srcname = (seq, "seqlight") if mapname in seq_maps else (lumps, "stock")
        s, e = map_lump_range(src, mapname)
        members = {n.upper(): b for n, b in src[s:e]}
        if "TEXTMAP" not in members:
            continue
        text = decode_textmap(members["TEXTMAP"])
        if "SMONF" not in text.upper():
            continue
        placements, notes = plan_for_map(text)
        if not placements and not notes:
            continue
        print(f"{mapname} (from {srcname}): {len(placements)} light(s)")
        for _, _, _, why in placements:
            print(f"    {why}")
        for n in notes:
            print(n)
        total += len(placements)
        if not placements:
            continue
        patched = text.rstrip() + "\n\n" + "".join(
            thing_block(x, y, h) for x, y, h, _ in placements
        )
        items: list[tuple[str, bytes]] = [(mapname, b"")]
        for n, b in src[s + 1 : e]:
            items.append((n, patched.encode("utf-8") if n.upper() == "TEXTMAP" else b))
        if items[-1][0].upper() != "ENDMAP":
            items.append(("ENDMAP", b""))
        combined.extend(items)

    print(f"\ntotal {total} light(s)")
    if dry:
        print("dry run -- nothing written")
        return
    if not combined:
        raise SystemExit("no maps needed lights")
    write_wad(OUTWAD, combined)
    print(f"wrote {OUTWAD}")


if __name__ == "__main__":
    main()
