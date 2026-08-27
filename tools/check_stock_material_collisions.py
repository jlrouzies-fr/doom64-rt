"""Stock Doom II materials must not land on Doom 64 art that shares a lump name.

The trap
--------
`rt/mat` in a dev build (and in any install made by copying the gzdoom-rt drop
rather than by `package_release.py`) still contains the ENTIRE Doom II: Ray
Traced material set that shipped with the engine -- ~149 `*_e.ktx2` alone.
RTGL1 keys materials by texture NAME, and Doom 64 Retribution reuses a number of
id's original lump names for completely different art. Where the names collide,
Doom II's map is applied to Doom 64's sprite.

The 2026-08-27 report was the chaingun: "the muzzle flash is supposed to be
purple, and it is, but there is also a yellow/red classic muzzle flash". Both
are true. `CHGFA0`/`CHGFB0` in Retribution are a BLUE-PURPLE flash (peak RGB
165,148,247); in Doom II they are the classic warm flash, and Doom II RT
authored `CHGFA0_e.ktx2` to match ITS art. Nothing in this project ever wrote
those files -- they are byte-identical to `gzdoom-rt-1.0.2/rt/mat/`, dated to
the vendor drop.

Two details made it read as a renderer bug rather than a stray file:

  * The chaingun ALTERNATES flash states shot to shot -- `A_GunFlash` ->
    `Flash:` (CHGF A/B) then `A_GunFlash("Flash2")` -> `Flash2:` (CHGF C/D).
    Doom II's chaingun flash has only A and B frames, so exactly half the
    flashes were contaminated and the other half were correct. It looked like a
    flicker between two muzzle flashes, which is what it was.
  * `mat_dev` does NOT shadow `mat` wholesale. Under `developerMode` RTGL1 tries
    the raw loader first and FALLS THROUGH to the KTX2 loader PER FILE
    (`TextureManager.h:179` builds the tuple, `TextureOverrides.cpp:117` chains
    to the next loader when the file is absent). So "we ship mat_dev, mat is
    stock and therefore inert" is false: mat wins for every name mat_dev does
    not define.

Releases are immune -- `package_release.py` drops `rt/mat` by omission from
RT_KEEP_DIRS -- which is exactly why this reproduced only on the dev machine and
no player ever saw it. That asymmetry is the reason this check exists: the
failure is invisible in the artefact you ship and visible only where you test.

What it checks
--------------
For every map in a build's `rt/mat` that is byte-identical to the vendor drop
(so our own authored KTX2 is never flagged), whose base name is used by the
Doom 64 art, and which `rt/mat_dev` does not define: FAIL.

Usage:
  python tools/check_stock_material_collisions.py
  python tools/check_stock_material_collisions.py --root "G:/Games/Doom64-RT"
  python tools/check_stock_material_collisions.py --fix   # move them to mat_e_quarantine/
"""

from __future__ import annotations

import argparse
import hashlib
import re
import shutil
import struct
import sys
import zipfile
from pathlib import Path

PROJ_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_ROOT = PROJ_ROOT / r"sourcecode\gzdoom-rt\build\RelWithDebInfo"
VENDOR_MAT = PROJ_ROOT / r"gzdoom-rt-1.0.2\rt\mat"

# Where the Doom 64 side's texture and sprite names come from. The base WAD plus
# every d64r-* overlay the launcher can load -- an overlay that renames art is
# exactly the sort of thing that would introduce a NEW collision quietly.
ART_GLOBS = ("D64RTR_v15.WAD", "d64r-*.wad", "d64r-*.pk3")
ART_DIR = PROJ_ROOT / "Doom64-Retribution"

POSTFIX_RE = re.compile(r"^(.*?)(_e|_n|_orm|_h)\.ktx2$", re.I)

QUARANTINE = "mat_e_quarantine"


def md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()


def doom64_art_names() -> set[str]:
    """Every lump / entry name the Doom 64 side defines."""
    names: set[str] = set()
    files: list[Path] = []
    for g in ART_GLOBS:
        files.extend(sorted(ART_DIR.glob(g)))

    for p in files:
        blob = p.read_bytes()
        if blob[:4] in (b"PWAD", b"IWAD"):
            count, off = struct.unpack_from("<ii", blob, 4)
            for i in range(count):
                _lo, _sz, nm = struct.unpack_from("<ii8s", blob, off + 16 * i)
                names.add(nm.rstrip(b"\0").decode("latin1").upper())
        else:
            try:
                for entry in zipfile.ZipFile(p).namelist():
                    names.add(Path(entry).stem.upper())
            except zipfile.BadZipFile:
                continue
    return names


def find_collisions(root: Path, names: set[str]) -> list[tuple[Path, str, str]]:
    """(live file, base name, postfix) for each stock map that will be applied."""
    mat = root / "rt" / "mat"
    mat_dev = root / "rt" / "mat_dev"
    if not mat.exists():
        return []

    out = []
    for f in sorted(mat.glob("*.ktx2")):
        m = POSTFIX_RE.match(f.name)
        if not m:
            continue
        base, postfix = m.group(1).upper(), m.group(2).lower()
        if base not in names:
            continue
        vendor = VENDOR_MAT / f.name
        # Only vendor-identical files are stock. Anything we authored ourselves and
        # dropped into mat/ is ours, however much its name looks like id's.
        if not vendor.exists() or md5(vendor) != md5(f):
            continue
        # mat_dev defines it -> the raw loader wins and mat is never consulted.
        if any(mat_dev.glob(f"{base}{postfix}.*")):
            continue
        out.append((f, base, postfix))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--root",
        default=str(DEFAULT_ROOT),
        help="game root holding rt/ (default: the RelWithDebInfo build)",
    )
    ap.add_argument(
        "--fix",
        action="store_true",
        help=f"move the offenders into rt/{QUARANTINE}/ instead of only reporting",
    )
    args = ap.parse_args()

    root = Path(args.root)
    if not (root / "rt").is_dir():
        sys.exit(f"no rt/ under {root}")
    if not VENDOR_MAT.is_dir():
        sys.exit(
            f"no vendor material set at {VENDOR_MAT} - cannot tell stock from authored"
        )

    names = doom64_art_names()
    if not names:
        sys.exit(f"found no Doom 64 art names under {ART_DIR} - check ART_GLOBS")

    hits = find_collisions(root, names)
    print(f"root:            {root}")
    print(f"doom64 art names: {len(names)}")
    print(f"collisions:       {len(hits)}")

    if not hits:
        print("\nPASS - no stock Doom II material is being applied to Doom 64 art.")
        return

    for f, base, postfix in hits:
        print(f"   {base:10s} {postfix:5s} {f}")

    if not args.fix:
        print(
            "\nFAIL - the maps above are Doom II: Ray Traced's, applied to Doom 64 art\n"
            "       that happens to share the lump name. Re-run with --fix to move them\n"
            f"       into rt/{QUARANTINE}/, or author a rt/mat_dev/<NAME><postfix>.png\n"
            "       so the raw loader wins."
        )
        sys.exit(1)

    quarantine = root / "rt" / QUARANTINE
    quarantine.mkdir(exist_ok=True)
    for f, _base, _postfix in hits:
        dst = quarantine / f.name
        if dst.exists():
            dst.unlink()
        shutil.move(str(f), str(dst))
    print(f"\nmoved {len(hits)} file(s) into {quarantine}")

    left = find_collisions(root, names)
    if left:
        sys.exit(f"FAIL - {len(left)} still live after --fix")
    print("PASS - clean.")


if __name__ == "__main__":
    main()
