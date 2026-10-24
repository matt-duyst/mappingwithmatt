"""Branching population counts over 30 s, read from window.mwmLand.stats() every 5 s after the hero lifts, with a capture at the end.
Usage: python3 tools/audit/life.py http://localhost:8000 <width> [--query '?pulse=2'] [--seconds 30] [--out life.png]

Each row holds the seconds since the lift and the live, growing and withdrawing branches, live segments, settled and withdrawn branches,
firings started, cascade hops and the breath's tempo. Chrome renders with the GPU in the dark scheme."""
import argparse, base64, json, os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from run import Chrome
CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
KEYS = ['since', 'live', 'growing', 'withdrawing', 'liveSegments', 'settled', 'withdrawn', 'firings', 'hops', 'tempo']

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('root'); ap.add_argument('width', type=int); ap.add_argument('--query', default=''); ap.add_argument('--seconds', type=float, default=30)
    ap.add_argument('--out', default=os.path.join(HERE, 'life.png')); ap.add_argument('--port', type=int, default=9975); ap.add_argument('--tmp', default=os.path.join(HERE, '.tmp'))
    a = ap.parse_args(); os.makedirs(a.tmp, exist_ok=True); h, dpr = (900, 2) if a.width >= 1000 else (844, 3)
    c = Chrome(CHROME, a.port, os.path.join(a.tmp, f'life-{a.width}'), a.width, h, False); rows = []
    try:
        for m in ('Page.enable', 'Runtime.enable'): c.send(m)
        c.send('Emulation.setDeviceMetricsOverride', {'width': a.width, 'height': h, 'deviceScaleFactor': dpr, 'mobile': a.width < 600})
        c.send('Emulation.setEmulatedMedia', {'features': [{'name': 'prefers-color-scheme', 'value': 'dark'}]})
        c.send('Page.addScriptToEvaluateOnNewDocument', {'source': "try { sessionStorage.setItem('mwm-welcome', '1'); } catch (e) {}"})
        c.send('Page.navigate', {'url': a.root.rstrip('/') + '/' + a.query}); t0 = time.time()
        while time.time() - t0 < 20 and not c.js("performance.getEntriesByName('hero-lift').length > 0 && !!window.mwmLand"): c.pump(0.2)
        t0 = time.time()
        while time.time() - t0 <= a.seconds:
            st = json.loads(c.js('JSON.stringify(window.mwmLand ? window.mwmLand.stats() : {})')); rows.append([st.get(k) for k in KEYS])
            c.pump(5.0)
        d = c.send('Page.captureScreenshot', {'format': 'png', 'clip': {'x': 0, 'y': 0, 'width': a.width, 'height': h, 'scale': 1}})['data']; open(a.out, 'wb').write(base64.b64decode(d))
        errors = [e['params']['exceptionDetails'].get('text', '')[:120] for e in c.ev if e.get('method') == 'Runtime.exceptionThrown']
    finally: c.close()
    print(json.dumps({'width': a.width, 'query': a.query, 'keys': KEYS, 'series': rows, 'errors': errors, 'capture': a.out}))

if __name__ == '__main__': main()
