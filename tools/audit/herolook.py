#!/usr/bin/env python3
"""The hero's look across a change, at a pinned blob clock, for CI; and proof that the clock parameter is inert when absent.

    python3 tools/audit/herolook.py BEFORE_URL AFTER_URL --chrome BINARY --out DIR [--before-label X] [--after-label Y]
    python3 tools/audit/herolook.py BEFORE_URL AFTER_URL --chrome BINARY --out DIR --noparam

Look check: at ?clock=0, ?clock=5000 and ?clock=20000, at 1440 dark, 1440 light and 390 dark, the hero's first viewport is captured on each
serving once the blob has faded in. The branching canvases (their own clock, which the parameter does not pin) and the typewriter line
(random typing delays) are hidden on both sides, so a difference belongs to the blob, the name's liquid fill or the page. DIR/hero/ holds each
pair side by side, before on the left; DIR/hero.md gives the share of differing pixels and the largest channel difference.

--noparam: each serving is loaded without the parameter and, 2 s after navigation, its DOM is serialized with the values that move every
frame or by chance masked (the blob discs' cx, cy and fill, inline styles, the typed text) and the source text of every script and style
element emptied, since that is the change itself and its console and exceptions are collected;
DIR/noparam.md reports the lines that differ.
"""
import argparse, base64, difflib, io, json, os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); from run import Chrome
from PIL import Image, ImageChops
ap = argparse.ArgumentParser(); ap.add_argument('before'); ap.add_argument('after')
ap.add_argument('--chrome', default='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'); ap.add_argument('--out', default=os.path.join(HERE, 'herolook'))
ap.add_argument('--before-label', default='before'); ap.add_argument('--after-label', default='after'); ap.add_argument('--noparam', action='store_true')
a = ap.parse_args(); os.makedirs(os.path.join(a.out, 'hero'), exist_ok=True)
HIDE = "#land, #land-live, #type { visibility: hidden !important; }"
LIGHT = "(function f() { if (document.documentElement) document.documentElement.setAttribute('data-theme', 'light'); else setTimeout(f, 0); })();"

def open_page(url, w, h, theme, extra=''):
    c = Chrome(a.chrome, 9996, os.path.join(HERE, '.tmp', 'herolook'), w, h, True)
    for m in ('Page.enable', 'Runtime.enable', 'Log.enable'): c.send(m)
    c.send('Emulation.setDeviceMetricsOverride', {'width': w, 'height': h, 'deviceScaleFactor': 1, 'mobile': w < 600})
    c.send('Emulation.setEmulatedMedia', {'features': [{'name': 'prefers-color-scheme', 'value': theme}]})
    c.send('Page.addScriptToEvaluateOnNewDocument', {'source': (LIGHT if theme == 'light' else '') + extra})
    c.send('Page.navigate', {'url': url}); return c

def shot(url, w, h, theme):
    hide = f" document.addEventListener('DOMContentLoaded', () => {{ const s = document.createElement('style'); s.textContent = {json.dumps(HIDE)}; document.head.appendChild(s); }});"
    c = open_page(url, w, h, theme, hide)
    try:
        t0 = time.time()
        while time.time() - t0 < 40 and not c.js("performance.getEntriesByName('hero-ready').length > 0"): c.pump(0.2)
        c.pump(3.0)   # the blob fades in over 1.6 s and its discs take their color over 0.8 s
        return Image.open(io.BytesIO(base64.b64decode(c.send('Page.captureScreenshot', {'format': 'png'})['data']))).convert('RGB')
    finally: c.close()

if a.noparam:
    MASK = """(() => { const d = document.documentElement.cloneNode(true);
      d.querySelectorAll('#goo circle').forEach(e => { e.removeAttribute('cx'); e.removeAttribute('cy'); e.removeAttribute('fill'); });
      d.querySelectorAll('[style]').forEach(e => e.removeAttribute('style')); d.querySelectorAll('script, style').forEach(e => { e.textContent = ''; }); const t = d.querySelector('#typed'); if (t) t.textContent = '';
      return d.outerHTML.replace(/></g, '>\\n<'); })()"""
    md = ['## The clock parameter when absent', '']
    for w, h, theme in ((1440, 900, 'dark'), (390, 844, 'dark')):
        got = {}
        for side, url in (('before', a.before), ('after', a.after)):
            c = open_page(url, w, h, theme)
            try:
                c.pump(2.0); dom = c.js(MASK)
                con = [f"{e['params']['type']}: " + ' '.join(str(x.get('value', x.get('description', ''))) for x in e['params']['args']) for e in c.ev if e.get('method') == 'Runtime.consoleAPICalled']
                con += ['exception: ' + e['params']['exceptionDetails'].get('text', '') for e in c.ev if e.get('method') == 'Runtime.exceptionThrown']
                con += [f"log {e['params']['entry']['level']}: {e['params']['entry']['text']}" for e in c.ev if e.get('method') == 'Log.entryAdded']
                got[side] = (dom.splitlines(), con)
            finally: c.close()
        dd = [l for l in difflib.unified_diff(got['before'][0], got['after'][0], lineterm='', n=0) if l[:1] in '+-' and l[:3] not in ('+++', '---')]
        cd = [l for l in difflib.unified_diff(got['before'][1], got['after'][1], lineterm='', n=0) if l[:1] in '+-' and l[:3] not in ('+++', '---')]
        md += [f"{w} {theme}: DOM lines {len(got['before'][0])} and {len(got['after'][0])}, {len(dd)} differing; console entries {len(got['before'][1])} and {len(got['after'][1])}, {len(cd)} differing.", *[f'    {l[:200]}' for l in (dd + cd)[:20]], '']
    open(os.path.join(a.out, 'noparam.md'), 'w').write('\n'.join(md) + '\n'); print('\n'.join(md)); sys.exit(0)

md = [f"## The hero at a pinned clock: {a.before_label} against {a.after_label}", '', '| Cell | Clock | Pixels differing | Share | Largest channel difference |', '|---|---|---|---|---|']
for w, h, theme in ((1440, 900, 'dark'), (1440, 900, 'light'), (390, 844, 'dark')):
    for clk in (0, 5000, 20000):
        q = f'?clock={clk}'; ia, ib = shot(a.before.rstrip('/') + '/' + q, w, h, theme), shot(a.after.rstrip('/') + '/' + q, w, h, theme)
        pair = Image.new('RGB', (ia.width + ib.width + 8, max(ia.height, ib.height)), (255, 0, 255)); pair.paste(ia, (0, 0)); pair.paste(ib, (ia.width + 8, 0))
        pair.save(os.path.join(a.out, 'hero', f'hero-{w}-{theme}-clock{clk}-{a.before_label}-vs-{a.after_label}.png'))
        if ia.size != ib.size: md.append(f'| {w} {theme} | {clk} | sizes differ | | |'); continue
        d = ImageChops.difference(ia, ib)
        px = sum(1 for p in d.getdata() if p != (0, 0, 0)); mx = max(max(p) for p in d.getdata()) if px else 0
        md.append(f'| {w} {theme} | {clk} | {px} of {ia.width * ia.height} | {px / (ia.width * ia.height):.4%} | {mx} |')
open(os.path.join(a.out, 'hero.md'), 'w').write('\n'.join(md) + '\n'); print('\n'.join(md))
