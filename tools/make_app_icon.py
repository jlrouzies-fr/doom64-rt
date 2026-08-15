"""Build the Windows application icon from a single source PNG.

The exe's icon is a resource: src/win32/zdoom.rc carries

    IDI_ICON1  ICON  "icon1.ico"

so replacing src/win32/icon1.ico and rebuilding changes the taskbar entry,
the window and the file in Explorer. Nothing else needs editing.

WHY THIS IS A SCRIPT RATHER THAN A ONE-LINE SAVE. Pillow will happily write a
multi-size .ico from one image, and the result looks wrong at 16 and 20 px: a
plain box downscale of busy art -- and this source is a circuit-panel plate
behind two numerals -- averages the detail into mud and the digits stop reading.
Each size is therefore resampled and then sharpened in proportion to how far it
fell, which keeps the numerals' edges when there are only sixteen pixels to say
"64" with.

The sizes are the ones Windows actually asks for: 16 and 20 in lists and the
taskbar, 24/32 in the tray and small icons, 48 in medium, 64/128/256 in large
and extra-large views and the Alt-Tab switcher.

Usage:
    python tools\\make_app_icon.py screen\\Icon64.png
    python tools\\make_app_icon.py screen\\Icon64.png --out some\\other.ico
    python tools\\make_app_icon.py --revert
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from PIL import Image, ImageEnhance, ImageFilter

PROJ_ROOT = Path(__file__).resolve().parent.parent
ICO = PROJ_ROOT / "sourcecode" / "gzdoom-rt" / "src" / "win32" / "icon1.ico"
BACKUP_SUFFIX = ".pre_d64rt"

SIZES = [256, 128, 64, 48, 32, 24, 20, 16]


def render(src: Image.Image, size: int) -> Image.Image:
    im = src.convert("RGBA")
    if size >= im.width:
        # Upscaling: LANCZOS on pixel-ish art keeps the edges from going soft.
        out = im.resize((size, size), Image.LANCZOS)
    else:
        out = im.resize((size, size), Image.LANCZOS)
        # The smaller the target, the more detail was just averaged away, so the
        # correction scales with the reduction rather than being a fixed number.
        drop = im.width / size
        if drop > 1.5:
            radius = 0.6 if size >= 32 else 0.4
            pct = min(180, int(60 * drop))
            out = out.filter(ImageFilter.UnsharpMask(radius=radius, percent=pct, threshold=2))
            # A touch of contrast as well: at 16 px the plate and the numerals
            # converge toward the same mid-tone and the digits stop separating.
            if size <= 24:
                out = ImageEnhance.Contrast(out).enhance(1.18)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("source", nargs="?", help="square PNG to build the icon from")
    ap.add_argument("--out", default=str(ICO))
    ap.add_argument("--revert", action="store_true")
    args = ap.parse_args()

    out = Path(args.out)
    backup = out.with_suffix(out.suffix + BACKUP_SUFFIX)

    if args.revert:
        if not backup.exists():
            sys.exit("no backup at %s" % backup)
        shutil.copy2(backup, out)
        backup.unlink()
        print("  restored %s" % out.name)
        return

    if not args.source:
        ap.error("give a source PNG, or --revert")
    src = Image.open(args.source).convert("RGBA")
    if src.width != src.height:
        print("  ! source is %dx%d, not square -- it will be squashed"
              % (src.width, src.height))

    if out.exists() and not backup.exists():
        shutil.copy2(out, backup)
        print("  backed up the stock icon to %s" % backup.name)

    frames = [render(src, s) for s in SIZES]
    # append_images carries the rest; sizes= must list them all or Pillow keeps one.
    frames[0].save(out, format="ICO", sizes=[(s, s) for s in SIZES])
    print("  %s  <-  %s" % (out, args.source))
    print("  sizes: %s" % ", ".join(str(s) for s in SIZES))
    print("  %.1f KB" % (out.stat().st_size / 1024))
    print("\n  Rebuild to see it:  .\\tools\\build-gzdoom-rt.cmd")


if __name__ == "__main__":
    main()
