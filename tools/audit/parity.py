#!/usr/bin/env python3
"""Visual parity of the contact band across a change, for CI: the band captured on two servings of the site at the same moments after load.

    python3 tools/audit/parity.py BEFORE_URL AFTER_URL --chrome BINARY --out DIR

At 1440 dark, 1440 light and 390 dark, the band is captured 0.5 s, 2 s and 4 s after navigation on each serving (DIR/parity/...png), and
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
def frames(url, w, h, theme):
    c = Chrome(chrome, 9995, os.path.join(HERE, '.tmp', 'parity'), w, h, True); shots = {}
    try:
        for m in ('Page.enable', 'Runtime.enable'): c.send(m)
        c.send('Emulation.setDeviceMetricsOverride', {'width': w, 'height': h, 'deviceScaleFactor': 1, 'mobile': w < 600})
        c.send('Emulation.setEmulatedMedia', {'features': [{'name': 'prefers-color-scheme', 'value': theme}]})
        c.send('Page.addScriptToEvaluateOnNewDocument', {'source': (LIGHT if theme == 'light' else '') + f" document.addEventListener('DOMContentLoaded', () => {{ const s = document.createElement('style'); s.textContent = {json.dumps(HIDE)}; document.head.appendChild(s); }});"})
        c.send('Page.navigate', {'url': url}); t0 = time.time()
        for at in (0.5, 2.0, 4.0):
            while time.time() - t0 < at: c.pump(0.02)
            b = json.loads(c.js("(() => { const r = document.querySelector('.band-wrap').getBoundingClientRect(); return JSON.stringify({x: r.left, y: r.top + scrollY, w: r.width, h: r.height}); })()"))
            shots[at] = base64.b64decode(c.send('Page.captureScreenshot', {'format': 'png', 'captureBeyondViewport': True, 'clip': {'x': 0, 'y': b['y'], 'width': w, 'height': b['h'], 'scale': 1}})['data'])
    finally: c.close()
    return shots
md = ['## Contact band parity', '', '| Cell | Time after load | Pixels differing | Share | Largest channel difference |', '|---|---|---|---|---|']
for w, h, theme in ((1440, 900, 'dark'), (1440, 900, 'light'), (390, 844, 'dark')):
    a, b = frames(before, w, h, theme), frames(after, w, h, theme)
    for at in (0.5, 2.0, 4.0):
        ia, ib = Image.open(io.BytesIO(a[at])).convert('RGB'), Image.open(io.BytesIO(b[at])).convert('RGB')
        for name, im in (('before', ia), ('after', ib)): im.save(os.path.join(out, 'parity', f'band-{w}-{theme}-{at}s-{name}.png'))
        if ia.size != ib.size: md.append(f'| {w} {theme} | {at} s | sizes differ: {ia.size} and {ib.size} | | |'); continue
        d = ImageChops.difference(ia, ib); px = sum(1 for p in d.getdata() if p != (0, 0, 0)); mx = max(max(p) for p in d.getdata())
        md.append(f'| {w} {theme} | {at} s | {px} of {ia.size[0] * ia.size[1]} | {px / (ia.size[0] * ia.size[1]):.4%} | {mx} |')
open(os.path.join(out, 'parity.md'), 'w').write('\n'.join(md) + '\n'); print('\n'.join(md))
