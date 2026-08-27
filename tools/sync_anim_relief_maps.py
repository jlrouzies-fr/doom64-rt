"""Give every frame of an animated texture the same _h / _n / _orm maps.

RTGL1 resolves auxiliary maps per texture NAME, and an ANIMDEFS animation is a
run of separate names (CTEL1..CTEL8, STRAKY1..STRAKY5, HLAVA1..HLAVA5). So if
only the first frame ships an `_h.png`, the surface is parallax-displaced on
that frame and flat on all the others, and the animation cycles the relief in
and out several times a second.

That does not look like a missing map. It looks like the TEXTURE MOVING UP AND
DOWN, which is how it was reported on MAP13's CTEL panel (2026-08-10) and again
on the STRAK hazard stripes (2026-08-23) -- and it sends you looking at
scrollers, lifts and sector specials, none of which are involved.

Sharing frame 1's maps is only correct when the frames are the SAME SURFACE.
That is checked, not assumed, by two gates -- a frame may share relief if:

  * it differs from frame 1 on at most MAX_DIFF_FRAC of the tile (CTEL is 45
    pixels of 4096, 1.1% -- the gems -- with the stone byte-identical); OR
  * its colour-REGION LAYOUT is byte-identical to frame 1's, i.e. the two are
    the same geometry under some recolour. STRAK is this case: 19.0% of the
    tile differs, but every one of its 13 colours sits in exactly the same
    pixels on every frame -- the animation is a brightness PULSE of the stripe,
    nothing moves. `STRAKY1_h` tracks albedo luminance, so regenerating `_h`
    per frame would make the stripe physically rise and fall with the pulse:
    it would author in the very artefact this fixes. Copying is the answer.

Note what the second gate does NOT say. It is invariant under any palette
permutation, so a frame that recoloured a raised region into what reads as a
recess would still pass. It means "same geometry, some recolour", and it is
guarded by MAX_STRUCT_COLOURS so that an image whose pixels are all distinct
(where the test is vacuously true) can never reach it.

A frame that fails both gates has genuinely different art and needs its OWN
maps -- generate them with `gen_ai_pbr.py` and bake the labels in with
`bake_material_labels_orm.py`; do not raise the gate.

  python tools/sync_anim_relief_maps.py --report    # sweep the whole game
  python tools/sync_anim_relief_maps.py             # report + fix CTEL
  python tools/sync_anim_relief_maps.py --dry-run   # report only
  python tools/sync_anim_relief_maps.py STRAKY      # some other base

A base is a name PREFIX whose frames end in digits, so `STRAKY` finds
STRAKY1..STRAKY5. Bases that are not themselves a numeric stem find nothing:
`STRAK` matches no frame at all (the suffix `Y1` is not all digits), and CFACE /
HTEL / SMONA are lettered rather than numbered, so `--report` is the way to see
those -- it walks ANIMDEFS itself and needs no base typed.

Where a bare lump shares the base name (`STRAKY` beside `STRAKY1`, `C307B`
beside `C307B1`) it is picked up as an extra target automatically. Those are
byte-identical duplicates of frame 1 and pass both gates trivially.
"""

from __future__ import annotations

import io
import re
import shutil
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))

from make_map_3dfloor_rtfix import WAD, read_wad_lumps

# Repo root, derived from this file so a clone can live anywhere.
PROJ_ROOT = Path(__file__).resolve().parents[1]

ROOT = PROJ_ROOT
MAT = ROOT / r"sourcecode\gzdoom-rt\build\RelWithDebInfo\rt\mat"
MAT_DEV = ROOT / r"sourcecode\gzdoom-rt\build\RelWithDebInfo\rt\mat_dev"
OMAT = ROOT / r"Doom64-Retribution\Retribution-RT-Materials\rt\mat"
# developerMode reads mat_dev in preference to mat (see rt-materials-mat-dev-wins
# memory), so the tracked mat_dev copy has to get the same fix or it ghosts:
# mat looks patched, the running game still reads the old, unpatched mat_dev.
OMAT_DEV = ROOT / r"Doom64-Retribution\Retribution-RT-Materials\rt\mat_dev"
DIRS = (MAT, MAT_DEV, OMAT, OMAT_DEV)

SUFFIXES = ("_h", "_n", "_orm")

# Above this share of differing pixels the frames are not "the same surface with
# a detail changing" on the pixel gate, and must clear the structure gate instead.
MAX_DIFF_FRAC = 0.05

# The structure gate is meaningless once every pixel is its own colour: the key
# degenerates to [0, 1, 2, ...] and any two images of a size would match. Every
# Doom 64 tile measured is 8-16 colours (STRAKY1 is 13 of 2048 pixels), so this
# cap sits far above every real case and far below the degenerate one.
MAX_STRUCT_COLOURS = 64


def frames_for(base: str) -> list[str]:
    """Frames of `base`, in order. Numeric suffixes only -- see the docstring."""
    lumps = read_wad_lumps(WAD)
    seen: dict[str, bytes] = {}
    for name, blob in lumps:
        u = name.upper()
        if u.startswith(base) and u[len(base):].isdigit() and u not in seen:
            seen[u] = blob
    return sorted(seen, key=lambda n: int(n[len(base):]))


def diff_frac(a: Image.Image, b: Image.Image) -> float:
    if a.size != b.size:
        return 1.0
    ap, bp = a.load(), b.load()
    w, h = a.size
    n = sum(1 for y in range(h) for x in range(w) if ap[x, y] != bp[x, y])
    return n / float(w * h)


def struct_key(im: Image.Image):
    """Canonical region labelling: colour -> index of its first appearance.

    Two frames of a palette-recolour animation produce the same key. Returns
    None when the image has too many colours for the test to mean anything.
    """
    p = im.load()
    w, h = im.size
    seen: dict[tuple, int] = {}
    out: list[int] = []
    for y in range(h):
        for x in range(w):
            c = p[x, y]
            if c not in seen:
                if len(seen) >= MAX_STRUCT_COLOURS:
                    return None
                seen[c] = len(seen)
            out.append(seen[c])
    return (im.size, tuple(out))


def shares_relief(ref: Image.Image, other: Image.Image) -> tuple[bool, str]:
    """May `other` use `ref`'s relief maps? Returns the verdict and the reason."""
    frac = diff_frac(ref, other)
    if frac <= MAX_DIFF_FRAC:
        return True, f"differs on {frac:.1%} of the tile"
    a, b = struct_key(ref), struct_key(other)
    if a is not None and a == b:
        return True, (f"differs on {frac:.1%} of the tile but the colour-region "
                      f"layout is byte-identical -- a recolour, not a redraw")
    return False, f"differs from the reference on {frac:.1%} of the tile"


def covered(name: str) -> bool:
    """True when `name` has all three relief maps in all four material dirs."""
    return all((d / f"{name}{suf}.png").exists() for d in DIRS for suf in SUFFIXES)


def animations() -> list[tuple[str, list[str]]]:
    """(name, distinct frame names in order) for every ANIMDEFS animation."""
    text = ""
    for name, blob in read_wad_lumps(WAD):
        if name.upper() == "ANIMDEFS":
            text = blob.decode("latin1", "replace")
            break
    out: list[tuple[str, list[str]]] = []
    cur: list[str] | None = None
    for line in text.splitlines():
        s = line.strip()
        m = re.match(r"(?i)^(?:texture|flat)\s+(\S+)", s)
        if m:
            cur = []
            out.append((m.group(1).upper(), cur))
            continue
        m = re.match(r"(?i)^pic\s+(\S+)", s)
        if m and cur is not None and m.group(1).upper() not in cur:
            cur.append(m.group(1).upper())
    return [(n, f) for n, f in out if len(f) > 1]


def report() -> None:
    """Sweep every ANIMDEFS animation for inconsistent relief-map coverage."""
    lumps = {n.upper(): b for n, b in read_wad_lumps(WAD)}
    partial = 0
    for name, frames in animations():
        have = [f for f in frames if covered(f)]
        miss = [f for f in frames if not covered(f)]
        if not have or not miss:
            continue
        partial += 1
        print(f"{name}: {len(frames)} frames, {len(have)} with maps, "
              f"{len(miss)} without")
        donor = have[0]
        if donor not in lumps:
            print(f"  {donor} has no WAD lump (a TEXTURES composite) -- this tool "
                  f"cannot inspect it; the frames need their own maps")
            continue
        ref = Image.open(io.BytesIO(lumps[donor])).convert("RGB")
        for f in miss:
            if f not in lumps:
                print(f"  {f}: no WAD lump (TEXTURES composite) -- NEEDS ITS OWN maps")
                continue
            ok, why = shares_relief(ref, Image.open(io.BytesIO(lumps[f])).convert("RGB"))
            verdict = "copy-safe" if ok else "NEEDS ITS OWN maps"
            print(f"  {f}: {verdict} ({why})")
    if not partial:
        print("every ANIMDEFS animation has consistent relief-map coverage")
    else:
        print(f"\n{partial} animation(s) with partial coverage")


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    dry = "--dry-run" in sys.argv

    if "--report" in sys.argv:
        report()
        return

    lumps = {n.upper(): b for n, b in read_wad_lumps(WAD)}
    for base in args or ["CTEL"]:
        names = frames_for(base)
        if len(names) < 2:
            print(f"{base}: not an animation ({len(names)} frame(s)) -- skipped")
            continue

        first, rest = names[0], names[1:]
        # A bare lump sharing the base name (STRAKY beside STRAKY1) is the same
        # surface under another name and wants the same maps; frames_for cannot
        # see it because its suffix is not numeric.
        if base in lumps and base not in names:
            rest = rest + [base]
        img0 = Image.open(io.BytesIO(lumps[first])).convert("RGB")
        print(f"{base}: {len(names)} frames, reference {first}")

        # Decide once per frame, not once per frame per suffix -- otherwise a
        # refusal is printed three times and the images are compared three times.
        verdict: dict[str, tuple[bool, str]] = {}
        for nm in rest:
            verdict[nm] = shares_relief(
                img0, Image.open(io.BytesIO(lumps[nm])).convert("RGB")
            )
        for nm, (ok, why) in verdict.items():
            print(f"  {nm}: {'shares' if ok else 'NEEDS ITS OWN map'} -- {why}")

        for suf in SUFFIXES:
            src = OMAT / f"{first}{suf}.png"
            if not src.exists():
                print(f"  {suf}: {first} has none -- nothing to share")
                continue
            wrote = 0
            for nm in rest:
                if not verdict[nm][0]:
                    continue
                for d in DIRS:
                    dst = d / f"{nm}{suf}.png"
                    if dst.exists():
                        continue
                    if dry:
                        print(f"  would write {dst}")
                    else:
                        dst.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copyfile(src, dst)
                        wrote += 1
            if not dry:
                shared = sum(1 for nm in rest if verdict[nm][0])
                print(f"  {suf}: shared with {shared} frame(s), {wrote} file(s) written")


if __name__ == "__main__":
    main()
