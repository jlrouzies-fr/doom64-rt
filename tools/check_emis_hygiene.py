"""
Fast offline checks for gallery emissive hygiene (no gzdoom launch).

Fails if:
  - world allowlist is empty / huge
  - GLOBAL rt/data/textures.json has emis/light meta outside the authored
    overlay keep set (wash-qa root cause: stock PLAY* @4.25, FIRELAVA @0.7)
  - GLOBAL has duplicate textureName entries where any copy has emis fields
  - gallery scene has emissiveMult outside allowlist (+ eyes/FX prefixes)
  - near-solid non-allowlist _e maps exist in engine mat/

Usage:
  python tools/check_emis_hygiene.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from PIL import Image

# Repo root, derived from this file so a clone can live anywhere.
PROJ_ROOT = Path(__file__).resolve().parents[1]

ROOT = PROJ_ROOT
WORLD = ROOT / r"Doom64-Retribution\Retribution-RT-Materials\rt\data\textures_world_emis.json"
GLOBAL = ROOT / r"sourcecode\gzdoom-rt\build\RelWithDebInfo\rt\data\textures.json"
SCENE = (
    ROOT
    / r"sourcecode\gzdoom-rt\build\RelWithDebInfo\rt\data\scenes\d64rtexg_map99\textures.json"
)
MAT = ROOT / r"sourcecode\gzdoom-rt\build\RelWithDebInfo\rt\mat"

OVERLAY_DIR = ROOT / r"Doom64-Retribution\Retribution-RT-Materials\rt\data"
OVERLAY_KEEPS = (
    "textures_world_emis.json",
    "textures_enemy_eyes.json",
    "textures_pinky_eyes.json",
    "textures_fx.json",
    "textures_explosions.json",
    "textures_statue_eyes.json",
    "textures_dart.json",
)

# Sprite _e / scene-meta exemptions. Fire-frame coverage is SUFFIX-based on
# purpose: blanket PLAY/FIRE/BFG prefixes were the wash contaminants
# (PLAY body @4.25, FIRELAVA @0.7) — never re-add them as bare prefixes.
KEEP_E_RE = re.compile(
    r"^(POSS|SPOS|CPOS|SSWV|TROO|TRO2|SARG|SAR2|SKUL|HEAD|BOSS|PAIN|"
    r"PLAYF|BFGF|FIRE[A-E]0|"
    # The two gargoyle statues, red eyes only (tools/gen_statue_eye_emissives.py).
    # Anchored to the single frame each actually has: A028A0/A029A0 and nothing else,
    # so this cannot grow into a bare A02 prefix that would swallow the other seven
    # A02x decorations.
    r"A028A0|A029A0|"
    # The dart/nail projectile's red head (tools/gen_dart_emissives.py). DART is the
    # whole sprite family — five lumps, four masked — so the bare prefix is exact here
    # and cannot widen onto anything else.
    r"DART|"
    r"BAR1|BEXP|MISL|MISF|BAL|RBAL|TRCR|RECT|MANF|APLS|APBX|PLSS|PLSE|"
    r"PUFF|BLUD|TFOG|IFOG|FCAN|RT_|MZL)",
    re.I,
)

# Tolerant scanners for the comment-y, leading-comma stock-style global JSON.
ENTRY_RE = re.compile(r"\{[^{}\n]*\"textureName\"[^{}\n]*\}")
NAME_RE = re.compile(r'"textureName"\s*:\s*"([^"]+)"')
EMIS_FIELD_RE = re.compile(r'"(emissiveMult|lightIntensity|lightColorHEX|lightColor)"')


def load_keep_set() -> set[str]:
    """Authored names from the overlay JSONs — the only legal emis/light holders."""
    keep: set[str] = set()
    for fn in OVERLAY_KEEPS:
        p = OVERLAY_DIR / fn
        if not p.exists():
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        for e in data.get("array", []):
            n = e.get("textureName")
            if n:
                keep.add(str(n).upper())
    return keep


def check_global(errors: list[str], keep: set[str]) -> None:
    if not GLOBAL.exists():
        errors.append(f"missing global {GLOBAL}")
        return
    text = GLOBAL.read_text(encoding="utf-8", errors="replace")
    stray: list[str] = []
    emis_count: dict[str, int] = {}
    for m in ENTRY_RE.finditer(text):
        block = m.group(0)
        # Skip entries inside // comments (stock file disables lines that way;
        # RTGL's comment-tolerant parser never sees them either).
        line_start = text.rfind("\n", 0, m.start()) + 1
        if "//" in text[line_start : m.start()]:
            continue
        nm = NAME_RE.search(block)
        if not nm:
            continue
        name = nm.group(1).upper()
        if not EMIS_FIELD_RE.search(block):
            continue
        emis_count[name] = emis_count.get(name, 0) + 1
        if name not in keep:
            stray.append(name)
    dupes = sorted(n for n, c in emis_count.items() if c > 1)
    print(f"global emis entries: {sum(emis_count.values())}, keep set: {len(keep)}")
    print(f"global stray emis meta: {len(stray)}")
    if stray:
        errors.append(
            f"global stray emis (run tools/gen_world_emissives.py to scrub): "
            f"{sorted(set(stray))[:12]}"
        )
    if dupes:
        errors.append(f"global duplicate emis names (first wins in RTGL): {dupes[:12]}")


def main() -> int:
    errors: list[str] = []
    if not WORLD.exists():
        print("FAIL: missing world emis overlay — run gen_world_emissives.py")
        return 2
    allow = {
        e["textureName"].upper()
        for e in json.loads(WORLD.read_text(encoding="utf-8")).get("array", [])
    }
    print(f"world allowlist: {len(allow)}")
    if len(allow) < 20:
        errors.append(f"allowlist too small ({len(allow)})")
    # The wash guard counts AREA risk, not names. Switch faces are excluded because a
    # switch mask is a handful of texels — SWXCB is 7 of 1024 — so a hundred of them
    # cannot wash anything, and they arrive in bulk: one lit 32x32 patch is stamped into
    # up to 18 CMPSW* wall panels, and the panel is what the engine names, so all of them
    # must be allowlisted or the composite switches go dark (the 2026-08-11 bug: 41 bare
    # switch faces lit, 54 composite ones inert). Counting them here would have made the
    # fix trip this guard and tempted someone to raise the threshold for everything,
    # which is the one change that would let a real wash back in.
    SWITCH_RE = re.compile(r"^(SWX|CMPSW\d+[AB]$)", re.I)
    wash = {n for n in allow if not SWITCH_RE.match(n)}
    print(f"  wash-relevant (non-switch): {len(wash)}")
    if len(wash) > 120:
        errors.append(f"allowlist suspiciously large ({len(wash)} non-switch) — wash risk")

    keep = load_keep_set()
    check_global(errors, keep)

    if SCENE.exists():
        arr = json.loads(SCENE.read_text(encoding="utf-8")).get("array", [])
        bad = []
        for e in arr:
            name = str(e.get("textureName", "")).upper()
            emis = float(e.get("emissiveMult") or 0)
            li = float(e.get("lightIntensity") or 0)
            if emis <= 0 and li <= 0:
                continue
            if name in allow or KEEP_E_RE.match(name):
                continue
            bad.append(name)
        print(f"gallery scene stray emis meta: {len(bad)}")
        if bad:
            errors.append(f"stray scene emis: {bad[:12]}")
    else:
        errors.append(f"missing gallery scene {SCENE}")

    solid = []
    if MAT.exists():
        for p in MAT.glob("*_e.png"):
            stem = p.name[: -len("_e.png")].upper()
            if stem in allow or KEEP_E_RE.match(stem):
                continue
            im = Image.open(p).convert("RGBA")
            w, h = im.size
            n = w * h
            px = im.load()
            opaq = lit = 0
            for y in range(h):
                for x in range(w):
                    r, g, b, a = px[x, y]
                    if a < 8:
                        continue
                    opaq += 1
                    if r + g + b > 40:
                        lit += 1
            if n and opaq / n >= 0.45 and lit / max(1, opaq) >= 0.7:
                solid.append(stem)
    print(f"non-allowlist solidish _e: {len(solid)}")
    if solid:
        errors.append(f"solidish stray _e: {solid[:12]}")

    # Required heroes present
    for need in ("SMONAA", "HLAVA1", "D64LAVA1", "SEXIT"):
        if need not in allow:
            errors.append(f"missing required emitter {need}")
        elif not (MAT / f"{need}_e.png").exists():
            errors.append(f"missing _e.png for {need}")

    if errors:
        print("FAIL:")
        for e in errors:
            print(" -", e)
        return 2
    print("PASS: emissive hygiene ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
