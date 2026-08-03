"""Restore pre–wall-wash gallery emissive state for batch testing.

1) Restore global textures.json from pre_noemis backup (keys/FX/stock metas)
2) Regen world _e at visible mults (writes mat + mat_dev)
3) Regen FX + eyes overlays on top
4) Reseed batch scene textures.json from world emis

WARNING: the pre_noemis backup contains STOCK Doom II high-mult metas
(PLAY* @ 4.25 etc. — the wall-wash root cause). This script is only safe
because gen_world_emissives.py now scrubs stock global emis BY DEFAULT
(--no-scrub must never be passed here). A final check_emis_hygiene.py gate
verifies the global JSON is clean after the chain; treat a FAIL as fatal.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(r"G:\AI\Doom64-RT")
PY = sys.executable
DATA = ROOT / r"sourcecode\gzdoom-rt\build\RelWithDebInfo\rt\data"
BACKUP = DATA / "textures.json.pre_noemis_ab"
GLOBAL = DATA / "textures.json"
WORLD = (
    ROOT
    / r"Doom64-Retribution\Retribution-RT-Materials\rt\data\textures_world_emis.json"
)
ENGINE_SCENES = DATA / "scenes"
OVERLAY_SCENES = (
    ROOT / r"Doom64-Retribution\Retribution-RT-Materials\rt\data\scenes"
)


def main() -> int:
    if not BACKUP.exists():
        print(f"ERROR: missing backup {BACKUP}")
        return 1
    shutil.copy2(BACKUP, GLOBAL)
    print(f"restored {GLOBAL.name} from {BACKUP.name} ({BACKUP.stat().st_size} bytes)")

    for script in (
        "gen_world_emissives.py",  # scrubs stock global emis by default — required
        "gen_fx_emissives.py",
        "gen_enemy_eye_emissives.py",
    ):
        print(f"== {script} ==")
        subprocess.check_call([PY, str(ROOT / "tools" / script)], cwd=str(ROOT / "tools"))

    world = json.loads(WORLD.read_text(encoding="utf-8"))
    text = json.dumps(world, indent=2) + "\n"
    for i in range(1, 9):
        stem = f"d64rtexg{i:02d}_map99"
        for base in (ENGINE_SCENES, OVERLAY_SCENES):
            d = base / stem
            d.mkdir(parents=True, exist_ok=True)
            (d / "textures.json").write_text(text, encoding="utf-8")
    # full gallery scene already upserted by gen_world; reseed for consistency
    for base in (ENGINE_SCENES, OVERLAY_SCENES):
        d = base / "d64rtexg_map99"
        if d.exists():
            # merge: keep existing roughness entries, upsert world emis via gen already
            pass

    # sanity
    sexit = (
        ROOT
        / r"sourcecode\gzdoom-rt\build\RelWithDebInfo\rt\mat_dev\SEXIT_e.png"
    )
    print(f"SEXIT mat_dev exists={sexit.exists()} bytes={sexit.stat().st_size if sexit.exists() else 0}")
    t = GLOBAL.read_text(encoding="utf-8", errors="replace")
    print("RKEYB0 still in global:", "RKEYB0" in t, "emissiveMult count:", t.count("emissiveMult"))

    # Hard gate: restored backup carried stock metas — hygiene must confirm
    # the regen chain scrubbed them back out.
    rc = subprocess.call(
        [PY, str(ROOT / "tools" / "check_emis_hygiene.py")], cwd=str(ROOT / "tools")
    )
    if rc != 0:
        print("FATAL: hygiene FAIL after restore — global meta contaminated")
        return 2
    print("done — launch: tools\\launch-gallery-batch.cmd 2  (SEXIT/SMONBA)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
