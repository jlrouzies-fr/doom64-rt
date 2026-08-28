"""The page body for build_vile_glow_gallery.py. Split out only so the HTML is
editable without stepping around the generator's own Python."""

FONTS = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
    'family=Oswald:wght@400;600&family=Barlow:wght@400;500;600&'
    'family=IBM+Plex+Mono:wght@400;600&display=swap">'
)

CSS = r"""
:root{
  --ground:#f4efe9; --panel:#fffdfa; --panel2:#efe7de; --line:#dccfc2;
  --ink:#221a15; --muted:#6d6055; --fire:#c25a06; --mask:#0d7f9c; --ok:#2f7a35;
}
@media (prefers-color-scheme: dark){
  :root:not([data-theme="light"]){
    --ground:#14100e; --panel:#1c1815; --panel2:#241e1a; --line:#3a2f28;
    --ink:#ece2d9; --muted:#9d8e83; --fire:#ff9028; --mask:#38e0ff; --ok:#7bc47f;
  }
}
:root[data-theme="dark"]{
  --ground:#14100e; --panel:#1c1815; --panel2:#241e1a; --line:#3a2f28;
  --ink:#ece2d9; --muted:#9d8e83; --fire:#ff9028; --mask:#38e0ff; --ok:#7bc47f;
}
*{box-sizing:border-box}
body{margin:0;background:var(--ground);color:var(--ink);
  font-family:Barlow,system-ui,sans-serif;line-height:1.55;}
.wrap{max-width:1180px;margin:0 auto;padding:40px 24px 96px;}
header{border-bottom:2px solid var(--line);padding-bottom:22px;}
h1{font-family:Oswald,Impact,sans-serif;font-weight:600;letter-spacing:.02em;
  font-size:clamp(30px,4.6vw,46px);margin:0 0 6px;text-wrap:balance;text-transform:uppercase;}
.sub{color:var(--muted);max-width:66ch;margin:0;}
.eyebrow{font-family:"IBM Plex Mono",monospace;font-size:11px;letter-spacing:.16em;
  text-transform:uppercase;color:var(--fire);margin:0 0 10px;}
.note{background:var(--panel);border:1px solid var(--line);border-left:3px solid var(--fire);
  padding:16px 18px;margin:26px 0;max-width:78ch;}
.note p{margin:0 0 8px}.note p:last-child{margin:0}
.note b{color:var(--fire)}
.bar{display:flex;gap:14px;flex-wrap:wrap;align-items:center;margin:22px 0 20px;
  position:sticky;top:0;background:var(--ground);padding:14px 0;z-index:5;
  border-bottom:1px solid var(--line);}
button{font-family:"IBM Plex Mono",monospace;font-size:12px;letter-spacing:.06em;
  text-transform:uppercase;background:var(--panel2);color:var(--ink);
  border:1px solid var(--line);padding:9px 14px;cursor:pointer;}
button:hover{border-color:var(--fire);color:var(--fire)}
button:focus-visible{outline:2px solid var(--fire);outline-offset:2px}
button[aria-pressed="true"]{background:var(--fire);color:var(--ground);border-color:var(--fire)}
button.primary{border-color:var(--fire);color:var(--fire)}
button[disabled]{opacity:.45;cursor:default}
.slab{display:flex;align-items:center;gap:9px;font-family:"IBM Plex Mono",monospace;
  font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);}
input[type=range]{accent-color:var(--fire);width:170px;}
.val{color:var(--fire);font-variant-numeric:tabular-nums;min-width:3ch;}
.said{font-family:"IBM Plex Mono",monospace;font-size:11px;color:var(--ok);}
.grid{display:grid;gap:22px;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));}
.card{background:var(--panel);border:1px solid var(--line);display:flex;flex-direction:column;}
.card.tuned{border-color:var(--fire)}
.card h2{font-family:Oswald,sans-serif;font-weight:600;font-size:17px;margin:0;
  padding:11px 14px;border-bottom:1px solid var(--line);display:flex;
  justify-content:space-between;align-items:baseline;gap:8px;text-transform:uppercase;}
.card h2 span{font-family:"IBM Plex Mono",monospace;font-size:11px;color:var(--muted);
  text-transform:none;letter-spacing:0;}
.stage{position:relative;background:
  repeating-conic-gradient(var(--panel2) 0 25%, transparent 0 50%) 0 0/16px 16px;
  display:flex;align-items:center;justify-content:center;padding:10px;}
.box{position:relative;cursor:crosshair;}
.box img,.box canvas{image-rendering:pixelated;display:block;position:absolute;
  left:0;top:0;width:100%;height:100%;}
.box img{position:relative}
.pin{position:absolute;width:13px;height:13px;margin:-7px 0 0 -7px;border-radius:50%;
  border:2px solid var(--ground);background:var(--fire);pointer-events:none;}
.pin.auto{background:transparent;border-color:var(--mask);width:15px;height:15px;
  margin:-8px 0 0 -8px;}
.ctl{display:flex;align-items:center;gap:8px;padding:9px 14px;border-top:1px solid var(--line);
  font-family:"IBM Plex Mono",monospace;font-size:10.5px;letter-spacing:.06em;
  text-transform:uppercase;color:var(--muted);}
.ctl input[type=range]{width:100%;flex:1}
.meta{font-family:"IBM Plex Mono",monospace;font-size:11.5px;color:var(--muted);
  padding:9px 14px;border-top:1px solid var(--line);display:flex;
  justify-content:space-between;gap:8px;font-variant-numeric:tabular-nums;}
.pts{font-family:"IBM Plex Mono",monospace;font-size:11.5px;padding:0 14px 12px;
  color:var(--ink);min-height:20px;font-variant-numeric:tabular-nums;}
.pts:empty::before{content:"no points \2014 click the flame";color:var(--muted);}
.out{width:100%;min-height:200px;background:var(--panel);color:var(--ink);
  border:1px solid var(--line);font-family:"IBM Plex Mono",monospace;font-size:12px;
  padding:14px;margin-top:16px;resize:vertical;}
footer{margin-top:36px;color:var(--muted);font-size:13.5px;max-width:72ch;}
code{font-family:"IBM Plex Mono",monospace;background:var(--panel2);padding:1px 5px;}
"""

SHELL = r"""
<header>
  <p class="eyebrow">Doom 64 RT &middot; Unseen Evil &middot; emissive review</p>
  <h1>Arch-Vile Flame Map</h1>
  <p class="sub">Every BRIGHT frame of the cast. Tune the detector until the cyan covers the
  fire and nothing else, then click where each flame's light belongs. <b>Save marks</b> writes
  them back into this page, so they can be read straight out of it.</p>
</header>

<div class="note">
  <p><b>Why this asks instead of detecting.</b> The Baron's fist glow is masked from the
  mod's own authored brightmaps &mdash; the artists drew it and the tool just reads it.
  Unseen Evil ships no monster brightmaps, so the cyan here is only a colour threshold.</p>
  <p><b>Why one threshold won't do.</b> The wind-up frames are a thin rim of fire and the
  peak frames are a wall of it, so a floor that reads G correctly floods J. Each card has
  its own slider; the global one moves every frame you haven't tuned by hand. Red saturates
  at 255, so past that the range tightens colour purity and brightness instead &mdash; that
  is the band for frames that over-capture.</p>
  <p><b>Why the light is misplaced today.</b> RTGL1 pins a sprite's attached light to the
  centre of the billboard quad. The fire is in the raised hands, so the light lands in the
  chest &mdash; and with two hands, both average into one point between them.</p>
</div>

<div class="bar">
  <div class="slab"><label for="gf">Sensitivity</label>
    <input type="range" id="gf" min="90" max="300" value="170">
    <span class="val" id="gfv">170</span></div>
  <button id="tMask" aria-pressed="true">Mask</button>
  <button id="tAuto" aria-pressed="true">Blobs</button>
  <button id="tScale">Zoom 6&times;</button>
  <button id="clr">Clear points</button>
  <button id="cp">Copy result</button>
  <button id="save" class="primary">Save marks</button>
  <span class="said" id="said"></span>
</div>

<div class="grid" id="grid"></div>
<textarea class="out" id="out" readonly aria-label="Result"></textarea>

<footer>
  <p><code>lat</code> is pixels right of the origin column, <code>up</code> is pixels above
  the feet row &mdash; map units at Retribution's 1:1 sprite scale. Same body-relative form
  <code>tools/gen_hand_light_offsets.py</code> emits for <code>RT_UploadHandGlowLights</code>.</p>
</footer>
"""

BOOT = r"""
const FONTS = __FONTS__;
const DATA = JSON.parse(document.getElementById('data').textContent);
const STATE = JSON.parse(document.getElementById('state').textContent);
const MIN_BLOB = 12;

let scale = 6, showMask = true, showAuto = true;
let globalFloor = STATE.globalFloor || 170;
const picks = Object.assign({}, STATE.picks || {});
const floors = Object.assign({}, STATE.floors || {});
const tuned = Object.assign({}, STATE.tuned || {});
const cells = {};

document.getElementById('app').innerHTML =
  document.getElementById('shell').innerHTML;

function detect(f, floor){
  const src = cells[f.frame].data, w = f.w, h = f.h;
  const hot = new Uint8Array(w * h);
  // The red term is CLAMPED at 255. Red cannot exceed 255, so past that a raw
  // "r >= floor" matches nothing and the slider goes dead rather than getting
  // stricter. Above 255 the range keeps biting through the other two terms --
  // red-vs-blue separation and total brightness -- so 255..300 selects only
  // near-saturated, strongly red-dominant texels: the core of a flame rather
  // than its falloff. That is the range for the frames that over-capture.
  const minR = Math.min(floor, 255), minRB = floor * 0.4, minSum = floor * 1.8;
  let n = 0;
  for (let i = 0, p = 0; i < hot.length; i++, p += 4){
    if (src[p + 3] < 128) continue;
    const r = src[p], g = src[p + 1], b = src[p + 2];
    if (r >= minR && r - b >= minRB && r + g + b >= minSum){ hot[i] = 1; n++; }
  }
  const seen = new Uint8Array(w * h), out = [], stack = [];
  for (let s = 0; s < hot.length; s++){
    if (!hot[s] || seen[s]) continue;
    stack.length = 0; stack.push(s); seen[s] = 1;
    let cnt = 0, sx = 0, sy = 0;
    while (stack.length){
      const i = stack.pop(), x = i % w, y = (i / w) | 0;
      cnt++; sx += x; sy += y;
      for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++){
        const nx = x + dx, ny = y + dy;
        if (nx < 0 || ny < 0 || nx >= w || ny >= h) continue;
        const j = ny * w + nx;
        if (hot[j] && !seen[j]){ seen[j] = 1; stack.push(j); }
      }
    }
    if (cnt >= MIN_BLOB) out.push({n: cnt, cx: sx / cnt, cy: sy / cnt});
  }
  out.sort((a, b) => b.n - a.n);
  return {hot, n, blobs: out};
}

function paint(f){
  const floor = floors[f.frame], r = detect(f, floor), el = f._el;
  const ctx = el.canvas.getContext('2d');
  const img = ctx.createImageData(f.w, f.h);
  if (showMask){
    const cy = getComputedStyle(document.documentElement)
      .getPropertyValue('--mask').trim();
    const rr = parseInt(cy.slice(1,3),16), gg = parseInt(cy.slice(3,5),16),
          bb = parseInt(cy.slice(5,7),16);
    for (let i = 0, p = 0; i < r.hot.length; i++, p += 4){
      if (!r.hot[i]) continue;
      img.data[p] = rr; img.data[p+1] = gg; img.data[p+2] = bb; img.data[p+3] = 150;
    }
  }
  ctx.putImageData(img, 0, 0);

  el.pins.innerHTML = '';
  const pin = (x, y, cls) => {
    const p = document.createElement('i');
    p.className = cls;
    p.style.left = ((x + 0.5) / f.w * 100) + '%';
    p.style.top  = ((y + 0.5) / f.h * 100) + '%';
    el.pins.appendChild(p);
  };
  if (showAuto) for (const b of r.blobs) pin(b.cx, b.cy, 'pin auto');
  for (const pt of (picks[f.frame] || [])) pin(pt[0], pt[1], 'pin');

  el.meta.innerHTML = '<span>' + f.w + '×' + f.h + ' · origin ' + f.ox + ',' + f.oy +
    '</span><span>' + r.n + ' hot · ' + r.blobs.length + ' blob' +
    (r.blobs.length === 1 ? '' : 's') + '</span>';
  el.pts.textContent = (picks[f.frame] || [])
    .map(p => 'lat ' + (p[0] - f.ox) + '  up ' + (f.oy - p[1])).join('   ');
  el.card.classList.toggle('tuned', !!tuned[f.frame]);
  el.fv.textContent = floor;
  el.fr.value = floor;
}

function sizeBox(f){
  f._el.box.style.width = (f.w * scale) + 'px';
  f._el.box.style.height = (f.h * scale) + 'px';
}

function build(){
  const grid = document.getElementById('grid');
  for (const f of DATA){
    if (floors[f.frame] === undefined) floors[f.frame] = globalFloor;
    const card = document.createElement('div');
    card.className = 'card';
    const h2 = document.createElement('h2');
    h2.innerHTML = 'Frame ' + (f.frame === '[' ? '&#91;' : f.frame) +
      '<span>' + f.lump + ' · ' + f.kind + '</span>';
    card.appendChild(h2);

    const stage = document.createElement('div'); stage.className = 'stage';
    const box = document.createElement('div'); box.className = 'box';
    const img = new Image();
    img.src = f.sprite; img.alt = 'Arch-Vile frame ' + f.frame;
    const canvas = document.createElement('canvas');
    canvas.width = f.w; canvas.height = f.h;
    const pins = document.createElement('div');
    pins.style.cssText = 'position:absolute;inset:0;pointer-events:none';
    box.append(img, canvas, pins);
    stage.appendChild(box); card.appendChild(stage);

    const ctl = document.createElement('div'); ctl.className = 'ctl';
    const lab = document.createElement('label'); lab.textContent = 'Sens';
    const fr = document.createElement('input');
    fr.type = 'range'; fr.min = '90'; fr.max = '300'; fr.value = String(floors[f.frame]);
    fr.setAttribute('aria-label', 'Sensitivity for frame ' + f.frame);
    const fv = document.createElement('span'); fv.className = 'val';
    ctl.append(lab, fr, fv); card.appendChild(ctl);

    const meta = document.createElement('div'); meta.className = 'meta';
    const pts = document.createElement('div'); pts.className = 'pts';
    card.append(meta, pts);

    f._el = {card, box, img, canvas, pins, meta, pts, fr, fv};
    sizeBox(f);

    fr.addEventListener('input', () => {
      floors[f.frame] = +fr.value; tuned[f.frame] = true; paint(f); dirty();
    });
    box.addEventListener('click', ev => {
      const r = box.getBoundingClientRect();
      const x = Math.min(f.w - 1, Math.max(0, Math.floor((ev.clientX - r.left) / scale)));
      const y = Math.min(f.h - 1, Math.max(0, Math.floor((ev.clientY - r.top) / scale)));
      picks[f.frame] = picks[f.frame] || [];
      const near = picks[f.frame].findIndex(p => Math.abs(p[0]-x) < 4 && Math.abs(p[1]-y) < 4);
      if (near >= 0) picks[f.frame].splice(near, 1); else picks[f.frame].push([x, y]);
      paint(f); emit(); dirty();
    });

    grid.appendChild(card);

    img.decode().then(() => {
      const c = document.createElement('canvas');
      c.width = f.w; c.height = f.h;
      const cx = c.getContext('2d', {willReadFrequently: true});
      cx.drawImage(img, 0, 0);
      cells[f.frame] = cx.getImageData(0, 0, f.w, f.h);
      paint(f);
    });
  }
}

function emit(){
  const lines = ['# frame  px_x px_y   lat   up    sens   (lat = right of origin, up = above feet)'];
  for (const f of DATA) for (const p of (picks[f.frame] || [])){
    lines.push('  ' + f.frame.padEnd(6) + String(p[0]).padStart(4) +
      String(p[1]).padStart(5) + String(p[0]-f.ox).padStart(6) +
      String(f.oy-p[1]).padStart(6) + String(floors[f.frame]).padStart(7));
  }
  document.getElementById('out').value = lines.length > 1
    ? lines.join('\n') : 'Click the flames on each frame; the coordinates land here.';
}

const said = m => { document.getElementById('said').textContent = m || ''; };
const dirty = () => said('unsaved');
const repaint = () => DATA.forEach(f => { if (cells[f.frame]) paint(f); });

function buildDoc(state){
  const css = document.getElementById('css').textContent;
  const shell = document.getElementById('shell').innerHTML;
  const boot = document.getElementById('boot').textContent;
  const data = document.getElementById('data').textContent;
  const S = '<' + 'script', E = '<' + '/' + 'script>';
  return '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n' +
    '<meta name="viewport" content="width=device-width,initial-scale=1">\n' +
    '<title>Arch-Vile Flame Map</title>\n' + FONTS +
    '\n<style id="css">' + css + '</style>\n</head>\n<body>\n' +
    '<template id="shell">' + shell + '</template>\n' +
    '<div class="wrap" id="app"></div>\n' +
    S + ' id="data" type="application/json">' + data + E + '\n' +
    S + ' id="state" type="application/json">' + JSON.stringify(state) + E + '\n' +
    S + ' id="boot">' + boot + E + '\n</body>\n</html>';
}

document.getElementById('gf').value = globalFloor;
document.getElementById('gfv').textContent = globalFloor;
document.getElementById('gf').addEventListener('input', e => {
  globalFloor = +e.target.value;
  document.getElementById('gfv').textContent = globalFloor;
  for (const f of DATA) if (!tuned[f.frame]) floors[f.frame] = globalFloor;
  repaint(); dirty();
});
document.getElementById('tMask').addEventListener('click', e => {
  showMask = !showMask; e.currentTarget.setAttribute('aria-pressed', showMask); repaint();
});
document.getElementById('tAuto').addEventListener('click', e => {
  showAuto = !showAuto; e.currentTarget.setAttribute('aria-pressed', showAuto); repaint();
});
document.getElementById('tScale').addEventListener('click', e => {
  scale = scale === 6 ? 10 : (scale === 10 ? 4 : 6);
  e.currentTarget.innerHTML = 'Zoom ' + scale + '×';
  DATA.forEach(sizeBox);
});
document.getElementById('clr').addEventListener('click', () => {
  for (const k of Object.keys(picks)) delete picks[k]; repaint(); emit(); dirty();
});

// Clipboard: navigator.clipboard is unavailable in plenty of embedded views, and
// selecting a READONLY textarea is not enough on its own. Fall back to a real
// temporary textarea + execCommand, then to leaving the text selected.
document.getElementById('cp').addEventListener('click', async e => {
  const txt = document.getElementById('out').value;
  let ok = false;
  try { await navigator.clipboard.writeText(txt); ok = true; } catch (_) {}
  if (!ok){
    const ta = document.createElement('textarea');
    ta.value = txt;
    ta.style.cssText = 'position:fixed;top:0;left:0;opacity:0';
    document.body.appendChild(ta);
    ta.focus(); ta.select();
    try { ok = document.execCommand('copy'); } catch (_) {}
    ta.remove();
  }
  if (!ok){
    const out = document.getElementById('out');
    out.focus(); out.select();
  }
  e.currentTarget.textContent = ok ? 'Copied' : 'Selected — press Ctrl+C';
  setTimeout(() => { e.currentTarget.textContent = 'Copy result'; }, 2200);
});

document.getElementById('save').addEventListener('click', async e => {
  const btn = e.currentTarget;
  btn.disabled = true; said('saving…');
  const artifact = await claude.use('artifact');
  if (!artifact){
    said('saving unavailable here — use Copy result');
    btn.disabled = false; return;
  }
  try {
    await artifact.publish(buildDoc({picks, floors, tuned, globalFloor}));
    said('saved');
  } catch (err){
    const code = err && err.code;
    if (code === 'conflict') said('reloading to a newer version…');
    else if (code === 'not_writer' || code === 'not_granted'){
      said('read-only view — use Copy result'); btn.remove(); return;
    }
    else said('save failed (' + (code || 'error') + ') — use Copy result');
    btn.disabled = false;
  }
});

build(); emit();
if (Object.keys(picks).length) said('loaded saved marks');
"""
