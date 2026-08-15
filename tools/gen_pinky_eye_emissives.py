"""
Pinky (SARG / 64Demon) eye glow for RTGL1.

Retribution ships grayscale eye brightmaps (brightmaps/bd64/SARG*B.png).
In classic GL those mask fullbright pixels; in gzdoom-rt, rt_mod_compat only
sets a *whole-primitive* emissive float — not a mask.

Proper subtle eyes = companion rt/mat/<SPRITE>_e.png (red, eyes only)
+ low textures.json emissiveMult (no analytic lightIntensity).
"""
from __future__ import annotations

import io
import json
import re
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
OMAT = ROOT / r"Doom64-Retribution\Retribution-RT-Materials\rt\mat"
GLOBAL = ROOT / r"sourcecode\gzdoom-rt\build\RelWithDebInfo\rt\data\textures.json"
SCENE = ROOT / r"sourcecode\gzdoom-rt\build\RelWithDebInfo\rt\data\scenes\d64rtr_v15_map01\textures.json"
OVERLAY = ROOT / r"Doom64-Retribution\Retribution-RT-Materials\rt\data\textures_pinky_eyes.json"

# Subtle: glow on eyes, no attached light cast into the room.
# Prefer tools/gen_enemy_eye_emissives.py for all monsters (5x strength).
EMIS = 4.25
RED = (255, 36, 28)


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


def bm_to_texname(stem: str) -> str:
    s = stem.upper()
    # SARGA1B / SARGA2A8B → SARGA1 / SARGA2A8
    if s.endswith("B") and len(s) > 5:
        s = s[:-1]
    return s


def mask_to_red_e(mask: Image.Image, albedo: Image.Image | None) -> Image.Image:
    m = mask.convert("RGBA")
    if albedo is not None and albedo.size != m.size:
        # brightmaps sometimes padded differently — resize mask to albedo
        m = m.resize(albedo.size, Image.Resampling.NEAREST)
        size = albedo.size
    else:
        size = m.size
    out = Image.new("RGBA", size, (0, 0, 0, 0))
    mp = list(m.getdata())
    ap = list(albedo.convert("RGBA").getdata()) if albedo is not None else None
    pixels = []
    for i, (r, g, b, a) in enumerate(mp):
        lum = max(r, g, b)
        if a < 20 or lum < 20:
            pixels.append((0, 0, 0, 0))
            continue
        # strength from brightmap luminance
        t = min(1.0, lum / 255.0)
        # Prefer albedo redness if present
        if ap is not None:
            ar, ag, ab, aa = ap[i]
            if aa > 40 and ar > ag + 15 and ar > ab + 15:
                pixels.append(
                    (
                        min(255, int(ar * 1.2)),
                        min(255, int(ag * 0.35)),
                        min(255, int(ab * 0.35)),
                        int(200 + 55 * t),
                    )
                )
                continue
        pixels.append(
            (
                int(RED[0] * t),
                int(RED[1] * t),
                int(RED[2] * t),
                int(180 + 75 * t),
            )
        )
    out.putdata(pixels)
    return out


def patch_global(entries: dict[str, dict]) -> None:
    text = GLOBAL.read_text(encoding="utf-8")
    for name, meta in entries.items():
        parts = [f'"textureName":"{name}"']
        for k, v in meta.items():
            if k == "textureName":
                continue
            if isinstance(v, bool):
                parts.append(f'"{k}":{"true" if v else "false"}')
            elif isinstance(v, float) and v == int(v):
                parts.append(f'"{k}":{int(v)}')
            elif isinstance(v, (int, float)):
                parts.append(f'"{k}":{v}')
            else:
                parts.append(f'"{k}":"{v}"')
        line = "    ,   { " + "  ,".join(parts) + " }"
        pat = re.compile(
            rf'^[ \t]*,?[ \t]*\{{[ \t]*"textureName"[ \t]*:[ \t]*"{re.escape(name)}".*$',
            re.M,
        )
        if pat.search(text):
            text = pat.sub(line, text, count=1)
        else:
            text = re.sub(r"\n(\s*\]\s*\}\s*)$", "\n" + line + r"\n\1", text, count=1)
    GLOBAL.write_text(text, encoding="utf-8")


def upsert_json(path: Path, entries: dict[str, dict], replace: bool = False) -> None:
    if path.exists() and not replace:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {"version": 0, "array": []}
    else:
        data = {"version": 0, "array": []}
    by = {e["textureName"]: dict(e) for e in data.get("array", []) if "textureName" in e}
    for name, meta in entries.items():
        cur = by.get(name, {"textureName": name})
        cur.update(meta)
        cur["textureName"] = name
        by[name] = cur
    data["array"] = list(by.values())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    lumps = wad_lumps()
    MAT.mkdir(parents=True, exist_ok=True)
    OMAT.mkdir(parents=True, exist_ok=True)

    entries: dict[str, dict] = {}
    made = 0

    with zipfile.ZipFile(BM) as z:
        for n in z.namelist():
            if "SARG" not in n.upper() or not n.lower().endswith(".png"):
                continue
            stem = Path(n).stem
            tex = bm_to_texname(stem)
            mask = Image.open(io.BytesIO(z.read(n)))
            albedo = None
            if tex in lumps:
                try:
                    albedo = Image.open(io.BytesIO(lumps[tex]))
                except Exception:
                    albedo = None
            eimg = mask_to_red_e(mask, albedo)
            for dest in (MAT / f"{tex}_e.png", OMAT / f"{tex}_e.png"):
                eimg.save(dest)
            entries[tex] = {
                "textureName": tex,
                "emissiveMult": EMIS,
                # no lightIntensity — eyes should not light the room
            }
            made += 1
            lit = sum(1 for p in eimg.getdata() if p[3] > 20)
            print(f"{stem} -> {tex}_e.png  lit={lit}")

    # Also mark other SARG frames with tiny emissiveMult so any future _e works;
    # without _e, keep emissiveMult low / absent to avoid full-body glow.
    print(f"wrote {made} eye emissive maps, {len(entries)} meta entries")
    patch_global(entries)
    if SCENE.exists():
        upsert_json(SCENE, entries, replace=False)
    upsert_json(OVERLAY, entries, replace=True)
    print("done")


if __name__ == "__main__":
    main()
