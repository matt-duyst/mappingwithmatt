"""A close 400 by 300 crop of one tree at full growth: the page is loaded at 1440 in the dark scheme with ?seeds=3&glow=off and its content
hidden, frames are taken for 14 s, and the densest 400 by 300 window of any frame is saved.
Usage: python3 tools/audit/crop.py http://localhost:8000 [--out tree.png]"""
import argparse, base64, io, os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from run import Chrome
from PIL import Image, ImageOps
CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('root'); ap.add_argument('--out', default=os.path.join(HERE, 'tree.png')); ap.add_argument('--port', type=int, default=9976); ap.add_argument('--tmp', default=os.path.join(HERE, '.tmp'))
    a = ap.parse_args(); os.makedirs(a.tmp, exist_ok=True)
    c = Chrome(CHROME, a.port, os.path.join(a.tmp, 'crop'), 1440, 900, False); best = None
    try:
        for m in ('Page.enable', 'Runtime.enable'): c.send(m)
        c.send('Emulation.setDeviceMetricsOverride', {'width': 1440, 'height': 900, 'deviceScaleFactor': 1, 'mobile': False})
        c.send('Emulation.setEmulatedMedia', {'features': [{'name': 'prefers-color-scheme', 'value': 'dark'}]})
        c.send('Page.addScriptToEvaluateOnNewDocument', {'source': "try { sessionStorage.setItem('mwm-welcome', '1'); } catch (e) {} document.addEventListener('DOMContentLoaded', () => { const st = document.createElement('style'); st.textContent = '#goo, .intro, main, footer, #rail { visibility: hidden !important; }'; document.head.appendChild(st); });"})
        c.send('Page.navigate', {'url': a.root.rstrip('/') + '/?seeds=3&glow=off'}); c.pump(1.0); t0 = time.time()
        while time.time() - t0 < 14:
            d = c.send('Page.captureScreenshot', {'format': 'png', 'clip': {'x': 0, 'y': 0, 'width': 1440, 'height': 900, 'scale': 1}})['data']
            im = Image.open(io.BytesIO(base64.b64decode(d))).convert('RGB'); ink = ImageOps.grayscale(im).point(lambda v: 255 if v > 24 else 0)
            for x in range(0, 1440 - 400, 40):
                for y in range(0, 900 - 300, 40):
                    score = sum(ink.crop((x, y, x + 400, y + 300)).resize((40, 30)).tobytes())
                    if best is None or score > best[0]: best = (score, im.crop((x, y, x + 400, y + 300)), (x, y))
            c.pump(1.0)
    finally: c.close()
    best[1].save(a.out); print('wrote', a.out, 'from window at', best[2])

if __name__ == '__main__': main()
