"""Page body for build_sprite_mark_gallery.py -- a per-texel emissive painter.

Detection was tried first and abandoned on the evidence: the Revenant's eyes are
4 texels of pure (128,0,0) and separate cleanly, but the Arch-Vile's gave ONE
texel at the same settings. A threshold that finds a subtle eye also finds the
body, so the mask gets drawn by hand instead. What survives from the detector is
one optional shortcut -- SEED, which learns the colour from texels already
painted and looks for it in the frame's other rotations. That is seeded by the
artist rather than guessed, which is the difference that makes it usable."""

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
.wrap{max-width:1300px;margin:0 auto;padding:38px 22px 96px;}
header{border-bottom:2px solid var(--line);padding-bottom:20px;}
h1{font-family:Oswald,Impact,sans-serif;font-weight:600;letter-spacing:.02em;
  font-size:clamp(28px,4.4vw,44px);margin:0 0 6px;text-wrap:balance;text-transform:uppercase;}
.sub{color:var(--muted);max-width:68ch;margin:0;}
.eyebrow{font-family:"IBM Plex Mono",monospace;font-size:11px;letter-spacing:.16em;
  text-transform:uppercase;color:var(--fire);margin:0 0 10px;}
.note{background:var(--panel);border:1px solid var(--line);border-left:3px solid var(--fire);
  padding:15px 17px;margin:22px 0;max-width:80ch;}
.note p{margin:0 0 8px}.note p:last-child{margin:0}
.note b{color:var(--fire)}
kbd{font-family:"IBM Plex Mono",monospace;font-size:11px;background:var(--panel2);
  border:1px solid var(--line);padding:1px 5px;}
.bar{display:flex;gap:12px;flex-wrap:wrap;align-items:center;margin:18px 0;
  position:sticky;top:0;background:var(--ground);padding:12px 0;z-index:8;
  border-bottom:1px solid var(--line);}
button{font-family:"IBM Plex Mono",monospace;font-size:12px;letter-spacing:.06em;
  text-transform:uppercase;background:var(--panel2);color:var(--ink);
  border:1px solid var(--line);padding:8px 13px;cursor:pointer;}
button:hover{border-color:var(--fire);color:var(--fire)}
button:focus-visible{outline:2px solid var(--fire);outline-offset:2px}
button[aria-pressed="true"]{background:var(--fire);color:var(--ground);border-color:var(--fire)}
button.primary{border-color:var(--fire);color:var(--fire)}
button.mini{font-size:10px;padding:4px 7px;letter-spacing:.04em;}
button[disabled]{opacity:.45;cursor:default}
.slab{display:flex;align-items:center;gap:8px;font-family:"IBM Plex Mono",monospace;
  font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);}
.val{color:var(--fire);font-variant-numeric:tabular-nums;min-width:2ch;}
.said{font-family:"IBM Plex Mono",monospace;font-size:11px;color:var(--ok);}
details{border:1px solid var(--line);background:var(--panel);margin:14px 0;}
summary{font-family:Oswald,sans-serif;font-weight:600;font-size:19px;padding:12px 16px;
  cursor:pointer;text-transform:uppercase;letter-spacing:.02em;display:flex;
  justify-content:space-between;align-items:baseline;gap:10px;}
summary span{font-family:"IBM Plex Mono",monospace;font-size:11px;color:var(--muted);
  text-transform:none;letter-spacing:0;font-weight:400;}
summary:focus-visible{outline:2px solid var(--fire);outline-offset:-2px}
.secbody{padding:0 16px 16px}
.fgroup{margin:14px 0 0;border-top:1px solid var(--line);padding-top:12px;}
.fhead{display:flex;align-items:center;gap:10px;margin-bottom:8px;}
.fhead b{font-family:Oswald,sans-serif;font-size:15px;text-transform:uppercase;}
.row{display:flex;gap:12px;flex-wrap:wrap;}
.card{background:var(--panel2);border:1px solid var(--line);}
.card.has{border-color:var(--fire)}
.card h4{font-family:"IBM Plex Mono",monospace;font-weight:400;font-size:10px;margin:0;
  padding:5px 7px;border-bottom:1px solid var(--line);color:var(--muted);
  display:flex;justify-content:space-between;gap:6px;}
.card h4 b{color:var(--ink);font-weight:600;}
.stage{position:relative;padding:6px;background:
  repeating-conic-gradient(var(--panel) 0 25%, transparent 0 50%) 0 0/12px 12px;}
.box{position:relative;cursor:crosshair;touch-action:none;}
.box img,.box canvas{image-rendering:pixelated;display:block;position:absolute;
  left:0;top:0;width:100%;height:100%;}
.box img{position:relative}
.out{width:100%;min-height:170px;background:var(--panel);color:var(--ink);
  border:1px solid var(--line);font-family:"IBM Plex Mono",monospace;font-size:12px;
  padding:13px;margin-top:16px;resize:vertical;}
footer{margin-top:32px;color:var(--muted);font-size:13.5px;max-width:74ch;}
code{font-family:"IBM Plex Mono",monospace;background:var(--panel2);padding:1px 5px;}
"""

SHELL = r"""
<header>
  <p class="eyebrow">Doom 64 RT &middot; Unseen Evil &middot; emissive painter</p>
  <h1>Unseen Evil Emissive Masks</h1>
  <p class="sub">Paint the emissive texels directly &mdash; eyes for the Arch-Vile,
  Revenant and Spider Mastermind, and whatever should glow on the Chaingunner.
  <b>Save marks</b> writes every mask back into this page so it can be read out of it.</p>
</header>

<div class="note">
  <p><b>Drag to paint, <kbd>Alt</kbd>-drag or right-drag to erase.</b> Brush size and zoom
  are in the bar. Each monster is collapsed until you open it &mdash; there are 310 lumps
  here and drawing them all at once would be unusable.</p>
  <p><b>Rotations are the work, so there is a shortcut for them.</b> <kbd>SEED</kbd> on a
  frame takes the colours you already painted on its first rotation and finds those same
  colours in the others, restricted to nearby body-relative positions. It is seeded by
  what you drew rather than guessed at, which is why it is offered when blind detection
  was not: a threshold that catches a subtle eye also catches the body. Always check what
  it produced &mdash; it is a starting point, not an answer.</p>
  <p><b>One lump can serve two frames, and is drawn once.</b> <code>VILEA2D8</code> is
  frame A rotation 2 <em>and</em> frame D rotation 8 &mdash; a single image. It is filed
  under the first frame that uses it and its card is tagged <code>+D</code>, so painting it
  covers both. Frame D's row is correspondingly shorter; that is not a gap.</p>
</div>

<div class="bar">
  <div class="slab"><label for="brush">Brush</label>
    <input type="range" id="brush" min="1" max="4" value="1" style="width:80px">
    <span class="val" id="brushv">1</span></div>
  <button id="tScale">Zoom 6&times;</button>
  <button id="tErase" aria-pressed="false">Erase</button>
  <button id="cp">Copy result</button>
  <button id="save" class="primary">Save marks</button>
  <span class="said" id="said"></span>
</div>

<div id="sections"></div>
<textarea class="out" id="out" readonly aria-label="Result"></textarea>

<footer>
  <p>Masks come out as sprite-pixel lists per lump. The generator turns them into
  <code>_e</code> images the same way <code>gen_vile_glow_emissives.py</code> does &mdash;
  each texel's own hue saturated to full range, never the raw albedo, because
  <code>RsWorld.inl</code> multiplies by baseColor again and squaring dark art annihilates
  the glow.</p>
</footer>
"""

BOOT = r"""
const FONTS = __FONTS__;
const DATA = JSON.parse(document.getElementById('data').textContent);
const STATE = JSON.parse(document.getElementById('state').textContent);

const ZOOMS = [2, 3, 4, 6, 8, 12, 16];   // 2x is for finding a frame, 12-16 for painting it
let scale = 6, brush = 1, erasing = false, painting = false;
const masks = {};                       // lump -> Set of pixel index
for (const [k, v] of Object.entries(STATE.masks || {})) masks[k] = new Set(v);
const cells = {}, els = {};

document.getElementById('app').innerHTML = document.getElementById('shell').innerHTML;

const said = m => { document.getElementById('said').textContent = m || ''; };
const dirty = () => said('unsaved');

function paint(f){
  const el = els[f.lump];
  if (!el) return;
  const ctx = el.canvas.getContext('2d');
  const img = ctx.createImageData(f.w, f.h);
  const cs = getComputedStyle(document.documentElement);
  const v = cs.getPropertyValue('--mask').trim();
  const r = parseInt(v.slice(1,3),16), g = parseInt(v.slice(3,5),16), b = parseInt(v.slice(5,7),16);
  const set = masks[f.lump];
  if (set) for (const i of set){
    const p = i * 4;
    img.data[p] = r; img.data[p+1] = g; img.data[p+2] = b; img.data[p+3] = 200;
  }
  ctx.putImageData(img, 0, 0);
  const n = set ? set.size : 0;
  el.card.classList.toggle('has', n > 0);
  el.count.textContent = n ? String(n) : '';
}

function dab(f, ev){
  const el = els[f.lump];
  const r = el.box.getBoundingClientRect();
  const cx = Math.floor((ev.clientX - r.left) / scale);
  const cy = Math.floor((ev.clientY - r.top) / scale);
  const set = masks[f.lump] || (masks[f.lump] = new Set());
  const rad = brush - 1;
  const rm = erasing || ev.altKey || ev.buttons === 2;
  for (let y = cy - rad; y <= cy + rad; y++)
    for (let x = cx - rad; x <= cx + rad; x++){
      if (x < 0 || y < 0 || x >= f.w || y >= f.h) continue;
      const i = y * f.w + x;
      if (rm) set.delete(i); else set.add(i);
    }
  paint(f); dirty();
}

// SEED: learn the colours from what is already painted on `from`, then find them
// in `to` -- near the same body-relative spot, so a red eye colour that also
// appears on a belt does not drag the belt in.
function seed(group){
  const src = group[0];
  const have = masks[src.lump];
  if (!have || !have.size){ said('paint the first rotation before seeding'); return; }
  const sp = cells[src.lump];
  if (!sp) return;
  const want = new Set();
  let sx = 0, sy = 0;
  for (const i of have){
    const p = i * 4;
    want.add((sp.data[p] >> 3) + ',' + (sp.data[p+1] >> 3) + ',' + (sp.data[p+2] >> 3));
    sx += (i % src.w) - src.ox; sy += ((i / src.w) | 0) - src.oy;
  }
  sx /= have.size; sy /= have.size;

  let made = 0;
  for (const f of group.slice(1)){
    const c = cells[f.lump];
    if (!c) continue;
    const set = masks[f.lump] || (masks[f.lump] = new Set());
    for (let i = 0, p = 0; i < f.w * f.h; i++, p += 4){
      if (c.data[p+3] < 128) continue;
      const key = (c.data[p] >> 3) + ',' + (c.data[p+1] >> 3) + ',' + (c.data[p+2] >> 3);
      if (!want.has(key)) continue;
      const dx = (i % f.w) - f.ox - sx, dy = ((i / f.w) | 0) - f.oy - sy;
      if (dx * dx + dy * dy > 18 * 18) continue;   // stay near where you painted
      set.add(i); made++;
    }
    paint(f);
  }
  said('seeded ' + made + ' texel' + (made === 1 ? '' : 's') + ' — check them');
  emit(); dirty();
}

function makeCard(f){
  const card = document.createElement('div'); card.className = 'card';
  const h4 = document.createElement('h4');
  const count = document.createElement('b'); count.textContent = '';
  const shared = (f.shared && f.shared.length)
    ? ' +' + f.shared.join('')          // this image also serves that frame
    : '';
  h4.innerHTML = '<span>' + f.lump + shared + '</span>';
  h4.prepend(count);
  const stage = document.createElement('div'); stage.className = 'stage';
  const box = document.createElement('div'); box.className = 'box';
  box.style.width = (f.w * scale) + 'px';
  box.style.height = (f.h * scale) + 'px';
  const img = new Image(); img.src = f.sprite; img.alt = f.lump;
  const canvas = document.createElement('canvas');
  canvas.width = f.w; canvas.height = f.h;
  box.append(img, canvas); stage.appendChild(box);
  card.append(h4, stage);

  els[f.lump] = {card, box, canvas, count};

  box.addEventListener('contextmenu', e => e.preventDefault());
  box.addEventListener('pointerdown', e => {
    painting = true; box.setPointerCapture(e.pointerId); dab(f, e); e.preventDefault();
  });
  box.addEventListener('pointermove', e => { if (painting) dab(f, e); });
  box.addEventListener('pointerup', () => { painting = false; emit(); });
  box.addEventListener('pointercancel', () => { painting = false; });

  img.decode().then(() => {
    const c = document.createElement('canvas');
    c.width = f.w; c.height = f.h;
    const cx = c.getContext('2d', {willReadFrequently: true});
    cx.drawImage(img, 0, 0);
    cells[f.lump] = cx.getImageData(0, 0, f.w, f.h);
    paint(f);
  });
  return card;
}

function buildSection(sec, body){
  for (const group of sec.groups){
    const g = document.createElement('div'); g.className = 'fgroup';
    const head = document.createElement('div'); head.className = 'fhead';
    const b = document.createElement('b'); b.textContent = 'Frame ' + group.frame;
    const seedBtn = document.createElement('button');
    seedBtn.className = 'mini'; seedBtn.textContent = 'Seed rotations';
    seedBtn.addEventListener('click', () => seed(group.lumps));
    const clr = document.createElement('button');
    clr.className = 'mini'; clr.textContent = 'Clear frame';
    clr.addEventListener('click', () => {
      for (const f of group.lumps){ masks[f.lump] = new Set(); paint(f); }
      emit(); dirty();
    });
    head.append(b, seedBtn, clr);
    const row = document.createElement('div'); row.className = 'row';
    for (const f of group.lumps) row.appendChild(makeCard(f));
    g.append(head, row); body.appendChild(g);
  }
}

function build(){
  const root = document.getElementById('sections');
  for (const sec of DATA){
    const d = document.createElement('details');
    const s = document.createElement('summary');
    const n = sec.groups.reduce((a, g) => a + g.lumps.length, 0);
    s.innerHTML = sec.title + '<span>' + sec.groups.length + ' frames · ' + n + ' lumps</span>';
    d.appendChild(s);
    const body = document.createElement('div'); body.className = 'secbody';
    d.appendChild(body);
    let done = false;
    d.addEventListener('toggle', () => {
      if (d.open && !done){ done = true; buildSection(sec, body); }
    });
    root.appendChild(d);
  }
}

function emit(){
  const out = [];
  for (const sec of DATA){
    const rows = [];
    for (const g of sec.groups) for (const f of g.lumps){
      const set = masks[f.lump];
      if (!set || !set.size) continue;
      const px = [...set].sort((a, b) => a - b)
        .map(i => (i % f.w) + ',' + ((i / f.w) | 0)).join(' ');
      rows.push('  ' + f.lump.padEnd(11) + ' ' + px);
    }
    out.push('# ' + sec.sprite + ' — ' + rows.length + ' lump(s) painted');
    out.push(...rows);
    out.push('');
  }
  document.getElementById('out').value = out.join('\n');
}

function buildDoc(state){
  const S = '<' + 'script', E = '<' + '/' + 'script>';
  return '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n' +
    '<meta name="viewport" content="width=device-width,initial-scale=1">\n' +
    '<title>Unseen Evil Emissive Masks</title>\n' + FONTS +
    '\n<style id="css">' + document.getElementById('css').textContent + '</style>\n</head>\n<body>\n' +
    '<template id="shell">' + document.getElementById('shell').innerHTML + '</template>\n' +
    '<div class="wrap" id="app"></div>\n' +
    S + ' id="data" type="application/json">' + document.getElementById('data').textContent + E + '\n' +
    S + ' id="state" type="application/json">' + JSON.stringify(state) + E + '\n' +
    S + ' id="boot">' + document.getElementById('boot').textContent + E + '\n</body>\n</html>';
}

document.getElementById('brush').addEventListener('input', e => {
  brush = +e.target.value; document.getElementById('brushv').textContent = brush;
});
document.getElementById('tScale').addEventListener('click', e => {
  const i = ZOOMS.indexOf(scale);
  scale = ZOOMS[(i + 1) % ZOOMS.length];
  e.currentTarget.innerHTML = 'Zoom ' + scale + '×';
  for (const sec of DATA) for (const g of sec.groups) for (const f of g.lumps){
    const el = els[f.lump];
    if (el){ el.box.style.width = (f.w * scale) + 'px'; el.box.style.height = (f.h * scale) + 'px'; }
  }
});
document.getElementById('tErase').addEventListener('click', e => {
  erasing = !erasing; e.currentTarget.setAttribute('aria-pressed', erasing);
});
document.getElementById('cp').addEventListener('click', async e => {
  const txt = document.getElementById('out').value;
  let ok = false;
  try { await navigator.clipboard.writeText(txt); ok = true; } catch (_) {}
  if (!ok){
    const ta = document.createElement('textarea');
    ta.value = txt; ta.style.cssText = 'position:fixed;top:0;left:0;opacity:0';
    document.body.appendChild(ta); ta.focus(); ta.select();
    try { ok = document.execCommand('copy'); } catch (_) {}
    ta.remove();
  }
  if (!ok){ const o = document.getElementById('out'); o.focus(); o.select(); }
  e.currentTarget.textContent = ok ? 'Copied' : 'Selected — press Ctrl+C';
  setTimeout(() => { e.currentTarget.textContent = 'Copy result'; }, 2200);
});
document.getElementById('save').addEventListener('click', async e => {
  const btn = e.currentTarget; btn.disabled = true; said('saving…');
  const artifact = await claude.use('artifact');
  if (!artifact){ said('saving unavailable here — use Copy result'); btn.disabled = false; return; }
  const flat = {};
  for (const [k, v] of Object.entries(masks)) if (v.size) flat[k] = [...v].sort((a,b) => a-b);
  try {
    await artifact.publish(buildDoc({masks: flat}));
    said('saved');
  } catch (err){
    const code = err && err.code;
    if (code === 'conflict') said('reloading to a newer version…');
    else if (code === 'not_writer' || code === 'not_granted'){
      said('read-only view — use Copy result'); btn.remove(); return;
    } else said('save failed (' + (code || 'error') + ') — use Copy result');
    btn.disabled = false;
  }
});

build(); emit();
const painted = Object.values(masks).filter(s => s.size).length;
if (painted) said('loaded ' + painted + ' painted lump' + (painted === 1 ? '' : 's'));
"""
