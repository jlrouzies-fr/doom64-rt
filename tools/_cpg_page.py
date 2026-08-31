"""Page body for build_glow_gallery.py -- colour-detected emissive families.

Detection is the right tool for these three, unlike the Arch-Vile's eyes: every
family separates on colour with room to spare, and the numbers are in the page.
The one thing that had to be got right first is the RULE. A plain "reddish" test
(r>=140, r-g>=60, r-b>=60) matches 425..2922 texels per Mastermind frame -- that
is its red-brown BODY, not its eyes. The discriminator is PURITY: the glowing
parts have green and blue near zero, the flesh does not. With g,b <= 40 the same
sprites give 13..26 texels on the walk (the eyes) and 1187 on H1 (the guns).
"""

FONTS = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
    'family=Oswald:wght@400;600&family=Barlow:wght@400;500;600&'
    'family=IBM+Plex+Mono:wght@400;600&display=swap">'
)

CSS = r"""
:root{
  --ground:#f2f0ec; --panel:#fffefc; --panel2:#e8e5df; --line:#d5d0c7;
  --ink:#1c1e1a; --muted:#5f6359; --accent:#3f7d3a;
  --grn:#2fbf3a; --mzl:#8a6bd6; --red:#d62828;
}
@media (prefers-color-scheme: dark){
  :root:not([data-theme="light"]){
    --ground:#101210; --panel:#191c19; --panel2:#212520; --line:#333a32;
    --ink:#e4e8e0; --muted:#8e968a; --accent:#7ddc72;
    --grn:#5cff6a; --mzl:#c4a6ff; --red:#ff5a5a;
  }
}
:root[data-theme="dark"]{
  --ground:#101210; --panel:#191c19; --panel2:#212520; --line:#333a32;
  --ink:#e4e8e0; --muted:#8e968a; --accent:#7ddc72;
  --grn:#5cff6a; --mzl:#c4a6ff; --red:#ff5a5a;
}
*{box-sizing:border-box}
body{margin:0;background:var(--ground);color:var(--ink);
  font-family:Barlow,system-ui,sans-serif;line-height:1.55;}
.wrap{max-width:1280px;margin:0 auto;padding:38px 22px 90px;}
header{border-bottom:2px solid var(--line);padding-bottom:20px;}
h1{font-family:Oswald,Impact,sans-serif;font-weight:600;letter-spacing:.02em;
  font-size:clamp(28px,4.4vw,44px);margin:0 0 6px;text-wrap:balance;text-transform:uppercase;}
.sub{color:var(--muted);max-width:68ch;margin:0;}
.eyebrow{font-family:"IBM Plex Mono",monospace;font-size:11px;letter-spacing:.16em;
  text-transform:uppercase;color:var(--accent);margin:0 0 10px;}
.note{background:var(--panel);border:1px solid var(--line);border-left:3px solid var(--accent);
  padding:15px 17px;margin:22px 0;max-width:80ch;}
.note p{margin:0 0 8px}.note p:last-child{margin:0}
.note b{color:var(--accent)}
.bar{display:flex;gap:12px;flex-wrap:wrap;align-items:center;margin:18px 0;
  position:sticky;top:0;background:var(--ground);padding:12px 0;z-index:8;
  border-bottom:1px solid var(--line);}
button{font-family:"IBM Plex Mono",monospace;font-size:12px;letter-spacing:.06em;
  text-transform:uppercase;background:var(--panel2);color:var(--ink);
  border:1px solid var(--line);padding:8px 13px;cursor:pointer;}
button:hover{border-color:var(--accent);color:var(--accent)}
button:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
button[aria-pressed="true"]{background:var(--accent);color:var(--ground);border-color:var(--accent)}
button.primary{border-color:var(--accent);color:var(--accent)}
details{border:1px solid var(--line);background:var(--panel);margin:16px 0;}
summary{font-family:Oswald,sans-serif;font-weight:600;font-size:20px;padding:12px 16px;
  cursor:pointer;text-transform:uppercase;letter-spacing:.02em;display:flex;
  justify-content:space-between;align-items:baseline;gap:10px;}
summary span{font-family:"IBM Plex Mono",monospace;font-size:11px;color:var(--muted);
  text-transform:none;letter-spacing:0;font-weight:400;}
summary:focus-visible{outline:2px solid var(--accent);outline-offset:-2px}
.secbody{padding:0 16px 16px}
.blurb{color:var(--muted);font-size:14px;margin:2px 0 12px;max-width:76ch;}
.fam{border:1px solid var(--line);background:var(--panel2);padding:10px 13px;
  display:flex;gap:14px;flex-wrap:wrap;align-items:center;margin:10px 0;}
.fam h3{font-family:Oswald,sans-serif;font-size:14px;margin:0;text-transform:uppercase;
  letter-spacing:.03em;min-width:8ch;}
.slab{display:flex;align-items:center;gap:7px;font-family:"IBM Plex Mono",monospace;
  font-size:10.5px;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);}
input[type=range]{accent-color:var(--accent);width:112px;}
.val{color:var(--accent);font-variant-numeric:tabular-nums;min-width:3ch;}
.said{font-family:"IBM Plex Mono",monospace;font-size:11px;color:var(--accent);}
.grid{display:grid;gap:12px;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));}
.card{background:var(--panel);border:1px solid var(--line);}
.card.hit{border-color:var(--accent)}
.card h4{font-family:"IBM Plex Mono",monospace;font-size:10px;margin:0;padding:5px 7px;
  border-bottom:1px solid var(--line);color:var(--muted);}
.stage{position:relative;padding:6px;display:flex;justify-content:center;background:
  repeating-conic-gradient(var(--panel2) 0 25%, transparent 0 50%) 0 0/12px 12px;
  overflow:auto;}
.box{position:relative;flex:none;}
.box img,.box canvas{image-rendering:pixelated;display:block;position:absolute;
  left:0;top:0;width:100%;height:100%;}
.box img{position:relative}
.meta{font-family:"IBM Plex Mono",monospace;font-size:10px;padding:4px 7px;
  border-top:1px solid var(--line);display:flex;gap:8px;font-variant-numeric:tabular-nums;}
.out{width:100%;min-height:190px;background:var(--panel);color:var(--ink);
  border:1px solid var(--line);font-family:"IBM Plex Mono",monospace;font-size:12px;
  padding:13px;margin-top:16px;resize:vertical;}
footer{margin-top:30px;color:var(--muted);font-size:13.5px;max-width:74ch;}
code{font-family:"IBM Plex Mono",monospace;background:var(--panel2);padding:1px 5px;}
"""

SHELL = r"""
<header>
  <p class="eyebrow">Doom 64 RT &middot; Unseen Evil &middot; glow detection</p>
  <h1>Unseen Evil Glow Families</h1>
  <p class="sub">Colour-detected emissives for the Chaingunner, Spider Mastermind and
  Revenant. Tune each family until the overlay covers what should glow and nothing else,
  then <b>Save marks</b> &mdash; the thresholds are what the generator uses.</p>
</header>

<div class="note">
  <p><b>Why nothing glowed before.</b> RTGL1 takes emission <em>solely</em> from an
  <code>_e</code> override. A flash painted into the albedo, however bright it looks, emits
  nothing without one &mdash; and none of these sprites had an <code>_e</code> at all.</p>
  <p><b>Purity is the discriminator, not hue.</b> A plain "reddish" test matches 425&ndash;2922
  texels per Mastermind frame &mdash; that is its red-brown body. Requiring green and blue
  both near zero gives 13&ndash;26 on the walk (the eyes) and 1187 on H1 (the guns). The
  <em>cap</em> slider is doing more work than the <em>level</em> one; move it first.</p>
  <p><b>One family can mean two things.</b> The Mastermind's eyes and its firing parts are
  the same red; they are told apart by which frame they appear on, not by colour. Same for
  the Revenant's eye dots and its launcher elements on frame J.</p>
</div>

<div class="bar">
  <button id="tScale">Zoom 3&times;</button>
  <button id="tOnly" aria-pressed="false">Only hits</button>
  <button id="cp">Copy result</button>
  <button id="save" class="primary">Save marks</button>
  <span class="said" id="said"></span>
</div>

<div id="sections"></div>
<textarea class="out" id="out" readonly aria-label="Result"></textarea>

<footer>
  <p>Each family is written as its own <code>_e</code> at full range in its own colour,
  never the raw albedo &mdash; <code>RsWorld.inl</code> multiplies by baseColor again, and
  squaring dark art annihilates the glow.</p>
</footer>
"""

BOOT = r"""
const FONTS = __FONTS__;
const DATA = JSON.parse(document.getElementById('data').textContent);
const STATE = JSON.parse(document.getElementById('state').textContent);

const ZOOMS = [1, 2, 3, 5, 8, 12];   // small first: these pages are read
let scale = 3, onlyHits = false;
const T = {};                       // secId.famId -> params
for (const sec of DATA) for (const fam of sec.families){
  const key = sec.id + '.' + fam.id;
  T[key] = Object.assign({}, fam.params, (STATE.t || {})[key] || {});
}
const cells = {};
document.getElementById('app').innerHTML = document.getElementById('shell').innerHTML;
const said = m => { document.getElementById('said').textContent = m || ''; };

function hits(fam, key, r, g, b){
  const p = T[key];
  if (fam.kind === 'pure'){
    // One channel high, the OTHER TWO capped. This is what separates a glowing
    // red from red-brown flesh; a dominance test does not.
    const v = fam.ch === 'r' ? r : fam.ch === 'g' ? g : b;
    const o1 = fam.ch === 'r' ? g : r;
    const o2 = fam.ch === 'b' ? g : b;
    return v >= p.level && o1 <= p.cap && o2 <= p.cap;
  }
  if (fam.kind === 'dominant'){
    const v = fam.ch === 'r' ? r : fam.ch === 'g' ? g : b;
    const o1 = fam.ch === 'r' ? g : r;
    const o2 = fam.ch === 'b' ? g : b;
    return v >= p.level && v - o1 >= p.sep && v - o2 >= p.sep;
  }
  // cool: bright, no channel dark, never warm -- keeps orange-lit skin out.
  const mx = Math.max(r, g, b), mn = Math.min(r, g, b);
  return mx >= p.bright && mn >= p.floor && (b - r) >= p.cool;
}

function paint(sec, f){
  const el = f._el, ctx = el.canvas.getContext('2d');
  const src = cells[f.lump].data;
  const img = ctx.createImageData(f.w, f.h);
  const cs = getComputedStyle(document.documentElement);
  const cols = sec.families.map(fm => {
    const v = cs.getPropertyValue(fm.color).trim();
    return [parseInt(v.slice(1,3),16), parseInt(v.slice(3,5),16), parseInt(v.slice(5,7),16)];
  });
  const counts = sec.families.map(() => 0);
  for (let i = 0, p = 0; i < f.w * f.h; i++, p += 4){
    if (src[p+3] < 128) continue;
    for (let k = 0; k < sec.families.length; k++){
      const fam = sec.families[k];
      if (!fam._on) continue;
      if (hits(fam, sec.id + '.' + fam.id, src[p], src[p+1], src[p+2])){
        counts[k]++;
        const c = cols[k];
        img.data[p] = c[0]; img.data[p+1] = c[1]; img.data[p+2] = c[2]; img.data[p+3] = 195;
        break;
      }
    }
  }
  ctx.putImageData(img, 0, 0);
  el.meta.innerHTML = sec.families.map((fm, k) =>
    '<span style="color:var(' + fm.color + ')">' + counts[k] + '</span>').join('');
  const any = counts.some(n => n > 0);
  el.card.classList.toggle('hit', any);
  el.card.style.display = (onlyHits && !any) ? 'none' : '';
  f._c = counts;
}

function repaintSec(sec){ sec.frames.forEach(f => { if (cells[f.lump]) paint(sec, f); }); emit(); }
const repaintAll = () => DATA.forEach(sec => { if (sec._built) repaintSec(sec); });

function buildSection(sec, body){
  const blurb = document.createElement('p');
  blurb.className = 'blurb'; blurb.textContent = sec.blurb;
  body.appendChild(blurb);

  for (const fam of sec.families){
    fam._on = true;
    const key = sec.id + '.' + fam.id;
    const row = document.createElement('div'); row.className = 'fam';
    const h3 = document.createElement('h3');
    h3.textContent = fam.label; h3.style.color = 'var(' + fam.color + ')';
    row.appendChild(h3);
    for (const [pk, label] of Object.entries(fam.sliders)){
      const wrap = document.createElement('div'); wrap.className = 'slab';
      const lab = document.createElement('label'); lab.textContent = label.name;
      const r = document.createElement('input');
      r.type = 'range'; r.min = String(label.min); r.max = String(label.max);
      r.value = String(T[key][pk]);
      r.setAttribute('aria-label', fam.label + ' ' + label.name + ' for ' + sec.title);
      const v = document.createElement('span'); v.className = 'val'; v.textContent = r.value;
      r.addEventListener('input', () => {
        T[key][pk] = +r.value; v.textContent = r.value; repaintSec(sec); said('unsaved');
      });
      wrap.append(lab, r, v); row.appendChild(wrap);
    }
    const tog = document.createElement('button');
    tog.textContent = 'Show'; tog.setAttribute('aria-pressed', 'true');
    tog.addEventListener('click', () => {
      fam._on = !fam._on; tog.setAttribute('aria-pressed', fam._on); repaintSec(sec);
    });
    row.appendChild(tog);
    body.appendChild(row);
  }

  const grid = document.createElement('div'); grid.className = 'grid';
  for (const f of sec.frames){
    const card = document.createElement('div'); card.className = 'card';
    const h4 = document.createElement('h4'); h4.textContent = f.lump;
    const stage = document.createElement('div'); stage.className = 'stage';
    const box = document.createElement('div'); box.className = 'box';
    box.style.width = (f.w * scale) + 'px'; box.style.height = (f.h * scale) + 'px';
    const img = new Image(); img.src = f.sprite; img.alt = f.lump;
    const canvas = document.createElement('canvas');
    canvas.width = f.w; canvas.height = f.h;
    box.append(img, canvas); stage.appendChild(box);
    const meta = document.createElement('div'); meta.className = 'meta';
    card.append(h4, stage, meta); grid.appendChild(card);
    f._el = {card, box, canvas, meta};
    img.decode().then(() => {
      const c = document.createElement('canvas');
      c.width = f.w; c.height = f.h;
      const cx = c.getContext('2d', {willReadFrequently: true});
      cx.drawImage(img, 0, 0);
      cells[f.lump] = cx.getImageData(0, 0, f.w, f.h);
      paint(sec, f); emit();
    });
  }
  body.appendChild(grid);
  sec._built = true;
}

function build(){
  const root = document.getElementById('sections');
  for (const sec of DATA){
    const d = document.createElement('details');
    const s = document.createElement('summary');
    s.innerHTML = sec.title + '<span>' + sec.frames.length + ' lumps · ' +
      sec.families.map(f => f.label).join(' + ') + '</span>';
    d.appendChild(s);
    const body = document.createElement('div'); body.className = 'secbody';
    d.appendChild(body);
    d.addEventListener('toggle', () => { if (d.open && !sec._built) buildSection(sec, body); });
    root.appendChild(d);
  }
}

function emit(){
  const out = [];
  for (const sec of DATA){
    out.push('# ' + sec.sprite + '  ' + sec.families.map(f =>
      f.id + '(' + Object.entries(T[sec.id + '.' + f.id])
        .map(([k, v]) => k + '=' + v).join(' ') + ')').join('  '));
    if (sec._built){
      for (const f of sec.frames){
        if (!f._c || !f._c.some(n => n)) continue;
        out.push('  ' + f.lump.padEnd(11) + f._c.map((n, k) =>
          sec.families[k].id + '=' + n).join(' '));
      }
    } else {
      out.push('  (section not opened)');
    }
    out.push('');
  }
  document.getElementById('out').value = out.join('\n');
}

document.getElementById('tScale').addEventListener('click', e => {
  const i = ZOOMS.indexOf(scale);
  scale = ZOOMS[(i + 1) % ZOOMS.length];
  e.currentTarget.innerHTML = 'Zoom ' + scale + '×';
  for (const sec of DATA) for (const f of sec.frames) if (f._el){
    f._el.box.style.width = (f.w * scale) + 'px';
    f._el.box.style.height = (f.h * scale) + 'px';
  }
});
document.getElementById('tOnly').addEventListener('click', e => {
  onlyHits = !onlyHits; e.currentTarget.setAttribute('aria-pressed', onlyHits); repaintAll();
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
  const S = '<' + 'script', E = '<' + '/' + 'script>';
  const doc = '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n' +
    '<meta name="viewport" content="width=device-width,initial-scale=1">\n' +
    '<title>Unseen Evil Glow Families</title>\n' + FONTS +
    '\n<style id="css">' + document.getElementById('css').textContent + '</style>\n</head>\n<body>\n' +
    '<template id="shell">' + document.getElementById('shell').innerHTML + '</template>\n' +
    '<div class="wrap" id="app"></div>\n' +
    S + ' id="data" type="application/json">' + document.getElementById('data').textContent + E + '\n' +
    S + ' id="state" type="application/json">' + JSON.stringify({t: T}) + E + '\n' +
    S + ' id="boot">' + document.getElementById('boot').textContent + E + '\n</body>\n</html>';
  try { await artifact.publish(doc); said('saved'); }
  catch (err){
    const code = err && err.code;
    if (code === 'conflict') said('reloading to a newer version…');
    else if (code === 'not_writer' || code === 'not_granted'){
      said('read-only view — use Copy result'); btn.remove(); return;
    } else said('save failed (' + (code || 'error') + ') — use Copy result');
    btn.disabled = false;
  }
});

build(); emit();
"""
