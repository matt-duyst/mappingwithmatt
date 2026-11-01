#!/usr/bin/env python3
"""The hero's look across a change, at a pinned blob clock, for CI; and proof that the clock parameter is inert when absent.

    python3 tools/audit/herolook.py BEFORE_URL AFTER_URL --chrome BINARY --out DIR [--before-label X] [--after-label Y]
    python3 tools/audit/herolook.py BEFORE_URL AFTER_URL --chrome BINARY --out DIR --noparam
    python3 tools/audit/herolook.py BEFORE_URL AFTER_URL --chrome BINARY --out DIR --blob [--dpr 2]

Look check: at ?clock=0, ?clock=5000 and ?clock=20000, at 1440 dark, 1440 light and 390 dark, the hero's first viewport is captured on each
serving once the blob has faded in. The branching canvases (their own clock, which the parameter does not pin) and the typewriter line
(random typing delays) are hidden on both sides, so a difference belongs to the blob, the name's liquid fill or the page. DIR/hero/ holds each
pair side by side, before on the left; DIR/hero.md gives the share of differing pixels and the largest channel difference.

--noparam: each serving is loaded without the parameter and, 2 s after navigation, its DOM is serialized with the values that move every
frame or by chance masked (the blob discs' cx, cy and fill, inline styles, the typed text) and the source text of every script and style
element emptied, since that is the change itself and its console and exceptions are collected;
DIR/noparam.md reports the lines that differ.

--blob (report only): the blob layer alone, every other layer hidden, the page's backgrounds cleared and the layer's blend mode set to normal
on both sides alike, captured with a transparent background at the same clocks and cells. A pixel is covered when its alpha is at least
half the layer's full alpha (0.9 layer opacity times 0.5 group opacity, so 0.225, or 57 of 255). For each side DIR/blob.md gives the covered
area in CSS pixels, the connected blobs of 50 px or more with their centroids in CSS pixels, and the circular mean hue of the covered pixels;
then the area difference in percent, the largest offset from a blob's centroid to the nearest blob on the other side, and the hue difference
in degrees, beside the targets (area within 3 percent, centroids within 4 px, hue within 5 degrees). It also records the viewport's inner
and client widths and the device pixel ratio, since a classic scrollbar makes the two widths differ.

--dpr N renders at device scale factor N (default 1) for the look check and the blob measure; the blob measure works on the CSS-pixel grid.
"""
import argparse, base64, colorsys, difflib, io, json, math, os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); from run import Chrome
from PIL import Image, ImageChops
ap = argparse.ArgumentParser(); ap.add_argument('before'); ap.add_argument('after')
ap.add_argument('--chrome', default='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'); ap.add_argument('--out', default=os.path.join(HERE, 'herolook'))
ap.add_argument('--before-label', default='before'); ap.add_argument('--after-label', default='after'); ap.add_argument('--noparam', action='store_true')
ap.add_argument('--blob', action='store_true'); ap.add_argument('--dpr', type=float, default=1)
a = ap.parse_args(); os.makedirs(os.path.join(a.out, 'hero'), exist_ok=True)
HIDE = "#land, #land-live, #type { visibility: hidden !important; }"
LIGHT = "(function f() { if (document.documentElement) document.documentElement.setAttribute('data-theme', 'light'); else setTimeout(f, 0); })();"

def open_page(url, w, h, theme, extra=''):
    c = Chrome(a.chrome, 9996, os.path.join(HERE, '.tmp', 'herolook'), w, h, True)
    for m in ('Page.enable', 'Runtime.enable', 'Log.enable'): c.send(m)
    c.send('Emulation.setDeviceMetricsOverride', {'width': w, 'height': h, 'deviceScaleFactor': a.dpr, 'mobile': w < 600})
    c.send('Emulation.setEmulatedMedia', {'features': [{'name': 'prefers-color-scheme', 'value': theme}]})
    c.send('Page.addScriptToEvaluateOnNewDocument', {'source': (LIGHT if theme == 'light' else '') + extra})
    c.send('Page.navigate', {'url': url}); return c

BLOB_ONLY = "body > :not(#goo) { visibility: hidden !important; } html, body { background: transparent !important; } #goo { mix-blend-mode: normal !important; }"
def shot(url, w, h, theme, blob=False):
    hide = f" document.addEventListener('DOMContentLoaded', () => {{ const s = document.createElement('style'); s.textContent = {json.dumps(BLOB_ONLY if blob else HIDE)}; document.head.appendChild(s); }});"
    c = open_page(url, w, h, theme, hide)
    try:
        if blob: c.send('Emulation.setDefaultBackgroundColorOverride', {'color': {'r': 0, 'g': 0, 'b': 0, 'a': 0}})
        t0 = time.time()
        while time.time() - t0 < 40 and not c.js("performance.getEntriesByName('hero-ready').length > 0"): c.pump(0.2)
        c.pump(3.0)   # the blob fades in over 1.6 s and its discs take their color over 0.8 s
        im = Image.open(io.BytesIO(base64.b64decode(c.send('Page.captureScreenshot', {'format': 'png'})['data'])))
        if blob: shot.widths = json.loads(c.js("JSON.stringify([innerWidth, document.documentElement.clientWidth, devicePixelRatio])")); return im.convert('RGBA')
        return im.convert('RGB')
    finally: c.close()

COVER = 57   # alpha at or above half the layer's full alpha, 0.9 x 0.5 x 255 / 2
def measure(im, w, h):
    """Covered area, connected blobs of 50 px or more with their centroids, and the circular mean hue, on the CSS-pixel grid."""
    if im.size != (w, h): im = im.resize((w, h), Image.BOX)
    data = list(im.getdata()); cover = bytearray(1 if p[3] >= COVER else 0 for p in data)
    area = sum(cover); sx = sy = 0.0
    for i in range(w * h):
        if cover[i]:
            r, g, b, al = data[i]; hh = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)[0] * 2 * math.pi; sx += math.cos(hh); sy += math.sin(hh)
    hue = (math.degrees(math.atan2(sy, sx)) + 360) % 360 if area else None
    seen, blobs = bytearray(w * h), []
    for i0 in range(w * h):
        if cover[i0] and not seen[i0]:
            stack, n, cx, cy = [i0], 0, 0, 0; seen[i0] = 1
            while stack:
                i = stack.pop(); x, y = i % w, i // w; n += 1; cx += x; cy += y
                for j, ok in ((i + 1, x + 1 < w), (i - 1, x > 0), (i + w, y + 1 < h), (i - w, y > 0)):
                    if ok and cover[j] and not seen[j]: seen[j] = 1; stack.append(j)
            if n >= 50: blobs.append((round(cx / n, 1), round(cy / n, 1), n))
    return area, sorted(blobs, key=lambda b: -b[2]), hue

if a.blob:
    md = [f"## The blob layer alone, {a.before_label} against {a.after_label}, device pixel ratio {a.dpr:g}", '', 'Targets: area within 3 percent, centroids within 4 px, hue within 5 degrees.', '',
          '| Cell | Clock | Area before / after (CSS px) | Area difference | Blobs before / after | Largest centroid offset (px) | Hue before / after | Hue difference | Targets met |', '|---|---|---|---|---|---|---|---|---|']
    widths = {}
    for w, h, theme in ((1440, 900, 'dark'), (1440, 900, 'light'), (390, 844, 'dark')):
        for clk in (0, 5000, 20000):
            q = f'?clock={clk}'; ia = shot(a.before.rstrip('/') + '/' + q, w, h, theme, True); wa = shot.widths; ib = shot(a.after.rstrip('/') + '/' + q, w, h, theme, True); widths[f'{w} {theme}'] = (wa, shot.widths)
            (aa, ba, ha), (ab, bb, hb) = measure(ia, w, h), measure(ib, w, h)
            da = (ab - aa) / aa * 100 if aa else float('nan')
            offs = [min(math.hypot(x - u, y - v) for u, v, _ in bb) for x, y, _ in ba] + [min(math.hypot(x - u, y - v) for u, v, _ in ba) for x, y, _ in bb] if ba and bb else []
            dh = abs(((hb - ha) + 180) % 360 - 180) if ha is not None and hb is not None else float('nan')
            ok = bool(offs) and abs(da) <= 3 and max(offs) <= 4 and dh <= 5
            md.append(f"| {w} {theme} | {clk} | {aa} / {ab} | {da:+.2f}% | {len(ba)} / {len(bb)} | {max(offs) if offs else float('nan'):.1f} | {'none' if ha is None else round(ha, 1)} / {'none' if hb is None else round(hb, 1)} | {dh:.1f} | {'yes' if ok else 'no'} |")
    md += ['', 'Viewport, before then after (inner width, client width, device pixel ratio): ' + '; '.join(f"{k}: {v[0]} / {v[1]}" for k, v in widths.items())]
    name = 'blob.md' if a.dpr == 1 else f'blob-dpr{a.dpr:g}.md'
    open(os.path.join(a.out, name), 'w').write('\n'.join(md) + '\n'); print('\n'.join(md)); sys.exit(0)

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

md = [f"## The hero at a pinned clock: {a.before_label} against {a.after_label}, device pixel ratio {a.dpr:g}", '', '| Cell | Clock | Pixels differing | Share | Largest channel difference |', '|---|---|---|---|---|']
for w, h, theme in ((1440, 900, 'dark'), (1440, 900, 'light'), (390, 844, 'dark')):
    for clk in (0, 5000, 20000):
        q = f'?clock={clk}'; ia, ib = shot(a.before.rstrip('/') + '/' + q, w, h, theme), shot(a.after.rstrip('/') + '/' + q, w, h, theme)
        pair = Image.new('RGB', (ia.width + ib.width + 8, max(ia.height, ib.height)), (255, 0, 255)); pair.paste(ia, (0, 0)); pair.paste(ib, (ia.width + 8, 0))
        pair.save(os.path.join(a.out, 'hero', f'hero-{w}-{theme}-clock{clk}' + (f'-dpr{a.dpr:g}' if a.dpr != 1 else '') + f'-{a.before_label}-vs-{a.after_label}.png'))
        if ia.size != ib.size: md.append(f'| {w} {theme} | {clk} | sizes differ | | |'); continue
        d = ImageChops.difference(ia, ib)
        px = sum(1 for p in d.getdata() if p != (0, 0, 0)); mx = max(max(p) for p in d.getdata()) if px else 0
        md.append(f'| {w} {theme} | {clk} | {px} of {ia.width * ia.height} | {px / (ia.width * ia.height):.4%} | {mx} |')
open(os.path.join(a.out, 'hero.md' if a.dpr == 1 else f'hero-dpr{a.dpr:g}.md'), 'w').write('\n'.join(md) + '\n'); print('\n'.join(md))
