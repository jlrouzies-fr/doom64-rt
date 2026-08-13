"""
Automatic ORM metallic fix using a local VLM on CUDA (Qwen2.5-VL-7B).

Classifies each albedo as dielectric | metal | mixed, then rewrites the
ORM metallic (B) channel to kill soft metal fog that stresses DLSS-RR.

Default scope: MAP01-used textures that have an _orm.png.
Use --all for every authored _orm under Retribution-RT-Materials.

Requires the project venv:
  deps\\orm-vlm\\venv\\Scripts\\python.exe tools\\fix_orm_metallic_ai.py
"""
from __future__ import annotations

import argparse
import json
import re
import struct
import time
from pathlib import Path

import numpy as np
from PIL import Image

# Repo root, derived from this file so a clone can live anywhere.
PROJ_ROOT = Path(__file__).resolve().parents[1]

ROOT = PROJ_ROOT
WAD = ROOT / r"Doom64-Retribution\D64RTR_v15.WAD"
OVERLAY_MAT = ROOT / r"Doom64-Retribution\Retribution-RT-Materials\rt\mat"
ENGINE_RT = ROOT / r"sourcecode\gzdoom-rt\build\RelWithDebInfo\rt"
ENGINE_MAT = ENGINE_RT / "mat"
ENGINE_MAT_DEV = ENGINE_RT / "mat_dev"
SCENE_OVERLAY = (
    ROOT
    / r"Doom64-Retribution\Retribution-RT-Materials\rt\data\scenes\d64rtr_v15_map01\textures.json"
)
SCENE_ENGINE = ENGINE_RT / r"data\scenes\d64rtr_v15_map01\textures.json"
GLOBAL_ENGINE = ENGINE_RT / r"data\textures.json"
OUT_DIR = ROOT / r"tools\_orm_metal_fix"
BACKUP_DIR = OUT_DIR / "backup"
MANIFEST_PATH = OUT_DIR / "manifest.json"
HF_CACHE = ROOT / r"deps\orm-vlm\hf-cache"
MODEL_ID = "Qwen/Qwen2.5-VL-7B-Instruct"

PROMPT = """You are classifying a classic Doom / Doom 64 wall or floor texture for PBR metalness.

Look at the albedo image. Reply with ONLY a single JSON object, no markdown:
{"class":"dielectric"|"metal"|"mixed","confidence":0.0}

Rules:
- dielectric: concrete, stone, brick, plaster, dirt, rusted or PAINTED panels, plastic, wood,
  tech walls with yellow/red/green paint or hazard stripes, monitors, switches, organic goo,
  glass screens without chrome — almost no bare metal. Prefer dielectric when unsure.
- metal: mostly bare steel / chrome / brushed metal / grated metal across MOST of the surface.
  Do NOT call painted Doom64 SPACE panels metal just because they look industrial.
- mixed: mostly dielectric with clear bare-metal trims, rivets, frames, or pipes only.

confidence is 0..1."""


def load_wad_pngs(wad_path: Path) -> dict[str, bytes]:
    """Map uppercased lump name -> PNG bytes for PNG lumps in the WAD."""
    data = wad_path.read_bytes()
    n, o = struct.unpack_from("<II", data, 4)
    out: dict[str, bytes] = {}
    for i in range(n):
        off, sz, raw = struct.unpack_from("<II8s", data, o + i * 16)
        if sz <= 0 or off < 0 or off + sz > len(data):
            continue
        blob = data[off : off + sz]
        if blob[:4] != b"\x89PNG":
            continue
        nm = raw.split(b"\0")[0].decode("ascii", "replace").rstrip().upper()
        if nm:
            out[nm] = blob
    return out


def map01_texture_names(scene_json: Path) -> list[str]:
    doc = json.loads(scene_json.read_text(encoding="utf-8"))
    arr = doc.get("array") or []
    names = []
    for e in arr:
        if isinstance(e, dict) and e.get("textureName"):
            names.append(str(e["textureName"]))
    return names


def all_orm_texture_names(mat_dir: Path) -> list[str]:
    return sorted({p.name[: -len("_orm.png")] for p in mat_dir.glob("*_orm.png")})


def thumb_albedo(img: Image.Image, max_side: int = 512) -> Image.Image:
    im = img.convert("RGB")
    w, h = im.size
    scale = min(1.0, max_side / max(w, h))
    if scale < 1.0:
        im = im.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.Resampling.BILINEAR)
    return im


def rewrite_metallic(orm: Image.Image, cls: str) -> tuple[Image.Image, dict]:
    """Return new ORM (RGB) and stats."""
    arr = np.asarray(orm.convert("RGB"), dtype=np.float32)
    ao = arr[:, :, 0]
    rough = arr[:, :, 1]
    metal = arr[:, :, 2] / 255.0
    mean_before = float(metal.mean())
    frac_hi_before = float((metal > 0.5).mean())

    # Conservative demotion: Retribution CE ORMs are soft-metal foggy; VLM often
    # labels painted SPACE/tech as metal. Only keep strong chrome-like maps.
    effective = cls
    if cls == "metal":
        if mean_before < 0.28 or frac_hi_before < 0.12:
            # Weak / soft authored metal → treat as painted dielectric.
            effective = "dielectric"
        elif mean_before < 0.45 or frac_hi_before < 0.25:
            # Ambiguous — keep only hard metal islands.
            effective = "mixed"

    if effective == "dielectric":
        metal_new = np.zeros_like(metal)
    elif effective == "metal":
        # Keep authored metal; do not lift — lifting false positives caused RR noise.
        metal_new = metal.copy()
    else:  # mixed — kill soft fog, keep islands
        t = np.clip((metal - 0.40) / 0.20, 0.0, 1.0)
        t = t * t * (3.0 - 2.0 * t)
        metal_new = metal * t

    out = np.stack(
        [ao, rough, np.clip(metal_new * 255.0, 0, 255)],
        axis=-1,
    ).astype(np.uint8)
    mean_after = float(metal_new.mean())
    frac_hi_after = float((metal_new > 0.5).mean())
    stats = {
        "class_effective": effective,
        "meanM_before": round(mean_before, 4),
        "meanM_after": round(mean_after, 4),
        "fracMgt05_before": round(frac_hi_before, 4),
        "fracMgt05_after": round(frac_hi_after, 4),
    }
    return Image.fromarray(out, mode="RGB"), stats


def metallic_default_for_class(cls: str, previous: float | None) -> float:
    if cls == "dielectric":
        return 0.0
    if cls == "metal":
        return max(0.55, float(previous or 0.0))
    # mixed
    return min(0.10, float(previous or 0.10))


def upsert_scene_metallic(path: Path, updates: dict[str, float]) -> int:
    if not path.exists() or not updates:
        return 0
    raw = path.read_text(encoding="utf-8")
    # Stock RT textures.json allows // comments — strip before json.loads.
    cleaned = re.sub(r"//.*?$", "", raw, flags=re.M)
    doc = json.loads(cleaned)
    arr = doc.get("array") or []
    changed = 0
    by_name = {str(e.get("textureName", "")).upper(): e for e in arr if isinstance(e, dict)}
    for name, metal in updates.items():
        e = by_name.get(name.upper())
        if not e:
            continue
        old = e.get("metallicDefault")
        e["metallicDefault"] = metal
        if old != metal:
            changed += 1
    # Preserve original formatting only for strict JSON files; commented stock
    # global JSON is rewritten without comments (engine Glaze accepts either).
    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return changed


def parse_class_json(text: str) -> tuple[str, float]:
    text = text.strip()
    # Strip markdown fences if the model ignores instructions.
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    m = re.search(r"\{[^{}]*\}", text, re.S)
    if not m:
        raise ValueError(f"no JSON object in model output: {text[:200]!r}")
    obj = json.loads(m.group(0))
    cls = str(obj.get("class", "")).strip().lower()
    if cls not in ("dielectric", "metal", "mixed"):
        raise ValueError(f"bad class {cls!r} in {obj}")
    conf = float(obj.get("confidence", 0.5))
    return cls, conf


class VlmClassifier:
    def __init__(self, model_id: str = MODEL_ID):
        import torch
        from transformers import AutoProcessor, Qwen2_5_VLForConditionalGeneration

        HF_CACHE.mkdir(parents=True, exist_ok=True)
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        dtype = torch.bfloat16 if self.device == "cuda" else torch.float32
        print(f"Loading {model_id} on {self.device} ({dtype}) …")
        self.processor = AutoProcessor.from_pretrained(
            model_id, cache_dir=str(HF_CACHE), trust_remote_code=True
        )
        self.model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
            model_id,
            cache_dir=str(HF_CACHE),
            torch_dtype=dtype,
            device_map="auto" if self.device == "cuda" else None,
            trust_remote_code=True,
        )
        if self.device == "cpu":
            self.model = self.model.to(self.device)
        self.model.eval()
        self.torch = torch

    def classify(self, albedo: Image.Image) -> tuple[str, float, str]:
        from qwen_vl_utils import process_vision_info

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": albedo},
                    {"type": "text", "text": PROMPT},
                ],
            }
        ]
        text = self.processor.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        image_inputs, video_inputs = process_vision_info(messages)
        inputs = self.processor(
            text=[text],
            images=image_inputs,
            videos=video_inputs,
            padding=True,
            return_tensors="pt",
        )
        inputs = inputs.to(self.model.device)
        with self.torch.inference_mode():
            generated = self.model.generate(**inputs, max_new_tokens=64, do_sample=False)
        trimmed = [o[len(i) :] for i, o in zip(inputs.input_ids, generated)]
        out_text = self.processor.batch_decode(
            trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False
        )[0]
        cls, conf = parse_class_json(out_text)
        return cls, conf, out_text.strip()


def save_orm_everywhere(name: str, img: Image.Image, dry_run: bool) -> list[str]:
    written: list[str] = []
    targets = [
        OVERLAY_MAT / f"{name}_orm.png",
        ENGINE_MAT / f"{name}_orm.png",
        ENGINE_MAT_DEV / f"{name}_orm.png",
    ]
    for path in targets:
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
        dest.write_bytes(src.read_bytes())
    return dest


def load_manifest() -> dict:
    if MANIFEST_PATH.exists():
        return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return {"version": 1, "model": MODEL_ID, "entries": {}}


def save_manifest(doc: dict) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--all", action="store_true", help="Process every authored _orm.png")
    ap.add_argument("--limit", type=int, default=0, help="Stop after N textures (smoke)")
    ap.add_argument("--dry-run", action="store_true", help="Classify + plan only, no writes")
    ap.add_argument("--force", action="store_true", help="Ignore resume / reprocess all")
    ap.add_argument(
        "--heuristic-fallback",
        action="store_true",
        help="If albedo missing, use soft-fog mixed rewrite without VLM",
    )
    ap.add_argument(
        "--model",
        default=MODEL_ID,
        help=(
            "HF model id (default Qwen2.5-VL-7B-Instruct). "
            "On 32GB VRAM you can try e.g. Qwen/Qwen2.5-VL-72B-Instruct with "
            "bitsandbytes 4-bit if classification quality needs a bump."
        ),
    )
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    model_id = args.model

    if args.all:
        names = all_orm_texture_names(OVERLAY_MAT)
        print(f"Scope: ALL authored ORM ({len(names)})")
    else:
        names = [
            n
            for n in map01_texture_names(SCENE_OVERLAY)
            if (OVERLAY_MAT / f"{n}_orm.png").exists()
        ]
        print(f"Scope: MAP01 with _orm ({len(names)})")

    if args.limit > 0:
        names = names[: args.limit]
        print(f"Limited to {len(names)}")

    print("Indexing WAD PNG albedos…")
    wad_pngs = load_wad_pngs(WAD) if WAD.exists() else {}
    print(f"  WAD PNG lumps: {len(wad_pngs)}")

    manifest = load_manifest()
    manifest["model"] = model_id
    entries: dict = manifest.setdefault("entries", {})

    # Pre-filter resume
    todo: list[str] = []
    for name in names:
        orm_path = OVERLAY_MAT / f"{name}_orm.png"
        mtime = orm_path.stat().st_mtime if orm_path.exists() else 0
        prev = entries.get(name.upper())
        if (
            not args.force
            and prev
            and prev.get("src_mtime") == mtime
            and prev.get("status") == "ok"
        ):
            continue
        todo.append(name)
    print(f"To process: {len(todo)} (skipped resumed: {len(names) - len(todo)})")

    clf: VlmClassifier | None = None
    if todo:
        # Only load VLM if at least one albedo is available or we need classification
        need_vlm = False
        for name in todo:
            if name.upper() in wad_pngs:
                need_vlm = True
                break
            # also accept loose albedo next to mats (rare)
            if (OVERLAY_MAT / f"{name}.png").exists():
                need_vlm = True
                break
        if need_vlm or not args.heuristic_fallback:
            clf = VlmClassifier(model_id)

    meta_updates: dict[str, float] = {}
    ok = fail = 0
    t0 = time.time()

    for i, name in enumerate(todo, 1):
        orm_path = OVERLAY_MAT / f"{name}_orm.png"
        key = name.upper()
        try:
            orm = Image.open(orm_path)
            albedo_img: Image.Image | None = None
            if key in wad_pngs:
                from io import BytesIO

                albedo_img = Image.open(BytesIO(wad_pngs[key]))
            elif (OVERLAY_MAT / f"{name}.png").exists():
                albedo_img = Image.open(OVERLAY_MAT / f"{name}.png")

            raw_out = ""
            if albedo_img is not None and clf is not None:
                cls, conf, raw_out = clf.classify(thumb_albedo(albedo_img))
            elif args.heuristic_fallback or albedo_img is None:
                # No albedo: treat as mixed soft-fog kill (safe for RR).
                cls, conf, raw_out = "mixed", 0.0, "heuristic:no-albedo"
            else:
                raise RuntimeError("no albedo and VLM required")

            new_orm, stats = rewrite_metallic(orm, cls)
            effective = stats.get("class_effective", cls)
            backup_orm(orm_path, args.dry_run)
            written = save_orm_everywhere(name, new_orm, args.dry_run)

            # previous metallicDefault from scene if any
            prev_metal = None
            try:
                scene = json.loads(SCENE_OVERLAY.read_text(encoding="utf-8"))
                for e in scene.get("array") or []:
                    if isinstance(e, dict) and str(e.get("textureName", "")).upper() == key:
                        prev_metal = e.get("metallicDefault")
                        break
            except Exception:
                pass
            meta_updates[name] = metallic_default_for_class(
                effective, float(prev_metal) if prev_metal is not None else None
            )

            entries[key] = {
                "textureName": name,
                "class": cls,
                "class_effective": effective,
                "confidence": conf,
                "raw": raw_out[:300],
                "stats": stats,
                "src_mtime": orm_path.stat().st_mtime,
                "status": "ok",
                "written": written,
                "dry_run": bool(args.dry_run),
            }
            ok += 1
            print(
                f"[{i}/{len(todo)}] {name}: {cls}"
                + (f"->{effective}" if effective != cls else "")
                + f" conf={conf:.2f} "
                f"meanM {stats['meanM_before']:.3f}->{stats['meanM_after']:.3f}"
            )
        except Exception as e:
            fail += 1
            entries[key] = {
                "textureName": name,
                "status": "error",
                "error": str(e),
                "src_mtime": orm_path.stat().st_mtime if orm_path.exists() else 0,
            }
            print(f"[{i}/{len(todo)}] {name}: ERROR {e}")

        if i % 10 == 0:
            manifest["entries"] = entries
            save_manifest(manifest)

    manifest["entries"] = entries
    manifest["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    manifest["ok"] = ok
    manifest["fail"] = fail
    save_manifest(manifest)

    if not args.dry_run and meta_updates:
        c1 = upsert_scene_metallic(SCENE_OVERLAY, meta_updates)
        c2 = upsert_scene_metallic(SCENE_ENGINE, meta_updates)
        c3 = upsert_scene_metallic(GLOBAL_ENGINE, meta_updates) if args.all else 0
        print(f"Updated metallicDefault: overlay={c1} engine_map01={c2} global={c3}")

    elapsed = time.time() - t0
    print(f"Done. ok={ok} fail={fail} in {elapsed:.1f}s. Manifest: {MANIFEST_PATH}")
    return 0 if fail == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
