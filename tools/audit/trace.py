#!/usr/bin/env python3
"""Where the cold load's main-thread time goes, for CI: a Chrome Performance trace of the main page at 1440 x 900 and at 390 x 844, dark,
cold, with the audit's network throttling.

    python3 tools/audit/trace.py URL --chrome BINARY --out DIR

Writes DIR/trace-1440.json and DIR/trace-390.json (the raw traces, loadable in the Performance panel) and DIR/trace.md: the ten longest
main-thread tasks at 1440, each with its duration, the work that dominates it, the script URL and function at the top of its stack, and
whether a task with the same top frame and at least half its length also runs at 390; then, for the three longest, the largest events nested
inside each, so the work a frame callback does is named; and for the same three, each task's self time split into scripting, style, layout, paint,
rasterization, compositing and other, with the work the compositor, raster and display threads did while it ran.
"""
import json, os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); from run import Chrome, THROTTLE
args = sys.argv[1:]
def opt(name, default=None):
    if name not in args: return default
    i = args.index(name); v = args[i + 1]; del args[i:i + 2]; return v
chrome = opt('--chrome', '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'); out = opt('--out', os.path.join(HERE, 'trace')); root = args[0] if args else 'http://localhost:8000/'
os.makedirs(out, exist_ok=True)
CATS = 'devtools.timeline,toplevel,v8.execute,blink.user_timing,loading,disabled-by-default-devtools.timeline,disabled-by-default-devtools.timeline.stack,disabled-by-default-devtools.timeline.frame,cc,viz,benchmark,gpu'
JS = ('EvaluateScript', 'v8.evaluateModule', 'FunctionCall', 'TimerFire', 'FireAnimationFrame', 'EventDispatch', 'v8.compile', 'v8.compileModule')

def record(w, h):
    c = Chrome(chrome, 9994, os.path.join(HERE, '.tmp', f'trace-{w}'), w, h, True)
    try:
        for m in ('Page.enable', 'Runtime.enable', 'Network.enable'): c.send(m)
        c.send('Network.setCacheDisabled', {'cacheDisabled': True}); c.send('Network.emulateNetworkConditions', dict(offline=False, **THROTTLE))
        c.send('Emulation.setDeviceMetricsOverride', {'width': w, 'height': h, 'deviceScaleFactor': 1, 'mobile': w < 600})
        c.send('Emulation.setEmulatedMedia', {'features': [{'name': 'prefers-color-scheme', 'value': 'dark'}]})
        c.send('Tracing.start', {'categories': CATS, 'transferMode': 'ReportEvents'})
        c.send('Page.navigate', {'url': root}); t0 = time.time()
        while time.time() - t0 < 40 and not c.js("performance.getEntriesByName('hero-ready').length > 0"): c.pump(0.1)
        c.pump(3.0); c.ev.clear(); c.send('Tracing.end'); events = []; t0 = time.time()
        while time.time() - t0 < 60:
            c.pump(0.2); done = False
            for e in c.ev:
                if e.get('method') == 'Tracing.dataCollected': events += e['params']['value']
                if e.get('method') == 'Tracing.tracingComplete': done = True
            c.ev.clear()
            if done: break
    finally: c.close()
    json.dump({'traceEvents': events}, open(os.path.join(out, f'trace-{w}.json'), 'w'))
    return events

def fn_of(e):
    d = (e.get('args', {}).get('data') or {}); f = d.get('functionName') or ''; u = (d.get('url') or '').rsplit('/', 1)[-1]
    return (f + (f' line {d["lineNumber"]}' if d.get('lineNumber') is not None else '') + (f' ({u})' if u else '')).strip()


BUCKETS = (('scripting', ('FunctionCall', 'EvaluateScript', 'FireAnimationFrame', 'TimerFire', 'EventDispatch', 'RunMicrotasks', 'v8.', 'V8.', 'GC', 'MinorGC', 'MajorGC', 'v8::', 'Compile', 'ParseHTML')),
           ('style', ('UpdateLayoutTree', 'RecalculateStyles', 'ScheduleStyleRecalculation', 'ParseAuthorStyleSheet')),
           ('layout', ('Layout', 'UpdateLayout', 'LocalFrameView::layout')),
           ('paint', ('Paint', 'PrePaint', 'PaintImage', 'Layerize', 'UpdateLayer', 'Decode', 'PaintArtifactCompositor', 'LocalFrameView::RunPrePaint', 'LocalFrameView::RunPaint')),
           ('rasterization', ('Raster', 'TileManager', 'GpuRasterization', 'ImageDecode', 'SoftwareRaster')),
           ('compositing', ('Commit', 'CompositeLayers', 'BeginMainFrame', 'ProxyMain', 'ProxyImpl', 'LayerTreeHost', 'cc::', 'Scheduler', 'Animate', 'Canvas', 'Swap', 'Draw')))

def bucket(name):
    for b, keys in BUCKETS:
        if any(name.startswith(k) or name == k for k in keys): return b
    return 'other'

def breakdown(events, main, task):
    """Self time on the main thread inside one task, by kind, and the busiest events on every other renderer or display thread in its window."""
    t0, t1 = task['ts'], task['ts'] + task['dur']
    inside = sorted([e for e in events if (e.get('pid'), e.get('tid')) == main and e.get('ph') == 'X' and 'dur' in e and t0 <= e['ts'] and e['ts'] + e['dur'] <= t1], key=lambda e: (e['ts'], -e['dur']))
    self_t, stack = {}, []
    for e in inside:
        while stack and stack[-1]['ts'] + stack[-1]['dur'] <= e['ts']: stack.pop()
        if stack: self_t[id(stack[-1])] = self_t.get(id(stack[-1]), stack[-1]['dur']) - e['dur']
        self_t.setdefault(id(e), e['dur']); stack.append(e)
    kinds, other_names = {}, {}
    for e in inside:
        k = bucket(e['name']) if e['name'] not in ('RunTask', 'ThreadControllerImpl::RunTask') else 'other'
        kinds[k] = kinds.get(k, 0) + max(0, self_t[id(e)])
        if k == 'other': other_names[e['name']] = other_names.get(e['name'], 0) + max(0, self_t[id(e)])
    names = {(e['pid'], e['tid']): e['args'].get('name') for e in events if e.get('ph') == 'M' and e.get('name') == 'thread_name'}
    threads = {}
    for e in events:
        if e.get('ph') != 'X' or 'dur' not in e or (e.get('pid'), e.get('tid')) == main or e['ts'] >= t1 or e['ts'] + e['dur'] <= t0: continue
        tn = names.get((e.get('pid'), e.get('tid'))) or 'thread'
        if not any(x in tn for x in ('Compositor', 'Raster', 'Viz', 'Gpu', 'CrGpuMain', 'TileWorker')): continue
        ov = min(t1, e['ts'] + e['dur']) - max(t0, e['ts']); threads.setdefault(tn, {}); threads[tn][e['name']] = max(threads[tn].get(e['name'], 0), ov)
    return ({k: round(v / 1000, 1) for k, v in sorted(kinds.items(), key=lambda x: -x[1])}, {k: round(v / 1000, 1) for k, v in sorted(other_names.items(), key=lambda x: -x[1])[:4]},
            {tn: ', '.join(f'{n} {round(v / 1000, 1)}' for n, v in sorted(d.items(), key=lambda x: -x[1])[:4]) for tn, d in threads.items()})


def tasks(events):
    """The page's renderer main thread: the CrRendererMain whose thread parsed the page's HTML."""
    names = {(e['pid'], e['tid']): e['args'].get('name') for e in events if e.get('ph') == 'M' and e.get('name') == 'thread_name'}
    parse = [(e['pid'], e['tid']) for e in events if e.get('name') == 'ParseHTML']
    main = max(set(parse), key=parse.count) if parse else next(k for k, v in names.items() if v == 'CrRendererMain')
    on = sorted([e for e in events if (e.get('pid'), e.get('tid')) == main and e.get('ph') == 'X' and 'dur' in e], key=lambda e: e['ts'])
    out = []
    for t in [e for e in on if e['name'] in ('RunTask', 'ThreadControllerImpl::RunTask')]:
        inside = [e for e in on if e is not t and t['ts'] <= e['ts'] and e['ts'] + e['dur'] <= t['ts'] + t['dur']]
        top = max((e for e in inside if e['name'] not in ('RunTask', 'ThreadControllerImpl::RunTask')), key=lambda e: e['dur'], default=None)
        # the top of the stack: the first event inside the task that names a script or a function (a frame callback's own event names neither)
        named = lambda e: (e.get('args', {}).get('data') or {}).get('url') or (e.get('args', {}).get('data') or {}).get('functionName')
        js = next((e for e in inside if e['name'] in JS and named(e)), None) or next((e for e in inside if e['name'] in JS), None); d = (js or {}).get('args', {}).get('data', {}) if js else {}
        render = max((e for e in inside if e['name'] in ('UpdateLayoutTree', 'Layout', 'RecalculateStyles', 'Paint', 'PrePaint', 'Layerize', 'UpdateLayer')), key=lambda e: e['dur'], default=None)
        url = d.get('url') or d.get('scriptName') or ''; fn = d.get('functionName') or ''
        line = d.get('lineNumber'); frame = f"{fn or '(top level)'}{f' line {line}' if line is not None else ''}" if js else ''
        out.append({'task': t, 'main': main, 'ms': round(t['dur'] / 1000, 1), 'work': top['name'] if top else '', 'event': js['name'] if js else '', 'url': url.replace(root.rstrip('/'), ''), 'frame': frame,
                    'render': f"{render['name']} {round(render['dur'] / 1000, 1)} ms" if render else '',
                    'inside': [f"{e['name']}{' ' + fn_of(e) if fn_of(e) else ''} {round(e['dur'] / 1000, 1)} ms" for e in sorted([e for e in inside if e['name'] not in ('RunTask', 'ThreadControllerImpl::RunTask')], key=lambda e: -e['dur'])[:8]]})
    return sorted(out, key=lambda x: -x['ms'])

ev_wide = record(1440, 900); wide, narrow = tasks(ev_wide), tasks(record(390, 844))
md = ['## Load-time trace, 1440 x 900 dark, cold, throttled', '', '| # | ms | Dominant work | JS entry | Script | Function | Largest rendering step | Also at 390 |', '|---|---|---|---|---|---|---|---|']
for i, t in enumerate(wide[:10], 1):
    twin = next((n for n in narrow if n['url'] == t['url'] and n['frame'] == t['frame'] and n['work'] == t['work'] and n['ms'] >= t['ms'] / 2), None)
    also = 'yes, ' + str(twin['ms']) + ' ms' if twin else 'no'
    md.append(f"| {i} | {t['ms']} | {t['work']} | {t['event']} | {t['url'] or '(none)'} | {t['frame'] or '(none)'} | {t['render'] or '(none)'} | {also} |")
md += ['', f"Main-thread tasks over 50 ms: {sum(1 for t in wide if t['ms'] > 50)} at 1440, {sum(1 for t in narrow if t['ms'] > 50)} at 390; "
       f"their time over 50 ms (the blocking share): {round(sum(t['ms'] - 50 for t in wide if t['ms'] > 50))} ms at 1440, {round(sum(t['ms'] - 50 for t in narrow if t['ms'] > 50))} ms at 390."]
md += ['', 'Inside the three longest tasks at 1440, largest first:', ''] + [f"{i}. {t['ms']} ms: " + '; '.join(t['inside']) for i, t in enumerate(wide[:6:2], 1)]
md += ['', 'The same three tasks at 1440, self time in ms by kind; then the largest other self-time events; then, per thread, the longest events overlapping the task (ms):', '']
for i, t in enumerate(wide[:6:2], 1):
    kinds, others, threads = breakdown(ev_wide, t['main'], t['task'])
    md += [f"{i}. {t['ms']} ms: " + ', '.join(f'{k} {v}' for k, v in kinds.items()) + '; other: ' + (', '.join(f'{k} {v}' for k, v in others.items()) or 'none')]
    md += [f"   - {tn}: {v}" for tn, v in sorted(threads.items())]
open(os.path.join(out, 'trace.md'), 'w').write('\n'.join(md) + '\n'); print('\n'.join(md))
