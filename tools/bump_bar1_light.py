"""SUPERSEDED -- DO NOT RUN. Kept only as a record of the barrel light history.

This was a one-off that wrote BAR1A0/BAR1B0 meta straight into the built
textures.json. Its values (noShadow: True, lightIntensity 420/360) are exactly the
combination that caused the mid-sprite fizzle reported in
screen/barrelsBlinkFizzle.png: a sphere light at the sprite's own centre with
nothing to occlude it. Running this would undo the fix.

The barrels are owned by tools/gen_fx_emissives.py (the FORCE table, which carries
the full explanation). Change them there and regenerate.
"""

import json
import re
import sys
from pathlib import Path

sys.exit(
    "bump_bar1_light.py is superseded and would re-add noShadow to the barrels. "
    "Edit FORCE in tools/gen_fx_emissives.py and re-run that instead."
)

GLOBAL = Path(
    r"G:\AI\Doom64-RT\sourcecode\gzdoom-rt\build\RelWithDebInfo\rt\data\textures.json"
)
SCENE = Path(
    r"G:\AI\Doom64-RT\sourcecode\gzdoom-rt\build\RelWithDebInfo\rt\data\scenes\d64rtr_v15_map01\textures.json"
)
GEN = Path(r"G:\AI\Doom64-RT\tools\gen_fx_emissives.py")

BAR = {
    "BAR1A0": {
        "emissiveMult": 1.6,
        "noShadow": True,
        "lightIntensity": 420,
        "lightColorHEX": "3dff4a",
    },
    "BAR1B0": {
        "emissiveMult": 1.4,
        "noShadow": True,
        "lightIntensity": 360,
        "lightColorHEX": "2ecc40",
    },
}


def line_for(name: str, meta: dict) -> str:
    parts = [f'"textureName":"{name}"']
    for k, v in meta.items():
        if isinstance(v, bool):
            parts.append(f'"{k}":{"true" if v else "false"}')
        elif isinstance(v, float) and v == int(v):
            parts.append(f'"{k}":{int(v)}')
        elif isinstance(v, (int, float)):
            parts.append(f'"{k}":{v}')
        else:
            parts.append(f'"{k}":"{v}"')
    return "    ,   { " + "  ,".join(parts) + " }"


t = GLOBAL.read_text(encoding="utf-8")
for name, meta in BAR.items():
    t, n = re.subn(
        rf'^[ \t]*,?[ \t]*\{{[ \t]*"textureName"[ \t]*:[ \t]*"{name}".*$',
        line_for(name, meta),
        t,
        count=1,
        flags=re.M,
    )
    print("global", name, n)
GLOBAL.write_text(t, encoding="utf-8")

data = json.loads(SCENE.read_text(encoding="utf-8"))
by = {e["textureName"]: e for e in data["array"] if "textureName" in e}
for name, meta in BAR.items():
    cur = by.get(name, {"textureName": name})
    cur.update(meta)
    cur["textureName"] = name
    by[name] = cur
data["array"] = list(by.values())
SCENE.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
print("scene ok")

g = GEN.read_text(encoding="utf-8")
g = g.replace(
    '"BAR1A0": {\n        "emissiveMult": 1.2,\n        "noShadow": True,\n        "lightIntensity": 180,\n        "lightColorHEX": "3dff4a",\n    }',
    '"BAR1A0": {\n        "emissiveMult": 1.6,\n        "noShadow": True,\n        "lightIntensity": 420,\n        "lightColorHEX": "3dff4a",\n    }',
)
g = g.replace(
    '"BAR1B0": {\n        "emissiveMult": 1.0,\n        "noShadow": True,\n        "lightIntensity": 140,\n        "lightColorHEX": "2ecc40",\n    }',
    '"BAR1B0": {\n        "emissiveMult": 1.4,\n        "noShadow": True,\n        "lightIntensity": 360,\n        "lightColorHEX": "2ecc40",\n    }',
)
# also prefix rule
g = g.replace('("BAR1", 1.1, 160, "3dff4a")', '("BAR1", 1.5, 400, "3dff4a")')
GEN.write_text(g, encoding="utf-8")
print("gen ok")
