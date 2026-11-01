#!/usr/bin/env python3
"""The map's label glyphs on one serving of the main page, for CI: every glyph range requested and every failed request.

    python3 tools/audit/glyphcheck.py URL --chrome BINARY --out DIR

At 1440 x 900 and 390 x 844, dark, the page is scrolled top to bottom with a stop at the map until it settles, then every "on the map"
button in the record (or, on a page without the record, every stop tab on the map) is pressed in turn and the map's flight to that stop is given 6 s. DIR/glyphs.md lists each glyph range with its HTTP
status, every response at or above 400, and every console error and uncaught exception; the exit code is 1 when any glyph request fails
or any console error or exception is logged.
"""
import argparse, json, os, sys, time, urllib.parse
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); from run import Chrome
ap = argparse.ArgumentParser(); ap.add_argument('url')
ap.add_argument('--chrome', default='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'); ap.add_argument('--out', default=os.path.join(HERE, 'glyphs'))
a = ap.parse_args(); os.makedirs(a.out, exist_ok=True)
md = [f'## Map glyphs at {a.url}', '']; bad = 0
for w, h in ((1440, 900), (390, 844)):
    c = Chrome(a.chrome, 9997, os.path.join(HERE, '.tmp', 'glyphs'), w, h, True)
    try:
        for m in ('Page.enable', 'Runtime.enable', 'Network.enable', 'Log.enable'): c.send(m)
        c.send('Network.setCacheDisabled', {'cacheDisabled': True})
        c.send('Emulation.setDeviceMetricsOverride', {'width': w, 'height': h, 'deviceScaleFactor': 1, 'mobile': w < 600})
        c.send('Emulation.setEmulatedMedia', {'features': [{'name': 'prefers-color-scheme', 'value': 'dark'}]})
        c.send('Page.navigate', {'url': a.url}); t0 = time.time()
        while time.time() - t0 < 40 and not c.js("performance.getEntriesByName('hero-ready').length > 0"): c.pump(0.2)
        c.js("(async () => { const m = document.getElementById('map'); const stop = m.getBoundingClientRect().top + scrollY; for (let y = 0; y < stop; y += 450) { scrollTo(0, y); await new Promise(r => setTimeout(r, 220)); } m.scrollIntoView({ block: 'center' }); await new Promise(r => setTimeout(r, 12000)); for (let y = scrollY; y < document.body.scrollHeight; y += 450) { scrollTo(0, y); await new Promise(r => setTimeout(r, 220)); } return true; })()", wait=True)
        # the record's "on the map" buttons where the page has them; otherwise (main, before the record) the map's own stop tabs
        sel = '.on-map' if int(c.js("document.querySelectorAll('.on-map').length")) else '#rt-app .tab'
        n = int(c.js(f"document.querySelectorAll({json.dumps(sel)}).length"))
        for i in range(n):
            pre = "scrollTo(0, 0); " if sel == '.on-map' else "document.getElementById('map').scrollIntoView({ block: 'center' }); "
            c.js(f"{pre}document.querySelectorAll({json.dumps(sel)})[{i}].click(); true"); c.pump(6.0)
        seen, fails = {}, []
        for e in c.ev:
            if e.get('method') != 'Network.responseReceived': continue
            u, st = e['params']['response']['url'], e['params']['response']['status']
            if '/vendor/glyphs/' in u: seen.setdefault(urllib.parse.unquote(u.split('/vendor/glyphs/', 1)[1]), st)
            if st >= 400: fails.append(f'{st} {u}')
        g404 = [k for k, v in seen.items() if v >= 400]; bad += len(g404)
        console = [e['params']['entry']['text'][:160] for e in c.ev if e.get('method') == 'Log.entryAdded' and e['params']['entry']['level'] == 'error'] + \
                  ['exception: ' + e['params']['exceptionDetails'].get('text', '')[:160] for e in c.ev if e.get('method') == 'Runtime.exceptionThrown']
        bad += len(console)
        md += [f'{w}: {n} stop flights through {sel}; glyph ranges requested: ' + (', '.join(f'{v} {k}' for k, v in seen.items()) or 'none'),
               f'{w}: glyph requests failing: {len(g404)}; all responses at or above 400: {len(fails)}; console errors and exceptions: {len(console)}',
               *[f'    {f}' for f in fails[:20]], *[f'    console: {x}' for x in console[:20]], '']
    finally: c.close()
open(os.path.join(a.out, 'glyphs.md'), 'w').write('\n'.join(md) + '\n'); print('\n'.join(md)); sys.exit(1 if bad else 0)
