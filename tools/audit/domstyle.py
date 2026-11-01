#!/usr/bin/env python3
"""Proof that a change renders nothing differently, for CI: the page's text and every element's computed style on two commits.

    python3 tools/audit/domstyle.py BEFORE_URL AFTER_URL --chrome BINARY --out DIR

At 1440 x 900 and 390 x 844, dark, each serving is loaded with prefers-reduced-motion: reduce, so the typewriter shows its whole text, the
blob and the mark stay still and nothing moves between the two loads. Once the page is ready it records the body's text and, for every element
in document order, its tag and id and every computed style property, sorted by name, since Chrome lists custom properties in no fixed order. DIR/domstyle.md reports how many elements and text lines differ and
lists the first differences; the exit code is 1 when anything differs.
"""
import argparse, difflib, json, os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); from run import Chrome
ap = argparse.ArgumentParser(); ap.add_argument('before'); ap.add_argument('after')
ap.add_argument('--chrome', default='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'); ap.add_argument('--out', default=os.path.join(HERE, 'domstyle'))
a = ap.parse_args(); os.makedirs(a.out, exist_ok=True)
SNAP = """JSON.stringify({ text: document.body.innerText, styles: [...document.querySelectorAll('*')].map(e => { const cs = getComputedStyle(e);
  return e.tagName.toLowerCase() + (e.id ? '#' + e.id : '') + ' ' + [...cs].sort().map(p => p + ':' + cs.getPropertyValue(p)).join(';'); }) })"""

def snap(url, w, h):
    c = Chrome(a.chrome, 9998, os.path.join(HERE, '.tmp', 'domstyle'), w, h, True)
    try:
        for m in ('Page.enable', 'Runtime.enable'): c.send(m)
        c.send('Emulation.setDeviceMetricsOverride', {'width': w, 'height': h, 'deviceScaleFactor': 1, 'mobile': w < 600})
        c.send('Emulation.setEmulatedMedia', {'features': [{'name': 'prefers-color-scheme', 'value': 'dark'}, {'name': 'prefers-reduced-motion', 'value': 'reduce'}]})
        c.send('Page.navigate', {'url': url}); t0 = time.time()
        while time.time() - t0 < 40 and not c.js("performance.getEntriesByName('hero-ready').length > 0"): c.pump(0.2)
        c.pump(3.0); return json.loads(c.js(SNAP))
    finally: c.close()

md = ['## Rendered text and computed styles', '']; bad = 0
for w, h in ((1440, 900), (390, 844)):
    x, y = snap(a.before, w, h), snap(a.after, w, h)
    td = [l for l in difflib.unified_diff(x['text'].splitlines(), y['text'].splitlines(), lineterm='', n=0) if l[:1] in '+-' and l[:3] not in ('+++', '---')]
    sd = [(p, q) for p, q in zip(x['styles'], y['styles']) if p != q]
    count = len(sd) + abs(len(x['styles']) - len(y['styles'])); bad += count + len(td)
    md += [f"{w}: {len(x['styles'])} and {len(y['styles'])} elements, {count} with a differing computed style; {len(x['text'].splitlines())} and {len(y['text'].splitlines())} text lines, {len(td)} differing."]
    for p, q in sd[:5]:
        pp, qq = p.split(' ', 1)[1].split(';'), q.split(' ', 1)[1].split(';')
        md.append(f"    {p.split(' ', 1)[0]}: " + ' | '.join(f'{x} -> {y}' for x, y in zip(pp, qq) if x != y)[:400] + (f' (property counts {len(pp)} and {len(qq)})' if len(pp) != len(qq) else ''))
    md += [f'    {l[:200]}' for l in td[:10]]
open(os.path.join(a.out, 'domstyle.md'), 'w').write('\n'.join(md) + '\n'); print('\n'.join(md)); sys.exit(1 if bad else 0)
