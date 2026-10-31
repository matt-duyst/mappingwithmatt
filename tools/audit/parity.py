#!/usr/bin/env python3
"""Visual parity of the contact band across a change, for CI: the band captured on two servings of the site at the same moments after load.

    python3 tools/audit/parity.py BEFORE_URL AFTER_URL --chrome BINARY --out DIR

At 1440 dark, 1440 light and 390 dark, the band is captured 0.5 s, 2 s and 4 s after navigation on each serving (DIR/parity/...png),
and once more after every section entrance has finished, and
DIR/parity.md reports, for each pair, how many pixels differ and the largest channel difference. The page's own animated layers (the liquid
blob and the branching canvases, which draw from the clock and the pointer) are hidden in both, so a difference belongs to the band.
"""
import base64, io, json, os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); from run import Chrome
from PIL import Image, ImageChops
args = sys.argv[1:]
def opt(name, default=None):
    if name not in args: return default
    i = args.index(name); v = args[i + 1]; del args[i:i + 2]; return v
chrome = opt('--chrome', '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'); out = opt('--out', os.path.join(HERE, 'parity')); before, after = args[0], args[1]
os.makedirs(os.path.join(out, 'parity'), exist_ok=True)
HIDE = "#goo, #land, #land-live { visibility: hidden !important; }"
LIGHT = "(function f() { if (document.documentElement) document.documentElement.setAttribute('data-theme', 'light'); else setTimeout(f, 0); })();"
# every element in the band: its box relative to the band and the computed properties that decide its pixels
DOM = """JSON.stringify((() => { const band = document.querySelector('.band-wrap'), o = band.getBoundingClientRect();
  return [band, ...band.querySelectorAll('*')].map((e, i) => { const r = e.getBoundingClientRect(), cs = getComputedStyle(e);
    return [i + ' ' + e.tagName.toLowerCase() + (e.id ? '#' + e.id : '') + (typeof e.className === 'string' && e.className ? '.' + e.className.trim().split(/\\s+/).join('.') : ''),
      [Math.round(r.left - o.left), Math.round(r.top - o.top), Math.round(r.width), Math.round(r.height)].join(','), cs.color, cs.backgroundColor, cs.backgroundImage.slice(0, 80), cs.opacity, cs.transform, cs.fill, cs.borderColor, cs.boxShadow.slice(0, 60), cs.filter].join(' | ') }); })())"""
# what lies under five points of the captured strip, top to bottom of the stack; the page is scrolled to the band for this and back
UNDER = """JSON.stringify((() => { const band = document.querySelector('.band-wrap'), y0 = scrollY; band.scrollIntoView({ block: 'center' }); const r = band.getBoundingClientRect();
  const name = e => e.tagName.toLowerCase() + (e.id ? '#' + e.id : '') + (typeof e.className === 'string' && e.className ? '.' + e.className.trim().split(/\\s+/).join('.') : '');
  const pts = [[45, 20], [innerWidth / 2, 20], [innerWidth - 45, 20], [45, r.height / 2], [innerWidth - 45, r.height / 2]];
  const out = pts.map(([x, dy]) => Math.round(x) + ',' + Math.round(dy) + ': ' + document.elementsFromPoint(x, r.top + dy).slice(0, 4).map(name).join(' > ')); scrollTo(0, y0); return out; })())"""
def frames(url, w, h, theme):
    c = Chrome(chrome, 9995, os.path.join(HERE, '.tmp', 'parity'), w, h, True); shots = {}; global boxes; boxes = {}
    try:
        for m in ('Page.enable', 'Runtime.enable'): c.send(m)
        c.send('Emulation.setDeviceMetricsOverride', {'width': w, 'height': h, 'deviceScaleFactor': 1, 'mobile': w < 600})
        c.send('Emulation.setEmulatedMedia', {'features': [{'name': 'prefers-color-scheme', 'value': theme}]})
        c.send('Page.addScriptToEvaluateOnNewDocument', {'source': (LIGHT if theme == 'light' else '') + f" document.addEventListener('DOMContentLoaded', () => {{ const s = document.createElement('style'); s.textContent = {json.dumps(HIDE)}; document.head.appendChild(s); }});"})
        c.send('Page.navigate', {'url': url}); t0 = time.time()
        for at in (0.5, 2.0, 4.0, 'entered'):
            if at == 'entered':   # every section entrance finished, so the band is compared in the state a reader scrolls to
                c.js("document.querySelectorAll('.reveal').forEach(e => e.classList.add('in')); true"); c.pump(2.5)
            else:
                while time.time() - t0 < at: c.pump(0.02)
            b = json.loads(c.js("(() => { const el = document.querySelector('.band-wrap'), r = el.getBoundingClientRect(), rv = el.closest('.reveal'); return JSON.stringify({x: r.left, y: r.top + scrollY, w: r.width, h: r.height, entered: rv ? rv.classList.contains('in') : null, opacity: rv ? getComputedStyle(rv).opacity : null}); })()"))
            if at == 'entered': b['dom'] = json.loads(c.js(DOM)); b['under'] = json.loads(c.js(UNDER))
            boxes[at] = b; shots[at] = base64.b64decode(c.send('Page.captureScreenshot', {'format': 'png', 'captureBeyondViewport': True, 'clip': {'x': 0, 'y': b['y'], 'width': w, 'height': b['h'], 'scale': 1}})['data'])
    finally: c.close()
    return shots, dict(boxes)
notes = []
md = ['## Contact band parity', '', '| Cell | Time after load | Pixels differing | Share | Largest channel difference | Band top and height, before / after | Entrance done, before / after | Differing region (x0, y0, x1, y1) |', '|---|---|---|---|---|---|---|---|']
for w, h, theme in ((1440, 900, 'dark'), (1440, 900, 'light'), (390, 844, 'dark')):
    (a, ba), (b, bb) = frames(before, w, h, theme), frames(after, w, h, theme)
    for at in (0.5, 2.0, 4.0, 'entered'):
        ia, ib = Image.open(io.BytesIO(a[at])).convert('RGB'), Image.open(io.BytesIO(b[at])).convert('RGB')
        for name, im in (('before', ia), ('after', ib)): im.save(os.path.join(out, 'parity', f"band-{w}-{theme}-{at if at == 'entered' else str(at) + 's'}-{name}.png"))
        where = f"{round(ba[at]['y'])}, {round(ba[at]['h'])} / {round(bb[at]['y'])}, {round(bb[at]['h'])} | {ba[at]['entered']} (opacity {ba[at]['opacity']}) / {bb[at]['entered']} (opacity {bb[at]['opacity']})"
        if ia.size != ib.size: md.append(f'| {w} {theme} | {at if at == "entered" else str(at) + " s"} | sizes differ: {ia.size} and {ib.size} | | | {where} | |'); continue
        d = ImageChops.difference(ia, ib); px = sum(1 for p in d.getdata() if p != (0, 0, 0)); mx = max(max(p) for p in d.getdata())
        md.append(f'| {w} {theme} | {"every entrance finished" if at == "entered" else str(at) + " s"} | {px} of {ia.size[0] * ia.size[1]} | {px / (ia.size[0] * ia.size[1]):.4%} | {mx} | {where} | {d.getbbox() or "none"} |')
    da, db = ba['entered']['dom'], bb['entered']['dom']
    diff = [f'  - before: {x}\n    after:  {y}' for x, y in zip(da, db) if x != y] + ([f'  - element counts differ: {len(da)} before, {len(db)} after'] if len(da) != len(db) else [])
    notes += ['', f'Under the strip at {w} {theme}, before:', *[f'  - {u}' for u in ba['entered']['under']], f'Under the strip at {w} {theme}, after:', *[f'  - {u}' for u in bb['entered']['under']]]
    notes += ['', f'Band elements that differ at {w} {theme} once every entrance has finished: {len(diff) if diff else "none"}', *diff[:12]]
md += notes
open(os.path.join(out, 'parity.md'), 'w').write('\n'.join(md) + '\n'); print('\n'.join(md))
