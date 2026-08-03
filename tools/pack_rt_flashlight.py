"""Pack d64r-rt-flashlight.pk3 (battery HUD EventHandler)."""
from __future__ import annotations

import zipfile
from pathlib import Path

ROOT = Path(r"G:\AI\Doom64-RT")
SRC = ROOT / r"tools\d64r-rt-flashlight"
OUT = ROOT / r"Doom64-Retribution\d64r-rt-flashlight.pk3"


def main() -> None:
    if not (SRC / "ZSCRIPT").is_file() or not (SRC / "MAPINFO").is_file():
        raise SystemExit(f"missing sources under {SRC}")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(OUT, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name in ("ZSCRIPT", "MAPINFO", "KEYCONF"):
            zf.write(SRC / name, name)
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
