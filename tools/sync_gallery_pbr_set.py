"""
Sync PBR companion maps into the engine rt/mat/ tree for gallery A/B.

  baseline  — Retribution-RT-Materials (authored / gallery stubs)
  ce        — Retribution-RT-Materials-CE (converted from DoomCE GFX.PBR)

Only touches *_orm.png and *_n.png. Leaves *_e.png (eyes/world emis) alone.

Usage:
  python tools/sync_gallery_pbr_set.py baseline
  python tools/sync_gallery_pbr_set.py ce
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

# Repo root, derived from this file so a clone can live anywhere.
PROJ_ROOT = Path(__file__).resolve().parents[1]

ROOT = PROJ_ROOT
ENGINE_MAT = ROOT / r"sourcecode\gzdoom-rt\build\RelWithDebInfo\rt\mat"
BASE_MAT = ROOT / r"Doom64-Retribution\Retribution-RT-Materials\rt\mat"
CE_MAT = ROOT / r"Doom64-Retribution\Retribution-RT-Materials-CE\rt\mat"
CE_MANIFEST = ROOT / r"Doom64-Retribution\Retribution-RT-Materials-CE\manifest.json"
STAMP = ENGINE_MAT / "_pbr_set.txt"


def copy_pair(src_dir: Path, names: set[str] | None = None) -> int:
    n = 0
    if not src_dir.exists():
        raise SystemExit(f"missing mat dir: {src_dir}")
    ENGINE_MAT.mkdir(parents=True, exist_ok=True)
    for path in src_dir.glob("*_orm.png"):
        stem = path.name[: -len("_orm.png")]
        if names is not None and stem not in names:
            continue
        shutil.copy2(path, ENGINE_MAT / path.name)
        n_src = src_dir / f"{stem}_n.png"
        if n_src.exists():
            shutil.copy2(n_src, ENGINE_MAT / n_src.name)
        n += 1
    # also copy orphan normals if any
    for path in src_dir.glob("*_n.png"):
        stem = path.name[: -len("_n.png")]
        if names is not None and stem not in names:
            continue
        dst = ENGINE_MAT / path.name
        if not dst.exists() or names is not None:
            shutil.copy2(path, dst)
    return n


def sync_baseline() -> None:
    """Restore baseline orm/n, and undo CE-only overlays when possible."""
    ce_names: set[str] = set()
    if CE_MANIFEST.exists():
        doc = json.loads(CE_MANIFEST.read_text(encoding="utf-8"))
        ce_names = set(doc.get("converted", []))

    # Restore every baseline orm/n
    count = copy_pair(BASE_MAT)
    # For CE names that baseline does not cover, remove engine overlays so stubs/defaults return
    removed = 0
    for stem in ce_names:
        base_orm = BASE_MAT / f"{stem}_orm.png"
        if base_orm.exists():
            continue
        for suf in ("_orm.png", "_n.png"):
            p = ENGINE_MAT / f"{stem}{suf}"
            if p.exists():
                p.unlink()
                removed += 1

    STAMP.write_text("baseline\n", encoding="utf-8")
    print(f"synced baseline orm/n pairs~{count} into {ENGINE_MAT} (removed CE-only={removed})")


def sync_ce() -> None:
    if not CE_MANIFEST.exists():
        raise SystemExit(
            "missing CE convert output — run: python tools/convert_ce_pbr_to_rt.py"
        )
    doc = json.loads(CE_MANIFEST.read_text(encoding="utf-8"))
    names = set(doc.get("converted", []))
    if not names:
        raise SystemExit("CE manifest has no converted textures")

    # Start from baseline so non-CE textures stay consistent, then overlay CE
    if BASE_MAT.exists():
        copy_pair(BASE_MAT)
    count = copy_pair(CE_MAT, names=names)
    STAMP.write_text("ce\n", encoding="utf-8")
    print(f"synced CE PBR overlay ({count} textures) into {ENGINE_MAT}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("set", choices=("baseline", "ce"))
    args = ap.parse_args()
    if args.set == "baseline":
        sync_baseline()
    else:
        sync_ce()


if __name__ == "__main__":
    main()
