"""Pack d64r-rt-flashlight.pk3 (battery HUD EventHandler + battery sound cues).

The D64FLK* / DFL*.wav cues come from tools/gen_flashlight_sounds.py or
tools/gen_flashlight_real_sounds.py -- run one of those first if they are
missing.
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
)


def main() -> None:
    # Auto-discover all WAVs in the source directory
    wav_names = sorted(f.name for f in SRC.glob("*.wav"))
    all_names = list(NAMES) + wav_names
    missing = [n for n in all_names if not (SRC / n).is_file()]
    if missing:
        raise SystemExit(
            f"missing under {SRC}: {', '.join(missing)}\n"
            "(WAVs: python tools/gen_flashlight_sounds.py or "
            "tools/gen_flashlight_real_sounds.py)"
        )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(OUT, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name in all_names:
            arcname = f"sounds/{name}" if name.endswith(".wav") else name
            zf.write(SRC / name, arcname)
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
