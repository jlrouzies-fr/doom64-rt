"""
Export every sprite frame used in Doom 64: Retribution as a single browsable
HTML page (pixels decoded straight out of the WAD). Sibling to
export_all_textures_gallery.py, same page shape, sprite domain instead of
wall/flat textures.

Sprite lumps sit between SS_START/SS_END. Most are PNG lumps named with the
classic Doom convention: 4-char sprite code + frame letter + rotation digit,
optionally + a second frame+rotation pair when one image is shared (mirrored)
between two rotations, e.g. TROOA2A8 = frame A, rotation 2 as-is and rotation
8 as a horizontal flip of the same pixels. A handful of effect sprites
(spent shell casings) are stored in the older raw column-post picture format
instead of PNG; this WAD carries no PLAYPAL, so those are decoded and shown
as an index-value grayscale approximation, clearly labeled as such.

Zero-length lumps inside the sprite range are the pack's own section
dividers (WEAPONS, MONSTERS, ITEMS, ...) - reused here as the category filter.

Usage:  py -3 tools\\export_all_sprites_gallery.py
Output: tools\\_gallery\\all_sprites_export.html
        tools\\_gallery\\all_sprites_export.json
"""
from __future__ import annotations

import base64
import io
import json
import re
import struct
from pathlib import Path

from PIL import Image

ROOT = Path(r"G:\ai\Doom64-RT")
WAD = ROOT / r"Doom64-Retribution\D64RTR_v15.WAD"
OUT_HTML = ROOT / r"tools\_gallery\all_sprites_export.html"
OUT_JSON = ROOT / r"tools\_gallery\all_sprites_export.json"

MAX_PX = 168
NAME_RE = re.compile(r"^([A-Z0-9]{4})([A-Z\[\\\]])([0-8])(?:([A-Z\[\\\]])([0-8]))?$")


def read_lumps() -> list[tuple[str, int, int]]:
    d = WAD.read_bytes()
    n, o = struct.unpack_from("<II", d, 4)
    lumps = []
    for i in range(n):
        off, sz, name = struct.unpack_from("<II8s", d, o + i * 16)
        nm = name.split(b"\0")[0].decode("ascii", "replace")
        lumps.append((nm, off, sz))
    return lumps


def decode_doompic_grayscale(raw: bytes) -> Image.Image | None:
    """Classic column-post picture format. No PLAYPAL in this WAD, so pixel
    indices are rendered as a grayscale ramp -- shape-accurate, color-approx."""
    if len(raw) < 8:
        return None
    w, h, leftoff, topoff = struct.unpack_from("<hhhh", raw, 0)
    if w <= 0 or h <= 0 or w > 4096 or h > 4096:
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
            pos += 3  # topdelta, length, unused
            for j in range(length):
                if pos + j >= len(raw):
                    break
                idx = raw[pos + j]
                y = topdelta + j
                if 0 <= y < h:
                    g = idx  # index-as-grayscale approximation (no PLAYPAL)
                    px[x, y] = (g, g, g, 255)
            pos += length + 1  # data + trailing unused
    return canvas


def render_sprite(raw: bytes) -> tuple[bytes, int, int, str] | None:
    if raw.startswith(b"\x89PNG"):
        try:
            im = Image.open(io.BytesIO(raw))
            w, h = im.size
        except Exception:
            return None
        return raw, w, h, "png"
    im = decode_doompic_grayscale(raw)
    if im is None:
        return None
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue(), im.width, im.height, "doompic"


def main() -> None:
    data = WAD.read_bytes()
    lumps = read_lumps()
    names = [nm for nm, _, _ in lumps]
    s0, s1 = names.index("SS_START"), names.index("SS_END")
    section = lumps[s0 + 1 : s1]
    print(f"sprite-range lumps: {len(section)}")

    category = "UNCATEGORIZED"
    records = []
    skipped = []
    for nm, off, sz in section:
        if sz == 0:
            category = nm
            continue
        m = NAME_RE.match(nm)
        if not m:
            skipped.append(nm)
            continue
        code, f1, r1, f2, r2 = m.groups()
        raw = data[off : off + sz]
        result = render_sprite(raw)
        if result is None:
            skipped.append(nm)
            continue
        png_bytes, w, h, fmt = result
        b64 = base64.b64encode(png_bytes).decode("ascii")
        records.append(
            {
                "lump": nm, "category": category, "code": code,
                "frame": f1, "rot": r1, "mirror_of": None,
                "w": w, "h": h, "format": fmt, "png_b64": b64,
            }
        )
        if f2 is not None:
            flipped = Image.open(io.BytesIO(png_bytes)).transpose(Image.FLIP_LEFT_RIGHT)
            fb = io.BytesIO()
            flipped.save(fb, "PNG")
            records.append(
                {
                    "lump": nm, "category": category, "code": code,
                    "frame": f2, "rot": r2, "mirror_of": f"{f1}{r1}",
                    "w": w, "h": h, "format": fmt,
                    "png_b64": base64.b64encode(fb.getvalue()).decode("ascii"),
                }
            )

    print(f"rendered records: {len(records)}  (incl. mirrored rotations)")
    print(f"unrecognized/unrendered lumps: {len(skipped)}")
    if skipped:
        print("  sample:", skipped[:20])

    frame_counts: dict[str, int] = {}
    for r in records:
        frame_counts[r["code"]] = frame_counts.get(r["code"], 0) + 1
    for r in records:
        r["code_frames"] = frame_counts[r["code"]]

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(
        json.dumps(
            {
                "generated_from": str(WAD),
                "count": len(records),
                "sprites": [{k: v for k, v in r.items() if k != "png_b64"} for r in records],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    write_html(records)
    print("wrote", OUT_HTML)


def write_html(records: list[dict]) -> None:
    categories = sorted({r["category"] for r in records})
    cat_options = "".join(f'<option value="{c}">{c.title()}</option>' for c in categories)

    figs = []
    for r in records:
        w, h = r["w"], r["h"]
        scale = MAX_PX / max(w, h) if max(w, h) > 0 else 1
        dw, dh = max(1, round(w * scale)), max(1, round(h * scale))
        label = f'{r["frame"]}{r["rot"]}'
        sub = f'mirror of {r["mirror_of"]}' if r["mirror_of"] else r["lump"]
        approx = '<p class="note">raw picture format, no PLAYPAL in this WAD &mdash; indices shown as grayscale</p>' if r["format"] == "doompic" else ""
        figs.append(
            f'''<figure class="tx" data-code="{r["code"]}" data-cat="{r["category"]}" data-name="{r["code"]}{label}" data-frames="{r["code_frames"]}">
  <div class="px"><img style="--w:{dw}px;--h:{dh}px" src="data:image/png;base64,{r["png_b64"]}" alt="{r["code"]}{label}" loading="lazy" width="{dw}" height="{dh}"></div>
  <figcaption>
    <div class="hd"><b>{r["code"]}</b><span class="maps"><span class="m">{r["category"]}</span></span></div>
    <dl>
      <div><dt>frame</dt><dd class="n">{label}</dd></div>
      <div><dt>frames</dt><dd class="n">{r["code_frames"]}</dd></div>
      <div><dt>px</dt><dd class="n">{w}&times;{h}</dd></div>
    </dl>
    <p class="meta">{sub}</p>
    {approx}
  </figcaption>
</figure>'''
        )

    codes = sorted({r["code"] for r in records})
    total = len(records)

    html = f'''<title>Every sprite in Doom 64: Retribution</title>
<style>
:root {{
  --paper:#E9ECEF; --card:#F7F8FA; --edge:#C6CDD4; --edge-soft:#DCE2E7;
  --ink:#131A20; --ink-2:#495660; --ink-3:#6B7883;
  --lamp-line:#7A3FB0; --lamp-ink:#5C2C87; --lamp-bg:#E9DCF4;
  --well:#171D23; --field:#FFFFFF;
}}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{
    --paper:#0E1317; --card:#171E24; --edge:#2C363E; --edge-soft:#232C33;
    --ink:#E4EAEF; --ink-2:#9DAAB4; --ink-3:#75838D;
    --lamp-line:#8C6AC2; --lamp-ink:#CBAAF0; --lamp-bg:#251A33;
    --well:#080B0E; --field:#0C1115;
  }}
}}
:root[data-theme="dark"] {{
  --paper:#0E1317; --card:#171E24; --edge:#2C363E; --edge-soft:#232C33;
  --ink:#E4EAEF; --ink-2:#9DAAB4; --ink-3:#75838D;
  --lamp-line:#8C6AC2; --lamp-ink:#CBAAF0; --lamp-bg:#251A33;
  --well:#080B0E; --field:#0C1115;
}}
* {{ box-sizing:border-box; }}
body {{
  background:var(--paper); color:var(--ink);
  font:16px/1.6 system-ui,-apple-system,"Segoe UI",sans-serif;
  margin:0; padding:clamp(18px,3.4vw,44px);
}}
.wrap {{ max-width:1320px; margin:0 auto; display:flex; flex-direction:column; gap:28px; }}
.mono, code, dl, .hd b, h1, .eyebrow, .band h2, button, input, select, .m
  {{ font-family:ui-monospace,"Cascadia Mono",Consolas,"SF Mono",monospace; }}
code {{ font-size:.88em; background:var(--edge-soft); padding:.1em .34em; border-radius:3px; }}

header {{ display:flex; flex-direction:column; gap:13px; max-width:70ch; }}
.eyebrow {{ font-size:12px; letter-spacing:.14em; text-transform:uppercase; color:var(--ink-3); }}
h1 {{ font-weight:600; font-size:clamp(23px,3.2vw,32px); line-height:1.22;
  letter-spacing:-.01em; text-wrap:balance; margin:0; }}
header p {{ margin:0; color:var(--ink-2); }}

.bar {{ position:sticky; top:0; z-index:5; background:var(--paper);
  border-bottom:1px solid var(--edge); padding:12px 0;
  display:flex; gap:10px; align-items:center; flex-wrap:wrap; }}
.bar input, .bar select {{ background:var(--field); color:var(--ink); border:1px solid var(--edge);
  border-radius:4px; padding:7px 10px; font-size:13.5px; min-width:120px; }}
.grp {{ display:flex; border:1px solid var(--edge); border-radius:4px; overflow:hidden; }}
.grp button {{ background:var(--card); color:var(--ink-2); border:0; cursor:pointer;
  padding:7px 12px; font-size:12.5px; letter-spacing:.03em; }}
.grp button + button {{ border-left:1px solid var(--edge); }}
.grp button[aria-pressed="true"] {{ background:var(--lamp-bg); color:var(--lamp-ink); }}
button:focus-visible, input:focus-visible, select:focus-visible {{ outline:2px solid var(--lamp-line); outline-offset:1px; }}
.count {{ color:var(--ink-3); font-size:13px; margin-left:auto; font-variant-numeric:tabular-nums; }}

.grid {{ display:grid; gap:14px; grid-template-columns:repeat(auto-fill,minmax(190px,1fr)); }}
.tx {{ margin:0; background:var(--card); border:1px solid var(--edge); border-radius:5px;
  overflow:hidden; display:flex; flex-direction:column; }}
.tx.matched {{ border-color:var(--lamp-line); }}
.tx[hidden] {{ display:none; }}
.px {{ background:var(--well); display:grid; place-items:center; padding:16px 0;
  border-bottom:1px solid var(--edge-soft); }}
.px img {{ width:var(--w); height:var(--h); image-rendering:pixelated; display:block;
  outline:1px solid rgba(140,150,160,.35); outline-offset:2px; }}
figcaption {{ padding:11px 13px 13px; display:flex; flex-direction:column; gap:7px; }}
.hd {{ display:flex; align-items:center; justify-content:space-between; gap:8px; }}
.hd b {{ font-size:13.5px; letter-spacing:.02em; }}
.maps {{ display:flex; gap:3px; flex-wrap:wrap; justify-content:flex-end; }}
.m {{ font-size:10px; letter-spacing:.06em; padding:2px 5px; border-radius:3px;
  background:var(--edge-soft); color:var(--ink-3); }}
dl {{ margin:0; display:flex; gap:13px; font-size:11.5px; flex-wrap:wrap; }}
dl div {{ display:flex; gap:5px; }}
dt {{ color:var(--ink-3); margin:0; }}
dd {{ margin:0; color:var(--ink); }}
.n {{ font-variant-numeric:tabular-nums; }}
.meta {{ margin:0; font-size:12px; color:var(--ink-2); }}
.note {{ margin:0; font-size:11.5px; color:var(--ink-3); }}
footer {{ color:var(--ink-3); font-size:13.5px; border-top:1px solid var(--edge);
  padding-top:16px; max-width:74ch; }}
</style>

<div class="wrap">
<header>
  <div class="eyebrow">{len(codes)} sprite codes &middot; D64RTR_v15.WAD</div>
  <h1>Every sprite frame the game uses</h1>
  <p>All {total} of them, pixels decoded straight out of the <span class="mono">SS_START..SS_END</span>
  range &mdash; PNG lumps read as-is; the mirrored half of a rotation pair (the WAD stores one image
  for e.g. rotations 2 and 8) is generated here as a horizontal flip of its twin, same as the engine
  does at render time. A few effect sprites (spent shell casings) are the older raw column-post picture
  format; this WAD ships no <span class="mono">PLAYPAL</span>, so those render as a grayscale
  approximation of their palette indices &mdash; flagged on the card.</p>
  <p>Categories are the pack's own section dividers inside the sprite range
  (<span class="mono">WEAPONS</span>, <span class="mono">MONSTERS</span>, ...), reused here as the
  filter. <b>frames</b> is how many frames that 4-letter sprite code has in total.</p>
</header>

<div class="bar">
  <input id="q" type="search" placeholder="filter by code&hellip;" aria-label="Filter by code">
  <select id="catSel" aria-label="Category">
    <option value="all">all categories</option>
    {cat_options}
  </select>
  <div class="grp" role="group" aria-label="Sort">
    <button data-sort="grouped" aria-pressed="true">grouped</button>
    <button data-sort="name" aria-pressed="false">A&ndash;Z</button>
    <button data-sort="frames" aria-pressed="false">most frames</button>
  </div>
  <span class="count" id="count"></span>
</div>

<div class="grid" id="grid">
{"".join(figs)}
</div>

<footer>
  Generated by <code>tools/export_all_sprites_gallery.py</code> from <code>D64RTR_v15.WAD</code>.
</footer>
</div>

<script>
(function() {{
  const grid = document.getElementById('grid');
  const items = Array.from(grid.querySelectorAll('.tx'));
  const order = items.map((it, i) => i);
  const q = document.getElementById('q');
  const catSel = document.getElementById('catSel');
  const sortGrp = document.querySelector('.grp[aria-label="Sort"]');
  const countEl = document.getElementById('count');
  let sortKey = 'grouped';

  function apply() {{
    const term = q.value.trim().toUpperCase();
    const cat = catSel.value;
    let visible = 0;
    items.forEach((it, i) => {{
      const nameOk = !term || it.dataset.name.includes(term) || it.dataset.code.includes(term);
      const catOk = cat === 'all' || it.dataset.cat === cat;
      const show = nameOk && catOk;
      it.hidden = !show;
      if (show) visible++;
    }});
    const shown = items.filter(it => !it.hidden);
    shown.sort((a, b) => {{
      if (sortKey === 'name') return a.dataset.name.localeCompare(b.dataset.name);
      if (sortKey === 'frames') {{
        const d = (+b.dataset.frames) - (+a.dataset.frames);
        return d !== 0 ? d : a.dataset.name.localeCompare(b.dataset.name);
      }}
      return order[items.indexOf(a)] - order[items.indexOf(b)];
    }});
    shown.forEach(it => grid.appendChild(it));
    countEl.textContent = visible + ' / ' + items.length;
  }}

  q.addEventListener('input', apply);
  catSel.addEventListener('change', apply);
  sortGrp.addEventListener('click', e => {{
    const btn = e.target.closest('button[data-sort]');
    if (!btn) return;
    sortGrp.querySelectorAll('button').forEach(b => b.setAttribute('aria-pressed', 'false'));
    btn.setAttribute('aria-pressed', 'true');
    sortKey = btn.dataset.sort;
    apply();
  }});
  apply();
}})();
</script>
'''
    OUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    OUT_HTML.write_text(html, encoding="utf-8")


if __name__ == "__main__":
    main()
