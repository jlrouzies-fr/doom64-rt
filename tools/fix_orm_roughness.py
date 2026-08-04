"""
ORM roughness clamp for DLSS-RR walk stability.

Rewrites ORM G (roughness): floor dielectrics high, metals milder.
Optional light blur on G. Raises roughnessDefault in scene JSON.

Default scope: MAP01 textures that have an _orm.png.
Use --all for every authored _orm under Retribution-RT-Materials.

    python tools/fix_orm_roughness.py
    python tools/fix_orm_roughness.py --from-backup --floor 0.82 --metal-floor 0.55 --blur --blur-always
"""
from __future__ import annotations

import argparse
import json
import shutil
import time
from pathlib import Path

from PIL import Image, ImageFilter

ROOT = Path(r"G:\AI\Doom64-RT")
OVERLAY_MAT = ROOT / r"Doom64-Retribution\Retribution-RT-Materials\rt\mat"
ENGINE_RT = ROOT / r"sourcecode\gzdoom-rt\build\RelWithDebInfo\rt"
ENGINE_MAT = ENGINE_RT / "mat"
ENGINE_MAT_DEV = ENGINE_RT / "mat_dev"
SCENE_OVERLAY = (
    ROOT
    / r"Doom64-Retribution\Retribution-RT-Materials\rt\data\scenes\d64rtr_v15_map01\textures.json"
)
SCENE_ENGINE = ENGINE_RT / r"data\scenes\d64rtr_v15_map01\textures.json"
OUT_DIR = ROOT / r"tools\_orm_rough_fix"
BACKUP_DIR = OUT_DIR / "backup"
MANIFEST_PATH = OUT_DIR / "manifest.json"

try:
    import numpy as np

    HAS_NP = True
except ImportError:
    HAS_NP = False


def map01_texture_names(scene_json: Path) -> list[str]:
    doc = json.loads(scene_json.read_text(encoding="utf-8"))
    names = []
    for e in doc.get("array") or []:
        if isinstance(e, dict) and e.get("textureName"):
            names.append(str(e["textureName"]))
    return names


def all_orm_texture_names(mat_dir: Path) -> list[str]:
    return sorted({p.name[: -len("_orm.png")] for p in mat_dir.glob("*_orm.png")})


def mean_abs_grad_g(g_u8, step: int = 4) -> float:
    """Rough high-frequency score on G channel (0..1 scale)."""
    if HAS_NP:
        g = g_u8.astype(np.float32) / 255.0
        h, w = g.shape
        s = max(1, step)
        dx = np.abs(g[::s, s:] - g[::s, :-s]).mean() if w > s else 0.0
        dy = np.abs(g[s:, ::s] - g[:-s, ::s]).mean() if h > s else 0.0
        return float(0.5 * (dx + dy))
    w, h = g_u8.size
    px = g_u8.load()
    s = max(1, step)
    diffs = []
    for y in range(0, h - s, s):
        for x in range(0, w - s, s):
            v = px[x, y]
            diffs.append(abs(px[x + s, y] - v))
            diffs.append(abs(px[x, y + s] - v))
    return (sum(diffs) / len(diffs) / 255.0) if diffs else 0.0


def rewrite_roughness(
    orm: Image.Image,
    *,
    floor_dielectric: float,
    floor_metal: float,
    metal_thresh: float,
    blur: bool,
    blur_always: bool,
    blur_hf_thresh: float,
    blur_radius: float,
) -> tuple[Image.Image, dict]:
    rgb = orm.convert("RGB")
    do_blur = bool(blur and blur_radius > 0)

    def apply_g_blur(g_img: Image.Image) -> Image.Image:
        return g_img.filter(ImageFilter.BoxBlur(blur_radius))

    if HAS_NP:
        arr = np.asarray(rgb, dtype=np.float32)
        ao = arr[:, :, 0]
        rough = arr[:, :, 1] / 255.0
        metal = arr[:, :, 2] / 255.0
        mean_g0 = float(rough.mean())
        frac_lo0 = float((rough < 0.5).mean())
        hf0 = mean_abs_grad_g(arr[:, :, 1])
        should_blur = do_blur and (blur_always or hf0 >= blur_hf_thresh)

        t = np.clip((metal - metal_thresh) / max(1e-6, 1.0 - metal_thresh), 0.0, 1.0)
        floor = floor_dielectric * (1.0 - t) + floor_metal * t
        rough_new = np.maximum(rough, floor)

        g_img = Image.fromarray(np.clip(rough_new * 255.0 + 0.5, 0, 255).astype(np.uint8), mode="L")
        if should_blur:
            g_img = apply_g_blur(g_img)
            rough_new = np.asarray(g_img, dtype=np.float32) / 255.0
            rough_new = np.maximum(rough_new, floor)

        out = np.stack(
            [
                np.clip(ao + 0.5, 0, 255).astype(np.uint8),
                np.clip(rough_new * 255.0 + 0.5, 0, 255).astype(np.uint8),
                np.clip(metal * 255.0 + 0.5, 0, 255).astype(np.uint8),
            ],
            axis=-1,
        )
        new_img = Image.fromarray(out, mode="RGB")
        mean_g1 = float(rough_new.mean())
        frac_lo1 = float((rough_new < 0.5).mean())
        hf1 = mean_abs_grad_g(out[:, :, 1])
    else:
        r_ch, g_ch, b_ch = rgb.split()
        mean_g0 = sum(g_ch.getdata()) / (255.0 * g_ch.size[0] * g_ch.size[1])
        frac_lo0 = sum(1 for v in g_ch.getdata() if v < 128) / (g_ch.size[0] * g_ch.size[1])
        hf0 = mean_abs_grad_g(g_ch)
        should_blur = do_blur and (blur_always or hf0 >= blur_hf_thresh)
        floor_d_u8 = int(round(floor_dielectric * 255))
        floor_m_u8 = int(round(floor_metal * 255))
        mt_u8 = int(round(metal_thresh * 255))

        def lift(px_g: int, px_b: int) -> int:
            if px_b <= mt_u8:
                return max(px_g, floor_d_u8)
            t = (px_b - mt_u8) / max(1, 255 - mt_u8)
            fl = int(round(floor_d_u8 * (1.0 - t) + floor_m_u8 * t))
            return max(px_g, fl)

        g_only = Image.frombytes(
            "L",
            g_ch.size,
            bytes(lift(gv, bv) for gv, bv in zip(g_ch.getdata(), b_ch.getdata())),
        )
        if should_blur:
            g_only = apply_g_blur(g_only)
            g_only = Image.frombytes(
                "L",
                g_only.size,
                bytes(lift(gv, bv) for gv, bv in zip(g_only.getdata(), b_ch.getdata())),
            )
        new_img = Image.merge("RGB", (r_ch, g_only, b_ch))
        mean_g1 = sum(g_only.getdata()) / (255.0 * g_only.size[0] * g_only.size[1])
        frac_lo1 = sum(1 for v in g_only.getdata() if v < 128) / (g_only.size[0] * g_only.size[1])
        hf1 = mean_abs_grad_g(g_only)

    stats = {
        "meanG_before": mean_g0,
        "meanG_after": mean_g1,
        "fracG_lt_0_5_before": frac_lo0,
        "fracG_lt_0_5_after": frac_lo1,
        "hf_before": hf0,
        "hf_after": hf1,
        "blurred": bool(should_blur),
    }
    return new_img, stats


def restore_from_backup(name: str) -> Path:
    src = BACKUP_DIR / f"{name}_orm.png"
    if not src.exists():
        raise FileNotFoundError(f"missing backup {src}")
    dest = OVERLAY_MAT / f"{name}_orm.png"
    shutil.copy2(src, dest)
    return dest


def save_orm_everywhere(name: str, img: Image.Image, dry_run: bool) -> list[str]:
    written: list[str] = []
    for path in (
        OVERLAY_MAT / f"{name}_orm.png",
        ENGINE_MAT / f"{name}_orm.png",
        ENGINE_MAT_DEV / f"{name}_orm.png",
    ):
        if dry_run:
            written.append(str(path) + " (dry-run)")
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        img.save(path)
        written.append(str(path))
    return written


def backup_orm(src: Path, dry_run: bool) -> Path | None:
    if not src.exists():
        return None
    dest = BACKUP_DIR / src.name
    if dry_run:
        return dest
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    if not dest.exists():
        shutil.copy2(src, dest)
    return dest


def upsert_scene_roughness(
    scene_path: Path,
    *,
    floor_dielectric: float,
    floor_metal: float,
    metal_thresh: float,
    dry_run: bool,
) -> int:
    if not scene_path.exists():
        return 0
    doc = json.loads(scene_path.read_text(encoding="utf-8"))
    arr = doc.get("array") or []
    changed = 0
    for e in arr:
        if not isinstance(e, dict) or not e.get("textureName"):
            continue
        metal = float(e.get("metallicDefault", 0.0) or 0.0)
        floor = floor_metal if metal >= metal_thresh else floor_dielectric
        prev = e.get("roughnessDefault")
        prev_f = float(prev) if prev is not None else 0.0
        new_f = max(prev_f, floor)
        if prev is None or abs(new_f - prev_f) > 1e-6:
            e["roughnessDefault"] = round(new_f, 4)
            changed += 1
    if not dry_run and changed:
        scene_path.parent.mkdir(parents=True, exist_ok=True)
        scene_path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return changed


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--all", action="store_true", help="Every authored _orm.png")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument(
        "--floor",
        type=float,
        default=0.70,
        help="Minimum roughness for dielectric pixels (default 0.70)",
    )
    ap.add_argument(
        "--metal-floor",
        type=float,
        default=0.45,
        help="Minimum roughness for metallic pixels (default 0.45)",
    )
    ap.add_argument(
        "--metal-thresh",
        type=float,
        default=0.35,
        help="B channel above this treated as metal for floor lerp",
    )
    ap.add_argument(
        "--blur",
        action="store_true",
        help="BoxBlur on G when high-frequency score >= --blur-hf (or always with --blur-always)",
    )
    ap.add_argument(
        "--blur-always",
        action="store_true",
        help="With --blur, soft-blur every map's G (not only high-HF)",
    )
    ap.add_argument("--blur-hf", type=float, default=0.10, help="HF threshold for blur")
    ap.add_argument(
        "--blur-radius",
        type=float,
        default=1.0,
        help="PIL BoxBlur radius on G (default 1)",
    )
    ap.add_argument(
        "--from-backup",
        action="store_true",
        help="Restore each ORM from tools/_orm_rough_fix/backup before rewriting",
    )
    ap.add_argument("--no-meta", action="store_true", help="Skip roughnessDefault JSON upsert")
    args = ap.parse_args()

    if not HAS_NP:
        print("NOTE: numpy not found; using slower Pillow path. Prefer orm-vlm venv.")

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    if args.all:
        names = all_orm_texture_names(OVERLAY_MAT)
        print(f"Scope: ALL authored ORM ({len(names)})")
    else:
        names = [
            n
            for n in map01_texture_names(SCENE_OVERLAY)
            if (OVERLAY_MAT / f"{n}_orm.png").exists()
            or (BACKUP_DIR / f"{n}_orm.png").exists()
        ]
        print(f"Scope: MAP01 with _orm ({len(names)})")

    if args.limit > 0:
        names = names[: args.limit]
        print(f"Limited to {len(names)}")

    if args.from_backup:
        print(f"Restoring from {BACKUP_DIR}")

    manifest = {
        "version": 1,
        "floor": args.floor,
        "metal_floor": args.metal_floor,
        "metal_thresh": args.metal_thresh,
        "blur": bool(args.blur),
        "blur_always": bool(args.blur_always),
        "blur_hf": args.blur_hf,
        "blur_radius": args.blur_radius,
        "from_backup": bool(args.from_backup),
        "entries": {},
    }

    ok = fail = 0
    sum_g0 = sum_g1 = 0.0
    sum_lo0 = sum_lo1 = 0.0
    blurred_n = 0
    t0 = time.time()

    for i, name in enumerate(names, 1):
        orm_path = OVERLAY_MAT / f"{name}_orm.png"
        key = name.upper()
        try:
            if args.from_backup:
                orm_path = restore_from_backup(name)
            elif not orm_path.exists():
                raise FileNotFoundError(orm_path)
            orm = Image.open(orm_path)
            new_orm, stats = rewrite_roughness(
                orm,
                floor_dielectric=args.floor,
                floor_metal=args.metal_floor,
                metal_thresh=args.metal_thresh,
                blur=args.blur,
                blur_always=args.blur_always,
                blur_hf_thresh=args.blur_hf,
                blur_radius=args.blur_radius,
            )
            # Only seed backup from pre-fix source; never overwrite existing backups.
            if not args.from_backup:
                backup_orm(orm_path, args.dry_run)
            written = save_orm_everywhere(name, new_orm, args.dry_run)
            if stats["blurred"]:
                blurred_n += 1
            sum_g0 += stats["meanG_before"]
            sum_g1 += stats["meanG_after"]
            sum_lo0 += stats["fracG_lt_0_5_before"]
            sum_lo1 += stats["fracG_lt_0_5_after"]
            manifest["entries"][key] = {
                "textureName": name,
                "stats": stats,
                "status": "ok",
                "written": written,
                "dry_run": bool(args.dry_run),
            }
            ok += 1
            print(
                f"[{i}/{len(names)}] {name}: "
                f"meanG {stats['meanG_before']:.3f}->{stats['meanG_after']:.3f} "
                f"frac<0.5 {stats['fracG_lt_0_5_before']:.1%}->{stats['fracG_lt_0_5_after']:.1%}"
                + (" blur" if stats["blurred"] else "")
            )
        except Exception as e:
            fail += 1
            manifest["entries"][key] = {
                "textureName": name,
                "status": "error",
                "error": str(e),
            }
            print(f"[{i}/{len(names)}] {name}: ERROR {e}")

    n = max(ok, 1)
    manifest["ok"] = ok
    manifest["fail"] = fail
    manifest["blurred"] = blurred_n
    manifest["meanG_before"] = sum_g0 / n
    manifest["meanG_after"] = sum_g1 / n
    manifest["fracG_lt_0_5_before"] = sum_lo0 / n
    manifest["fracG_lt_0_5_after"] = sum_lo1 / n
    manifest["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")

    if not args.no_meta:
        c1 = upsert_scene_roughness(
            SCENE_OVERLAY,
            floor_dielectric=args.floor,
            floor_metal=args.metal_floor,
            metal_thresh=args.metal_thresh,
            dry_run=args.dry_run,
        )
        c2 = upsert_scene_roughness(
            SCENE_ENGINE,
            floor_dielectric=args.floor,
            floor_metal=args.metal_floor,
            metal_thresh=args.metal_thresh,
            dry_run=args.dry_run,
        )
        manifest["roughnessDefault_overlay"] = c1
        manifest["roughnessDefault_engine"] = c2
        print(f"Updated roughnessDefault: overlay={c1} engine={c2}")

    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    elapsed = time.time() - t0
    print(
        f"Done. ok={ok} fail={fail} blurred={blurred_n} in {elapsed:.1f}s. "
        f"meanG {manifest['meanG_before']:.3f}->{manifest['meanG_after']:.3f} "
        f"fracG<0.5 {manifest['fracG_lt_0_5_before']:.1%}->{manifest['fracG_lt_0_5_after']:.1%}"
    )
    print(f"Manifest: {MANIFEST_PATH}")
    return 0 if fail == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
