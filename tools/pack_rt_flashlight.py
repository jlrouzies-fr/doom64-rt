"""Pack d64r-rt-flashlight.pk3 (battery HUD EventHandler + battery sound cues).

The D64FLK*.wav cues come from tools/gen_flashlight_sounds.py -- run that first
if they are missing.
"""
from __future__ import annotations

import zipfile
from pathlib import Path

# Repo root, derived from this file so a clone can live anywhere.
PROJ_ROOT = Path(__file__).resolve().parents[1]

ROOT = PROJ_ROOT
SRC = ROOT / r"tools\d64r-rt-flashlight"
OUT = ROOT / r"Doom64-Retribution\d64r-rt-flashlight.pk3"


NAMES = (
    "ZSCRIPT",
    "MAPINFO",
    "KEYCONF",
    "SNDINFO",
    "CVARINFO",
    "D64FLKO.wav",
    "D64FLKR.wav",
    "D64FLKN.wav",
)


def main() -> None:
    missing = [n for n in NAMES if not (SRC / n).is_file()]
    if missing:
        raise SystemExit(
            f"missing under {SRC}: {', '.join(missing)}\n"
            "(WAVs: python tools/gen_flashlight_sounds.py)"
        )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(OUT, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name in NAMES:
            zf.write(SRC / name, name)
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
