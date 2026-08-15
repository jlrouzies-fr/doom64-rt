"""
Export every wall/flat texture used across ALL Doom 64: Retribution maps as a
single browsable HTML page (pixels decoded straight out of the WAD, composite
textures rendered from their TEXTURES-lump patch definitions).

This is the "all levels" follow-up to the earlier MAP01-03 export: same idea,
scanned over every MAPxx in D64RTR_v15.WAD instead of three.

Usage:  py -3 tools\\export_all_textures_gallery.py
Output: tools\\_gallery\\all_maps_texture_export.html
        tools\\_gallery\\all_maps_texture_export.json   (raw data, for reuse)
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

# Repo root, derived from this file so a clone can live anywhere.
PROJ_ROOT = Path(__file__).resolve().parents[1]

ROOT = PROJ_ROOT
WAD = ROOT / r"Doom64-Retribution\D64RTR_v15.WAD"
OUT_HTML = ROOT / r"tools\_gallery\all_maps_texture_export.html"
OUT_JSON = ROOT / r"tools\_gallery\all_maps_texture_export.json"

SKIP_NAMES = {"-", "", "F_SKY1", "P_SKY1"}
MAX_PX = 168  # matches the MAP01-03 export's preview scale


# ---------------------------------------------------------------- WAD lumps

def read_lumps() -> list[tuple[str, int, int]]:
    d = WAD.read_bytes()
    n, o = struct.unpack_from("<II", d, 4)
    lumps = []
    for i in range(n):
        off, sz, name = struct.unpack_from("<II8s", d, o + i * 16)
        nm = name.split(b"\0")[0].decode("ascii", "replace")
        lumps.append((nm, off, sz))
    return lumps


def build_lump_bytes(data: bytes, lumps: list[tuple[str, int, int]]) -> dict[str, bytes]:
    out: dict[str, bytes] = {}
    for nm, off, sz in lumps:
        out[nm] = data[off : off + sz]  # later entries override earlier (WAD semantics)
    return out


# ------------------------------------------------------------ TEXTURES lump

def strip_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    text = re.sub(r"//[^\n]*", "", text)
    return text


def parse_textures(text: str) -> dict[str, dict]:
    text = strip_comments(text)
    defs: dict[str, dict] = {}
    for m in re.finditer(
        r"\bTexture\s+([A-Za-z0-9_]+)\s*,\s*(\d+)\s*,\s*(\d+)", text
    ):
        name, w, h = m.group(1), int(m.group(2)), int(m.group(3))
        brace = text.find("{", m.end())
        if brace < 0:
            continue
        depth = 0
        i = brace
        end = -1
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
        body = text[brace + 1 : end]
        patches = []
        for pm in re.finditer(
            r"Patch\s+([A-Za-z0-9_]+)\s*,\s*(-?\d+)\s*,\s*(-?\d+)\s*(\{[^}]*\})?",
            body,
        ):
            pname, px, py, flagblock = pm.group(1), int(pm.group(2)), int(pm.group(3)), pm.group(4)
            flags: dict = {}
            if flagblock:
                if re.search(r"\bFlipX\b", flagblock):
                    flags["flipx"] = True
                if re.search(r"\bFlipY\b", flagblock):
                    flags["flipy"] = True
                rm = re.search(r"\bRotate\s+(-?\d+)", flagblock)
                if rm:
                    flags["rotate"] = int(rm.group(1))
            patches.append({"name": pname, "x": px, "y": py, "flags": flags})
        defs[name] = {"width": w, "height": h, "patches": patches}
    return defs


# ------------------------------------------------------------------ TEXTMAP

BLOCK_RE = re.compile(r"([A-Za-z]+)\s*\{([^{}]*)\}", re.S)
FIELD_RE = re.compile(r"([A-Za-z0-9_]+)\s*=\s*(\"(?:[^\"\\]|\\.)*\"|[-+]?[0-9.]+|true|false)\s*;")


def parse_fields(body: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for fm in FIELD_RE.finditer(body):
        k, v = fm.group(1), fm.group(2)
        if v.startswith('"'):
            v = v[1:-1]
        out[k] = v
    return out


def parse_map(textmap_text: str) -> tuple[list[dict], list[dict]]:
    """Returns (sectors, sidedefs) in declaration order."""
    sectors: list[dict] = []
    sidedefs: list[dict] = []
    for bm in BLOCK_RE.finditer(textmap_text):
        kind = bm.group(1).lower()
        if kind not in ("sector", "sidedef"):
            continue
        fields = parse_fields(bm.group(2))
        if kind == "sector":
            sectors.append(fields)
        else:
            sidedefs.append(fields)
    return sectors, sidedefs


# --------------------------------------------------------------- rendering

def render_texture(name: str, tex_defs: dict[str, dict], lumps: dict[str, bytes]) -> tuple[bytes, int, int] | None:
    if name in tex_defs:
        d = tex_defs[name]
        w, h = d["width"], d["height"]
        canvas = Image.new("RGBA", (max(w, 1), max(h, 1)), (0, 0, 0, 0))
        for p in d["patches"]:
            raw = lumps.get(p["name"])
            if not raw or not raw.startswith(b"\x89PNG"):
                continue
            try:
                pim = Image.open(io.BytesIO(raw)).convert("RGBA")
            except Exception:
                continue
            if p["flags"].get("flipx"):
                pim = pim.transpose(Image.FLIP_LEFT_RIGHT)
            if p["flags"].get("flipy"):
                pim = pim.transpose(Image.FLIP_TOP_BOTTOM)
            rot = p["flags"].get("rotate")
            if rot:
                pim = pim.rotate(-rot, expand=True)
            canvas.paste(pim, (p["x"], p["y"]), pim)
        buf = io.BytesIO()
        canvas.save(buf, "PNG")
        return buf.getvalue(), w, h

    raw = lumps.get(name)
    if raw and raw.startswith(b"\x89PNG"):
        try:
            im = Image.open(io.BytesIO(raw))
            w, h = im.size
        except Exception:
            return None
        return raw, w, h

    return None


# --------------------------------------------------------------------- main

def main() -> None:
    data = WAD.read_bytes()
    lump_list = read_lumps()
    lumps = build_lump_bytes(data, lump_list)

    textures_text = lumps.get("TEXTURES", b"").decode("utf-8", "replace")
    tex_defs = parse_textures(textures_text)
    print(f"composite texture defs: {len(tex_defs)}")

    # Split into MAPxx blocks
    maps: list[tuple[str, list[tuple[str, int, int]]]] = []
    i = 0
    while i < len(lump_list):
        nm = lump_list[i][0]
        if re.fullmatch(r"MAP\d+", nm):
            block = [lump_list[i]]
            j = i + 1
            while j < len(lump_list) and not re.fullmatch(r"MAP\d+", lump_list[j][0]):
                block.append(lump_list[j])
                j += 1
            maps.append((nm, block))
            i = j
        else:
            i += 1
    print(f"maps found: {len(maps)}")

    # texture usage aggregation
    usage: dict[str, dict] = defaultdict(
        lambda: {"per_map": defaultdict(int), "placements": set(), "light_min": None, "light_max": None}
    )

    for mname, block in maps:
        textmap_bytes = None
        for nm, off, sz in block:
            if nm == "TEXTMAP":
                textmap_bytes = data[off : off + sz]
                break
        if textmap_bytes is None:
            continue
        text = textmap_bytes.decode("utf-8", "replace")
        sectors, sidedefs = parse_map(text)

        def sector_light(idx_str: str | None) -> int:
            try:
                idx = int(idx_str)
            except (TypeError, ValueError):
                return 160
            if 0 <= idx < len(sectors):
                try:
                    return int(float(sectors[idx].get("lightlevel", "160")))
                except ValueError:
                    return 160
            return 160

        def record(name: str, placement: str, light: int) -> None:
            if name in SKIP_NAMES:
                return
            u = usage[name]
            u["per_map"][mname] += 1
            u["placements"].add(placement)
            if u["light_min"] is None or light < u["light_min"]:
                u["light_min"] = light
            if u["light_max"] is None or light > u["light_max"]:
                u["light_max"] = light

        for sd in sidedefs:
            light = sector_light(sd.get("sector"))
            for field, placement in (
                ("texturetop", "top"),
                ("texturemiddle", "mid"),
                ("texturebottom", "bot"),
            ):
                name = sd.get(field, "-")
                if name not in SKIP_NAMES:
                    record(name, placement, light)

        for sec in sectors:
            try:
                slight = int(float(sec.get("lightlevel", "160")))
            except ValueError:
                slight = 160
            for field, placement in (("texturefloor", "flr"), ("textureceiling", "ceil")):
                name = sec.get(field, "-")
                if name not in SKIP_NAMES:
                    record(name, placement, slight)

    print(f"unique textures across all maps: {len(usage)}")

    # render + assemble records
    records = []
    missing = []
    for name in sorted(usage.keys()):
        u = usage[name]
        result = render_texture(name, tex_defs, lumps)
        if result is None:
            missing.append(name)
            continue
        png_bytes, w, h = result
        b64 = base64.b64encode(png_bytes).decode("ascii")
        per_map = dict(u["per_map"])
        game_uses = sum(per_map.values())
        composite = tex_defs.get(name)
        records.append(
            {
                "name": name,
                "w": w,
                "h": h,
                "uses": game_uses,
                "maps": sorted(per_map.keys(), key=lambda m: int(m[3:])),
                "per_map": per_map,
                "placements": sorted(u["placements"]),
                "light_min": u["light_min"],
                "light_max": u["light_max"],
                "composite_of": [p["name"] for p in composite["patches"]] if composite else None,
                "png_b64": b64,
            }
        )

    print(f"rendered: {len(records)}  missing pixels: {len(missing)}")
    if missing:
        print("  missing sample:", missing[:20])

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(
        json.dumps(
            {
                "generated_from": str(WAD),
                "map_count": len(maps),
                "texture_count": len(records),
                "textures": [{k: v for k, v in r.items() if k != "png_b64"} for r in records],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    write_html(records, [m for m, _ in maps])
    print("wrote", OUT_HTML)


MAP_TITLES = {
    "MAP00": "Hub / Tutorial",
}


def write_html(records: list[dict], map_names: list[str]) -> None:
    map_options = "".join(
        f'<option value="{m}">{m}</option>' for m in sorted(map_names, key=lambda m: int(m[3:]))
    )

    figs = []
    for r in records:
        w, h = r["w"], r["h"]
        scale = MAX_PX / max(w, h) if max(w, h) > 0 else 1
        dw, dh = max(1, round(w * scale)), max(1, round(h * scale))
        maps_attr = " ".join(r["maps"])
        badges = "".join(f'<span class="m">{m[3:]}</span>' for m in r["maps"][:10])
        more = f'<span class="m">+{len(r["maps"]) - 10}</span>' if len(r["maps"]) > 10 else ""
        light = ""
        if r["light_min"] is not None:
            light = f' &middot; light {r["light_min"]}&ndash;{r["light_max"]}'
        placement = "+".join(r["placements"])
        note = ""
        if r["composite_of"]:
            note = f'<p class="note">composite of {", ".join(r["composite_of"])}</p>'
        per_map_json = json.dumps(r["per_map"]).replace('"', "&quot;")
        figs.append(
            f'''<figure class="tx" data-name="{r["name"]}" data-uses="{r["uses"]}" data-maps="{maps_attr}" data-permap="{per_map_json}">
  <div class="px"><img style="--w:{dw}px;--h:{dh}px" src="data:image/png;base64,{r["png_b64"]}" alt="{r["name"]}" loading="lazy" width="{dw}" height="{dh}"></div>
  <figcaption>
    <div class="hd"><b>{r["name"]}</b><span class="maps">{badges}{more}</span></div>
    <dl>
      <div><dt>game</dt><dd class="n">{r["uses"]}</dd></div>
      <div><dt>here</dt><dd class="n here-val">{r["uses"]}</dd></div>
      <div><dt>px</dt><dd class="n">{w}&times;{h}</dd></div>
    </dl>
    <p class="meta">{placement}{light}</p>
    {note}
  </figcaption>
</figure>'''
        )

    total_maps = len(map_names)
    total_tex = len(records)

    html = f'''<title>Every texture in every Doom 64: Retribution map</title>
<style>
:root {{
  --paper:#E9ECEF; --card:#F7F8FA; --edge:#C6CDD4; --edge-soft:#DCE2E7;
  --ink:#131A20; --ink-2:#495660; --ink-3:#6B7883;
  --lamp-line:#B0741F; --lamp-ink:#7A4A0C; --lamp-bg:#F4E4C9;
  --well:#171D23; --field:#FFFFFF;
}}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{
    --paper:#0E1317; --card:#171E24; --edge:#2C363E; --edge-soft:#232C33;
    --ink:#E4EAEF; --ink-2:#9DAAB4; --ink-3:#75838D;
    --lamp-line:#8A6A3B; --lamp-ink:#F0BC6E; --lamp-bg:#33260F;
    --well:#080B0E; --field:#0C1115;
  }}
}}
:root[data-theme="dark"] {{
  --paper:#0E1317; --card:#171E24; --edge:#2C363E; --edge-soft:#232C33;
  --ink:#E4EAEF; --ink-2:#9DAAB4; --ink-3:#75838D;
  --lamp-line:#8A6A3B; --lamp-ink:#F0BC6E; --lamp-bg:#33260F;
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

.grid {{ display:grid; gap:14px; grid-template-columns:repeat(auto-fill,minmax(212px,1fr)); }}
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
.matched .m {{ background:var(--lamp-bg); color:var(--lamp-ink); }}
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
  <div class="eyebrow">All {total_maps} maps &middot; D64RTR_v15.WAD</div>
  <h1>Every texture the whole game uses</h1>
  <p>All {total_tex} of them, pixels decoded straight out of <span class="mono">D64RTR_v15.WAD</span> &mdash;
  plain graphic lumps read as-is, composite textures rendered from their
  <span class="mono">TEXTURES</span>-lump patch definitions. Ordered rarest first: a light
  fixture used a handful of times reads very differently from panelling reused thousands
  of times across every map.</p>
  <p><b>here</b> tracks uses inside whichever map(s) the filter below is scoped to; <b>game</b>
  is the total across all {total_maps} maps. <b>light</b> is the sector light-level range every
  sidedef/flat use of that texture was found at.</p>
</header>

<div class="bar">
  <input id="q" type="search" placeholder="filter by name&hellip;" aria-label="Filter by name">
  <select id="mapSel" aria-label="Map">
    <option value="all">all maps</option>
    {map_options}
  </select>
  <div class="grp" role="group" aria-label="Sort">
    <button data-sort="uses" aria-pressed="true">rarest first</button>
    <button data-sort="name" aria-pressed="false">A&ndash;Z</button>
    <button data-sort="here" aria-pressed="false">most used here</button>
  </div>
  <span class="count" id="count"></span>
</div>

<div class="grid" id="grid">
{"".join(figs)}
</div>

<footer>
  Generated by <code>tools/export_all_textures_gallery.py</code> from <code>D64RTR_v15.WAD</code>.
</footer>
</div>

<script>
(function() {{
  const grid = document.getElementById('grid');
  const items = Array.from(grid.querySelectorAll('.tx'));
  const q = document.getElementById('q');
  const mapSel = document.getElementById('mapSel');
  const sortGrp = document.querySelector('.grp[aria-label="Sort"]');
  const countEl = document.getElementById('count');
  let sortKey = 'uses';

  function hereCount(it, map) {{
    if (map === 'all') return +it.dataset.uses;
    try {{
      const pm = JSON.parse(it.dataset.permap);
      return pm[map] || 0;
    }} catch (e) {{ return 0; }}
  }}

  function apply() {{
    const term = q.value.trim().toUpperCase();
    const map = mapSel.value;
    let visible = 0;
    items.forEach(it => {{
      const name = it.dataset.name;
      const maps = it.dataset.maps.split(' ');
      const nameOk = !term || name.includes(term);
      const mapOk = map === 'all' || maps.includes(map);
      const here = hereCount(it, map);
      it.querySelector('.here-val').textContent = here;
      it.classList.toggle('matched', map !== 'all' && mapOk);
      const show = nameOk && mapOk;
      it.hidden = !show;
      it._here = here;
      if (show) visible++;
    }});
    const shown = items.filter(it => !it.hidden);
    shown.sort((a, b) => {{
      if (sortKey === 'name') return a.dataset.name.localeCompare(b.dataset.name);
      if (sortKey === 'here') return b._here - a._here;
      return (+a.dataset.uses) - (+b.dataset.uses);
    }});
    shown.forEach(it => grid.appendChild(it));
    countEl.textContent = visible + ' / ' + items.length;
  }}

  q.addEventListener('input', apply);
  mapSel.addEventListener('change', apply);
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
