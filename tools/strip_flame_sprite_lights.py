"""Zero the ATTACHED light on every open-flame sprite; the engine lights them now.

Torches, loose fires and the candle are lit by RT_UploadFlameLights (rt_main.cpp, table
RT_FLAME_KINDS, cvar rt_flame_light_on) rather than by RTGL1's sprite-attached light,
because texture meta cannot express either half of what a fire needs:

  * OFFSET. RTGL1 attaches a sprite light at the CENTRE of the billboard quad
    (VulkanDevice.cpp: center = average of the 4 quad verts). The mod's GLDEFS lifts these
    lights 8..80 units up onto the flame, and texture meta has no offset field, so a
    100-unit standing torch was lighting the room from its own midriff.
  * FLICKER. Meta is static per sprite frame. Driving intensity off the A..E animation is
    the only data-only way to vary it, and every one of these props spawns at map load —
    so the whole level would pulse in lockstep, which reads as a fault, not as fire.

So `lightIntensity` goes to 0 (the muzzle-flash convention already in these files: a 0
casts nothing) and `emissiveMult` is left alone, because the flame must still glow on
screen. Running this twice is a no-op.

The owning generators are updated to match — gen_fx_emissives.py PREFIX_RULES and
gen_torch_emissives.py INTENSITY. If you only fix the JSON, the next `gen_*` run puts the
double lights back; that is exactly how the LPUF regression survived a whole release.
"""
from __future__ import annotations

import re
from pathlib import Path

# Repo root, derived from this file so a clone can live anywhere.
PROJ_ROOT = Path(__file__).resolve().parents[1]

ROOT = PROJ_ROOT

# Must match RT_FLAME_KINDS in src/common/rendering/rt/rt_main.cpp, one for one.
# (label, name regex). The label is only for the report; the regex is what matches a
# textureName. Default form is prefix + [A-Z0-9]* — anything sharing the four characters.
FLAME_PREFIXES = [
    "TLBL", "TLGR", "TLRD", "TLYL",   # standing torches, long
    "TSBL", "TSGR", "TSRD", "TSYL",   # standing torches, short
    "A030", "A031", "A032", "GTCH",   # wall sconces
    "BFLM", "GFLM", "RFLM", "YFLM",   # loose fires
    "CAND",                           # candle
]

# FIRE cannot use the blanket form. Doom II's world fire/lava WALL textures are FIRELAVA,
# FIRELAV2/3, FIREWALL, FIREWALA/B, FIREMAG1-3, FIREBLU1/2 — all of which start with FIRE
# and none of which is the 64BigFire sprite. gen_fx_emissives.py needs a WORLD_TEX_RE
# guard for the same reason. The sprite lumps are exactly FIREA0..FIREH0, so pin the
# shape: four letters, one frame letter, one rotation digit.
FLAME_EXACT = [
    ("FIRE", r"FIRE[A-Z]0"),          # 64BigFire / 64MotherFire / 64MotherFireTrail
]

# Every file RTGL1 might read, plus the mod's source-of-record overlays. The vendor copies
# under gzdoom-rt-1.0.2/ and runtime-mod/ contain // comments and are NOT valid JSON, so
# this patches textually rather than through json.load.
FILES = [
    r"sourcecode\gzdoom-rt\build\RelWithDebInfo\rt\data\textures.json",
    r"sourcecode\gzdoom-rt\build\RelWithDebInfo\rt\data\scenes\d64rtr_v15_map01\textures.json",
    r"sourcecode\gzdoom-rt\build\WashScratch\rt\data\textures.json",
    r"sourcecode\gzdoom-rt\build\WashScratch\rt\data\scenes\d64rtr_v15_map01\textures.json",
    r"Doom64-Retribution\Retribution-RT-Materials\rt\data\textures_fx.json",
    r"Doom64-Retribution\Retribution-RT-Materials\rt\data\scenes\d64rtr_v15_map01\textures.json",
]

# Bounded by [^}] so the search can never run out of one entry and into the next one's
# lightIntensity — an entry that simply has no light must not steal the following entry's.
PATTERNS = [
    (
        label,
        re.compile(
            r'("textureName"\s*:\s*"' + body + r'"[^}]{0,300}?"lightIntensity"\s*:\s*)'
            r'(?!0\s*[,}])[0-9.]+'
        ),
    )
    for label, body in (
        [ (p, p + r"[A-Z0-9]*") for p in FLAME_PREFIXES ] + FLAME_EXACT
    )
]


def main() -> None:
    for rel in FILES:
        path = ROOT / rel
        if not path.exists():
            print(f"  skip (missing) {rel}")
            continue
        text = path.read_text(encoding="utf-8")
        total = 0
        hits = []
        for prefix, pat in PATTERNS:
            text, n = pat.subn(lambda m: m.group(1) + "0", text)
            total += n
            if n:
                hits.append(f"{prefix}:{n}")
        path.write_text(text, encoding="utf-8")
        print(f"  {total:3d} zeroed  {' '.join(hits) or '(already clean)'}\n           {rel}")


if __name__ == "__main__":
    main()
