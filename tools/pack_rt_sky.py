"""Pack d64r-rt-sky.pk3 (night sky + moon).

The pk3 was hand-assembled until the moon arrived; it now carries a generated
texture, so it needs a builder. Run tools/gen_moon_sky.py first if MOONSKY.png
is missing.

MOONSKY_preview.png is deliberately NOT packed -- it is a brightened copy for
looking at on a monitor, and shipping it would put a second, wrong sky texture
in the archive under a name GZDoom would happily resolve.
"""
from __future__ import annotations

import zipfile
from pathlib import Path

ROOT = Path(r"G:\AI\Doom64-RT")
SRC = ROOT / r"tools\d64r-rt-sky"
OUT = ROOT / r"Doom64-Retribution\d64r-rt-sky.pk3"

NAMES = (
    "MAPINFO",
    "ZSCRIPT",
    "textures/MOONSKY.png",
)


def main() -> None:
    missing = [n for n in NAMES if not (SRC / n).is_file()]
    if missing:
        raise SystemExit(
            f"missing under {SRC}: {', '.join(missing)}\n"
            "(MOONSKY.png: python tools/gen_moon_sky.py)"
        )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(OUT, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name in NAMES:
            zf.write(SRC / name, name)
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes): {', '.join(NAMES)}")


if __name__ == "__main__":
    main()
