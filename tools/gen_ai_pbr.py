"""
Local AI companion maps for Retribution textures (keeps original albedo pixels).

Pipeline (RTX-friendly via Diffusers):
  1) Nearest-upscale albedo
  2) MarigoldNormalsPipeline → TEX_n.png
  3) ORM: heuristic rivet metal (default) or Marigold IID / solid
  4) Pack ORM (G=rough, B=metal; R≈AO from luma) → TEX_orm.png
     into rt/mat_dev/ (PNG authoring path)

Default ORM is sparse hardware metal — IID often chromes rock panels.
Does NOT restyle albedo. Does NOT set isMirror. Uses tools/.venv-ai.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

ROOT = Path(r"G:\AI\Doom64-RT")
sys.path.insert(0, str(ROOT / "tools"))
from gen_detail_orm import (  # noqa: E402
    BOOTHS,
    MAT,
    MAT_DEV,
    OMAT,
    category_base,
    make_orm,
    solid_orm_image,
    wad_png,
)

DEFAULT_NORMALS = "prs-eth/marigold-normals-v1-1"
DEFAULT_IID = "prs-eth/marigold-iid-appearance-v1-1"


def _ensure_min_side(img: Image.Image, min_side: int) -> Image.Image:
    w, h = img.size
    long_side = max(w, h)
    if long_side >= min_side:
        return img.convert("RGB")
    scale = int(np.ceil(min_side / long_side))
    return img.resize((w * scale, h * scale), Image.Resampling.NEAREST).convert("RGB")


def _to_hwc(pred: np.ndarray) -> np.ndarray:
    arr = np.asarray(pred)
    if arr.ndim == 4:
        arr = arr[0]
    if arr.ndim == 3 and arr.shape[0] in (1, 2, 3, 4) and arr.shape[0] < arr.shape[-1]:
        arr = np.transpose(arr, (1, 2, 0))
    return arr.astype(np.float32)


def _prediction_to_rgb(pred: np.ndarray) -> Image.Image:
    """Marigold normals prediction [-1,1] → OpenGL-ish RGB normal map."""
    arr = _to_hwc(pred)
    if arr.shape[-1] > 3:
        arr = arr[..., :3]
    rgb = ((arr * 0.5 + 0.5) * 255.0).clip(0, 255).astype(np.uint8)
    return Image.fromarray(rgb, mode="RGB")


def boost_normals(nrgb: Image.Image, strength: float) -> Image.Image:
    arr = np.asarray(nrgb).astype(np.float32) / 255.0
    n = arr * 2.0 - 1.0
    n[..., 0] *= strength
    n[..., 1] *= strength
    inv = np.linalg.norm(n, axis=2, keepdims=True)
    inv = np.maximum(inv, 1e-6)
    n = n / inv
    out = ((n * 0.5 + 0.5) * 255.0).clip(0, 255).astype(np.uint8)
    return Image.fromarray(out, mode="RGB")


def _load_pipe(cls_name: str, model: str, dtype_name: str):
    import torch
    import diffusers

    dtype = torch.float16 if dtype_name == "fp16" else torch.float32
    kwargs: dict = {"torch_dtype": dtype}
    if dtype_name == "fp16":
        kwargs["variant"] = "fp16"
    cls = getattr(diffusers, cls_name)
    pipe = cls.from_pretrained(model, **kwargs).to("cuda")
    try:
        pipe.enable_attention_slicing()
    except Exception:
        pass
    return pipe


def load_normals_pipe(model: str = DEFAULT_NORMALS, dtype_name: str = "fp16"):
    return _load_pipe("MarigoldNormalsPipeline", model, dtype_name)


def load_iid_pipe(model: str = DEFAULT_IID, dtype_name: str = "fp16"):
    return _load_pipe("MarigoldIntrinsicsPipeline", model, dtype_name)


def estimate_normal(
    pipe,
    albedo: Image.Image,
    *,
    min_side: int = 768,
    ensemble: int = 1,
    steps: int = 4,
    strength: float = 2.4,
) -> Image.Image:
    up = _ensure_min_side(albedo, min_side)
    out = pipe(
        up,
        num_inference_steps=steps,
        ensemble_size=ensemble,
        processing_resolution=None,
        match_input_resolution=True,
    )
    nrgb = _prediction_to_rgb(out.prediction)
    nrgb = nrgb.resize(albedo.size, Image.Resampling.NEAREST)
    return boost_normals(nrgb, strength)


def _iid_maps(pipe, up: Image.Image, *, steps: int, ensemble: int) -> tuple[np.ndarray, np.ndarray]:
    """Return (roughness, metallicity) float maps in [0,1] at `up` resolution."""
    out = pipe(
        up,
        num_inference_steps=steps,
        ensemble_size=ensemble,
        processing_resolution=None,
        match_input_resolution=True,
    )
    # Prefer named visualize output when available
    try:
        vis = pipe.image_processor.visualize_intrinsics(out.prediction, pipe.target_properties)
        entry = vis[0] if isinstance(vis, list) else vis
        rough_im = entry["roughness"].convert("L")
        metal_im = entry["metallicity"].convert("L")
        rough = np.asarray(rough_im).astype(np.float32) / 255.0
        metal = np.asarray(metal_im).astype(np.float32) / 255.0
        return rough, metal
    except Exception:
        pass

    arr = _to_hwc(out.prediction)
    # appearance IID: typically albedo RGB + roughness + metallicity, or stacked modalities
    props = getattr(pipe, "target_properties", None) or {}
    names = props.get("target_names") or props.get("names") or []
    if names and arr.ndim == 3:
        # channel layout follows target list
        name_l = [str(x).lower() for x in names]
        # find indices
        def find(*keys):
            for k in keys:
                for i, n in enumerate(name_l):
                    if k in n:
                        return i
            return None

        ri = find("rough")
        mi = find("metal")
        if ri is not None and mi is not None:
            return arr[..., ri].clip(0, 1), arr[..., mi].clip(0, 1)

    # Fallback: last two channels
    if arr.ndim == 3 and arr.shape[-1] >= 2:
        return arr[..., -2].clip(0, 1), arr[..., -1].clip(0, 1)
    raise RuntimeError(f"Unexpected IID prediction shape: {arr.shape}")


def estimate_orm_iid(
    pipe,
    name: str,
    albedo: Image.Image,
    *,
    min_side: int = 768,
    ensemble: int = 1,
    steps: int = 4,
    metal_gamma: float = 1.35,
    metal_scale: float = 0.92,
    rough_floor: float = 0.08,
) -> tuple[Image.Image, dict]:
    """
    IID → ORM. Keeps original albedo; AO from luma.
    metal_gamma > 1 softens mid metal so whole walls don't go chrome.
    """
    up = _ensure_min_side(albedo, min_side)
    rough, metal = _iid_maps(pipe, up, steps=steps, ensemble=ensemble)
    # nearest back to native grid
    rough_im = Image.fromarray((rough * 255).clip(0, 255).astype(np.uint8), "L")
    metal_im = Image.fromarray((metal * 255).clip(0, 255).astype(np.uint8), "L")
    rough_im = rough_im.resize(albedo.size, Image.Resampling.NEAREST)
    metal_im = metal_im.resize(albedo.size, Image.Resampling.NEAREST)
    rough = np.asarray(rough_im).astype(np.float32) / 255.0
    metal = np.asarray(metal_im).astype(np.float32) / 255.0

    base_r, base_m = category_base(name)

    # IID on Doom pixels is conservative (metal often ~0.2–0.4). Stretch
    # relative contrast into a usable band; keep floors non-chrome.
    def _norm01(x: np.ndarray) -> np.ndarray:
        lo, hi = float(x.min()), float(x.max())
        if hi - lo < 1e-4:
            return np.full_like(x, 0.5)
        return (x - lo) / (hi - lo)

    metal_n = _norm01(metal)
    rough_n = _norm01(rough)
    if base_m >= 0.25:
        # metal class: map contrast → glossy metal vs duller paint/rust
        metal = np.clip(0.18 + metal_n**metal_gamma * 0.78 * metal_scale, 0.0, 1.0)
        # invert rough contrast a bit toward metal (shinier where metal high)
        rough = np.clip(0.10 + rough_n * 0.55 * (1.0 - 0.55 * metal_n), 0.0, 1.0)
    else:
        metal = np.clip(metal_n * 0.22, 0.0, 1.0)
        rough = np.clip(0.45 + rough_n * 0.45, 0.0, 1.0)

    rough = np.clip(np.maximum(rough, rough_floor * (1.0 - metal)), 0.0, 1.0)

    luma = np.asarray(ImageOps.grayscale(albedo.convert("RGB"))).astype(np.float32) / 255.0
    ao = np.clip(40 + luma * 215, 0, 255)
    orm = np.stack(
        [ao, rough * 255.0, metal * 255.0, np.full_like(ao, 255.0)],
        axis=-1,
    ).astype(np.uint8)

    # honor albedo alpha
    if albedo.mode == "RGBA":
        a = np.asarray(albedo.split()[-1])
        orm[a < 8] = (255, int(base_r * 255), 0, 0)

    stats = {
        "rough_mean": round(float(rough.mean()), 3),
        "metal_mean": round(float(metal.mean()), 3),
        "metal_frac": round(float((metal > 0.55).mean()), 3),
    }
    return Image.fromarray(orm, "RGBA"), stats


def make_height(albedo: Image.Image, *, crazy: float = 1.0) -> Image.Image:
    """Grayscale height for RTGL1 TEX_h (parallax). crazy>>1 → nuclear contrast."""
    luma = np.asarray(ImageOps.grayscale(albedo.convert("RGB")), dtype=np.float32)
    lo, hi = float(luma.min()), float(luma.max())
    if hi - lo < 1e-3:
        h = np.full_like(luma, 128.0)
    else:
        h = (luma - lo) / (hi - lo)
        # bright = raised; stretch toward 0/1
        gamma = max(0.05, 1.0 / max(crazy, 0.05))
        h = np.power(h, gamma)
        if crazy >= 8.0:
            h = (h > 0.45).astype(np.float32)
    return Image.fromarray((h * 255.0).clip(0, 255).astype(np.uint8), "L")


def write_maps(
    name: str,
    orm: Image.Image,
    normal: Image.Image | None,
    height: Image.Image | None = None,
) -> None:
    for mat in (MAT_DEV, OMAT, MAT):
        mat.mkdir(parents=True, exist_ok=True)
        orm.save(mat / f"{name}_orm.png")
        npath = mat / f"{name}_n.png"
        if normal is not None:
            normal.save(npath)
        elif npath.exists():
            npath.unlink()
        hpath = mat / f"{name}_h.png"
        if height is not None:
            height.save(hpath)
        elif hpath.exists():
            hpath.unlink()


def resolve_names(
    names: list[str],
    indices: str,
    *,
    start: int | None = None,
    count: int | None = None,
    all_booths: bool = False,
) -> list[str]:
    out = list(names)
    booths = json.loads(BOOTHS.read_text(encoding="utf-8"))["booths"]
    if all_booths:
        out.extend(b["texture"] for b in booths)
    elif start is not None:
        n = len(booths) if count is None else max(0, count)
        out.extend(b["texture"] for b in booths[start : start + n])
    elif indices.strip():
        for part in indices.split(","):
            out.append(booths[int(part.strip())]["texture"])
    seen, uniq = set(), []
    for n in out:
        u = n.upper()
        if u not in seen:
            seen.add(u)
            uniq.append(n)
    if not uniq:
        raise SystemExit("Provide --names, --indices, --start/--count, or --all")
    return uniq


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--names", nargs="*")
    ap.add_argument("--indices", default="")
    ap.add_argument("--start", type=int, default=None, help="Booth index start (with --count)")
    ap.add_argument("--count", type=int, default=None, help="Booth count from --start")
    ap.add_argument("--all", action="store_true", help="All booths in booths.json")
    ap.add_argument("--mode", choices=("ai", "solid"), default="ai")
    ap.add_argument("--normals-model", default=DEFAULT_NORMALS)
    ap.add_argument("--iid-model", default=DEFAULT_IID)
    ap.add_argument("--min-side", type=int, default=768)
    ap.add_argument("--steps", type=int, default=4)
    ap.add_argument("--ensemble", type=int, default=1)
    ap.add_argument("--strength", type=float, default=2.8)
    ap.add_argument("--dtype", choices=("fp16", "fp32"), default="fp16")
    ap.add_argument(
        "--orm",
        choices=("iid", "heuristic", "solid"),
        default="heuristic",
        help="ORM source: sparse rivet heuristic (default), Marigold IID, or solid category",
    )
    ap.add_argument("--metal-gamma", type=float, default=1.35)
    ap.add_argument(
        "--height-crazy",
        type=float,
        default=0.0,
        help="If >0, write TEX_h.png from albedo (higher = more extreme parallax). 0=off",
    )
    args = ap.parse_args()

    names = resolve_names(
        list(args.names or []),
        args.indices,
        start=args.start,
        count=args.count,
        all_booths=args.all,
    )
    report = []

    def _height_for(albedo: Image.Image) -> Image.Image | None:
        if args.height_crazy and args.height_crazy > 0:
            return make_height(albedo, crazy=float(args.height_crazy))
        return None

    def _try_albedo(n: str) -> Image.Image | None:
        try:
            return wad_png(n)
        except KeyError:
            print(f"{n}: SKIP (no PNG/TEXTURES albedo in WAD)", flush=True)
            report.append({"texture": n, "mode": "skip", "reason": "missing_albedo"})
            return None

    if args.mode == "solid":
        for n in names:
            albedo = _try_albedo(n)
            if albedo is None:
                continue
            orm = solid_orm_image(n, albedo.size)
            write_maps(n, orm, None, None)  # strip normals + height
            st = {"texture": n, "size": list(albedo.size), "mode": "solid"}
            report.append(st)
            print(f"{n}: solid {albedo.size[0]}x{albedo.size[1]}")
    else:
        import torch

        if args.orm == "iid":
            # IID first, then normals (lower peak VRAM)
            print(f"loading IID {args.iid_model}…", flush=True)
            iid_pipe = load_iid_pipe(args.iid_model, args.dtype)
            iid_cache: dict[str, tuple[Image.Image, dict]] = {}
            for n in names:
                albedo = _try_albedo(n)
                if albedo is None:
                    continue
                print(f"  iid {n} {albedo.size[0]}x{albedo.size[1]}…", flush=True)
                orm, st = estimate_orm_iid(
                    iid_pipe,
                    n,
                    albedo,
                    min_side=args.min_side,
                    ensemble=args.ensemble,
                    steps=args.steps,
                    metal_gamma=args.metal_gamma,
                )
                iid_cache[n] = (orm, st)
                print(
                    f"    rough_mean={st['rough_mean']} metal_mean={st['metal_mean']} "
                    f"metal_frac={st['metal_frac']}"
                )
            del iid_pipe
            torch.cuda.empty_cache()
            print(f"loading normals {args.normals_model}…", flush=True)
            npipe = load_normals_pipe(args.normals_model, args.dtype)

            for n in names:
                if n not in iid_cache:
                    continue
                albedo = wad_png(n)
                print(f"  normals {n}…", flush=True)
                normal = estimate_normal(
                    npipe,
                    albedo,
                    min_side=args.min_side,
                    ensemble=args.ensemble,
                    steps=args.steps,
                    strength=args.strength,
                )
                orm, st = iid_cache[n]
                height = _height_for(albedo)
                write_maps(n, orm, normal, height)
                var = float(np.asarray(normal).astype(np.float32).var())
                row = {
                    "texture": n,
                    "size": list(albedo.size),
                    "mode": "ai-iid",
                    "normal_var": round(var, 2),
                    "strength": args.strength,
                    "height_crazy": args.height_crazy,
                    **st,
                }
                report.append(row)
                print(f"{n}: ai-iid normal_var={var:.1f} metal_frac={st['metal_frac']}")
        else:
            print(f"loading normals {args.normals_model}…", flush=True)
            npipe = load_normals_pipe(args.normals_model, args.dtype)
            for n in names:
                albedo = _try_albedo(n)
                if albedo is None:
                    continue
                print(f"  normals {n} {albedo.size[0]}x{albedo.size[1]}…", flush=True)
                normal = estimate_normal(
                    npipe,
                    albedo,
                    min_side=args.min_side,
                    ensemble=args.ensemble,
                    steps=args.steps,
                    strength=args.strength,
                )
                if args.orm == "solid":
                    orm = solid_orm_image(n, albedo.size)
                    st = {"rough_mean": None, "metal_mean": None, "metal_frac": None}
                else:
                    orm = make_orm(n, albedo)
                    g = np.asarray(orm)[..., 1].astype(np.float32) / 255.0
                    b = np.asarray(orm)[..., 2].astype(np.float32) / 255.0
                    st = {
                        "orm": "heuristic",
                        "rough_mean": round(float(g.mean()), 3),
                        "metal_mean": round(float(b.mean()), 3),
                        "metal_frac": round(float((b > 0.55).mean()), 3),
                    }
                height = _height_for(albedo)
                write_maps(n, orm, normal, height)
                var = float(np.asarray(normal).astype(np.float32).var())
                report.append(
                    {
                        "texture": n,
                        "size": list(albedo.size),
                        "mode": f"ai-{args.orm}",
                        "normal_var": round(var, 2),
                        "strength": args.strength,
                        "height_crazy": args.height_crazy,
                        **{k: v for k, v in st.items() if v is not None},
                    }
                )
                mf = st.get("metal_frac")
                extra = f" metal_frac={mf}" if mf is not None else ""
                print(f"{n}: ai-{args.orm} normal_var={var:.1f}{extra} height={args.height_crazy}")

    out = ROOT / r"tools\_gallery\ai_pbr_report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("wrote", out)


if __name__ == "__main__":
    main()
