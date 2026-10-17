#!/usr/bin/env python3
"""Site audit: cold load, full scroll, hero marks, axe and internal links for the seven pages at 1440 and 390 in both themes.

Writes audit.json. Two network profiles per page: "throttled" (40 ms RTT, 10 Mbps, DPR 1) is the quoted figure and is run three
times, each metric's median standing as the figure with all three runs kept beside it; "local" (no throttling, DPR 2 at 1440 and 3 at 390)
is run once and recorded beside it. Chrome renders with the GPU unless --software is given. --checks-only loads each page once,
runs axe and the link sweep and skips every performance measurement, which is what CI runs.

    python3 tools/audit/run.py http://localhost:8000 --out tools/audit/audit.json
"""
import argparse, base64, collections, glob, html, json, os, re, shutil, subprocess, sys, threading, time, urllib.request
try:
    import websocket
except ImportError:
    sys.exit("needs websocket-client: python3 -m pip install websocket-client")

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.abspath(os.path.join(HERE, '..', '..'))
PAGES = ['/', '/projects/peatland/', '/projects/yangtze/', '/projects/carbon-trading/', '/projects/pv-thermal/', '/projects/flare-efficiency/', '/maps/']
WIDTHS = {1440: (900, 2), 390: (844, 3)}
THROTTLE = {'latency': 40, 'downloadThroughput': 10_000_000 / 8, 'uploadThroughput': 10_000_000 / 8}
OBSERVERS = """window.__lt = []; window.__lcp = []; window.__ls = [];
try {
  new PerformanceObserver(l => { for (const e of l.getEntries()) __lt.push([e.startTime, e.duration]); }).observe({type: 'longtask', buffered: true});
  new PerformanceObserver(l => { for (const e of l.getEntries()) __lcp.push({startTime: e.startTime, el: e.element ? e.element.tagName + (e.element.className ? '.' + String(e.element.className).split(' ')[0] : '') : null}); }).observe({type: 'largest-contentful-paint', buffered: true});
  new PerformanceObserver(l => { for (const e of l.getEntries()) __ls.push({value: e.value, hadRecentInput: e.hadRecentInput}); }).observe({type: 'layout-shift', buffered: true});
} catch (e) {}"""
METRICS = """JSON.stringify((() => {
  const paint = Object.fromEntries(performance.getEntriesByType('paint').map(e => [e.name, Math.round(e.startTime)]));
  const fcp = paint['first-contentful-paint'] || 0;
  const lt = (window.__lt || []).filter(e => e[0] + e[1] > fcp);
  const lcp = (window.__lcp || []).slice(-1)[0];
  return { fcp, lcp: lcp ? Math.round(lcp.startTime) : null, lcpElement: lcp ? lcp.el : null,
           tbt: Math.round(lt.reduce((s, e) => s + Math.max(0, e[1] - 50), 0)),
           cls: Math.round((window.__ls || []).filter(e => !e.hadRecentInput).reduce((s, e) => s + e.value, 0) * 1000) / 1000 };
})())"""


CHILDREN = []          # every Chrome started, so a watchdog can kill what is still running
LOG = collections.deque(maxlen=12)  # the last progress lines, printed when the watchdog fires

def say(*parts, **_):
    line = ' '.join(str(p) for p in parts); LOG.append(line); print(line, flush=True)


def watchdog(seconds):
    """Kill every Chrome and exit non-zero if the run takes longer than it should; a hung page must not hold the run open for hours."""
    def fire():
        say(f'TIMEOUT after {seconds} s; killing {len(CHILDREN)} Chrome process(es) and exiting')
        for p in CHILDREN:
            try: p.kill()
            except Exception: pass
        print('last progress lines:\n  ' + '\n  '.join(LOG), flush=True)
        os._exit(2)
    t = threading.Timer(seconds, fire); t.daemon = True; t.start(); return t


class Chrome:
    """One headless Chrome with a fresh profile, driven over the DevTools protocol."""
    def __init__(self, binary, port, profile, w, h, software):
        shutil.rmtree(profile, ignore_errors=True)
        flags = [binary, '--headless=new', f'--remote-debugging-port={port}', f'--user-data-dir={profile}', '--no-first-run',
                 '--disable-background-networking', '--disable-component-update', '--disable-sync', f'--window-size={w},{h}']
        if software: flags += ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--disable-gpu']
        if os.environ.get('CI'): flags += ['--no-sandbox']  # the hosted runner forbids the sandbox's user namespaces
        self.p = subprocess.Popen(flags + ['about:blank'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); CHILDREN.append(self.p)
        tabs = None
        for _ in range(80):
            try: tabs = json.load(urllib.request.urlopen(f'http://127.0.0.1:{port}/json')); break
            except Exception: time.sleep(0.25)
        if not tabs: raise RuntimeError('Chrome did not start')
        self.ws = websocket.create_connection([t for t in tabs if t['type'] == 'page'][0]['webSocketDebuggerUrl'], timeout=120, suppress_origin=True)
        self.n = 0; self.ev = []; self.profile = profile
    def send(self, method, params=None):
        self.n += 1; self.ws.send(json.dumps({'id': self.n, 'method': method, 'params': params or {}}))
        while True:
            r = json.loads(self.ws.recv())
            if r.get('id') == self.n:
                if 'error' in r: raise RuntimeError(f"{method}: {r['error']}")
                return r.get('result', {})
            self.ev.append(r)
    def pump(self, seconds):
        end = time.time() + seconds; self.ws.settimeout(0.25)
        while time.time() < end:
            try: self.ev.append(json.loads(self.ws.recv()))
            except Exception: pass
        self.ws.settimeout(120)
    def js(self, expr, wait=False):
        r = self.send('Runtime.evaluate', {'expression': expr, 'returnByValue': True, 'awaitPromise': wait})
        if 'exceptionDetails' in r: raise RuntimeError(r['exceptionDetails'].get('text', ''))
        return r['result'].get('value')
    def close(self):
        try: self.ws.close()
        except Exception: pass
        self.p.terminate()
        try: self.p.wait(10)
        except Exception: self.p.kill()
        shutil.rmtree(self.profile, ignore_errors=True)


def network(c, since=0):
    reqs = [e['params'] for e in c.ev if e.get('method') == 'Network.requestWillBeSent'][since:]
    fin = {e['params']['requestId']: e['params']['encodedDataLength'] for e in c.ev if e.get('method') == 'Network.loadingFinished'}
    by_type = {}
    for r in reqs:
        t = r.get('type', 'Other'); by_type.setdefault(t, [0, 0]); by_type[t][0] += 1; by_type[t][1] += fin.get(r['requestId'], 0)
    return {'requests': len(reqs), 'bytes': sum(fin.get(r['requestId'], 0) for r in reqs), 'by_type': {k: {'requests': v[0], 'bytes': v[1]} for k, v in sorted(by_type.items())}}


def errors(c):
    return [e['params']['exceptionDetails'].get('text', '')[:160] for e in c.ev if e.get('method') == 'Runtime.exceptionThrown'] + \
           [e['params']['entry']['text'][:160] for e in c.ev if e.get('method') == 'Log.entryAdded' and e['params']['entry']['level'] == 'error'] + \
           [f"HTTP {e['params']['response']['status']} {e['params']['response']['url']}" for e in c.ev if e.get('method') == 'Network.responseReceived' and e['params']['response']['status'] >= 400]


def audit_page(args, path, width, theme, profile, port, axe_src, checks_only=False):
    h, dpr = WIDTHS[width]
    if profile == 'throttled': dpr = 1
    c = Chrome(args.chrome, port, os.path.join(args.tmp, f'prof-{width}-{theme}-{profile}'), width, h, args.software)
    out = {}
    try:
        for m in ('Page.enable', 'Runtime.enable', 'Log.enable', 'Network.enable'): c.send(m)
        c.send('Emulation.setDeviceMetricsOverride', {'width': width, 'height': h, 'deviceScaleFactor': dpr, 'mobile': width < 600})
        if width < 600: c.send('Emulation.setTouchEmulationEnabled', {'enabled': True})
        c.send('Emulation.setEmulatedMedia', {'features': [{'name': 'prefers-color-scheme', 'value': theme}]})
        if profile == 'throttled': c.send('Network.emulateNetworkConditions', dict(offline=False, **THROTTLE))
        src = OBSERVERS + (" (function f() { if (document.documentElement) document.documentElement.setAttribute('data-theme', 'light'); else setTimeout(f, 0); })();" if theme == 'light' else '')
        c.send('Page.addScriptToEvaluateOnNewDocument', {'source': src})
        c.send('Page.navigate', {'url': args.root + path}); t0 = time.time()
        # the main page's first visit ends when its route has drawn; other pages when loaded
        done = "performance.getEntriesByName('intro:route-end').length > 0" if path == '/' else "document.readyState === 'complete'"
        while time.time() - t0 < 30:
            try:
                if c.js(done): break
            except Exception: pass
            c.pump(0.1)
        c.pump(1.0 if checks_only else 3.0)
        if checks_only:
            c.send('Runtime.evaluate', {'expression': axe_src})
            out['axe'] = json.loads(c.js("axe.run(document, {resultTypes: ['violations']}).then(r => JSON.stringify(r.violations.map(v => ({id: v.id, impact: v.impact, nodes: v.nodes.map(n => n.target.join(' '))}))))", wait=True))
            out['overflow'] = c.js('document.documentElement.scrollWidth > document.documentElement.clientWidth'); out['errors'] = errors(c)
            return out
        out['cold'] = json.loads(c.js(METRICS)); out['cold'].update(network(c))
        if path == '/':
            out['hero'] = json.loads(c.js("JSON.stringify(Object.fromEntries(performance.getEntriesByType('mark').filter(m => m.name.startsWith('intro:')).map(m => [m.name.slice(6), Math.round(m.startTime)])))"))
        c.js("(async () => { for (let y = 0; y < document.body.scrollHeight; y += 450) { scrollTo(0, y); await new Promise(r => setTimeout(r, 220)); } return true; })()", wait=True); c.pump(8.0)
        out['scroll'] = json.loads(c.js(METRICS)); out['scroll'].update(network(c))
        out['overflow'] = c.js('document.documentElement.scrollWidth > document.documentElement.clientWidth')
        if profile == 'local':
            c.send('Runtime.evaluate', {'expression': axe_src})
            out['axe'] = json.loads(c.js("axe.run(document, {resultTypes: ['violations']}).then(r => JSON.stringify(r.violations.map(v => ({id: v.id, impact: v.impact, nodes: v.nodes.map(n => n.target.join(' '))}))))", wait=True))
        out['errors'] = errors(c)
    finally:
        c.close()
    return out


def median_of(dicts):
    """Per-metric median across runs; the by_type breakdown is taken from the median-bytes run."""
    import statistics
    keys = [k for k in dicts[0] if isinstance(dicts[0][k], (int, float)) and not isinstance(dicts[0][k], bool)]
    out = {k: (statistics.median([d[k] for d in dicts if d.get(k) is not None]) if any(d.get(k) is not None for d in dicts) else None) for k in keys}
    for k in out:
        if out[k] is not None and all(isinstance(d.get(k), int) for d in dicts): out[k] = int(round(out[k]))
    mid = sorted(dicts, key=lambda d: d['bytes'])[len(dicts) // 2]
    out['by_type'] = mid.get('by_type'); out['lcpElement'] = mid.get('lcpElement')
    return out


def check_links():
    """Every internal href, src, poster, srcset and caption-bar link on every page must resolve, fragments included."""
    pages = ['index.html', 'maps/index.html'] + sorted(glob.glob('projects/*/index.html', root_dir=SITE)) + sorted(glob.glob('maps/*/index.html', root_dir=SITE))
    ids = {}
    def page_ids(p):
        if p not in ids: ids[p] = set(re.findall(r'\bid="([^"]+)"', open(os.path.join(SITE, p)).read()))
        return ids[p]
    bad = []; n = 0
    for pg in pages:
        t = re.sub(r'<script\b[^>]*>.*?</script>', '', open(os.path.join(SITE, pg)).read(), flags=re.S); base = os.path.dirname(pg)
        refs = [(a, html.unescape(u)) for a, u in re.findall(r'\b(href|src|poster|data-poster)="([^"]+)"', t)]
        refs += [('srcset', c.strip().split()[0]) for m in re.findall(r'srcset="([^"]+)"', t) for c in m.split(',')]
        refs += [('data-links', html.unescape(u)) for m in re.findall(r'data-links="([^"]+)"', t) for u in re.findall(r'href="([^"]+)"', html.unescape(m))]
        for attr, url in refs:
            if re.match(r'^(https?:|mailto:|tel:|data:)', url): continue
            n += 1
            p, _, frag = url.partition('#')
            target = pg if p == '' else (p.lstrip('/') or 'index.html') if p.startswith('/') else os.path.normpath(os.path.join(base, p))
            if os.path.isdir(os.path.join(SITE, target)): target = os.path.join(target, 'index.html')
            if not os.path.exists(os.path.join(SITE, target)): bad.append({'page': pg, 'attr': attr, 'url': url, 'problem': 'missing file ' + target}); continue
            if frag and not re.match(r'^map-stop-\d$', frag) and frag not in page_ids(target): bad.append({'page': pg, 'attr': attr, 'url': url, 'problem': 'missing fragment'})
    return {'pages': len(pages), 'references': n, 'problems': bad}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('root', help='URL root, e.g. http://localhost:8000')
    ap.add_argument('--out', default=os.path.join(HERE, 'audit.json'))
    ap.add_argument('--chrome', default='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')
    ap.add_argument('--software', action='store_true', help='render with SwiftShader instead of the GPU (not comparable with the baseline)')
    ap.add_argument('--profiles', default='throttled,local')
    ap.add_argument('--pages', default=','.join(PAGES))
    ap.add_argument('--tmp', default=os.path.join(HERE, '.tmp'))
    ap.add_argument('--port', type=int, default=9950)
    ap.add_argument('--runs', type=int, default=3, help='runs of the throttled profile; the median of each metric is the quoted figure')
    ap.add_argument('--checks-only', action='store_true', help='axe, errors, overflow and links only; no performance measurement')
    ap.add_argument('--timeout', type=int, default=7200, help='seconds before the run is abandoned, its Chrome processes killed and the exit code set to 2')
    args = ap.parse_args()
    args.root = args.root.rstrip('/')
    watchdog(args.timeout)
    axe_src = open(os.path.join(HERE, 'vendor', 'axe.min.js')).read()
    commit = subprocess.run(['git', '-C', SITE, 'rev-parse', '--short', 'HEAD'], capture_output=True, text=True).stdout.strip()
    result = {'meta': {'date': time.strftime('%Y-%m-%d'), 'commit': commit, 'root': args.root, 'renderer': 'software' if args.software else 'gpu', 'runs': 1 if args.checks_only else args.runs, 'checks_only': args.checks_only,
                       'profiles': {'throttled': '40 ms RTT, 10 Mbps, DPR 1 (the quoted figure)', 'local': 'no throttling, DPR 2 at 1440 and 3 at 390'}},
              'pages': {}, 'links': check_links()}
    port = args.port
    for path in args.pages.split(','):
        result['pages'][path] = {}
        for width in WIDTHS:
            result['pages'][path][str(width)] = {}
            for theme in ('dark', 'light'):
                entry = {}
                if args.checks_only:
                    port += 1
                    r = audit_page(args, path, width, theme, 'local', port, axe_src, checks_only=True)
                    entry = {'axe': r['axe'], 'errors': r['errors'], 'overflow': r['overflow']}
                    say(f"{path} {width} {theme}: axe {len(r['axe'])} errors {len(r['errors'])} overflow {r['overflow']}", flush=True)
                    result['pages'][path][str(width)][theme] = entry; continue
                for profile in args.profiles.split(','):
                    runs = []
                    for k in range(args.runs if profile == 'throttled' else 1):
                        port += 1
                        r = audit_page(args, path, width, theme, profile, port, axe_src)
                        runs.append(r)
                        say(f"{path} {width} {theme} {profile} run {k + 1}: cold {r['cold']['requests']} req {r['cold']['bytes'] // 1024} KB FCP {r['cold']['fcp']} LCP {r['cold']['lcp']} TBT {r['cold']['tbt']} CLS {r['cold']['cls']} | scroll {r['scroll']['requests']} req {r['scroll']['bytes'] // 1024} KB TBT {r['scroll']['tbt']} CLS {r['scroll']['cls']}" + (f" | axe {len(r['axe'])}" if 'axe' in r else '') + (f" | errors {len(r['errors'])}" if r['errors'] else ''), flush=True)
                    entry[profile] = {'cold': median_of([r['cold'] for r in runs]), 'scroll': median_of([r['scroll'] for r in runs]),
                                      'runs': [{'cold': r['cold'], 'scroll': r['scroll']} for r in runs],
                                      'errors': [e for r in runs for e in r['errors']], 'overflow': any(r['overflow'] for r in runs)}
                    if 'hero' in runs[0]: entry[profile]['hero'] = runs[0]['hero']
                    if 'axe' in runs[0]: entry['axe'] = runs[0]['axe']
                result['pages'][path][str(width)][theme] = entry
    shutil.rmtree(args.tmp, ignore_errors=True)
    json.dump(result, open(args.out, 'w'), indent=1)
    say('wrote', args.out, '| links:', result['links']['references'], 'references,', len(result['links']['problems']), 'problems')


if __name__ == '__main__':
    main()
