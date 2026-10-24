"""Hero frame cost: busy ms per frame at 60 fps on the GPU main thread and the renderer main thread, above the blob alone.
Usage: python3 tools/audit/hero.py http://localhost:8000 [--widths 1440,390] [--schemes dark,light] [--runs 3] [--settle 20] [--out hero.json]

For each width and scheme three scenarios are traced for 5 s after the settle, each the median of the runs: blob (assets/land.js blocked, the
blob alone), network (the page as served, pointer still) and cascade (?pulse=0.5, so firings run through the trace). The quoted figure is the
difference from blob; the target is under 0.5 ms on both threads. Chrome renders with the GPU. No trace starts while the one-minute load
average is 2 or more; the tool waits. Network is throttled as in run.py."""
import argparse, json, os, statistics, sys, time
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from run import Chrome, THROTTLE
CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'; TRACE_S = 5.0

def wait_for_load(limit=2.0):
    while True:
        load = os.getloadavg()[0]
        if load < limit: return load
        time.sleep(20)

def trace(root, width, scheme, scenario, settle, port, tmp):
    h, dpr = (900, 2) if width >= 1000 else (844, 3)
    c = Chrome(CHROME, port, os.path.join(tmp, f'hero-{width}-{scheme}-{scenario}-{port}'), width, h, False)
    try:
        for m in ('Page.enable', 'Runtime.enable', 'Network.enable'): c.send(m)
        c.send('Network.emulateNetworkConditions', dict(offline=False, **THROTTLE))
        c.send('Emulation.setDeviceMetricsOverride', {'width': width, 'height': h, 'deviceScaleFactor': dpr, 'mobile': width < 600})
        c.send('Emulation.setEmulatedMedia', {'features': [{'name': 'prefers-color-scheme', 'value': scheme}]})
        if scenario == 'blob': c.send('Network.setBlockedURLs', {'urls': ['*/assets/land.js']})
        c.send('Page.addScriptToEvaluateOnNewDocument', {'source': "try { sessionStorage.setItem('mwm-welcome', '1'); } catch (e) {}"})
        c.send('Page.navigate', {'url': root + '/' + ('?pulse=0.5' if scenario == 'cascade' else '')}); t0 = time.time()
        while time.time() - t0 < 20 and not c.js("performance.getEntriesByName('hero-lift').length > 0"): c.pump(0.2)
        c.pump(settle)
        c.send('Tracing.start', {'traceConfig': {'includedCategories': ['toplevel', 'disabled-by-default-devtools.timeline', 'devtools.timeline', '__metadata'], 'recordMode': 'recordContinuously'}, 'transferMode': 'ReportEvents'})
        c.pump(TRACE_S); c.send('Tracing.end'); t1 = time.time()
        while time.time() - t1 < 60 and not any(e.get('method') == 'Tracing.tracingComplete' for e in c.ev): c.pump(0.2)
        events = [x for e in c.ev if e.get('method') == 'Tracing.dataCollected' for x in e['params']['value']]
    finally: c.close()
    names, spans = {}, {}
    for e in events:
        if e.get('ph') == 'M' and e.get('name') == 'thread_name': names[(e['pid'], e['tid'])] = e['args']['name']
        elif e.get('ph') == 'X' and 'dur' in e: spans.setdefault((e['pid'], e['tid']), []).append((e['ts'], e['ts'] + e['dur']))
    out = {}
    for want in ('CrGpuMain', 'CrRendererMain'):   # the busiest thread of that name: the page's own renderer, the one GPU process
        cands = [k for k, n in names.items() if n == want and k in spans]
        if not cands: out[want] = None; continue
        iv = sorted(spans[max(cands, key=lambda k: len(spans[k]))]); busy = 0; end = -1
        for s, e in iv:   # top-level busy time only, so nested events are not counted twice
            if e <= end: continue
            busy += e - max(s, end); end = e
        out[want] = busy / 1000 / ((iv[-1][1] - iv[0][0]) / 1e6 * 60)
    return out

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('root'); ap.add_argument('--widths', default='1440,390'); ap.add_argument('--schemes', default='dark,light')
    ap.add_argument('--runs', type=int, default=3); ap.add_argument('--settle', type=float, default=20); ap.add_argument('--port', type=int, default=9980)
    ap.add_argument('--out', default=os.path.join(HERE, 'hero.json')); ap.add_argument('--tmp', default=os.path.join(HERE, '.tmp'))
    a = ap.parse_args(); os.makedirs(a.tmp, exist_ok=True); results = []
    for width in [int(w) for w in a.widths.split(',')]:
        for scheme in a.schemes.split(','):
            cell = {'width': width, 'scheme': scheme}
            for scenario in ('blob', 'network', 'cascade'):
                runs = []
                for i in range(a.runs):
                    load = wait_for_load(); runs.append(trace(a.root.rstrip('/'), width, scheme, scenario, a.settle, a.port + i, a.tmp))
                    print(f'{width} {scheme} {scenario} run {i + 1}: ' + ' '.join(f'{k} {v:.2f}' for k, v in runs[-1].items() if v is not None) + f' (load {load:.2f})', flush=True)
                cell[scenario] = {k: round(statistics.median([r[k] for r in runs if r[k] is not None]), 3) for k in ('CrGpuMain', 'CrRendererMain')}
            cell['above_blob'] = {s: {k: round(cell[s][k] - cell['blob'][k], 3) for k in cell['blob']} for s in ('network', 'cascade')}
            results.append(cell)
    json.dump({'meta': {'date': time.strftime('%Y-%m-%d'), 'root': a.root, 'runs': a.runs, 'settle_s': a.settle, 'trace_s': TRACE_S}, 'cells': results}, open(a.out, 'w'), indent=1)
    print('\nms per frame at 60 fps above the blob alone (GPU main / renderer main), median of', a.runs)
    for c in results:
        n, k = c['above_blob']['network'], c['above_blob']['cascade']
        print(f"{c['width']:>5} {c['scheme']:<6} still {n['CrGpuMain']:+.2f} / {n['CrRendererMain']:+.2f}   cascade {k['CrGpuMain']:+.2f} / {k['CrRendererMain']:+.2f}")
    print('wrote', a.out)

if __name__ == '__main__': main()
