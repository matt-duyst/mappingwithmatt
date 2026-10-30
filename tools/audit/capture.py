#!/usr/bin/env python3
"""Review captures for the About and record, one headless session per capture, for CI.

    python3 tools/audit/capture.py URL --chrome BINARY --out DIR

Full page with every fold closed at 1440 and 390 in both schemes; the Experience band at 1440 (dark) at rest and with the Grassroots Carbon
entry's "XGBoost" pill hovered; the Education band at 1440 (dark); the Awards + fellowships rows at 1440 in both schemes and at 390 (dark); and a
WebM at 1440 (dark), 15 s, scrolling from the About through the record. Screencast frames are replayed on a canvas and encoded by MediaRecorder
as VP9.
"""
import base64, json, os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); from run import Chrome
args = sys.argv[1:]
def opt(name, default=None):
    if name not in args: return default
    i = args.index(name); v = args[i + 1]; del args[i:i + 2]; return v
chrome = opt('--chrome', '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'); out = opt('--out', os.path.join(HERE, 'captures')); root = args[0] if args else 'http://localhost:8000/'
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
for theme in ('dark', 'light'):
    for w, h in ((1440, 900), (390, 844)):
        c = page(w, h, theme)
        try: tall(c, w); save(c, f'page-folded-{w}-{theme}.png')
        finally: c.close()
def band(name, sel, w=1440, h=900, theme='dark', pill=None):
    """A band alone: the viewport is made as tall as the band, so it renders whole; a pill is hovered after the last scroll so the pointer stays on it."""
    global c_w
    c = page(w, h, theme); c_w = w
    try:
        c.send('Emulation.setDeviceMetricsOverride', {'width': w, 'height': int(box(c, sel)['h']) + 80, 'deviceScaleFactor': 1, 'mobile': w < 600}); c.pump(0.8)
        c.js(f"scrollTo(0, {int(box(c, sel)['top']) - 40}); true"); c.pump(0.8)
        if pill:
            p = json.loads(c.js(f"JSON.stringify((() => {{ const t = [...document.querySelectorAll('{pill[0]} .tag')].find(x => x.textContent === {json.dumps(pill[1])}); const r = t.getBoundingClientRect(); return {{x: r.left + r.width / 2, y: r.top + r.height / 2}}; }})())"))
            hover(c, p['x'], p['y'])
        save(c, name)
    finally: c.close()
band('experience-1440-dark.png', '#band-experience')
band('experience-thread-xgboost-1440-dark.png', '#band-experience', pill=('#exp-grc', 'XGBoost'))
band('education-1440-dark.png', '#band-education')
band('awards-1440-dark.png', '#band-awards')
band('awards-1440-light.png', '#band-awards', theme='light')
band('awards-390-dark.png', '#band-awards', w=390, h=844)
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
