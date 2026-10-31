#!/usr/bin/env python3
"""Review captures for the About and record, one headless session per capture, for CI.

    python3 tools/audit/capture.py URL --chrome BINARY --out DIR

The About at 1440 (dark and light), at 1100 (dark), and at 390 (dark) with "keep reading" closed and open; the Grassroots Carbon entry at 1440
(dark) with "read the rest" open; the full page with every fold closed at 1440 (dark); the opening line and the mark under it at 1440 (dark)
with the mark's color cycle held at 0 s and at 16 s, each with the three stops' computed colors in mark.json; the map card after the map has flown to a stop, dark and light
(with --card-only and --label, that pair alone, for another serving); and a WebM at 1440 (dark), 15 s, scrolling from the
About through the record. Screencast frames are replayed on a canvas and encoded by MediaRecorder as VP9. The contact band's parity frames
come from parity.py.
"""
import base64, json, os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); from run import Chrome
args = sys.argv[1:]
def opt(name, default=None):
    if name not in args: return default
    i = args.index(name); v = args[i + 1]; del args[i:i + 2]; return v
chrome = opt('--chrome', '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'); out = opt('--out', os.path.join(HERE, 'captures')); label = opt('--label', 'after')
card_only = '--card-only' in args; args = [x for x in args if x != '--card-only']; root = args[0] if args else 'http://localhost:8000/'
os.makedirs(out, exist_ok=True); LIGHT = "(function f() { if (document.documentElement) document.documentElement.setAttribute('data-theme', 'light'); else setTimeout(f, 0); })();"
def page(w, h, theme='dark', dpr=1):
    c = Chrome(chrome, 9991, os.path.join(HERE, '.tmp', 'capture'), w, h, True)
    for m in ('Page.enable', 'Runtime.enable'): c.send(m)
    c.send('Emulation.setDeviceMetricsOverride', {'width': w, 'height': h, 'deviceScaleFactor': dpr, 'mobile': w < 600})
    c.send('Emulation.setEmulatedMedia', {'features': [{'name': 'prefers-color-scheme', 'value': theme}]})
    if theme == 'light': c.send('Page.addScriptToEvaluateOnNewDocument', {'source': LIGHT})
    c.send('Page.navigate', {'url': root}); t0 = time.time()
    while time.time() - t0 < 40 and not c.js("performance.getEntriesByName('hero-ready').length > 0"): c.pump(0.2)
    c.pump(1.5); return c
def box(c, sel): return json.loads(c.js(f"(() => {{ const r = document.querySelector('{sel}').getBoundingClientRect(); return JSON.stringify({{x: r.left, y: r.top, w: r.width, h: r.height, top: r.top + scrollY}}); }})()"))
def save(c, name, clip=None):
    p = {'format': 'png', 'captureBeyondViewport': bool(clip)}
    if clip: p['clip'] = dict(zip(('x', 'y', 'width', 'height'), clip), scale=1)
    open(os.path.join(out, name), 'wb').write(base64.b64decode(c.send('Page.captureScreenshot', p)['data'])); print('saved', name, flush=True)
def tall(c, w, dpr=1):
    """Make the viewport as tall as the document, so the fixed layers and the lazy parts render in place, and scroll to the top."""
    c.js("scrollTo(0, 0); true"); h = int(c.js("document.documentElement.scrollHeight")); c.send('Emulation.setDeviceMetricsOverride', {'width': w, 'height': min(h, 16000), 'deviceScaleFactor': dpr, 'mobile': w < 600}); c.pump(2.0)
def hover(c, x, y): c.send('Input.dispatchMouseEvent', {'type': 'mouseMoved', 'x': x, 'y': y}); c.pump(0.4)
def band(name, sel, w=1440, h=900, theme='dark', pill=None, click=None):
    """One element alone: the viewport is made as tall as the element, so it renders whole; a control is pressed first if asked."""
    global c_w
    c = page(w, h, theme); c_w = w
    try:
        if click: c.js(f"document.querySelector({json.dumps(click)}).click(); true"); c.pump(0.8)
        c.send('Emulation.setDeviceMetricsOverride', {'width': w, 'height': int(box(c, sel)['h']) + 80, 'deviceScaleFactor': 1, 'mobile': w < 600}); c.pump(0.8)
        c.js(f"scrollTo(0, {int(box(c, sel)['top']) - 40}); true"); c.pump(0.8)
        if pill:
            p = json.loads(c.js(f"JSON.stringify((() => {{ const t = [...document.querySelectorAll('{pill[0]} .tag')].find(x => x.textContent === {json.dumps(pill[1])}); const r = t.getBoundingClientRect(); return {{x: r.left + r.width / 2, y: r.top + r.height / 2}}; }})())"))
            hover(c, p['x'], p['y'])
        save(c, name)
    finally: c.close()
def card(theme):
    """The map card after the map has flown to a stop: the record's "Show UCLA on the map" button, then 6 s for the flight and the card."""
    c = page(1440, 900, theme)
    try:
        c.js("document.querySelector('.on-map[data-stop=\"1\"]').click(); true"); c.pump(6.0)
        b = box(c, '#card'); save(c, f'map-card-after-flight-1440-{theme}-{label}.png', (b['x'] - 8, b['top'] - 8, b['w'] + 16, b['h'] + 16))
    finally: c.close()
card('dark'); card('light')
if card_only: sys.exit(0)
band('about-1440-dark.png', '#about')
band('about-1440-light.png', '#about', theme='light')
band('about-1100-dark.png', '#about', w=1100)
band('about-390-dark-closed.png', '#about', w=390, h=844)
band('about-390-dark-open.png', '#about', w=390, h=844, click='#about-more')
band('entry-grassroots-open-1440-dark.png', '#exp-grc', click='#exp-grc .fold-btn')
c = page(1440, 900)
try: tall(c, 1440); save(c, 'page-folded-1440-dark.png')
finally: c.close()
# the opening line and the mark: every animation on the mark's stops is paused and set to the same clock time, so the frame is that moment
c = page(1440, 900); marks = {}
try:
    c.js(f"scrollTo(0, {int(box(c, '.about-lede')['top']) - 120}); true"); c.pump(0.8)
    for t in (0, 16):
        marks[f'{t}s'] = json.loads(c.js(f"""JSON.stringify((() => {{ const st = [...document.querySelectorAll('.about-mark i')];
          st.forEach(i => i.getAnimations().forEach(a => {{ a.pause(); a.currentTime = {t * 1000}; }}));
          return st.map(i => ({{ color: getComputedStyle(i).color, animations: i.getAnimations().length }})); }})())""")); c.pump(0.4)
        l, m = box(c, '.about-lede'), box(c, '.about-mark')
        save(c, f'lede-mark-1440-dark-{t}s.png', (max(0, l['x'] - 24), l['top'] - 24, l['w'] + 48, m['top'] + m['h'] - l['top'] + 48))
    open(os.path.join(out, 'mark.json'), 'w').write(json.dumps(marks, indent=1)); print('mark', json.dumps(marks), flush=True)
finally: c.close()
# the clip
c = page(1440, 900); frames = []
try:
    y0 = int(box(c, '#about')['top']) - 40; y1 = int(box(c, '.band-wrap')['top']) - 300; c.js(f"scrollTo(0, {y0}); true"); c.pump(1.0); c.ev.clear()
    c.send('Page.startScreencast', {'format': 'jpeg', 'quality': 80, 'maxWidth': 1440, 'maxHeight': 900, 'everyNthFrame': 1})
    c.js(f"(function () {{ var t0 = performance.now(); function step(t) {{ var k = Math.min(1, (t - t0) / 14000); scrollTo(0, {y0} + ({y1} - {y0}) * k); if (k < 1) requestAnimationFrame(step); }} requestAnimationFrame(step); }})(); true")
    t0 = time.time()
    while time.time() - t0 < 15.0:
        c.pump(0.05)
        for e in c.ev:
            if e.get('method') == 'Page.screencastFrame':
                frames.append((e['params']['metadata']['timestamp'], e['params']['data']))
                try: c.send('Page.screencastFrameAck', {'sessionId': e['params']['sessionId']})
                except Exception: pass
        c.ev.clear()
    c.send('Page.stopScreencast')
finally: c.close()
enc = Chrome(chrome, 9992, os.path.join(HERE, '.tmp', 'encode'), 1440, 900, True)
try:
    for m in ('Page.enable', 'Runtime.enable'): enc.send(m)
    enc.send('Page.navigate', {'url': 'about:blank'}); enc.pump(0.5); enc.js("window.__frames = []; true")
    for i in range(0, len(frames), 20): enc.send('Runtime.evaluate', {'expression': 'window.__frames.push(...' + json.dumps([[round(t - frames[0][0], 4), d] for t, d in frames[i:i + 20]]) + '); true'})
    data = enc.js("""(async () => {
      const imgs = await Promise.all(window.__frames.map(([t, d]) => new Promise(res => { const im = new Image(); im.onload = () => res([t, im]); im.src = 'data:image/jpeg;base64,' + d; })));
      const cv = document.createElement('canvas'); cv.width = imgs[0][1].naturalWidth; cv.height = imgs[0][1].naturalHeight; const cx = cv.getContext('2d'); document.body.appendChild(cv); cx.drawImage(imgs[0][1], 0, 0);
      const rec = new MediaRecorder(cv.captureStream(30), { mimeType: 'video/webm;codecs=vp9', videoBitsPerSecond: 5000000 }); const chunks = []; rec.ondataavailable = e => chunks.push(e.data); rec.start(100);
      const t0 = performance.now(); let i = 0;
      await new Promise(done => { function tick() { const el = (performance.now() - t0) / 1000; while (i < imgs.length && imgs[i][0] <= el) { cx.drawImage(imgs[i][1], 0, 0); i++; } if (i < imgs.length) requestAnimationFrame(tick); else setTimeout(done, 300); } requestAnimationFrame(tick); });
      rec.stop(); await new Promise(r => rec.onstop = r);
      const u = new Uint8Array(await new Blob(chunks, { type: 'video/webm' }).arrayBuffer()); let s = ''; for (let k = 0; k < u.length; k += 8192) s += String.fromCharCode.apply(null, u.subarray(k, k + 8192)); return btoa(s);
    })()""", wait=True)
    open(os.path.join(out, 'clip-about-record-1440-dark.webm'), 'wb').write(base64.b64decode(data)); print('saved clip-about-record-1440-dark.webm', len(frames), 'frames', flush=True)
finally: enc.close()
