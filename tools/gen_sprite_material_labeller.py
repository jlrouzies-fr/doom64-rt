"""Generate the SPRITE material labelling page.

The wall/flat labeller (tools/gen_material_labeller.py) asks one question per
texture. A sprite cannot be answered that way: a shotgun is a metal receiver, a
wooden stock and two hands, and they need different answers in the same image.

So this page labels COLOUR CLUSTERS, not images.

Why clusters rather than a paint brush: there are 1387 sprite lumps. Painting
each one is not a job anyone finishes. But a sprite CODE reuses one small set of
colours across every frame and rotation it has -- TROO is 68 frames sharing 219
distinct colours -- so labelling the colours once labels all 68 frames. Clicking
a cluster still highlights exactly the barrel or exactly the flesh, which is the
"select a part" the job actually needs; the brush is kept only for the case one
grey genuinely serves two materials.

Sprites are NOT all one format, which is why clustering is needed at all rather
than reading a palette: monsters are indexed PNGs with tight palettes (TROO 219
colours), but several weapon sprites are truecolour -- SHTG spans 4898 distinct
colours over 10 frames, PLSG 6823. Exact-colour labelling works for the first
group and explodes on the second, so everything is quantised to a common ceiling
and the human labels the quantised set.

MIRRORED ROTATIONS ARE NOT EMITTED. The WAD stores one image for e.g. rotations
2 and 8 and the engine flips it at render time -- it will flip the _orm exactly
the same way, so labelling the mirror would be labelling the same pixels twice.

Run with the project Python (it has Pillow):

  C:\\Users\\Winter\\AppData\\Local\\Programs\\Python\\Python313\\python.exe ^
      .\\tools\\gen_sprite_material_labeller.py --cat WEAPONS

Output: tools/_gallery/sprite_labeller_<cat>.html
Export from the page feeds tools/bake_sprite_materials.py.
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import re
import struct
import sys
from collections import Counter
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
WAD = ROOT / "Doom64-Retribution" / "D64RTR_v15.WAD"
OUTDIR = ROOT / "tools" / "_gallery"

NAME_RE = re.compile(r"^([A-Z0-9]{4})([A-Z\[\\\]])([0-8])(?:([A-Z\[\\\]])([0-8]))?$")

# Quantisation ceiling. High enough that a shading ramp keeps its steps (so
# "the lit side of the barrel" and "the shadowed side" stay one material rather
# than being forced apart), low enough that a human can get through the strip.
DEFAULT_CLUSTERS = 28

# Pixels sampled when building the cluster set. A weapon code is well under
# this; the cap exists so a 68-frame monster does not build a 3 M pixel image.
SAMPLE_CAP = 400_000

# call, key, metallic, roughness, hue for the UI
SURFACES = [
    ("metal",   "S", 1.0, 0.40, "#9FB3C8"),
    ("flesh",   "E", 0.0, 0.70, "#C86B6B"),
    ("cloth",   "C", 0.0, 0.90, "#6BA89A"),
    ("leather", "L", 0.0, 0.65, "#8A6A45"),
    ("wood",    "W", 0.0, 0.80, "#A9803F"),
    ("bone",    "B", 0.0, 0.55, "#CFC6A8"),
    ("rubber",  "R", 0.0, 0.60, "#7D7D86"),
    ("lens",    "G", 0.0, 0.15, "#C8A02A"),
    ("other",   "A", 0.0, 0.80, "#8E8E8E"),
]

ROUGH_BUCKETS = [0.05, 0.20, 0.40, 0.60, 0.80, 0.95]


def read_lumps(data: bytes) -> list[tuple[str, int, int]]:
    n, o = struct.unpack_from("<II", data, 4)
    out = []
    for i in range(n):
        off, sz, name = struct.unpack_from("<II8s", data, o + i * 16)
        out.append((name.split(b"\0")[0].decode("ascii", "replace"), off, sz))
    return out


def decode_doompic_grayscale(raw: bytes) -> Image.Image | None:
    """Classic column-post format. This WAD ships no PLAYPAL, so indices render
    as a grayscale ramp: shape-accurate, colour-approximate. Only a handful of
    effect sprites (shell casings) use it."""
    if len(raw) < 8:
        return None
    w, h, _lo, _to = struct.unpack_from("<hhhh", raw, 0)
    if not (0 < w <= 4096 and 0 < h <= 4096):
        return None
    colofs = struct.unpack_from(f"<{w}I", raw, 8)
    canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    px = canvas.load()
    for x in range(w):
        pos = colofs[x]
        if pos >= len(raw):
            continue
        while pos < len(raw):
            topdelta = raw[pos]
            if topdelta == 0xFF:
                break
            length = raw[pos + 1]
            pos += 3
            for j in range(length):
                if pos + j >= len(raw):
                    break
                y = topdelta + j
                if 0 <= y < h:
                    g = raw[pos + j]
                    px[x, y] = (g, g, g, 255)
            pos += length + 1
    return canvas


def load_sprite(raw: bytes) -> Image.Image | None:
    if raw.startswith(b"\x89PNG"):
        try:
            return Image.open(io.BytesIO(raw)).convert("RGBA")
        except Exception:
            return None
    return decode_doompic_grayscale(raw)


def collect(cat_filter: str | None, code_filter: set[str] | None):
    data = WAD.read_bytes()
    lumps = read_lumps(data)
    names = [nm for nm, _, _ in lumps]
    s0, s1 = names.index("SS_START"), names.index("SS_END")

    category = "UNCATEGORIZED"
    by_code: dict[str, dict] = {}
    for nm, off, sz in lumps[s0 + 1 : s1]:
        if sz == 0:  # section divider
            category = nm
            continue
        m = NAME_RE.match(nm)
        if not m:
            continue
        code = m.group(1)
        if cat_filter and category != cat_filter:
            continue
        if code_filter and code not in code_filter:
            continue
        im = load_sprite(data[off : off + sz])
        if im is None:
            continue
        rec = by_code.setdefault(code, {"code": code, "cat": category, "frames": []})
        # Only the stored image. The mirrored half of a rotation pair is the
        # same pixels and the engine flips the _orm with the albedo.
        rec["frames"].append({"lump": nm, "im": im})
    return by_code


def build_clusters(frames: list[dict], ncolors: int):
    """Quantise a code's whole colour set once. Returns centroids (list of RGB)
    and, per frame, a bytes id-map with 0 = transparent, else cluster+1."""
    pixels: list[tuple[int, int, int]] = []
    counts: Counter = Counter()
    for f in frames:
        for p in f["im"].getdata():
            if p[3] > 0:
                counts[(p[0], p[1], p[2])] += 1
    if not counts:
        return [], {}

    uniq = list(counts)
    if len(uniq) <= ncolors:
        centroids = uniq
    else:
        # Median-cut over a synthetic image of the colour set, weighted by how
        # often each colour actually appears -- an unweighted pass gives a
        # single stray highlight the same say as the body of the sprite.
        total = sum(counts.values())
        scale = min(1.0, SAMPLE_CAP / max(1, total))
        for rgb, n in counts.items():
            reps = max(1, int(n * scale))
            pixels.extend([rgb] * reps)
        strip = Image.new("RGB", (len(pixels), 1))
        strip.putdata(pixels)
        pal = strip.quantize(colors=ncolors, method=Image.Quantize.MEDIANCUT)
        raw = pal.getpalette()[: ncolors * 3]
        centroids = [tuple(raw[i * 3 : i * 3 + 3]) for i in range(ncolors)]

    # Nearest centroid for every distinct colour, once, then reused per frame.
    lut: dict[tuple[int, int, int], int] = {}
    for rgb in counts:
        best, bd = 0, 1 << 30
        for i, c in enumerate(centroids):
            d = (rgb[0] - c[0]) ** 2 + (rgb[1] - c[1]) ** 2 + (rgb[2] - c[2]) ** 2
            if d < bd:
                best, bd = i, d
        lut[rgb] = best

    idmaps = {}
    for f in frames:
        buf = bytearray(f["im"].width * f["im"].height)
        for i, p in enumerate(f["im"].getdata()):
            if p[3] > 0:
                buf[i] = lut[(p[0], p[1], p[2])] + 1
        idmaps[f["lump"]] = bytes(buf)

    # Order clusters so a shading ramp reads as a ramp: hue first, then value.
    def key(c):
        r, g, b = [v / 255 for v in c]
        mx, mn = max(r, g, b), min(r, g, b)
        v = mx
        s = 0 if mx == 0 else (mx - mn) / mx
        if mx == mn:
            h = -1.0  # greys first, they are most of a Doom 64 gun
        elif mx == r:
            h = ((g - b) / (mx - mn)) % 6
        elif mx == g:
            h = (b - r) / (mx - mn) + 2
        else:
            h = (r - g) / (mx - mn) + 4
        return (round(h, 1), round(s, 1), v)

    order = sorted(range(len(centroids)), key=lambda i: key(centroids[i]))
    remap = {old: new for new, old in enumerate(order)}
    centroids = [centroids[i] for i in order]
    for lump, buf in idmaps.items():
        idmaps[lump] = bytes(0 if v == 0 else remap[v - 1] + 1 for v in buf)

    weights = Counter()
    for rgb, n in counts.items():
        weights[remap[lut[rgb]]] += n
    return centroids, idmaps, weights


def png_b64(im: Image.Image) -> str:
    buf = io.BytesIO()
    im.save(buf, "PNG", optimize=True)
    return base64.b64encode(buf.getvalue()).decode()


def idmap_b64(buf: bytes, w: int, h: int) -> str:
    im = Image.frombytes("L", (w, h), buf)
    out = io.BytesIO()
    im.save(out, "PNG", optimize=True)
    return base64.b64encode(out.getvalue()).decode()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cat", default="WEAPONS", help="sprite section, or ALL")
    ap.add_argument("--codes", default="", help="comma-separated 4-letter codes")
    ap.add_argument("--clusters", type=int, default=DEFAULT_CLUSTERS)
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    cat = None if args.cat.upper() == "ALL" else args.cat.upper()
    codes = {c.strip().upper() for c in args.codes.split(",") if c.strip()} or None

    by_code = collect(cat, codes)
    if not by_code:
        sys.exit(f"no sprites for cat={args.cat} codes={args.codes}")

    payload = []
    total_frames = 0
    for code in sorted(by_code):
        rec = by_code[code]
        rec["frames"].sort(key=lambda f: f["lump"])
        centroids, idmaps, weights = build_clusters(rec["frames"], args.clusters)
        if not centroids:
            continue
        frames = []
        for f in rec["frames"]:
            im = f["im"]
            frames.append(
                {
                    "lump": f["lump"],
                    "w": im.width,
                    "h": im.height,
                    "d": png_b64(im),
                    "i": idmap_b64(idmaps[f["lump"]], im.width, im.height),
                }
            )
        total_frames += len(frames)
        payload.append(
            {
                "code": code,
                "cat": rec["cat"],
                "clusters": [list(c) for c in centroids],
                "weights": [weights.get(i, 0) for i in range(len(centroids))],
                "frames": frames,
            }
        )

    OUTDIR.mkdir(parents=True, exist_ok=True)
    slug = (args.cat or "all").lower()
    out = Path(args.out) if args.out else OUTDIR / f"sprite_labeller_{slug}.html"
    html = render_html(payload, args.cat.upper(), total_frames)
    out.write_text(html, encoding="utf-8")
    size = out.stat().st_size / 1e6
    print(f"{out}  {size:.2f} MB")
    print(f"codes: {len(payload)}   frames: {total_frames}")
    if size > 15.0:
        print("WARNING: over 15 MB -- the artifact ceiling is 16 MB. Split the category.")


def render_html(payload, cat: str, total_frames: int) -> str:
    data = json.dumps(payload, separators=(",", ":"))
    surf = json.dumps(
        [{"name": n, "key": k, "m": m, "r": r, "c": c} for n, k, m, r, c in SURFACES],
        separators=(",", ":"),
    )
    rough = json.dumps(ROUGH_BUCKETS)
    ncodes = len(payload)
    # A name, not a caption: "Weapon sprite materials" sits in a gallery beside
    # the wall/flat labeller and has to be told apart from it at a glance.
    nice = {"WEAPONS": "Weapon", "MONSTERS": "Monster", "ITEMS": "Item",
            "POWERUPS": "Powerup", "EFFECTS": "Effect", "STATIC": "Scenery",
            "CASINGS": "Casing", "CLSANIMS": "Classic-anim", "ALL": "Every"}
    title = f"{nice.get(cat, cat.title())} sprite materials"
    return TEMPLATE.format(
        cat=cat, title=title, ncodes=ncodes, nframes=total_frames,
        data=data, surf=surf, rough=rough
    )


TEMPLATE = r"""<title>{title}</title>
<style>
:root {{
  --void:#0A0909; --panel:#141212; --edge:#2A2626; --edge2:#3A3434;
  --ink:#E8E4E0; --ink2:#A39C96; --ink3:#6E6862; --accent:#C8501E;
}}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--void); color:var(--ink);
  font:14px/1.5 ui-monospace,Consolas,"Cascadia Mono",monospace; }}
button:focus-visible, textarea:focus-visible {{ outline:2px solid var(--accent);
  outline-offset:1px; }}
header {{ padding:14px 18px; border-bottom:1px solid var(--edge); display:flex;
  gap:14px; align-items:baseline; flex-wrap:wrap; }}
header h1 {{ font-size:15px; margin:0; font-weight:600; letter-spacing:.02em; }}
header .sub {{ color:var(--ink3); font-size:12px; }}
.count {{ margin-left:auto; color:var(--ink2); font-size:12px;
  font-variant-numeric:tabular-nums; }}
main {{ display:grid; grid-template-columns:150px minmax(0,1fr) 300px; gap:0;
  height:calc(100vh - 52px); }}
@media (max-width:900px) {{ main {{ grid-template-columns:1fr; height:auto; }} }}
.codes {{ border-right:1px solid var(--edge); overflow-y:auto; }}
.codes button {{ display:block; width:100%; text-align:left; background:none;
  border:0; border-bottom:1px solid var(--edge); color:var(--ink2);
  padding:9px 12px; cursor:pointer; font:inherit; font-size:12.5px; }}
.codes button[aria-pressed="true"] {{ background:var(--panel); color:var(--ink);
  box-shadow:inset 2px 0 0 var(--accent); }}
.codes .done {{ color:#6E8F6E; }}
.stage {{ display:flex; flex-direction:column; min-width:0; }}
.canvaswrap {{ flex:1; display:grid; place-items:center; overflow:auto;
  background:#050505; padding:20px; }}
.stack {{ position:relative; line-height:0; }}
.stack canvas {{ display:block; image-rendering:pixelated;
  outline:1px solid #262626; outline-offset:3px; }}
#ov {{ position:absolute; inset:0; }}
.strip {{ display:flex; gap:6px; padding:9px 12px; overflow-x:auto;
  border-top:1px solid var(--edge); background:var(--panel); }}
.strip button {{ background:none; border:1px solid var(--edge2); border-radius:3px;
  color:var(--ink3); cursor:pointer; padding:4px 7px; font:inherit; font-size:11px;
  white-space:nowrap; }}
.strip button[aria-pressed="true"] {{ border-color:var(--accent); color:var(--ink); }}
.side {{ border-left:1px solid var(--edge); overflow-y:auto; padding:12px; }}
.side h2 {{ font-size:11px; letter-spacing:.13em; text-transform:uppercase;
  color:var(--ink3); margin:16px 0 8px; font-weight:500; }}
.side h2:first-child {{ margin-top:0; }}
.swatches {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(52px,1fr));
  gap:5px; }}
.sw {{ position:relative; aspect-ratio:1; border:1px solid var(--edge2);
  border-radius:3px; cursor:pointer; padding:0; }}
.sw[aria-pressed="true"] {{ outline:2px solid var(--accent); outline-offset:1px; }}
.sw .tag {{ position:absolute; left:0; right:0; bottom:0; font-size:9px;
  background:rgba(0,0,0,.72); color:#fff; text-align:center; padding:1px 0;
  border-radius:0 0 2px 2px; }}
.sw .pct {{ position:absolute; top:1px; right:2px; font-size:8px; color:#fff;
  text-shadow:0 0 3px #000; }}
.classes {{ display:grid; grid-template-columns:1fr 1fr; gap:5px; }}
.classes button, .roughs button {{ background:var(--panel); border:1px solid var(--edge2);
  border-radius:3px; color:var(--ink2); cursor:pointer; padding:6px 5px;
  font:inherit; font-size:11.5px; text-align:left; }}
.classes button b {{ color:var(--ink); font-weight:600; }}
.roughs {{ display:grid; grid-template-columns:repeat(3,1fr); gap:5px; }}
.roughs button[aria-pressed="true"] {{ border-color:var(--accent); color:var(--ink); }}
.tools {{ display:flex; gap:6px; flex-wrap:wrap; }}
.tools button {{ background:var(--panel); border:1px solid var(--edge2);
  border-radius:3px; color:var(--ink2); cursor:pointer; padding:6px 9px;
  font:inherit; font-size:11.5px; }}
.tools button[aria-pressed="true"] {{ border-color:var(--accent); color:var(--ink); }}
textarea {{ width:100%; height:110px; background:#060606; color:var(--ink2);
  border:1px solid var(--edge2); border-radius:3px; font:inherit; font-size:10.5px;
  padding:7px; resize:vertical; }}
.hint {{ color:var(--ink3); font-size:11px; line-height:1.5; }}
kbd {{ background:var(--panel); border:1px solid var(--edge2); border-radius:3px;
  padding:0 4px; font-size:10.5px; }}
</style>

<header>
  <h1>Sprite materials — {cat}</h1>
  <span class="sub">{ncodes} codes · {nframes} frames · label the colours, not the pixels</span>
  <span class="count" id="count"></span>
</header>

<main>
  <nav class="codes" id="codes"></nav>
  <section class="stage">
    <div class="canvaswrap"><div class="stack">
      <canvas id="cv"></canvas><canvas id="ov"></canvas>
    </div></div>
    <div class="strip" id="frames"></div>
  </section>
  <aside class="side">
    <h2>Clusters</h2>
    <div class="swatches" id="sw"></div>
    <h2>Call it</h2>
    <div class="classes" id="cls"></div>
    <h2>Roughness</h2>
    <div class="roughs" id="rgh"></div>
    <h2>View</h2>
    <div class="tools">
      <button id="tOverlay" aria-pressed="true">tint by class</button>
      <button id="tZoom">zoom +</button>
      <button id="tZoomOut">zoom −</button>
    </div>
    <h2>Export</h2>
    <div class="tools">
      <button id="bCopy">copy JSON</button>
      <button id="bImport">import from box</button>
    </div>
    <textarea id="io" spellcheck="false"></textarea>
    <p class="hint">
      Click a swatch, then press a class key. The call covers every frame and
      rotation of this code at once — mirrored rotations included, since the
      engine flips the material with the art.<br><br>
      <kbd>←</kbd><kbd>→</kbd> frame · <kbd>Tab</kbd> next unlabelled cluster ·
      <kbd>1</kbd>–<kbd>6</kbd> roughness · <kbd>X</kbd> park · <kbd>U</kbd> undo
    </p>
  </aside>
</main>

<script id="payload" type="application/json">{data}</script>
<script>
(function(){{
"use strict";
const DATA = JSON.parse(document.getElementById("payload").textContent);
const SURF = {surf};
const ROUGH = {rough};
const KEY = "d64rt-sprite-labels-v1";

const byKey = {{}}; SURF.forEach(s => byKey[s.key] = s);
const byName = {{}}; SURF.forEach(s => byName[s.name] = s);

// labels[code] = {{ cls:[clusterIdx]->name|null, rgh:[clusterIdx]->number|null }}
let labels = {{}};
try {{
  const raw = localStorage.getItem(KEY);
  if (raw !== null) labels = JSON.parse(raw) || {{}};
}} catch (e) {{ labels = {{}}; }}

let ci = 0, fi = 0, sel = 0, zoom = 4, overlay = true;
const undo = [];
const imgs = new Map(), ids = new Map();

const $ = id => document.getElementById(id);
const cv = $("cv"), ov = $("ov");
const ctx = cv.getContext("2d"), octx = ov.getContext("2d", {{ willReadFrequently:false }});

function rec()  {{ return DATA[ci]; }}
function frame(){{ return rec().frames[fi]; }}
function lab()  {{
  const c = rec().code;
  if (!labels[c]) labels[c] = {{ cls:[], rgh:[] }};
  return labels[c];
}}
function save() {{ try {{ localStorage.setItem(KEY, JSON.stringify(labels)); }} catch(e){{}} }}

function load(f) {{
  if (imgs.has(f.lump)) return Promise.resolve();
  const a = new Image(), b = new Image();
  a.src = "data:image/png;base64," + f.d;
  b.src = "data:image/png;base64," + f.i;
  return Promise.all([a.decode(), b.decode()]).then(() => {{
    imgs.set(f.lump, a);
    // The id map is read back as pixels: R holds cluster+1, 0 = transparent.
    const c = document.createElement("canvas");
    c.width = f.w; c.height = f.h;
    c.getContext("2d", {{ willReadFrequently:true }}).drawImage(b, 0, 0);
    ids.set(f.lump, c.getContext("2d").getImageData(0, 0, f.w, f.h).data);
  }});
}}

function draw() {{
  const f = frame();
  load(f).then(() => {{
    const w = f.w * zoom, h = f.h * zoom;
    cv.width = w; cv.height = h; ov.width = w; ov.height = h;
    ctx.imageSmoothingEnabled = false;
    ctx.clearRect(0, 0, w, h);
    ctx.drawImage(imgs.get(f.lump), 0, 0, w, h);
    drawOverlay();
    paintUI();
  }});
}}

function drawOverlay() {{
  const f = frame(), w = f.w * zoom, h = f.h * zoom;
  octx.clearRect(0, 0, w, h);
  const map = ids.get(f.lump);
  if (!map) return;
  const L = lab();
  for (let y = 0; y < f.h; y++) {{
    for (let x = 0; x < f.w; x++) {{
      const v = map[(y * f.w + x) * 4];
      if (v === 0) continue;
      const k = v - 1;
      let fill = null;
      if (k === sel) fill = "rgba(200,80,30,.55)";
      else if (overlay && L.cls[k]) fill = hexA(byName[L.cls[k]].c, .34);
      if (!fill) continue;
      octx.fillStyle = fill;
      octx.fillRect(x * zoom, y * zoom, zoom, zoom);
    }}
  }}
}}

function hexA(hex, a) {{
  const n = parseInt(hex.slice(1), 16);
  return "rgba(" + (n >> 16) + "," + ((n >> 8) & 255) + "," + (n & 255) + "," + a + ")";
}}

function paintUI() {{
  const r = rec(), L = lab();

  $("codes").innerHTML = "";
  DATA.forEach((d, i) => {{
    const b = document.createElement("button");
    const done = labelled(d.code) === d.clusters.length;
    b.textContent = d.code + "  " + labelled(d.code) + "/" + d.clusters.length;
    b.setAttribute("aria-pressed", i === ci ? "true" : "false");
    if (done) b.className = "done";
    b.onclick = () => {{ ci = i; fi = 0; sel = 0; draw(); }};
    $("codes").appendChild(b);
  }});

  $("frames").innerHTML = "";
  r.frames.forEach((f, i) => {{
    const b = document.createElement("button");
    b.textContent = f.lump;
    b.setAttribute("aria-pressed", i === fi ? "true" : "false");
    b.onclick = () => {{ fi = i; draw(); }};
    $("frames").appendChild(b);
  }});

  const total = r.clusters.reduce((a, b) => a + b, 0) || 1;
  $("sw").innerHTML = "";
  r.clusters.forEach((c, i) => {{
    const b = document.createElement("button");
    b.className = "sw";
    b.style.background = "rgb(" + c[0] + "," + c[1] + "," + c[2] + ")";
    b.setAttribute("aria-pressed", i === sel ? "true" : "false");
    const pct = Math.round((r.weights[i] / (r.weights.reduce((a,x)=>a+x,0)||1)) * 100);
    b.innerHTML = '<span class="pct">' + (pct >= 1 ? pct + "%" : "") + "</span>" +
      (L.cls[i] ? '<span class="tag">' + L.cls[i].slice(0, 5) + "</span>" : "");
    b.onclick = () => {{ sel = i; drawOverlay(); paintUI(); }};
    $("sw").appendChild(b);
  }});

  $("cls").innerHTML = "";
  SURF.forEach(s => {{
    const b = document.createElement("button");
    b.innerHTML = "<b>" + s.key + "</b> " + s.name;
    b.style.borderColor = L.cls[sel] === s.name ? s.c : "";
    b.onclick = () => call(s.name);
    $("cls").appendChild(b);
  }});

  $("rgh").innerHTML = "";
  ROUGH.forEach((v, i) => {{
    const b = document.createElement("button");
    b.textContent = (i + 1) + " · " + v.toFixed(2);
    const cur = L.rgh[sel] !== undefined && L.rgh[sel] !== null
      ? L.rgh[sel] : (L.cls[sel] ? byName[L.cls[sel]].r : null);
    b.setAttribute("aria-pressed", cur === v ? "true" : "false");
    b.onclick = () => {{ L.rgh[sel] = v; save(); paintUI(); }};
    $("rgh").appendChild(b);
  }});

  let done = 0, all = 0;
  DATA.forEach(d => {{ all += d.clusters.length; done += labelled(d.code); }});
  $("count").textContent = labelled(r.code) + " of " + r.clusters.length + " in " +
    r.code + " · " + done + " of " + all + " overall";
}}

function labelled(code) {{
  const L = labels[code];
  if (!L || !L.cls) return 0;
  return L.cls.filter(Boolean).length;
}}

function call(name) {{
  const L = lab();
  undo.push({{ code: rec().code, i: sel, was: L.cls[sel], wasR: L.rgh[sel] }});
  L.cls[sel] = name;
  if (L.rgh[sel] === undefined || L.rgh[sel] === null) L.rgh[sel] = byName[name].r;
  save();
  nextUnlabelled();
  drawOverlay();
  paintUI();
}}

function nextUnlabelled() {{
  const L = lab(), n = rec().clusters.length;
  for (let d = 1; d <= n; d++) {{
    const k = (sel + d) % n;
    if (!L.cls[k]) {{ sel = k; return; }}
  }}
}}

document.addEventListener("keydown", e => {{
  if (e.target.tagName === "TEXTAREA") return;
  const k = e.key.toUpperCase();
  if (byKey[k]) {{ e.preventDefault(); call(byKey[k].name); return; }}
  if (k >= "1" && k <= String(ROUGH.length)) {{
    lab().rgh[sel] = ROUGH[+k - 1]; save(); paintUI(); return;
  }}
  if (k === "X") {{ call("other"); return; }}
  if (k === "U") {{
    const u = undo.pop();
    if (u) {{
      if (!labels[u.code]) labels[u.code] = {{ cls:[], rgh:[] }};
      labels[u.code].cls[u.i] = u.was;
      labels[u.code].rgh[u.i] = u.wasR;
      save(); drawOverlay(); paintUI();
    }}
    return;
  }}
  if (e.key === "ArrowRight") {{ fi = (fi + 1) % rec().frames.length; draw(); }}
  if (e.key === "ArrowLeft")  {{ fi = (fi - 1 + rec().frames.length) % rec().frames.length; draw(); }}
  if (e.key === "Tab") {{ e.preventDefault(); nextUnlabelled(); drawOverlay(); paintUI(); }}
}});

// Clicking the sprite selects whichever cluster that pixel belongs to -- the
// "point at the barrel" gesture, without a brush.
ov.onclick = e => {{
  const f = frame(), r = ov.getBoundingClientRect();
  const x = Math.floor((e.clientX - r.left) / zoom);
  const y = Math.floor((e.clientY - r.top) / zoom);
  const map = ids.get(f.lump);
  if (!map || x < 0 || y < 0 || x >= f.w || y >= f.h) return;
  const v = map[(y * f.w + x) * 4];
  if (v === 0) return;
  sel = v - 1; drawOverlay(); paintUI();
}};

$("tOverlay").onclick = () => {{
  overlay = !overlay;
  $("tOverlay").setAttribute("aria-pressed", overlay ? "true" : "false");
  drawOverlay();
}};
$("tZoom").onclick    = () => {{ zoom = Math.min(12, zoom + 1); draw(); }};
$("tZoomOut").onclick = () => {{ zoom = Math.max(1, zoom - 1); draw(); }};

function exportObj() {{
  const out = {{ version: 1, codes: {{}} }};
  let n = 0;
  DATA.forEach(d => {{
    const L = labels[d.code];
    if (!L || !L.cls || !L.cls.filter(Boolean).length) return;
    const cl = d.clusters.map((c, i) => {{
      if (!L.cls[i]) return null;
      const s = byName[L.cls[i]];
      return {{
        rgb: c,
        surface: L.cls[i],
        metallicDefault: s.m,
        roughnessDefault: (L.rgh[i] === undefined || L.rgh[i] === null) ? s.r : L.rgh[i]
      }};
    }});
    out.codes[d.code] = {{ clusters: cl, frames: d.frames.map(f => f.lump) }};
    n += cl.filter(Boolean).length;
  }});
  out.__meta = {{ scope: "{cat}", clusters_labelled: n }};
  return out;
}}

$("bCopy").onclick = () => {{
  const t = JSON.stringify(exportObj(), null, 1);
  $("io").value = t;
  $("io").select();
  if (navigator.clipboard) navigator.clipboard.writeText(t).catch(() => {{}});
}};

$("bImport").onclick = () => {{
  let o;
  try {{ o = JSON.parse($("io").value); }} catch (e) {{ alert("not JSON"); return; }}
  Object.entries(o.codes || {{}}).forEach(([code, v]) => {{
    const L = labels[code] || (labels[code] = {{ cls:[], rgh:[] }});
    (v.clusters || []).forEach((c, i) => {{
      if (!c) return;
      L.cls[i] = c.surface;
      L.rgh[i] = c.roughnessDefault;
    }});
  }});
  save(); draw();
}};

draw();
}})();
</script>
"""


if __name__ == "__main__":
    main()
