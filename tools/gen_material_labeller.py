"""
Build a self-contained, keyboard-driven metal/roughness labelling page.

Why this exists
---------------
Under path tracing, correct ``metallicDefault`` / ``roughnessDefault`` in the RT
material metadata buys real reflections and highlights for free.  We tried to
derive them automatically (``tools/fix_orm_metallic_ai.py``, a local Qwen2.5-VL
pass) and no model could reliably tell painted-steel-that-is-a-dielectric from
bare metal.  Doing 1300 textures by hand in a text editor is not worth anyone's
evening, so this generator bakes every texture into one page where a human can
classify them at roughly one keystroke each.

Scope
-----
Every wall/flat texture in the ``TX_START``..``TX_END`` namespace of
``D64RTR_v15.WAD`` (1187 lumps), plus every texture actually referenced by a map
sidedef/sector that lives outside that namespace and is defined as a composite in
the ``TEXTURES`` lump.  Sprites (``SS_``) are deliberately excluded -- metalness
on a sprite is a different question and there are 1388 of them.

Images are embedded as lossless WebP ``data:`` URIs (the artifact CSP blocks
every external host).  Nothing is downscaled below 128 px, which is native size
or better for ~95% of the set, so the labeller sees the real pixels.

Usage
-----
    C:\\Users\\...\\Python313\\python.exe tools\\gen_material_labeller.py
Output
    tools\\_gallery\\material_labeller.html
"""
from __future__ import annotations

import base64
import io
import json
import re
import struct
from collections import defaultdict
from pathlib import Path

from PIL import Image

PROJ_ROOT = Path(__file__).resolve().parents[1]
WAD = PROJ_ROOT / r"Doom64-Retribution\D64RTR_v15.WAD"
MAP_EXPORT = PROJ_ROOT / r"tools\_gallery\all_maps_texture_export.json"
TEXTURES_JSON = (
    PROJ_ROOT
    / r"Doom64-Retribution\Retribution-RT-Materials\rt\data\textures.json"
)
OUT_HTML = PROJ_ROOT / r"tools\_gallery\material_labeller.html"

MAX_PX = 128  # cap on the embedded thumbnail's long edge
SKIP_NAMES = {"-", "", "F_SKY1", "P_SKY1"}


# ---------------------------------------------------------------- WAD reading

def read_wad() -> tuple[bytes, list[tuple[str, int, int]]]:
    data = WAD.read_bytes()
    count, dir_off = struct.unpack_from("<II", data, 4)
    lumps = []
    for i in range(count):
        off, size, name = struct.unpack_from("<II8s", data, dir_off + i * 16)
        lumps.append((name.split(b"\0")[0].decode("ascii", "replace"), off, size))
    return data, lumps


def namespace(lumps: list[tuple[str, int, int]], start: str, end: str) -> list[tuple[str, int, int]]:
    names = [l[0] for l in lumps]
    try:
        a, b = names.index(start), names.index(end)
    except ValueError:
        return []
    return lumps[a + 1 : b]


# ------------------------------------------------------------ TEXTURES lump

def strip_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"//[^\n]*", "", text)


def parse_textures(text: str) -> dict[str, dict]:
    """Composite texture definitions: name -> {width, height, patches[]}."""
    text = strip_comments(text)
    defs: dict[str, dict] = {}
    for m in re.finditer(r"\bTexture\s+([A-Za-z0-9_]+)\s*,\s*(\d+)\s*,\s*(\d+)", text):
        name, w, h = m.group(1), int(m.group(2)), int(m.group(3))
        brace = text.find("{", m.end())
        if brace < 0:
            continue
        depth, i, end = 0, brace, -1
        while i < len(text):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    end = i
                    break
            i += 1
        if end < 0:
            continue
        patches = []
        for pm in re.finditer(
            r"Patch\s+([A-Za-z0-9_]+)\s*,\s*(-?\d+)\s*,\s*(-?\d+)\s*(\{[^}]*\})?",
            text[brace + 1 : end],
        ):
            flags: dict = {}
            block = pm.group(4)
            if block:
                if re.search(r"\bFlipX\b", block):
                    flags["flipx"] = True
                if re.search(r"\bFlipY\b", block):
                    flags["flipy"] = True
                rot = re.search(r"\bRotate\s+(-?\d+)", block)
                if rot:
                    flags["rotate"] = int(rot.group(1))
            patches.append(
                {"name": pm.group(1), "x": int(pm.group(2)), "y": int(pm.group(3)), "flags": flags}
            )
        defs[name] = {"width": w, "height": h, "patches": patches}
    return defs


# ------------------------------------------------------------------ rendering

def render(name: str, tex_defs: dict[str, dict], raw: dict[str, bytes]) -> Image.Image | None:
    """A plain PNG lump wins; otherwise composite it from its patches."""
    blob = raw.get(name)
    if blob and blob.startswith(b"\x89PNG"):
        try:
            return Image.open(io.BytesIO(blob)).convert("RGBA")
        except Exception:
            pass
    d = tex_defs.get(name)
    if not d:
        return None
    canvas = Image.new("RGBA", (max(d["width"], 1), max(d["height"], 1)), (0, 0, 0, 0))
    pasted = False
    for p in d["patches"]:
        pb = raw.get(p["name"])
        if not pb or not pb.startswith(b"\x89PNG"):
            continue
        try:
            pim = Image.open(io.BytesIO(pb)).convert("RGBA")
        except Exception:
            continue
        if p["flags"].get("flipx"):
            pim = pim.transpose(Image.FLIP_LEFT_RIGHT)
        if p["flags"].get("flipy"):
            pim = pim.transpose(Image.FLIP_TOP_BOTTOM)
        if p["flags"].get("rotate"):
            pim = pim.rotate(-p["flags"]["rotate"], expand=True)
        canvas.paste(pim, (p["x"], p["y"]), pim)
        pasted = True
    return canvas if pasted else None


def encode(im: Image.Image) -> tuple[str, int, int]:
    """Lossless WebP data-URI payload, long edge capped at MAX_PX."""
    if max(im.size) > MAX_PX:
        s = MAX_PX / max(im.size)
        im = im.resize((max(1, round(im.width * s)), max(1, round(im.height * s))), Image.BOX)
    buf = io.BytesIO()
    im.save(buf, "WEBP", lossless=True, quality=80, method=4)
    return base64.b64encode(buf.getvalue()).decode("ascii"), im.width, im.height


def average_hex(im: Image.Image) -> str:
    """Mean colour over opaque pixels -- used to tint the specular preview."""
    small = im.convert("RGBA").resize((8, 8), Image.BOX)
    raw = small.tobytes()
    tot = [0, 0, 0]
    n = 0
    for i in range(0, len(raw), 4):
        r, g, b, a = raw[i], raw[i + 1], raw[i + 2], raw[i + 3]
        if a < 8:
            continue
        tot[0] += r
        tot[1] += g
        tot[2] += b
        n += 1
    if not n:
        return "#8A8A8A"
    return "#%02X%02X%02X" % tuple(c // n for c in tot)


# --------------------------------------------------------------- name sorting

def prefix_of(name: str) -> str:
    """Leading alpha run, so SPACEB1/SPACEB2 and C10/C100 land in one group."""
    m = re.match(r"^[A-Z_]+", name)
    p = m.group(0) if m else name[:1]
    return p or "#"


def map_order_key(name: str) -> tuple:
    """MAP00..MAP34 numerically first, then the FUN/ABS/OUT/RDM/REC/RTR bonus lumps.

    Lexicographic order would file MAP10 before MAP2 and scatter the campaign lumps
    through the middle of the main run, which is not how anyone thinks about them.
    """
    m = re.fullmatch(r"([A-Z]+)(\d+)", name)
    if not m:
        return (2, name, 0)
    prefix, num = m.group(1), int(m.group(2))
    return (0 if prefix == "MAP" else 1, prefix, num)


def natural_key(name: str) -> tuple:
    parts = re.findall(r"\d+|\D+", name)
    return tuple((1, int(p)) if p.isdigit() else (0, p) for p in parts)


# --------------------------------------------------------------------- gather

def gather() -> tuple[list[dict], dict]:
    data, lumps = read_wad()
    raw = {nm: data[off : off + sz] for nm, off, sz in lumps}
    tex_defs = parse_textures(raw.get("TEXTURES", b"").decode("utf-8", "replace"))

    tx = [nm for nm, _, _ in namespace(lumps, "TX_START", "TX_END")]
    wanted: dict[str, str] = {nm: "tx" for nm in tx if nm not in SKIP_NAMES}

    map_uses: dict[str, int] = {}
    map_names: dict[str, list[str]] = {}
    if MAP_EXPORT.exists():
        for t in json.loads(MAP_EXPORT.read_text(encoding="utf-8"))["textures"]:
            map_uses[t["name"]] = t["uses"]
            map_names[t["name"]] = t["maps"]
            if t["name"] not in wanted and t["name"] not in SKIP_NAMES:
                wanted[t["name"]] = "composite"

    prior: dict[str, dict] = {}
    if TEXTURES_JSON.exists():
        for e in json.loads(TEXTURES_JSON.read_text(encoding="utf-8"))["array"]:
            keep = {k: e[k] for k in ("metallicDefault", "roughnessDefault") if k in e}
            if keep:
                prior[e["textureName"]] = keep

    # One shared, map-ordered list of map names; records reference it by index so
    # a texture used in thirty maps costs thirty small integers, not thirty strings.
    all_maps = sorted({m for v in map_names.values() for m in v}, key=map_order_key)
    map_idx = {m: i for i, m in enumerate(all_maps)}

    records: list[dict] = []
    missing: list[str] = []
    for name in sorted(wanted, key=natural_key):
        im = render(name, tex_defs, raw)
        if im is None:
            missing.append(name)
            continue
        b64, w, h = encode(im)
        rec = {
            "n": name,
            "g": prefix_of(name),
            "w": w,
            "h": h,
            "u": map_uses.get(name, 0),
            "m": [map_idx[m] for m in map_names.get(name, [])],
            "c": average_hex(im),
            "d": b64,
        }
        p = prior.get(name)
        if p:
            rec["p"] = [p.get("metallicDefault"), p.get("roughnessDefault")]
        records.append(rec)

    stats = {
        "maps": all_maps,
        "tx_lumps": len(tx),
        "composites_added": sum(1 for v in wanted.values() if v == "composite"),
        "missing": missing,
        "prior_hits": sum(1 for r in records if "p" in r),
        "map_used": sum(1 for r in records if r["u"] > 0),
    }
    return records, stats


# ------------------------------------------------------------------- the page

BUCKETS = [
    ("mirror", 0.05, "chrome, still water, a deliberate mirror"),
    ("polished", 0.20, "buffed plate, clean glass, wet stone"),
    ("satin", 0.40, "brushed steel, glazed tile, sealed paint"),
    ("matte", 0.60, "flat paint, dry concrete, plastic"),
    ("rough", 0.80, "worn plate, cast iron, dirty panelling"),
    ("very rough", 0.95, "rust, grating, rock, scorched metal"),
]


def write_html(records: list[dict], stats: dict) -> None:
    payload = json.dumps(records, separators=(",", ":"))
    buckets_json = json.dumps([[b[0], b[1], b[2]] for b in BUCKETS])
    maps_json = json.dumps(stats["maps"], separators=(",", ":"))
    total = len(records)

    map_opts = "".join(f'<option value="{i}">{m}</option>' for i, m in enumerate(stats["maps"]))

    bucket_rows = "".join(
        f'<button class="bk" data-b="{i}" type="button">'
        f'<kbd>{i + 1}</kbd><span class="bk-n">{n}</span>'
        f'<span class="bk-v">{v:.2f}</span><span class="bk-h">{h}</span></button>'
        for i, (n, v, h) in enumerate(BUCKETS)
    )

    groups = sorted({r["g"] for r in records})
    group_opts = "".join(f'<option value="{g}">{g}</option>' for g in groups)

    html = f"""<title>Metal or Not</title>
<style>
/* ── Committed dark instrument panel. Doom 64's own palette: near-black ground,
   blood-orange accent, a cool steel neutral for anything that reads as metal.
   Single-theme on purpose — you judge pixel colour against a fixed ground, and a
   light theme would relight every texture in the set. Painted explicitly so it
   holds on either host background. ─────────────────────────────────────────── */
:root {{
  color-scheme: dark;
  --void:#0A0909;          /* page ground */
  --pit:#060505;           /* the stage the texture sits on */
  --panel:#131110;         /* raised surfaces */
  --panel-2:#1B1817;
  --rule:#2A2523;
  --rule-soft:#1F1B1A;
  --ink:#EDE6E2;
  --ink-2:#A29791;
  --ink-3:#6E6560;
  --blood:#C8501E;         /* the accent. Spent on state, not decoration. */
  --blood-dim:#7A3113;
  --blood-wash:#2A140A;
  --steel:#7E93A6;         /* metal — sparks */
  --steel-wash:#161F27;
  --crete:#6E9E90;         /* concrete — dust and chips, no sparks */
  --crete-wash:#132220;
  --timber:#8A5A2B;        /* wood — splinters */
  --timber-wash:#221509;
  --fluid:#4F8FD0;         /* water, blood, nukage, lava — splash */
  --fluid-wash:#0E1B29;
  --park:#B8912F;          /* parked / ambiguous */
  --park-wash:#241B08;
  --mono:ui-monospace,"Cascadia Mono",Consolas,"SF Mono",monospace;
}}
* {{ box-sizing:border-box; }}
html,body {{ height:100%; }}
body {{
  margin:0; background:var(--void); color:var(--ink);
  font:14px/1.55 var(--mono);
  -webkit-font-smoothing:antialiased;
}}
kbd {{
  font:11px/1 var(--mono); display:inline-grid; place-items:center;
  min-width:19px; height:19px; padding:0 5px;
  background:var(--panel-2); color:var(--ink-2);
  border:1px solid var(--rule); border-bottom-width:2px; border-radius:3px;
}}
button {{ font:inherit; color:inherit; background:none; border:0; cursor:pointer; }}
:focus-visible {{ outline:2px solid var(--blood); outline-offset:2px; }}
@media (prefers-reduced-motion:reduce) {{ * {{ transition:none !important; animation:none !important; }} }}

/* ── shell ─────────────────────────────────────────────────────────────── */
.app {{
  height:100%; display:grid; gap:1px; background:var(--rule-soft);
  grid-template-columns:minmax(0,1fr) 336px;
  grid-template-rows:auto minmax(0,1fr) auto;
  grid-template-areas:"top top" "stage side" "strip side";
}}
@media (max-width:900px) {{
  .app {{ grid-template-columns:minmax(0,1fr); grid-template-rows:auto auto auto auto;
    grid-template-areas:"top" "stage" "strip" "side"; height:auto; }}
}}

/* ── top bar ───────────────────────────────────────────────────────────── */
.top {{
  grid-area:top; background:var(--void); padding:11px 18px;
  display:flex; align-items:baseline; gap:16px; flex-wrap:wrap;
}}
.title {{ font-size:13px; letter-spacing:.02em; }}
.title b {{ color:var(--blood); font-weight:600; }}
.eyebrow {{ font-size:10.5px; letter-spacing:.16em; text-transform:uppercase; color:var(--ink-3); }}
.prog {{ margin-left:auto; display:flex; align-items:center; gap:12px; }}
.meter {{ width:190px; height:6px; background:var(--panel-2); border:1px solid var(--rule); position:relative; }}
.meter i {{ position:absolute; inset:0 auto 0 0; background:var(--blood); transition:width .18s linear; }}
.meter i.park {{ background:var(--park); left:auto; }}
.tally {{ font-size:12px; font-variant-numeric:tabular-nums; color:var(--ink-2); }}
.tally b {{ color:var(--ink); font-weight:600; }}
.tally .glob {{ color:var(--ink-3); }}

/* The filter is a mode. It gets a loud, permanent flag in the top bar, because
   labelling for ten minutes without noticing one is on is the expensive mistake. */
.flag {{
  display:flex; align-items:center; gap:8px; padding:4px 6px 4px 10px;
  border:1px solid var(--blood-dim); background:var(--blood-wash); color:var(--blood);
  font-size:11px; letter-spacing:.08em; text-transform:uppercase;
}}
.flag[hidden] {{ display:none; }}
.flag b {{ color:var(--ink); font-weight:600; letter-spacing:.02em; text-transform:none; font-size:12px; }}
.flag button {{ border:1px solid var(--blood-dim); padding:2px 7px; font-size:10px;
  letter-spacing:.06em; color:var(--ink-2); }}
.flag button:hover {{ color:var(--ink); border-color:var(--blood); }}

/* ── stage ─────────────────────────────────────────────────────────────── */
.stage {{
  grid-area:stage; background:var(--pit); position:relative;
  display:grid; grid-template-rows:minmax(0,1fr) auto; min-height:340px;
}}
.canvaswrap {{ display:grid; place-items:center; padding:24px; min-height:0; overflow:hidden; }}
#big {{
  image-rendering:pixelated; display:block;
  max-width:100%; max-height:100%; object-fit:contain;
  box-shadow:0 0 0 1px var(--rule), 0 18px 48px -18px #000;
}}
.stage.s-metal    #big {{ box-shadow:0 0 0 1px var(--steel), 0 0 34px -6px rgba(126,147,166,.28), 0 18px 48px -18px #000; }}
.stage.s-concrete #big {{ box-shadow:0 0 0 1px var(--crete), 0 18px 48px -18px #000; }}
.stage.s-wood     #big {{ box-shadow:0 0 0 1px var(--timber), 0 18px 48px -18px #000; }}
.stage.s-fluid    #big {{ box-shadow:0 0 0 1px var(--fluid), 0 0 30px -8px rgba(79,143,208,.30), 0 18px 48px -18px #000; }}
.stage.s-other    #big {{ box-shadow:0 0 0 1px var(--blood-dim), 0 18px 48px -18px #000; }}
.stage.s-park     #big {{ box-shadow:0 0 0 1px var(--park), 0 18px 48px -18px #000; }}
.plate {{
  border-top:1px solid var(--rule-soft); padding:12px 18px 14px;
  display:flex; align-items:flex-end; gap:18px; flex-wrap:wrap;
  background:linear-gradient(var(--void),var(--void));
}}
.name {{ font-size:22px; letter-spacing:.03em; line-height:1.1; }}
.facts {{ display:flex; gap:14px; font-size:11.5px; color:var(--ink-3); flex-wrap:wrap; }}
.facts span b {{ color:var(--ink-2); font-weight:400; }}
.verdict {{ margin-left:auto; display:flex; align-items:center; gap:9px; }}
.chip {{
  font-size:11px; letter-spacing:.08em; text-transform:uppercase;
  padding:4px 9px; border:1px solid var(--rule); color:var(--ink-3);
}}
.chip.metal    {{ color:var(--steel); border-color:var(--steel); background:var(--steel-wash); }}
.chip.concrete {{ color:var(--crete); border-color:var(--crete); background:var(--crete-wash); }}
.chip.wood     {{ color:var(--timber); border-color:var(--timber); background:var(--timber-wash); }}
.chip.fluid    {{ color:var(--fluid); border-color:var(--fluid); background:var(--fluid-wash); }}
.chip.other    {{ color:var(--blood); border-color:var(--blood-dim); background:var(--blood-wash); }}
.chip.park     {{ color:var(--park); border-color:var(--park); background:var(--park-wash); }}
.chip .fx {{ color:var(--ink-3); text-transform:none; letter-spacing:.02em; }}
.chip.rough {{ color:var(--ink); border-color:var(--rule); background:var(--panel-2); text-transform:none; letter-spacing:.02em; }}
.chip.prior {{ border-style:dashed; }}

/* ── filmstrip ─────────────────────────────────────────────────────────── */
.strip {{ grid-area:strip; background:var(--void); border-top:1px solid var(--rule-soft); }}
.strip-rail {{ display:flex; gap:5px; padding:11px 18px; overflow-x:auto; scrollbar-width:thin; }}
.cell {{ position:relative; flex:0 0 auto; width:52px; height:52px; padding:0;
  border:1px solid var(--rule-soft); background:var(--pit); }}
.cell img {{ width:100%; height:100%; object-fit:cover; image-rendering:pixelated; display:block; opacity:.62; }}
.cell.done img, .cell.cur img {{ opacity:1; }}
.cell.cur {{ border-color:var(--blood); box-shadow:0 0 0 1px var(--blood); }}
.cell::after {{ content:""; position:absolute; left:0; right:0; bottom:0; height:3px; background:transparent; }}
.cell.s-metal::after    {{ background:var(--steel); }}
.cell.s-concrete::after {{ background:var(--crete); }}
.cell.s-wood::after     {{ background:var(--timber); }}
.cell.s-fluid::after    {{ background:var(--fluid); }}
.cell.s-other::after    {{ background:var(--blood); }}
.cell.s-park::after     {{ background:var(--park); }}
.cell.out {{ display:none; }}
.cell.gstart {{ margin-left:15px; }}
.cell.gstart::before {{
  content:attr(data-g); position:absolute; left:-15px; top:0; bottom:0; width:11px;
  writing-mode:vertical-rl; font-size:8.5px; letter-spacing:.1em; color:var(--ink-3);
  display:grid; place-items:center; border-left:1px solid var(--rule);
}}

/* ── sidebar ───────────────────────────────────────────────────────────── */
.side {{ grid-area:side; background:var(--void); overflow-y:auto; padding:16px 18px 26px;
  display:flex; flex-direction:column; gap:20px; }}
.sec {{ display:flex; flex-direction:column; gap:9px; }}
.sec > h2 {{ margin:0; font-size:10.5px; letter-spacing:.16em; text-transform:uppercase;
  color:var(--ink-3); font-weight:400; display:flex; align-items:center; gap:9px; }}
.sec > h2::after {{ content:""; flex:1; height:1px; background:var(--rule-soft); }}

.calls {{ display:grid; grid-template-columns:1fr 1fr; gap:7px; }}
.call {{ display:flex; align-items:center; gap:8px; padding:9px 10px;
  border:1px solid var(--rule); background:var(--panel); text-align:left;
  transition:background .12s, border-color .12s; }}
.call:hover {{ background:var(--panel-2); }}
.call[data-call="metal"].on    {{ border-color:var(--steel); background:var(--steel-wash); }}
.call[data-call="concrete"].on {{ border-color:var(--crete); background:var(--crete-wash); }}
.call[data-call="wood"].on     {{ border-color:var(--timber); background:var(--timber-wash); }}
.call[data-call="fluid"].on    {{ border-color:var(--fluid); background:var(--fluid-wash); }}
.call[data-call="other"].on    {{ border-color:var(--blood-dim); background:var(--blood-wash); }}
.call[data-call="park"].on     {{ border-color:var(--park); background:var(--park-wash); }}
.call em {{ font-style:normal; font-size:12px; }}
.call small {{ display:block; font-size:10px; color:var(--ink-3); }}
/* A hairline of the class's own colour, so the six buttons read apart at a glance. */
.call[data-call="metal"]    {{ border-left:2px solid var(--steel); }}
.call[data-call="concrete"] {{ border-left:2px solid var(--crete); }}
.call[data-call="wood"]     {{ border-left:2px solid var(--timber); }}
.call[data-call="fluid"]    {{ border-left:2px solid var(--fluid); }}
.call[data-call="clear"]    {{ grid-column:1 / -1; }}
.call[data-call="other"]    {{ border-left:2px solid var(--blood-dim); }}
.call[data-call="park"]     {{ border-left:2px solid var(--park); }}

.hint {{ margin:0; font-size:11.5px; line-height:1.5; color:var(--ink-2);
  border-left:2px solid var(--blood-dim); padding:2px 0 2px 10px; }}
.hint b {{ color:var(--ink); font-weight:600; }}

.bk {{ display:grid; grid-template-columns:auto 1fr auto; gap:4px 9px; align-items:center;
  padding:7px 10px; border:1px solid var(--rule-soft); background:var(--panel); text-align:left; }}
.bk:hover {{ background:var(--panel-2); }}
.bk.on {{ border-color:var(--blood); background:var(--blood-wash); }}
.bk.on .bk-n {{ color:var(--ink); }}
.bk-n {{ font-size:12px; color:var(--ink-2); }}
.bk-v {{ font-size:11px; color:var(--ink-3); font-variant-numeric:tabular-nums; }}
.bk-h {{ grid-column:2/4; font-size:10px; color:var(--ink-3); line-height:1.35; }}
.bk[data-b="4"], .bk[data-b="5"] {{ border-left:2px solid var(--blood-dim); }}
.bk[data-b="4"] .bk-n::after {{ content:"  ·  D"; color:var(--ink-3); font-size:10px; }}
.bk[data-b="5"] .bk-n::after {{ content:"  ·  F"; color:var(--ink-3); font-size:10px; }}
.bklist {{ display:flex; flex-direction:column; gap:4px; }}

#lobe {{ width:100%; height:44px; display:block; border:1px solid var(--rule-soft); background:var(--pit); }}
.lobe-cap {{ font-size:10px; color:var(--ink-3); }}

.keys {{ display:grid; grid-template-columns:auto 1fr; gap:5px 10px; font-size:11px; color:var(--ink-3); align-items:center; }}
.keys kbd + kbd {{ margin-left:3px; }}

.row {{ display:flex; gap:6px; flex-wrap:wrap; }}
.pair {{ display:grid; grid-template-columns:1fr 1fr; gap:6px; }}
.check {{ display:flex; align-items:center; gap:7px; font-size:11px; color:var(--ink-2); cursor:pointer; }}
.check input {{ width:13px; height:13px; accent-color:var(--blood); margin:0; }}
.btn {{ padding:7px 11px; border:1px solid var(--rule); background:var(--panel); font-size:11.5px;
  letter-spacing:.04em; }}
.btn:hover {{ background:var(--panel-2); border-color:var(--ink-3); }}
.btn.warn:hover {{ border-color:var(--blood); color:var(--blood); }}
select, textarea, input[type=search] {{
  font:12px/1.4 var(--mono); color:var(--ink); background:var(--panel);
  border:1px solid var(--rule); padding:7px 9px; width:100%; border-radius:0;
}}
textarea {{ min-height:104px; resize:vertical; white-space:pre; overflow:auto; }}
.note {{ font-size:10.5px; color:var(--ink-3); line-height:1.5; margin:0; }}
.say {{ font-size:11px; color:var(--blood); min-height:15px; }}
</style>

<div class="app">

  <div class="top">
    <div>
      <div class="eyebrow">D64RTR_v15.WAD &middot; {total} surfaces</div>
      <div class="title"><b>Metal or not</b> &mdash; then how rough</div>
    </div>
    <div class="flag" id="flag" hidden>working set <b id="flagname">&mdash;</b>
      <button type="button" id="flagoff">show all</button></div>
    <div class="prog">
      <div class="meter" aria-hidden="true"><i id="mfill" style="width:0"></i><i id="pfill" class="park" style="width:0"></i></div>
      <div class="tally" id="tally">0 of {total} labelled</div>
    </div>
  </div>

  <main class="stage" id="stage">
    <div class="canvaswrap"><img id="big" alt=""></div>
    <div class="plate">
      <div>
        <div class="name" id="tname">&nbsp;</div>
        <div class="facts" id="tfacts"></div>
      </div>
      <div class="verdict" id="verdict"></div>
    </div>
  </main>

  <div class="strip"><div class="strip-rail" id="rail"></div></div>

  <aside class="side">

    <section class="sec">
      <h2>The call</h2>
      <div class="calls">
        <button class="call" data-call="metal" type="button"><kbd>S</kbd><em>metal<small>steel, iron, grating &middot; sparks</small></em></button>
        <button class="call" data-call="concrete" type="button"><kbd>C</kbd><em>concrete<small>stone, brick, tile &middot; dust</small></em></button>
        <button class="call" data-call="wood" type="button"><kbd>W</kbd><em>wood<small>planks, crates &middot; splinters</small></em></button>
        <button class="call" data-call="fluid" type="button"><kbd>Q</kbd><em>fluid<small>water, blood, nukage, lava &middot; splash</small></em></button>
        <button class="call" data-call="other" type="button"><kbd>A</kbd><em>other<small>flesh, goo, glass, screens</small></em></button>
        <button class="call" data-call="park" type="button"><kbd>X</kbd><em>park it<small>decide later</small></em></button>
        <button class="call" data-call="clear" type="button"><kbd>&#9003;</kbd><em>clear<small>unlabel this one</small></em></button>
      </div>
      <p class="hint"><b>You are answering "what is this made of".</b> The class drives two
      different systems. It sets <i>metallic</i> for shading &mdash; and metallic means the surface
      answers light differently (no diffuse, specular tinted by the albedo, sheen at grazing angles),
      <i>not</i> that you can see yourself in it. It also picks the <b>impact effect</b>: a bullet
      into metal throws sparks, into concrete it throws dust and chips, into water a splash.
      Sparks currently fire on everything that is not flesh, liquid or sky, which is why
      concrete needs its own call &mdash; and the liquid test only knows about flats the map
      marks as liquid, so a wall of falling blood needs <b>fluid</b> saying so.
      Doom 64 is mostly painted steel, cast iron, worn plate and grating &mdash; nearly all of it
      metal <i>and</i> rough. Reach for <span style="color:var(--ink)">rough</span> and leave the
      mirror bucket for the handful of surfaces that earn it.</p>
    </section>

    <section class="sec">
      <h2>Roughness</h2>
      <div class="bklist">{bucket_rows}</div>
      <canvas id="lobe" width="600" height="88"></canvas>
      <div class="lobe-cap">Highlight this roughness gives, tinted by the texture's own colour.</div>
      <p class="hint" id="fluidnote" hidden>RTGL1 renders water and lava as media
      (<span class="mono">RG_MESH_PRIMITIVE_WATER</span> / <span class="mono">LAVA</span>), not
      through this BRDF. On a <b>fluid</b> texture the roughness pick is mostly cosmetic &mdash;
      take the obvious one and move on.</p>
    </section>

    <section class="sec">
      <h2>Keys</h2>
      <div class="keys">
        <div><kbd>S</kbd></div><div>metal &middot; rough 0.80 &middot; advance</div>
        <div><kbd>C</kbd></div><div>concrete &middot; advance</div>
        <div><kbd>W</kbd></div><div>wood &middot; advance</div>
        <div><kbd>Q</kbd></div><div>fluid &middot; advance</div>
        <div><kbd>A</kbd></div><div>other, not metal &middot; advance</div>
        <div><kbd>D</kbd><kbd>F</kbd></div><div>rough 0.80 / very rough 0.95</div>
        <div><kbd>1</kbd>&hellip;<kbd>6</kbd></div><div>roughness ladder, mirror &rarr; very rough</div>
        <div><kbd>X</kbd></div><div>park &amp; advance</div>
        <div><kbd>&larr;</kbd><kbd>&rarr;</kbd></div><div>previous / next</div>
        <div><kbd>&#9251;</kbd></div><div>next unlabelled</div>
        <div><kbd>U</kbd></div><div>undo last call</div>
        <div><kbd>/</kbd></div><div>jump to a name</div>
      </div>
      <p class="note">Set roughness first, then call it. Pressing <kbd>S</kbd> on its own means
      metal at 0.80 &mdash; the common case costs one key.</p>
    </section>

    <section class="sec">
      <h2>Working set</h2>
      <div class="pair">
        <select id="msel" aria-label="Limit to one map"><option value="-1">all maps</option>{map_opts}</select>
        <select id="gsel" aria-label="Jump to prefix"><option value="">&mdash; prefix &mdash;</option>{group_opts}</select>
      </div>
      <p class="note">Pick a map to label just that map first, apply it, and look at the
      result in game before committing to all {total}. Everything &mdash; arrows,
      <kbd>&#9251;</kbd>, the strip &mdash; stays inside the set. Labels stay put when you
      clear the filter; they are never scoped to a map.</p>
      <input type="search" id="find" placeholder="name or prefix, then Enter" aria-label="Jump to texture">
      <div class="row">
        <button class="btn" id="nextun" type="button">next unlabelled</button>
        <button class="btn" id="undo" type="button">undo</button>
      </div>
    </section>

    <section class="sec">
      <h2>Export</h2>
      <div class="row">
        <button class="btn" id="copy" type="button">copy JSON</button>
        <button class="btn" id="show" type="button">show / paste</button>
        <button class="btn warn" id="wipe" type="button">wipe all</button>
      </div>
      <div class="say" id="say"></div>
      <textarea id="io" spellcheck="false" hidden aria-label="Export and import JSON"></textarea>
      <label class="check"><input type="checkbox" id="only"> only what is in the current working set</label>
      <div class="row" id="iorow" hidden>
        <button class="btn" id="imp" type="button">import what's in the box</button>
      </div>
      <p class="note">Exports everything you have labelled by default, filter or no filter &mdash;
      the applier should never have to guess at scope. Saved to this browser on every keystroke.
      Downloads are blocked in this viewer, so copy the JSON out &mdash; paste it back into the box
      to resume on another machine.</p>
    </section>

  </aside>
</div>

<script id="tex" type="application/json">{payload}</script>
<script>
(function(){{
  "use strict";
  const T = JSON.parse(document.getElementById('tex').textContent);
  const BUCKETS = {buckets_json};
  const MAPS = {maps_json};
  const DEFAULT_B = 4;                 // rough 0.80 -- Doom 64's normal case
  const KEY = 'd64rt-metal-labels-v1';
  const N = T.length;

  // Surface class: shading metalness on one side, impact effect on the other.
  // Deliberately four values. The impact system needs metal-vs-not-metal to pick
  // sparks or dust; a longer taxonomy would cost labelling time it cannot repay.
  const SURF = {{
    metal:    {{ m: 1, fx: 'sparks' }},
    concrete: {{ m: 0, fx: 'dust, chips' }},
    wood:     {{ m: 0, fx: 'splinters' }},
    fluid:    {{ m: 0, fx: 'splash' }},
    other:    {{ m: 0, fx: 'no sparks' }}
  }};
  const CLASSES = ['metal', 'concrete', 'wood', 'fluid', 'other', 'park'];

  // Labels saved before the surface axis existed carry only {{m, b}}. Read them as
  // metal/other rather than making anyone re-label work they already did.
  const surfaceOf = l => (l && l.s && SURF[l.s]) ? l.s : (l && l.m === 1 ? 'metal' : 'other');

  // ---- state -------------------------------------------------------------
  // labels are keyed by texture name and are GLOBAL. The map filter narrows what
  // you are looking at, never what you have said -- label under a filter, clear the
  // filter, the call is still there.
  let labels = {{}};                    // name -> {{m:0|1, b:bucketIndex}} | {{park:1}}
  let idx = 0;                         // index into T
  let mapf = -1;                       // -1 = all maps, else index into MAPS
  let view = [];                       // indices into T that survive the filter
  let history = [];

  try {{ labels = JSON.parse(localStorage.getItem(KEY) || '{{}}') || {{}}; }} catch (e) {{ labels = {{}}; }}
  // `+null` is 0, so a missing key would read as "index 0" and quietly park a fresh
  // browser on the first map. Test for the key's absence, not its numeric value.
  try {{
    const s = localStorage.getItem(KEY + ':at');
    const i = s === null ? -1 : +s;
    if (i >= 0 && i < N) idx = i;
  }} catch (e) {{}}
  try {{
    const s = localStorage.getItem(KEY + ':map');
    const m = s === null ? -1 : +s;
    if (m >= 0 && m < MAPS.length) mapf = m;
  }} catch (e) {{}}

  function save() {{
    try {{
      localStorage.setItem(KEY, JSON.stringify(labels));
      localStorage.setItem(KEY + ':at', String(idx));
      localStorage.setItem(KEY + ':map', String(mapf));
    }} catch (e) {{ say('Browser storage is full — copy your JSON out now.'); }}
  }}

  const inFilter = i => mapf < 0 || T[i].m.indexOf(mapf) >= 0;

  // ---- element refs ------------------------------------------------------
  const big = document.getElementById('big');
  const stage = document.getElementById('stage');
  const tname = document.getElementById('tname');
  const tfacts = document.getElementById('tfacts');
  const verdict = document.getElementById('verdict');
  const rail = document.getElementById('rail');
  const tally = document.getElementById('tally');
  const mfill = document.getElementById('mfill');
  const pfill = document.getElementById('pfill');
  const io = document.getElementById('io');
  const iorow = document.getElementById('iorow');
  const sayEl = document.getElementById('say');
  const find = document.getElementById('find');
  const msel = document.getElementById('msel');
  const flag = document.getElementById('flag');
  const flagname = document.getElementById('flagname');
  const only = document.getElementById('only');
  const fluidnote = document.getElementById('fluidnote');
  const lobe = document.getElementById('lobe');
  const lctx = lobe.getContext('2d');

  let sayTimer = 0;
  function say(msg) {{
    sayEl.textContent = msg;
    clearTimeout(sayTimer);
    sayTimer = setTimeout(() => {{ sayEl.textContent = ''; }}, 4000);
  }}

  const src = r => 'data:image/webp;base64,' + r.d;

  // ---- filmstrip (built once, patched in place) --------------------------
  const cells = T.map((r, i) => {{
    const b = document.createElement('button');
    b.className = 'cell';
    b.type = 'button';
    b.title = r.n;
    const im = document.createElement('img');
    im.loading = 'lazy';
    im.decoding = 'async';
    im.alt = r.n;
    im.src = src(r);
    b.appendChild(im);
    b.addEventListener('click', () => go(i));
    rail.appendChild(b);
    return b;
  }});

  function paintCell(i) {{
    const c = cells[i], l = labels[T[i].n];
    c.classList.toggle('cur', i === idx);
    c.classList.toggle('done', !!l);
    const s = !l ? null : (l.park ? 'park' : surfaceOf(l));
    CLASSES.forEach(k => c.classList.toggle('s-' + k, s === k));
  }}

  // ---- the working set ---------------------------------------------------
  // One place decides what is in play. Navigation, the strip, the counter and the
  // "next unlabelled" hunt all read `view`, so nothing can step outside the filter.
  function rebuildView() {{
    view = [];
    let lastGroup = null;
    for (let i = 0; i < N; i++) {{
      const c = cells[i];
      if (!inFilter(i)) {{
        c.classList.add('out');
        c.classList.remove('gstart');
        continue;
      }}
      c.classList.remove('out');
      const g = T[i].g;
      if (g !== lastGroup) {{ c.classList.add('gstart'); c.dataset.g = g; lastGroup = g; }}
      else c.classList.remove('gstart');
      view.push(i);
    }}
    if (view.length && !inFilter(idx)) {{
      // Snap to the nearest member rather than dumping the labeller at the top.
      let best = view[0], bd = Infinity;
      for (const i of view) {{ const d = Math.abs(i - idx); if (d < bd) {{ bd = d; best = i; }} }}
      idx = best;
    }}
    const on = mapf >= 0;
    flag.hidden = !on;
    flagname.textContent = on ? MAPS[mapf] : '—';
    msel.value = String(mapf);
    only.disabled = !on;
    if (!on) only.checked = false;
  }}

  const vpos = () => {{ const p = view.indexOf(idx); return p < 0 ? 0 : p; }};

  // ---- specular preview: a rough lobe, never a chrome ball ---------------
  function drawLobe(rough, tint, metal) {{
    const w = lobe.width, h = lobe.height;
    lctx.clearRect(0, 0, w, h);
    const a = Math.max(rough, 0.02) * Math.max(rough, 0.02);
    const spread = 0.5 * a + 0.012;              // lobe half-width in x-units
    const peak = 1 / (1 + 14 * a);               // energy conserved, roughly
    const c = metal ? tint : '#E8E4E0';
    const cr = parseInt(c.slice(1, 3), 16), cg = parseInt(c.slice(3, 5), 16), cb = parseInt(c.slice(5, 7), 16);
    lctx.beginPath();
    lctx.moveTo(0, h);
    for (let x = 0; x <= w; x++) {{
      const d = (x / w - 0.5) / spread;
      const v = peak * Math.exp(-d * d) + (metal ? 0.015 : 0.05);
      lctx.lineTo(x, h - Math.min(1, v) * (h - 6) - 3);
    }}
    lctx.lineTo(w, h);
    lctx.closePath();
    const g = lctx.createLinearGradient(0, 0, 0, h);
    g.addColorStop(0, 'rgba(' + cr + ',' + cg + ',' + cb + ',.92)');
    g.addColorStop(1, 'rgba(' + cr + ',' + cg + ',' + cb + ',.10)');
    lctx.fillStyle = g;
    lctx.fill();
    lctx.strokeStyle = 'rgba(' + cr + ',' + cg + ',' + cb + ',.85)';
    lctx.lineWidth = 2;
    lctx.stroke();
  }}

  // ---- render current ----------------------------------------------------
  const bkEls = Array.from(document.querySelectorAll('.bk'));
  const callEls = Array.from(document.querySelectorAll('.call'));

  function render() {{
    const r = T[idx], l = labels[r.n];
    big.src = src(r);
    big.alt = r.n;
    // Nearest-neighbour blow-up: integer scale so pixels stay square.
    const k = Math.max(1, Math.floor(Math.min(560 / r.w, 420 / r.h)));
    big.style.width = (r.w * k) + 'px';
    big.style.height = (r.h * k) + 'px';
    tname.textContent = r.n;

    const f = ['<span><b>' + r.w + '&times;' + r.h + '</b> px</span>',
               '<span>group <b>' + r.g + '</b></span>',
               '<span><b>' + (vpos() + 1) + '</b> / ' + view.length
                 + (mapf >= 0 ? ' in ' + MAPS[mapf] : '') + '</span>'];
    // How widely a texture is reused is how much care it deserves: a wall in thirty
    // maps is worth a second look, a one-map trim is not.
    if (r.m.length) {{
      const names = r.m.map(i => MAPS[i]);
      const shown = names.slice(0, 5).join(' ');
      f.push('<span><b>' + r.m.length + '</b> map' + (r.m.length === 1 ? '' : 's') + ' &middot; '
             + shown + (names.length > 5 ? ' +' + (names.length - 5) : '') + '</span>');
    }} else f.push('<span>in no map &mdash; unused art</span>');
    if (r.u) f.push('<span><b>' + r.u + '</b> uses</span>');
    if (r.p) f.push('<span>already in textures.json: metal <b>' + r.p[0] + '</b> rough <b>' + (r.p[1] === undefined ? '&mdash;' : r.p[1]) + '</b></span>');
    tfacts.innerHTML = f.join('');

    const v = [];
    const s = !l ? null : (l.park ? 'park' : surfaceOf(l));
    if (s === 'park') v.push('<span class="chip park">parked</span>');
    else if (l) {{
      v.push('<span class="chip ' + s + '">' + s + ' <span class="fx">&middot; ' + SURF[s].fx + '</span></span>');
      v.push('<span class="chip rough">' + BUCKETS[l.b][0] + ' &middot; ' + BUCKETS[l.b][1].toFixed(2) + '</span>');
    }} else v.push('<span class="chip">unlabelled</span>');
    verdict.innerHTML = v.join('');

    CLASSES.forEach(k => stage.classList.toggle('s-' + k, s === k));
    // The roughness caveat surfaces only where it applies, rather than sitting there
    // as permanent noise on the 1300 textures it has nothing to do with.
    fluidnote.hidden = s !== 'fluid';

    const bsel = l && !l.park ? l.b : pending;
    bkEls.forEach((b, i) => b.classList.toggle('on', i === bsel));
    callEls.forEach(b => b.classList.toggle('on', b.dataset.call === s));

    drawLobe(BUCKETS[bsel === null ? DEFAULT_B : bsel][1], r.c, !l || l.m !== 0);

    cells.forEach((c, i) => c.classList.toggle('cur', i === idx));
    paintCell(idx);
    cells[idx].scrollIntoView({{ block: 'nearest', inline: 'center' }});
    tallyUp();
  }}

  function tallyUp() {{
    // Global truth first -- it is what the applier will eventually consume.
    let gdone = 0;
    for (const k in labels) if (!labels[k].park) gdone++;

    // The meter tracks the working set, so a map pilot shows real progress.
    let done = 0, park = 0;
    for (const i of view) {{
      const l = labels[T[i].n];
      if (!l) continue;
      if (l.park) park++; else done++;
    }}
    const n = view.length || 1;
    const where = mapf >= 0 ? ' in ' + MAPS[mapf] : ' labelled';
    tally.innerHTML = '<b>' + done + '</b> of ' + view.length + where
      + (park ? ' &middot; ' + park + ' parked' : '')
      + (mapf >= 0 ? ' <span class="glob">&middot; ' + gdone + ' / ' + N + ' overall</span>' : '');
    mfill.style.width = (done / n * 100) + '%';
    pfill.style.width = (park / n * 100) + '%';
    pfill.style.left = (done / n * 100) + '%';
    pfill.style.right = 'auto';
  }}

  // ---- actions -----------------------------------------------------------
  let pending = null;     // roughness chosen but the metal call not made yet

  function push(name) {{
    history.push([name, labels[name] ? JSON.parse(JSON.stringify(labels[name])) : null, idx]);
    if (history.length > 400) history.shift();
  }}

  function go(i) {{                      // i is an index into T; must be in the view
    const prev = idx;
    idx = Math.max(0, Math.min(N - 1, i));
    pending = null;
    paintCell(prev);
    render();
    save();
  }}

  function goView(p) {{                  // p is a position within the working set
    if (!view.length) return;
    go(view[Math.max(0, Math.min(view.length - 1, p))]);
  }}

  const step = d => goView(vpos() + d);

  function setBucket(b) {{
    const r = T[idx], l = labels[r.n];
    if (l && !l.park) {{ push(r.n); l.b = b; pending = null; }}
    else pending = b;
    render();
    save();
  }}

  function call(kind) {{
    const r = T[idx];
    push(r.n);
    if (kind === 'clear') delete labels[r.n];
    else if (kind === 'park') labels[r.n] = {{ park: 1 }};
    else labels[r.n] = {{
      m: SURF[kind].m,
      b: pending === null ? DEFAULT_B : pending,
      s: kind
    }};
    pending = null;
    save();
    if (kind === 'clear') {{ render(); return; }}
    const p = vpos();
    if (p < view.length - 1) goView(p + 1); else render();
  }}

  function undo() {{
    const h = history.pop();
    if (!h) {{ say('Nothing to undo.'); return; }}
    const [name, prior, at] = h;
    if (prior === null) delete labels[name]; else labels[name] = prior;
    if (inFilter(at)) idx = at;          // never let undo walk out of the working set
    pending = null;
    cells.forEach((c, i) => paintCell(i));
    render();
    save();
  }}

  function nextUnlabelled() {{
    const n = view.length;
    if (!n) return;
    const start = vpos();
    for (let s = 1; s <= n; s++) {{
      const p = (start + s) % n;
      if (!labels[T[view[p]].n]) {{ goView(p); return; }}
    }}
    say(mapf >= 0 ? 'Every texture in ' + MAPS[mapf] + ' has a call on it.'
                  : 'Every texture has a call on it.');
  }}

  // ---- export / import ---------------------------------------------------
  function exportObj() {{
    // Default is everything labelled, whatever the filter says. Narrowing is opt-in
    // so the applier never has to work out what scope it was handed.
    const scoped = only.checked && mapf >= 0;
    const out = {{}};
    const skipped = [];
    T.forEach((r, i) => {{
      const l = labels[r.n];
      if (!l) return;
      if (scoped && !inFilter(i)) return;
      if (l.park) {{ skipped.push(r.n); return; }}
      // The two existing fields keep their exact names and shape -- apply_material_labels.py
      // and bake_material_labels_orm.py read only these and ignore anything else, so
      // `surface` rides along for the impact system without touching what ships today.
      out[r.n] = {{
        metallicDefault: l.m ? 1.0 : 0.0,
        roughnessDefault: BUCKETS[l.b][1],
        surface: surfaceOf(l)
      }};
    }});
    const labelled = Object.keys(out).length;
    const counts = {{}};
    Object.keys(out).forEach(k => {{ const s = out[k].surface; counts[s] = (counts[s] || 0) + 1; }});
    out.__skipped = skipped;
    out.__meta = {{
      source: 'tools/gen_material_labeller.py',
      wad: 'D64RTR_v15.WAD',
      scope: scoped ? MAPS[mapf] : 'all',
      total: scoped ? view.length : N,
      labelled: labelled,
      surfaces: counts,
      exported: new Date().toISOString()
    }};
    return out;
  }}

  function exportText() {{ return JSON.stringify(exportObj(), null, 2); }}

  document.getElementById('copy').addEventListener('click', () => {{
    const t = exportText();
    if (navigator.clipboard && navigator.clipboard.writeText) {{
      navigator.clipboard.writeText(t).then(
        () => say('Copied ' + (exportObj().__meta.labelled) + ' entries.'),
        () => {{ showBox(t); say('Clipboard refused — select the box and copy.'); }}
      );
    }} else {{ showBox(t); say('Select the box and copy.'); }}
  }});

  function showBox(t) {{
    io.hidden = false; iorow.hidden = false;
    io.value = t === undefined ? exportText() : t;
    io.focus(); io.select();
  }}
  document.getElementById('show').addEventListener('click', () => showBox());

  document.getElementById('imp').addEventListener('click', () => {{
    let o;
    try {{ o = JSON.parse(io.value); }} catch (e) {{ say('That is not valid JSON.'); return; }}
    if (!o || typeof o !== 'object') {{ say('Expected a JSON object.'); return; }}
    const byName = {{}};
    T.forEach((r, i) => byName[r.n] = i);
    let hit = 0, miss = 0;
    Object.keys(o).forEach(k => {{
      if (k.slice(0, 2) === '__') return;
      if (!(k in byName)) {{ miss++; return; }}
      const e = o[k] || {{}};
      const rough = typeof e.roughnessDefault === 'number' ? e.roughnessDefault : BUCKETS[DEFAULT_B][1];
      let b = 0, best = 9;
      BUCKETS.forEach((bk, i) => {{ const d = Math.abs(bk[1] - rough); if (d < best) {{ best = d; b = i; }} }});
      const metal = e.metallicDefault >= 0.5 ? 1 : 0;
      // An export from before the surface axis has no `surface` -- derive it.
      const s = (typeof e.surface === 'string' && SURF[e.surface]) ? e.surface
                                                                  : (metal ? 'metal' : 'other');
      labels[k] = {{ m: metal, b: b, s: s }};
      hit++;
    }});
    (Array.isArray(o.__skipped) ? o.__skipped : []).forEach(k => {{
      if (k in byName) {{ labels[k] = {{ park: 1 }}; hit++; }} else miss++;
    }});
    history = [];
    cells.forEach((c, i) => paintCell(i));
    render();
    save();
    say('Imported ' + hit + ' entries' + (miss ? ', ' + miss + ' unknown names ignored.' : '.'));
  }});

  document.getElementById('wipe').addEventListener('click', () => {{
    if (!confirm('Discard every label in this browser? Copy the JSON out first if you want it.')) return;
    labels = {{}}; history = []; pending = null;
    cells.forEach((c, i) => paintCell(i));
    render(); save();
    say('Cleared.');
  }});

  // ---- wiring ------------------------------------------------------------
  bkEls.forEach(b => b.addEventListener('click', () => setBucket(+b.dataset.b)));
  callEls.forEach(b => b.addEventListener('click', () => call(b.dataset.call)));
  document.getElementById('undo').addEventListener('click', undo);
  document.getElementById('nextun').addEventListener('click', nextUnlabelled);

  function setMap(m) {{
    mapf = m;
    if (!T.some((r, i) => inFilter(i))) {{
      say('No texture in that map, filter left alone.');
      mapf = -1;
    }}
    pending = null;
    rebuildView();
    cells.forEach((c, i) => paintCell(i));
    render();
    save();
  }}

  msel.addEventListener('change', e => {{ setMap(+e.target.value); e.target.blur(); }});
  document.getElementById('flagoff').addEventListener('click', () => setMap(-1));
  only.addEventListener('change', () => {{ if (!io.hidden) io.value = exportText(); }});

  document.getElementById('gsel').addEventListener('change', e => {{
    const g = e.target.value;
    if (!g) return;
    const i = view.find(j => T[j].g === g);
    if (i === undefined) say(g + ' is not in ' + (mapf >= 0 ? MAPS[mapf] : 'the set') + '.');
    else go(i);
    e.target.blur();
  }});

  find.addEventListener('keydown', e => {{
    if (e.key !== 'Enter') return;
    const q = find.value.trim().toUpperCase();
    if (!q) return;
    // Search the working set only -- jumping silently out of a filter is how you
    // end up labelling the wrong map for ten minutes.
    let i = view.find(j => T[j].n === q);
    if (i === undefined) i = view.find(j => T[j].n.indexOf(q) === 0);
    if (i === undefined) i = view.find(j => T[j].n.indexOf(q) >= 0);
    if (i === undefined) {{
      const anywhere = T.some(r => r.n.indexOf(q) >= 0);
      say(anywhere && mapf >= 0
        ? q + ' exists, but not in ' + MAPS[mapf] + '.'
        : 'No texture matches ' + q + '.');
      return;
    }}
    go(i);
    find.blur();
  }});

  const DIGIT = {{ '1': 0, '2': 1, '3': 2, '4': 3, '5': 4, '6': 5 }};
  document.addEventListener('keydown', e => {{
    const t = e.target;
    if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.tagName === 'SELECT')) {{
      if (e.key === 'Escape') t.blur();
      return;
    }}
    if (e.ctrlKey || e.metaKey || e.altKey) {{
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'z') {{ e.preventDefault(); undo(); }}
      return;
    }}
    const k = e.key;
    if (k in DIGIT) {{ e.preventDefault(); setBucket(DIGIT[k]); return; }}
    switch (k.toLowerCase()) {{
      case 's': e.preventDefault(); call('metal'); break;
      case 'c': e.preventDefault(); call('concrete'); break;
      case 'w': e.preventDefault(); call('wood'); break;
      case 'q': e.preventDefault(); call('fluid'); break;
      case 'a': e.preventDefault(); call('other'); break;
      case 'd': e.preventDefault(); setBucket(4); break;
      case 'f': e.preventDefault(); setBucket(5); break;
      case 'x': e.preventDefault(); call('park'); break;
      case 'u': e.preventDefault(); undo(); break;
      case 'backspace': e.preventDefault(); call('clear'); break;
      case 'arrowright': e.preventDefault(); step(1); break;
      case 'arrowleft': e.preventDefault(); step(-1); break;
      case 'home': e.preventDefault(); goView(0); break;
      case 'end': e.preventDefault(); goView(view.length - 1); break;
      case ' ': e.preventDefault(); nextUnlabelled(); break;
      case '/': e.preventDefault(); find.focus(); find.select(); break;
      default: break;
    }}
  }});

  rebuildView();
  cells.forEach((c, i) => paintCell(i));
  render();
}})();
</script>
"""
    OUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    OUT_HTML.write_text(html, encoding="utf-8")


def main() -> None:
    records, stats = gather()
    write_html(records, stats)
    size = OUT_HTML.stat().st_size
    print(f"TX namespace lumps      : {stats['tx_lumps']}")
    print(f"composites folded in    : {stats['composites_added']}")
    print(f"textures on the page    : {len(records)}")
    print(f"  of which map-used     : {stats['map_used']}")
    print(f"  with a prior value    : {stats['prior_hits']}")
    print(f"failed to render        : {len(stats['missing'])} {stats['missing'][:12]}")
    print(f"wrote {OUT_HTML}  ({size / 1e6:.2f} MB)")


if __name__ == "__main__":
    main()
