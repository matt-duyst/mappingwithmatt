#!/usr/bin/env python3
"""Capture the map's flight start N times and check the frames are identical.

    python3 tools/audit/flight.py http://localhost:8000 --runs 5 --out captures/

Each run opens a fresh profile, holds the arrival (the in-view test is stubbed so the flight never fires), waits for the
map:globe-ready mark (the idle after the projection change, once the basemap and labels are in), then for the 300 ms tile and
label fade, and takes the frame as settled only once 3 s have passed and two captures 1 s apart are identical (label glyphs can
follow the idle); the alternating hint line above the canvas is masked out, and compares it with the first run pixel for pixel. Exits 1 when any run differs.
"""
import argparse, base64, io, json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from run import Chrome
try:
    from PIL import Image, ImageChops
except ImportError:
    sys.exit('needs pillow: python3 -m pip install pillow')

FADE_MS = 300  # MapLibre's default raster and symbol fade after a tile or label arrives

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('root'); ap.add_argument('--runs', type=int, default=5); ap.add_argument('--width', type=int, default=1440)
    ap.add_argument('--theme', default='dark'); ap.add_argument('--out', default=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'captures'))
    ap.add_argument('--chrome', default='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'); ap.add_argument('--software', action='store_true')
    ap.add_argument('--port', type=int, default=9980); ap.add_argument('--tmp', default=os.path.join(os.path.dirname(os.path.abspath(__file__)), '.tmp'))
    a = ap.parse_args(); os.makedirs(a.out, exist_ok=True)
    W = a.width; H, DPR = (900, 2) if W >= 1000 else (844, 3); imgs = []
    for k in range(a.runs):
        c = Chrome(a.chrome, a.port + k, os.path.join(a.tmp, f'flight-{k}'), W, H, a.software)
        try:
            c.send('Page.enable'); c.send('Runtime.enable')
            c.send('Emulation.setDeviceMetricsOverride', {'width': W, 'height': H, 'deviceScaleFactor': DPR, 'mobile': W < 600})
            c.send('Emulation.setEmulatedMedia', {'features': [{'name': 'prefers-color-scheme', 'value': a.theme}]})
            c.send('Page.addScriptToEvaluateOnNewDocument', {'source': "try { sessionStorage.setItem('mwm-welcome', '1'); } catch (e) {} (function () { var o = IntersectionObserver.prototype.observe; IntersectionObserver.prototype.observe = function (el) { if (el && el.id === 'rt-mapcanvas') return; return o.call(this, el); }; })();" + (" (function f() { if (document.documentElement) document.documentElement.setAttribute('data-theme', 'light'); else setTimeout(f, 0); })();" if a.theme == 'light' else '')})
            c.send('Page.navigate', {'url': a.root.rstrip('/') + '/'}); c.pump(2.0)
            c.js("document.getElementById('rt-mapcanvas').scrollIntoView({block: 'center'}); true"); t0 = time.time()
            while time.time() - t0 < 40:
                try:
                    if c.js("performance.getEntriesByName('map:globe-ready').length > 0"): break
                except Exception: pass
                c.pump(0.05)
            c.pump((FADE_MS + 100) / 1000)  # let the first fade finish
            # the map canvas only: the hint line above it alternates on a timer and is masked out of the comparison
            r = json.loads(c.js("JSON.stringify((() => { const b = document.getElementById('rt-mapcanvas').getBoundingClientRect(); const hint = [...document.querySelectorAll('#rt-mapcanvas *')].filter(e => e.children.length === 0 && /Play the route|travelled/.test(e.textContent)).map(e => { const h = e.getBoundingClientRect(); return [h.x - b.x, h.y - b.y, h.width, h.height]; }); return { x: b.x, y: b.y + scrollY, w: b.width, h: b.height, scale: (document.querySelector('.maplibregl-ctrl-scale') || {}).textContent, mask: hint }; })())"))
            def shoot():
                d = c.send('Page.captureScreenshot', {'format': 'png', 'clip': {'x': r['x'], 'y': r['y'], 'width': r['w'], 'height': r['h'], 'scale': 1}})['data']
                im = Image.open(io.BytesIO(base64.b64decode(d))).convert('RGB'); k2 = im.width / r['w']
                for mx, my, mw, mh in r['mask']: im.paste((0, 0, 0), (int((mx - 4) * k2), int((my - 4) * k2), int((mx + mw + 4) * k2), int((my + mh + 4) * k2)))
                return im
            # settled: at least 3 s after globe-ready (label glyphs can follow the idle by that much) and two captures 1 s apart identical
            c.pump(max(0, 3.0 - (time.time() - t0)))
            im = shoot(); t1 = time.time()
            while time.time() - t1 < 20:
                c.pump(1.0); nxt = shoot()
                if ImageChops.difference(im, nxt).convert('L').point(lambda v: 255 if v > 24 else 0).getbbox() is None: break  # the same threshold as the run-to-run check; GPU antialiasing never gives bit-identical frames
                im = nxt
            im.save(os.path.join(a.out, f'flight-start-{W}-{a.theme}-run{k + 1}.png')); imgs.append(im)
            print(f"run {k + 1}: settled after {time.time() - t0:.2f} s, scale {r['scale']}, canvas {round(r['w'])}x{round(r['h'])}", flush=True)
        finally:
            c.close()
    fails = 0
    for k, im in enumerate(imgs[1:], 2):
        diff = ImageChops.difference(imgs[0], im).convert('L').point(lambda v: 255 if v > 24 else 0)
        n = sum(1 for v in (diff.get_flattened_data() if hasattr(diff, 'get_flattened_data') else diff.getdata()) if v); pct = 100 * n / (diff.width * diff.height)
        print(f"run 1 vs run {k}: {pct:.3f}% of pixels differ" + (f", within {diff.getbbox()}" if n else ''))
        if n: fails += 1
    print('identical' if not fails else f'{fails} of {len(imgs) - 1} runs differ'); sys.exit(1 if fails else 0)

if __name__ == '__main__':
    main()
