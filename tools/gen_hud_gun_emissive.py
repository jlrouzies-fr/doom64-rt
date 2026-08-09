"""Masked emissive for the first-person plasma rifle / BFG sprites.

Why a mask and not an emissiveMult
----------------------------------
RTGL1 only has a per-texture emission MAP (`<NAME>_e.png` in rt/mat). With no map it
falls back to the albedo, so `emissiveMult` on a view-weapon makes the WHOLE gun emit.
On a dark backdrop that reads as a solid white gun (screen/plasmagunissue.png,
screen/bfgbug.png); on a bright one the emission swamps the body and the floor shows
through it (screen/plasmariflegettingtransparent.png). Both are the same bug.

The plasma rifle does have a real light source in the art — the blue electric core is
~10%% of the opaque texels on every frame — so the fix is to emit from those texels
only. Body stays ordinary lit geometry, core glows passively, nothing washes.

Never give these a `lightIntensity`: a same-sprite analytic light on a HUD sprite lights
the sprite that spawned it and bleaches it white (the Lost Soul lesson, see
tools/gen_fx_emissives.py). Scene cast during fire comes from engine RT_AddMuzzleFlash.

Run after tools/gen_fx_emissives.py — this upserts on top of it.

  python tools/gen_hud_gun_emissive.py [--check]
"""
from __future__ import annotations

import json
import re
import struct
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(r"G:\ai\Doom64-RT")
WAD = ROOT / r"Doom64-Retribution\D64RTR_v15.WAD"

MAT_DIRS = [
    ROOT / r"sourcecode\gzdoom-rt\build\RelWithDebInfo\rt\mat",
    ROOT / r"sourcecode\gzdoom-rt\build\RelWithDebInfo\rt\mat_dev",
    ROOT / r"Doom64-Retribution\Retribution-RT-Materials\rt\mat",
]
JSONS = [
    ROOT / r"Doom64-Retribution\Retribution-RT-Materials\rt\data\textures_fx.json",
    ROOT
    / r"Doom64-Retribution\Retribution-RT-Materials\rt\data\scenes\d64rtr_v15_map01\textures.json",
    ROOT / r"sourcecode\gzdoom-rt\build\RelWithDebInfo\rt\data\textures.json",
    ROOT / r"sourcecode\gzdoom-rt\build\RelWithDebInfo\rt\data\scenes\d64rtr_v15_map01\textures.json",
]

# Frame sets, with the emissive strength for each. PLSF* are NOT small muzzle overlays
# in Retribution — they are full gun sprites drawn on the WEAPON layer during Fire — so
# they are masked exactly like the idle frames, just a touch hotter.
# Plasma light colour. The old 55aaff / 66bbff / 66ccff read CYAN, not blue: green sat
# at 170-204, close enough to blue that the hue lands between the two. Pulling green
# down to 85 while keeping blue pinned puts it back on blue without going navy-dark.
# Applied to the gun AND to the projectile / impact FX below, which carried the same
# cyan and so lit rooms cyan while the bolt itself read blue.
PLASMA_BLUE = "3355ff"

# Plasma FX owned by gen_fx_emissives.py that share the gun's colour. Only their
# lightColorHEX is touched here; their emissiveMult / lightIntensity stay as authored.
PLASMA_FX_PREFIXES = ("PLSS", "PLSE", "CPLS")

# Everything this tool has ever owned. Frames that drop out of GROUPS (or whose core no
# longer survives the test) must have their JSON entry and _e map REMOVED, not left
# behind stale — that is how the BFG kept emitting after its group was deleted.
MANAGED = tuple(
    ["PLSG" + c + "0" for c in "ABCDEFGHR"]
    + ["PLSFA0", "PLSFB0"]
    + ["BFGG" + c + "0" for c in "ABCDE"]
)

# (frames, emissiveMult, lightColorHEX, core test, lightIntensity)
#
# lightIntensity is 0 on EVERY entry here, and must stay 0.
#
# A same-sprite light on a first-person weapon attaches a light to the rasterized quad it
# is supposed to illuminate. It does light the gun — but it also made the plasma rifle's
# dark chassis go half see-through, and the plasma rifle was the ONLY weapon carrying
# such a light, which is precisely why the artefact appeared on that gun and on no other
# (screen/Screenshot 2026-08-09 212205.png). The gun's glow is now a real viewer-attached
# light in the engine: rt_gunglow / rt_gunglow_intensity / rt_gunglow_color in
# rt_main.cpp, alongside the flashlight and the muzzle flash. Tune it there, not here.
#
# What stays here is emission only, which on a view weapon is a screen-space additive
# overlay — it makes the core LOOK lit, it does not light anything.
# (frames, emissiveMult, lightColorHEX, core test, lightIntensity, coverage)
#
# PLSF* get a much smaller, much weaker mask than the idle frames. Their art ALREADY
# depicts the gun mid-discharge — the muzzle end is painted as a flare — so the mask's
# "brightest texels" land on one big contiguous blob there, and adding the idle frames'
# emission on top blew it into a white smear (screen/rifleplasmeonespritebad.png).
# The idle frames need the help; the fire frames do not.
GROUPS = [
    (["PLSG" + c + "0" for c in "ABCDEFGH"] + ["PLSGR0"], 0.30, PLASMA_BLUE, "blue", 0, 0.03),
    (["PLSFA0", "PLSFB0"], 0.10, PLASMA_BLUE, "blue", 0, 0.03),
]

# No BFGG entry. The BFG's art has no coloured emitter — only a blown-out white strip —
# so a "hot texel" mask could only ever produce stray white specks on an idle gun, which
# is exactly what it did (screen/bfgbadmaskidle.png). The BFG is meant to be dark until
# it fires; its fire glow is the separate BFGF flash layer, owned by gen_fx_emissives.py.

# Hard coverage budget, as a fraction of the sprite's opaque texels.
#
# A plain colour threshold is not enough. On the idle frames it selects the coil (~10%),
# but on the FIRE frames (PLSF*) the whole chassis front lights up blue in the art, so
# the same test selected 23% of the gun. Emission on a view weapon is a screen-space
# ADDITIVE overlay (RsWorld.inl writes outScreenEmission; it is not path-traced light),
# so a mask that large stops reading as "a glowing core" and becomes a white ghost
# painted over the gun — which is what "the weapon goes invisible when I shoot" is.
# Keeping only the brightest N texels holds every frame to the same visual budget.
COVERAGE = 0.07

# Core tests, per weapon. Both land at ~2-13%% of opaque texels — well under
# check_emis_hygiene's 45%% "solidish _e" bar, which is the line between "a lamp in the
# art" and "the whole sprite emits".
#   blue: the plasma rifle's electric core is strongly blue-dominant.
#   hot:  the BFG has no coloured core, only a blown-out white aperture. A blue test
#         here selects the barrel's cool steel specular instead and makes the metal glow.
CORE_MIN_B = 100
# Dominance, not brightness. At 40 the test admitted texels like (189,214,255) — nearly
# white, dominance 41, scraping past the bar — and since candidates were then ranked by
# raw blue, those near-white SPECULAR HIGHLIGHTS outranked the coil and the mask came out
# as speckles scattered over the whole chassis (screen/plasmastillbadmask.png).
#
# The real fix is the RANKING (see score() below): candidates are now ordered by
# dominance, so the coil's (66,115,206) / (48,128,232) outrank any near-white highlight
# and the coverage budget is spent on the coil first. The bar itself only needs to be
# high enough to keep grey out — 90 was too strict and starved the recoil frames, whose
# coil is painted less saturated, down to 4 texels.
CORE_MIN_DOM = 55
HOT_MIN = 200
# 1.0 = emit the art's own colours. Anything above pushes the core's brightest texels
# toward 255,255,255 before emissiveMult even applies, which is how the coil detail got
# flattened into a white blob — the boost clips exactly the texels that carry the shape.
BOOST = 1.0


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


def is_core(r: int, g: int, b: int, mode: str) -> bool:
    if mode == "hot":
        return min(r, g, b) >= HOT_MIN
    return b >= CORE_MIN_B and b - max(r, g) >= CORE_MIN_DOM


def core_mask(img: Image.Image, mode: str, coverage: float) -> tuple[Image.Image, int, int]:
    """Keep the brightest core texels, up to `coverage` of the sprite; drop the rest."""
    px = list(img.get_flattened_data())
    opaque = sum(1 for q in px if q[3] >= 40)
    budget = max(1, int(opaque * coverage))

    def score(q: tuple[int, int, int, int]) -> int:
        r, g, b, _ = q
        # Rank by how blue it is, not how bright: ranking by brightness promotes white
        # highlights over the coil, which is the whole speckle problem.
        return min(r, g, b) if mode == "hot" else b - max(r, g)

    cand = sorted(
        (i for i, q in enumerate(px) if q[3] >= 40 and is_core(q[0], q[1], q[2], mode)),
        key=lambda i: -score(px[i]),
    )
    keep = set(cand[:budget])

    out_px = []
    for i, (r, g, b, a) in enumerate(px):
        if i in keep:
            out_px.append(
                (
                    min(255, int(r * BOOST)),
                    min(255, int(g * BOOST)),
                    min(255, int(b * BOOST)),
                    255,
                )
            )
        else:
            out_px.append((0, 0, 0, 0))
    e = Image.new("RGBA", img.size)
    e.putdata(out_px)
    return e, len(keep), opaque


BLOCK = re.compile(r"[ \t]*\{[^{}]*?\}[ \t]*,?[ \t]*\r?\n", re.S)
NAME = re.compile(r'"textureName"\s*:\s*"([^"]+)"')


def upsert(path: Path, metas: dict[str, dict]) -> tuple[int, int]:
    """Replace existing entries in place, append the rest. Text-level so the rest of the
    file keeps its formatting."""
    src = path.read_text(encoding="utf-8")
    indent = "    "
    replaced = 0

    def sub(m: re.Match[str]) -> str:
        nonlocal replaced
        blk = m.group(0)
        nm = NAME.search(blk)
        if not nm or nm.group(1) not in metas:
            return blk
        replaced += 1
        body = json.dumps(metas[nm.group(1)], indent=2)
        body = "\n".join(indent + ln for ln in body.splitlines())
        return body + ",\n"

    out = BLOCK.sub(sub, src)

    missing = [n for n in metas if f'"{n}"' not in out]
    if missing:
        blocks = []
        for n in missing:
            body = json.dumps(metas[n], indent=2)
            blocks.append("\n".join(indent + ln for ln in body.splitlines()))
        addition = ",\n".join(blocks)
        # append as the last elements of "array"
        idx = out.rfind("]")
        head = out[:idx].rstrip().rstrip(",")
        out = head + ",\n" + addition + "\n  " + out[idx:]

    out = re.sub(r",(\s*\])", r"\1", out)
    parsed = json.loads(out)["array"]
    for n, meta in metas.items():
        got = [e for e in parsed if e["textureName"] == n]
        assert len(got) == 1, f"{path.name}: {n} appears {len(got)}x"
        assert got[0]["emissiveMult"] == meta["emissiveMult"], f"{path.name}: {n} not applied"
    path.write_text(out, encoding="utf-8")
    return replaced, len(missing)


def main() -> None:
    check = "--check" in sys.argv
    # Tuning override for the attached light, e.g. --light=90. Use with
    # tools/probe-weapon-fire.ps1 -Weapon plasma-live to see the result.
    light_override: float | None = None
    for a in sys.argv[1:]:
        if a.startswith("--light="):
            light_override = float(a.split("=", 1)[1])
    lumps = wad_lumps()
    metas: dict[str, dict] = {}
    import io

    for names, mult, hexcol, mode, light, coverage in GROUPS:
        if light_override is not None:
            light = light_override
        for nm in names:
            if nm not in lumps:
                print(f"  skip {nm}: not in WAD")
                continue
            img = Image.open(io.BytesIO(lumps[nm])).convert("RGBA")
            mask, kept, opaque = core_mask(img, mode, coverage)
            pct = 100 * kept / max(1, opaque)
            if kept < 40:
                print(f"  skip {nm}: core only {kept} texels")
                continue
            if not check:
                for d in MAT_DIRS:
                    d.mkdir(parents=True, exist_ok=True)
                    mask.save(d / f"{nm}_e.png")
            metas[nm] = {
                "textureName": nm,
                "emissiveMult": mult,
                "lightColorHEX": hexcol,
                "noShadow": True,
            }
            if light > 0:
                metas[nm]["lightIntensity"] = light
            print(
                f"  {nm}: {mode} core {kept}/{opaque} ({pct:.1f}%) "
                f"emissiveMult={mult} light={light}"
            )

    if check:
        print("check only — nothing written")
        return

    for p in JSONS:
        if not p.exists():
            print(f"MISSING {p}")
            continue
        gone = purge(p, set(metas))
        rep, add = upsert(p, metas)
        tint = retint(p)
        print(f"{p.name}: replaced {rep}, added {add}, removed {gone}, retinted {tint} plasma FX")

    for d in MAT_DIRS:
        for nm in MANAGED:
            f = d / f"{nm}_e.png"
            if nm not in metas and f.exists():
                f.unlink()
                print(f"  removed stale {f.name} from {d.name}")


def purge(path: Path, keep: set[str]) -> int:
    """Drop entries for managed frames this run did not produce, so a frame that leaves
    GROUPS stops emitting instead of keeping its last written values."""
    src = path.read_text(encoding="utf-8")
    n = 0

    def sub(m: re.Match[str]) -> str:
        nonlocal n
        blk = m.group(0)
        nm = NAME.search(blk)
        if not nm or nm.group(1) not in MANAGED or nm.group(1) in keep:
            return blk
        n += 1
        return ""

    out = BLOCK.sub(sub, src)
    if n:
        out = re.sub(r",(\s*\])", r"\1", out)
        json.loads(out)
        path.write_text(out, encoding="utf-8")
    return n


def retint(path: Path) -> int:
    """Repoint the plasma projectile / impact FX from cyan to PLASMA_BLUE, leaving every
    other field alone."""
    src = path.read_text(encoding="utf-8")
    hits = 0

    def sub(m: re.Match[str]) -> str:
        nonlocal hits
        blk = m.group(0)
        nm = NAME.search(blk)
        if not nm or not nm.group(1).startswith(PLASMA_FX_PREFIXES):
            return blk
        new = re.sub(r'("lightColorHEX"\s*:\s*")[0-9a-fA-F]{6}(")', rf"\g<1>{PLASMA_BLUE}\2", blk)
        if new != blk:
            hits += 1
        return new

    out = BLOCK.sub(sub, src)
    if hits:
        json.loads(out)
        path.write_text(out, encoding="utf-8")
    return hits


if __name__ == "__main__":
    main()
