"""Render a GALLERY of candidate smoke looks: one capture per candidate, one PNG.

Why this exists. Every earlier round of smoke tuning compared a memory of one
run against a memory of another, in different rooms, at different moments in a
puff's life -- and twice that produced a confident conclusion that was simply
wrong (see the grey-wall sweep, where four settings were declared identical
because the backdrop hid all of them). A gallery removes the memory: every
candidate is the same map, the same spawn, the same capture tic, side by side in
one image with its parameters written on it.

A CANDIDATE IS A WHOLE LOOK, not one cvar. Single-cvar sweeps answer "what does
this knob do"; picking a look means judging combinations, so each row here is a
named set of overrides you can point at and say "that one".

Usage:
    python tools/smoke_gallery.py                 # the built-in candidate set
    python tools/smoke_gallery.py --tic 95        # capture at a different age

Output:
    tools/_smokelab/gallery.png
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

# Repo root, derived from this file so a clone can live anywhere.
PROJ_ROOT = Path(__file__).resolve().parents[1]

ROOT = PROJ_ROOT
LAB = ROOT / "tools" / "smoke-lab.cmd"
# 96 = the bright beige room, 97 = the dark cool one. Colour questions
# belong on 96: a grey puff on a dark blue wall is easy, and that is
# precisely why the beige case went unnoticed for so long.
LABMAP = "97"
WORK = ROOT / "tools" / "_smokelab"
OUT = WORK / "gallery.png"

# Each candidate: (label, {cvar: value}). Everything not named takes the pinned
# shipping value, so a row states only how it differs -- the same convention
# RT_SMOKE_PROFILES uses.
CANDIDATES: list[tuple[str, dict[str, str]]] = [
    # WHERE THE SMOKE LEAVES THE GUN. rt_smoke_muzzle_u raises the birth point
    # above the muzzle flash's, which is placed low for LIGHTING (-0.9 m) rather
    # than at a barrel. Too high and the smoke reads as coming off the raised
    # gun of the firing animation instead of out of the muzzle.
    ("A  muzzle_u 0.30  (shipping now)", {}),
    ("B  muzzle_u 0.15", {"rt_smoke_muzzle_u": "0.15"}),
    ("C  muzzle_u 0.00 - the flash's own height", {"rt_smoke_muzzle_u": "0"}),
    ("D  muzzle_u -0.15", {"rt_smoke_muzzle_u": "-0.15"}),
]

# Applied to EVERY candidate, so the comparison stays fair while removing a lab
# artifact. The map's stand-in muzzle lamp is STEADY, where a real muzzle flash
# lasts two or three frames -- so a big dense puff saturates to white here far
# worse than it ever would in play, and at the shipping dynlight intensity every
# candidate above ~17 cm clipped to a featureless blob. Dimming the lamp puts
# the range back on screen. It is not a smoke setting and must not be read as
# one; it only makes the sizes comparable.
BASE: dict[str, str] = {}

# The crop the plume lands in, found by differencing runs. Generous enough to
# survive a puff drifting a little between candidates.
CROP = (880, 480, 1660, 1369)


def capture(overrides: dict[str, str], tic: int, dest: Path) -> bool:
    for d in WORK.glob("2026*"):
        shutil.rmtree(d, ignore_errors=True)

    merged = {**BASE, **overrides}
    extra = " ".join(f"+{k} {v}" for k, v in merged.items())
    # NOT quoted, deliberately. `cmd /c "<string>"` strips the first and last
    # quote of the whole string, so a command that BEGINS with a quoted path
    # comes out mangled and the batch file never runs -- which shows up here as
    # every candidate silently failing to capture. The path has no spaces.
    cmd = (
        f"{LAB} 1 {LABMAP} -- {extra} "
        f"+rt_autoshot {tic} +rt_autoshot_every 0 +rt_autoquit {tic + 20}"
    )
    subprocess.run(["cmd", "/c", cmd], cwd=ROOT, capture_output=True, text=True)

    runs = sorted(WORK.glob("2026*"), key=lambda p: p.stat().st_mtime)
    if not runs:
        return False
    shots = sorted(runs[-1].glob("*.png"))
    if not shots:
        shutil.rmtree(runs[-1], ignore_errors=True)
        return False
    shutil.copy(shots[0], dest)
    shutil.rmtree(runs[-1], ignore_errors=True)
    return True


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tic", type=int, default=95,
                    help="maptime to screenshot at; the plume's age is a variable "
                         "like any other, so every candidate uses the same one")
    args = ap.parse_args()

    try:
        from PIL import Image, ImageDraw
    except ImportError:
        sys.exit("Pillow missing. Use the Python at "
                 r"C:\Users\Winter\AppData\Local\Programs\Python\Python313\python.exe")

    shots = WORK / "gallery_shots"
    shots.mkdir(parents=True, exist_ok=True)

    got: list[tuple[str, dict[str, str], Path]] = []
    for i, (label, ov) in enumerate(CANDIDATES):
        dest = shots / f"{i:02d}.png"
        print(f"  [{i + 1}/{len(CANDIDATES)}] {label} ...", flush=True)
        if capture(ov, args.tic, dest):
            got.append((label, ov, dest))
        else:
            print("        FAILED to capture")

    if not got:
        sys.exit("no captures")

    crops = [Image.open(p).convert("RGB").crop(CROP) for _, _, p in got]
    cw, ch = crops[0].size
    scale = 0.75
    cw, ch = int(cw * scale), int(ch * scale)
    crops = [c.resize((cw, ch), Image.LANCZOS) for c in crops]

    cols = 4
    rows = (len(crops) + cols - 1) // cols
    pad, head = 6, 46
    sheet = Image.new("RGB", (cols * (cw + pad) + pad,
                              rows * (ch + head + pad) + pad), (14, 14, 16))
    dr = ImageDraw.Draw(sheet)

    for i, ((label, ov, _), im) in enumerate(zip(got, crops)):
        r, c = divmod(i, cols)
        x = pad + c * (cw + pad)
        y = pad + r * (ch + head + pad)
        dr.text((x + 4, y + 4), label, fill=(255, 255, 255))
        detail = "  ".join(f"{k.replace('rt_smoke_', '').replace('rt_volume_', 'vol.')}={v}"
                           for k, v in ov.items()) or "(all shipping values)"
        dr.text((x + 4, y + 22), detail[:120], fill=(150, 150, 160))
        sheet.paste(im, (x, y + head))

    sheet.save(OUT)
    print(f"\nwrote {OUT}  ({sheet.size[0]}x{sheet.size[1]}, {len(got)} candidates)")


if __name__ == "__main__":
    main()
