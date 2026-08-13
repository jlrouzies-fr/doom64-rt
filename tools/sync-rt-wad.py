"""
Push rt-wad-overlay/ into every rt/wad the engine might load.

Why this exists
---------------
`rt/wad` is NOT a Doom 64 Retribution resource - it belongs to the gzdoom-rt
engine (Doom: Ray Traced). It is appended AFTER every `-file` PWAD in
`GetCmdLineFiles` (d_main.cpp:1960), so it OVERRIDES the mod rather than the
other way round. That means our menu/cvar customisations cannot live in a pk3
loaded via `-file`: nothing loaded that way can win against rt/wad.

They also cannot simply live in rt/wad itself, because both rt/wad trees are
gitignored (.gitignore:16 and :18) - edits there are invisible to git and are
lost if the tree is refreshed from a build or a dist copy.

So the tracked master copy lives in `rt-wad-overlay/` and this script mirrors it
into the real trees. Edit the overlay, run this, relaunch.

The live tree is the one under build/ - the launcher does `cd /d %ENGINE%`
before running gzdoom.exe, so that is what actually loads. runtime-mod/ is the
distributable copy and is kept in step so the two never drift.

Usage:
    py -3 tools/sync-rt-wad.py            # copy overlay -> both trees
    py -3 tools/sync-rt-wad.py --check    # report drift, change nothing
"""

import argparse
import filecmp
import os
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OVERLAY = os.path.join(ROOT, "rt-wad-overlay")

TARGETS = [
    # the live one: the launcher cd's here, so this is what the game reads
    os.path.join(ROOT, "sourcecode", "gzdoom-rt", "build", "RelWithDebInfo", "rt", "wad"),
    # the distributable copy
    os.path.join(ROOT, "runtime-mod", "rt", "wad"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="report drift without copying")
    args = ap.parse_args()

    files = sorted(f for f in os.listdir(OVERLAY) if not f.startswith("."))
    if not files:
        raise SystemExit("rt-wad-overlay/ is empty")

    drift = 0
    for target in TARGETS:
        if not os.path.isdir(target):
            print(f"MISSING target, skipped: {target}")
            continue
        for f in files:
            src = os.path.join(OVERLAY, f)
            dst = os.path.join(target, f)
            same = os.path.exists(dst) and filecmp.cmp(src, dst, shallow=False)
            if same:
                print(f"  ok    {f}  ->  {target}")
                continue
            drift += 1
            if args.check:
                print(f"  DRIFT {f}  ->  {target}")
            else:
                shutil.copy2(src, dst)
                print(f"  COPIED {f}  ->  {target}")

    if args.check:
        print(f"\n{drift} file(s) differ from the overlay")
        raise SystemExit(1 if drift else 0)
    print(f"\nsynced {len(files)} file(s) into {len(TARGETS)} tree(s)")


if __name__ == "__main__":
    main()
