"""WashScratch stage helpers — operate ONLY on build/WashScratch (never RelWithDebInfo)."""
from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(r"G:\AI\Doom64-RT")
SCRATCH = ROOT / r"sourcecode\gzdoom-rt\build\WashScratch"
STOCK = ROOT / r"gzdoom-rt-1.0.2"
LIVE = ROOT / r"sourcecode\gzdoom-rt\build\RelWithDebInfo"
STATE = SCRATCH / ".wash_scratch_state.json"
OVERLAY = ROOT / r"Doom64-Retribution\Retribution-RT-Materials\rt\data\textures_world_emis.json"
EYES_OVERLAY = (
    ROOT / r"Doom64-Retribution\Retribution-RT-Materials\rt\data\textures_enemy_eyes.json"
)
WORLD_MAT = ROOT / r"Doom64-Retribution\Retribution-RT-Materials\rt\mat"
WORLD_MAT_DEV = ROOT / r"Doom64-Retribution\Retribution-RT-Materials\rt\mat_dev"
LIVE_MAT = LIVE / "rt" / "mat"
LIVE_MAT_DEV = LIVE / "rt" / "mat_dev"

EMIS_KEYS = (
    "emissiveMult",
    "lightIntensity",
    "lightColor",
    "lightColorHEX",
    "lightEvenOnDynamic",
    "attachedLightIntensity",
    "attachedLightColor",
    "noShadow",
)


def load_state() -> dict:
    if STATE.exists():
        return json.loads(STATE.read_text(encoding="utf-8"))
    return {"stage": None, "applied": []}


def save_state(stage: str, applied_extra: str | None = None) -> None:
    st = load_state()
    st["stage"] = stage
    if applied_extra and applied_extra not in st["applied"]:
        st["applied"].append(applied_extra)
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(st, indent=2) + "\n", encoding="utf-8")
    print(f"STATE stage={stage} applied={st['applied']}")


def bootstrap() -> None:
    if not LIVE.joinpath("gzdoom.exe").exists():
        raise SystemExit(f"ERROR: missing live engine {LIVE / 'gzdoom.exe'} — build first")
    if not STOCK.joinpath("rt").is_dir():
        raise SystemExit(f"ERROR: missing stock rt at {STOCK / 'rt'}")

    if SCRATCH.exists():
        print(f"Removing old WashScratch: {SCRATCH}")
        shutil.rmtree(SCRATCH)
    SCRATCH.mkdir(parents=True)

    # Engine binary + deps from our patched build
    for name in (
        "gzdoom.exe",
        "zmusic.dll",
        "openal32.dll",
        "libsndfile-1.dll",
        "gzdoom.pk3",
        "game_support.pk3",
        "game_widescreen_gfx.pk3",
        "brightmaps.pk3",
        "lights.pk3",
    ):
        src = LIVE / name
        if src.exists():
            shutil.copy2(src, SCRATCH / name)
            print(f"copy {name}")

    # Stock RT tree (clean Doom II materials / textures.json)
    print("copy stock rt -> WashScratch/rt ...")
    shutil.copytree(STOCK / "rt", SCRATCH / "rt")

    # Prefer stock RTGL for true scratch; note path
    dll = SCRATCH / "rt" / "bin" / "RTGL1.dll"
    if not dll.exists():
        # some layouts nest differently
        for p in (STOCK / "rt" / "bin" / "RTGL1.dll", LIVE / "rt" / "bin" / "RTGL1.dll"):
            if p.exists():
                (SCRATCH / "rt" / "bin").mkdir(parents=True, exist_ok=True)
                shutil.copy2(p, dll)
                print(f"staged RTGL1 from {p}")
                break

    # Stock 1.0.2 often lacks Ray Reconstruction (nvngx_dlssd.dll). Overlay from live / SDK.
    _stage_nvidia_dlss_rr(SCRATCH / "rt" / "bin")

    save_state("S00", "bootstrap")
    print(f"BOOTSTRAP_OK {SCRATCH}")


def _stage_nvidia_dlss_rr(dst_bin: Path) -> None:
    """Ensure DLSS + DLSS-RR DLLs exist (stock release often misses nvngx_dlssd)."""
    dst_bin.mkdir(parents=True, exist_ok=True)
    names = ("nvngx_dlss.dll", "nvngx_dlssd.dll", "nvngx_dlssg.dll")
    sdk = ROOT / r"deps\DLSS\lib\Windows_x86_64\rel"
    live_bin = LIVE / "rt" / "bin"
    for name in names:
        dest = dst_bin / name
        for src in (live_bin / name, sdk / name):
            if src.exists():
                shutil.copy2(src, dest)
                print(f"NVIDIA overlay {name} from {src.parent.name}")
                break
        else:
            if not dest.exists():
                print(f"WARNING: missing {name} (Ray Reconstruction needs nvngx_dlssd.dll)")



def _parse_jsonc_array(path: Path) -> tuple[str, list[dict]]:
    """Best-effort: strip // comments then json-load. Returns (raw_for_rewrite_hint, array)."""
    raw = path.read_text(encoding="utf-8", errors="replace")
    # remove // line comments (stock textures.json uses them)
    no_c = re.sub(r"^[ \t]*//.*?$", "", raw, flags=re.M)
    data = json.loads(no_c)
    return raw, list(data.get("array", []))


def nuclear_scrub() -> None:
    tex = SCRATCH / "rt" / "data" / "textures.json"
    if not tex.exists():
        raise SystemExit(f"ERROR: missing {tex}")
    bak = tex.with_suffix(".json.pre_nuclear")
    if not bak.exists():
        shutil.copy2(tex, bak)
        print(f"backup -> {bak.name}")

    raw, arr = _parse_jsonc_array(tex)
    cleaned = 0
    new_arr = []
    for e in arr:
        if not isinstance(e, dict) or "textureName" not in e:
            new_arr.append(e)
            continue
        ne = {"textureName": e["textureName"]}
        # keep non-emis material fields (mirror/metal/roughness/water/...)
        for k, v in e.items():
            if k == "textureName" or k in EMIS_KEYS:
                if k in EMIS_KEYS:
                    cleaned += 1
                continue
            ne[k] = v
        new_arr.append(ne)

    out = {"version": 0, "array": new_arr}
    tex.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(f"stripped {cleaned} emis-related fields from {len(arr)} entries")

    # Quarantine all _e.png under mat + mat_dev
    qroot = SCRATCH / "rt" / "_e_quarantine"
    qroot.mkdir(parents=True, exist_ok=True)
    moved = 0
    for sub in ("mat", "mat_dev"):
        d = SCRATCH / "rt" / sub
        if not d.is_dir():
            continue
        q = qroot / sub
        q.mkdir(parents=True, exist_ok=True)
        for p in d.glob("*_e.png"):
            dest = q / p.name
            if dest.exists():
                dest.unlink()
            shutil.move(str(p), str(dest))
            moved += 1
        for p in d.glob("*_e.ktx2"):
            dest = q / p.name
            if dest.exists():
                dest.unlink()
            shutil.move(str(p), str(dest))
            moved += 1
    print(f"quarantined {moved} emissive maps -> {qroot}")
    save_state("S02", "nuclear_scrub")


def stage_rtgl_live() -> None:
    src_dll = LIVE / "rt" / "bin" / "RTGL1.dll"
    if not src_dll.exists():
        raise SystemExit(f"ERROR: missing {src_dll} — run tools/build-rtgl.cmd on live first")
    dst_bin = SCRATCH / "rt" / "bin"
    dst_bin.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src_dll, dst_bin / "RTGL1.dll")
    _stage_nvidia_dlss_rr(dst_bin)
    src_sh = LIVE / "rt" / "shaders"
    dst_sh = SCRATCH / "rt" / "shaders"
    if src_sh.is_dir():
        dst_sh.mkdir(parents=True, exist_ok=True)
        for p in src_sh.glob("*.spv"):
            shutil.copy2(p, dst_sh / p.name)
    print(f"staged live RTGL1 + shaders -> {SCRATCH / 'rt'}")
    save_state("S03", "patched_rtgl")


def stage_world_emis() -> None:
    if not OVERLAY.exists():
        raise SystemExit(f"ERROR: missing {OVERLAY} — run gen_world_emissives.py on live first")

    # Merge allowlist into WashScratch global textures.json (rewrite as proper JSON)
    tex = SCRATCH / "rt" / "data" / "textures.json"
    _, arr = _parse_jsonc_array(tex)
    by = {str(e.get("textureName", "")).upper(): dict(e) for e in arr if isinstance(e, dict)}

    overlay = json.loads(OVERLAY.read_text(encoding="utf-8"))
    oarr = overlay.get("array", [])
    n = 0
    for e in oarr:
        name = e.get("textureName")
        if not name:
            continue
        u = name.upper()
        cur = by.get(u, {"textureName": name})
        for k in EMIS_KEYS:
            cur.pop(k, None)
        for k, v in e.items():
            cur[k] = v
        by[u] = cur
        n += 1

    out_arr = list(by.values())
    tex.write_text(json.dumps({"version": 0, "array": out_arr}, indent=2) + "\n", encoding="utf-8")
    print(f"upserted {n} world emis metas into WashScratch textures.json")

    # Copy _e (+ optional companions) into mat + mat_dev
    names = [str(e["textureName"]).upper() for e in oarr if "textureName" in e]
    copied = 0
    for name in names:
        for src_root in (WORLD_MAT_DEV, WORLD_MAT):
            src = src_root / f"{name}_e.png"
            if not src.exists():
                continue
            for sub in ("mat", "mat_dev"):
                dst_dir = SCRATCH / "rt" / sub
                dst_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst_dir / f"{name}_e.png")
                copied += 1
            break
    print(f"copied {copied} _e.png into WashScratch mat/mat_dev")

    # Scene overlay for emis gallery if present
    for scene_name in ("d64remis_map99", "d64rtexg_map99", "d64rtr_v15_map01"):
        src = ROOT / "Doom64-Retribution" / "Retribution-RT-Materials" / "rt" / "data" / "scenes" / scene_name / "textures.json"
        if not src.exists():
            continue
        dst = SCRATCH / "rt" / "data" / "scenes" / scene_name / "textures.json"
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        print(f"scene overlay {scene_name}")

    save_state("S04", "world_emis")


def _upsert_overlay_meta(overlay_path: Path, label: str) -> list[str]:
    if not overlay_path.exists():
        raise SystemExit(f"ERROR: missing {overlay_path}")
    tex = SCRATCH / "rt" / "data" / "textures.json"
    _, arr = _parse_jsonc_array(tex)
    by = {str(e.get("textureName", "")).upper(): dict(e) for e in arr if isinstance(e, dict)}
    oarr = json.loads(overlay_path.read_text(encoding="utf-8")).get("array", [])
    names: list[str] = []
    for e in oarr:
        name = e.get("textureName")
        if not name:
            continue
        u = str(name).upper()
        cur = by.get(u, {"textureName": name})
        for k in EMIS_KEYS:
            cur.pop(k, None)
        for k, v in e.items():
            cur[k] = v
        by[u] = cur
        names.append(u)
    tex.write_text(
        json.dumps({"version": 0, "array": list(by.values())}, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"upserted {len(names)} {label} metas into WashScratch textures.json")
    return names


def _copy_e_maps(names: list[str], src_roots: list[Path]) -> int:
    copied = 0
    for name in names:
        src = None
        for root in src_roots:
            cand = root / f"{name}_e.png"
            if cand.exists():
                src = cand
                break
        if src is None:
            continue
        for sub in ("mat", "mat_dev"):
            dst_dir = SCRATCH / "rt" / sub
            dst_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst_dir / f"{name}_e.png")
            copied += 1
    return copied


def stage_enemy_eyes() -> None:
    """Re-apply existing eye overlay (same as gen_enemy_eye_emissives output)."""
    names = _upsert_overlay_meta(EYES_OVERLAY, "enemy-eye")
    copied = _copy_e_maps(
        names,
        [LIVE_MAT_DEV, LIVE_MAT, WORLD_MAT_DEV, WORLD_MAT],
    )
    print(f"copied {copied} eye/fire _e.png into WashScratch mat/mat_dev")

    # MAP01 + enemy gallery scene overlays if present on live / materials
    for scene_name in ("d64rtr_v15_map01", "d64renemyg_map98"):
        for base in (
            LIVE / "rt" / "data" / "scenes" / scene_name / "textures.json",
            ROOT
            / "Doom64-Retribution"
            / "Retribution-RT-Materials"
            / "rt"
            / "data"
            / "scenes"
            / scene_name
            / "textures.json",
        ):
            if not base.exists():
                continue
            dst = SCRATCH / "rt" / "data" / "scenes" / scene_name / "textures.json"
            dst.parent.mkdir(parents=True, exist_ok=True)
            # Merge eye entries into existing scene file if present
            if dst.exists():
                _, arr = _parse_jsonc_array(dst)
                by = {
                    str(e.get("textureName", "")).upper(): dict(e)
                    for e in arr
                    if isinstance(e, dict)
                }
                eyes = json.loads(EYES_OVERLAY.read_text(encoding="utf-8")).get("array", [])
                for e in eyes:
                    name = e.get("textureName")
                    if not name:
                        continue
                    u = str(name).upper()
                    cur = by.get(u, {"textureName": name})
                    for k in EMIS_KEYS:
                        cur.pop(k, None)
                    for k, v in e.items():
                        cur[k] = v
                    by[u] = cur
                dst.write_text(
                    json.dumps({"version": 0, "array": list(by.values())}, indent=2)
                    + "\n",
                    encoding="utf-8",
                )
            else:
                shutil.copy2(base, dst)
            print(f"scene eyes merge {scene_name}")
            break

    save_state("S06", "enemy_eyes")


def main() -> None:
    if len(sys.argv) < 2:
        print(
            "usage: apply_stage.py bootstrap|nuclear_scrub|stage_rtgl_live|"
            "stage_world_emis|stage_enemy_eyes|fix_nvidia|status"
        )
        raise SystemExit(2)
    cmd = sys.argv[1]
    if cmd == "bootstrap":
        bootstrap()
    elif cmd == "nuclear_scrub":
        nuclear_scrub()
    elif cmd == "stage_rtgl_live":
        stage_rtgl_live()
    elif cmd == "stage_world_emis":
        stage_world_emis()
    elif cmd == "stage_enemy_eyes":
        stage_enemy_eyes()
    elif cmd == "fix_nvidia":
        if not SCRATCH.exists():
            raise SystemExit("ERROR: WashScratch missing — run bootstrap first")
        _stage_nvidia_dlss_rr(SCRATCH / "rt" / "bin")
        print("FIX_NVIDIA_OK")
    elif cmd == "status":
        st = load_state()
        print(json.dumps(st, indent=2))
        print(f"SCRATCH={SCRATCH} exists={SCRATCH.exists()}")
        for name in ("RTGL1.dll", "nvngx_dlss.dll", "nvngx_dlssd.dll"):
            p = SCRATCH / "rt" / "bin" / name
            print(f"  {name}: {'OK' if p.exists() else 'MISSING'} {p}")
        for name in ("TROOA1_e.png", "SARGA1_e.png"):
            p = SCRATCH / "rt" / "mat_dev" / name
            print(f"  eye {name}: {'OK' if p.exists() else 'MISSING'}")
    else:
        raise SystemExit(f"unknown command {cmd}")


if __name__ == "__main__":
    main()
