#!/usr/bin/env python3
"""Paired timing of two servings of the main page on one runner, for CI: the keep test for a performance change, and the timing gate.

    python3 tools/audit/paired.py BEFORE_URL AFTER_URL --chrome BINARY --out DIR [--runs 9] [--before-label X] [--after-label Y]
    python3 tools/audit/paired.py MAIN_URL BRANCH_URL --gate --chrome BINARY --out DIR [--inject-busy-ms 150]

Each serving's main page is loaded with the audit's network throttling RUNS times per cell. The two servings alternate, and the order flips
every round (before then after, then after then before), so drift on the runner falls on both sides alike.

Without --gate (the keep test): cold loads at 1440 in both themes, cold total blocking time only. DIR/paired.md gives each side's runs, median
and minimum-to-maximum spread, and whether the after side's median falls by more than the larger of the two spreads.

With --gate (the timing gate): full loads, cold and then a scroll through the page, in four cells (1440 and 390, dark and light), recording
cold TBT, scroll TBT, FCP and LCP. For each cell and metric the round-by-round differences, after minus before, go to trend.paired_failure:
the branch fails only when at least 8 of 9 differences show it slower and the median difference exceeds 50 ms for cold TBT, 10 percent of
main's median for scroll TBT, or 100 ms for FCP and LCP. DIR/gate.md lists every cell and metric; the exit code is 1 when any fails and 2
when any data is missing, which is never a pass. --inject-busy-ms N, for the gate's own sensitivity test, adds to every document of the after
side only a script that blocks the main thread for N ms in a task queued as soon as the first contentful paint is recorded, so the delay
falls inside the window total blocking time counts; no page file changes.
"""
import argparse, json, os, statistics, sys, types
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from run import audit_page
from trend import paired_failure

ap = argparse.ArgumentParser()
ap.add_argument('before'); ap.add_argument('after')
ap.add_argument('--chrome', default='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')
ap.add_argument('--out', default=os.path.join(HERE, 'paired')); ap.add_argument('--runs', type=int, default=9)
ap.add_argument('--before-label', default='before'); ap.add_argument('--after-label', default='after')
ap.add_argument('--gate', action='store_true'); ap.add_argument('--inject-busy-ms', type=int, default=0)
a = ap.parse_args(); os.makedirs(a.out, exist_ok=True)
INJECT = (" (function () { try { new PerformanceObserver(function (l) { if (l.getEntries().some(function (e) { return e.name === 'first-contentful-paint'; }))"
          " setTimeout(function () { var t = performance.now(); while (performance.now() - t < %d) {} }, 0); }).observe({ type: 'paint', buffered: true }); } catch (e) {} })();"
          % a.inject_busy_ms) if a.inject_busy_ms else ''
sides = {'before': a.before.rstrip('/'), 'after': a.after.rstrip('/')}

def load(side, width, theme, port, cold_only):
    ns = types.SimpleNamespace(chrome=a.chrome, tmp=os.path.join(HERE, '.tmp', 'paired'), software=True, root=sides[side])
    return audit_page(ns, '/', width, theme, 'throttled', port, None, cold_only=cold_only, extra_src=INJECT if side == 'after' else '')

if not a.gate:
    res = {t: {'before': [], 'after': []} for t in ('dark', 'light')}; port = 9700
    for k in range(a.runs):
        order = ('before', 'after') if k % 2 == 0 else ('after', 'before')
        for theme in ('dark', 'light'):
            for side in order:
                port += 1; r = load(side, 1440, theme, port, True)
                res[theme][side].append(r['cold']['tbt']); print(f"round {k + 1} {theme} {side}: TBT {r['cold']['tbt']} FCP {r['cold']['fcp']} LCP {r['cold']['lcp']}", flush=True)
    md = [f"## Paired cold TBT at 1440: {a.before_label} against {a.after_label}, {a.runs} runs per side, alternating", '',
          '| Theme | Side | Runs (ms) | Median | Spread (min to max) |', '|---|---|---|---|---|']
    verdict = {}
    for theme, v in res.items():
        st = {}
        for side in ('before', 'after'):
            xs = v[side]; med = statistics.median(xs); st[side] = (med, max(xs) - min(xs))
            md.append(f"| {theme} | {a.before_label if side == 'before' else a.after_label} | {', '.join(str(x) for x in xs)} | {med} | {min(xs)} to {max(xs)} ({max(xs) - min(xs)}) |")
        drop, bar = st['before'][0] - st['after'][0], max(st['before'][1], st['after'][1])
        verdict[theme] = {'drop': drop, 'larger_spread': bar, 'passes': drop > bar}
    md += [''] + [f"{t}: the median falls by {v['drop']} ms against a larger spread of {v['larger_spread']} ms; keep test {'passed' if v['passes'] else 'not passed'}." for t, v in verdict.items()]
    json.dump({'runs': res, 'verdict': verdict, 'before': a.before_label, 'after': a.after_label}, open(os.path.join(a.out, 'paired.json'), 'w'), indent=1)
    open(os.path.join(a.out, 'paired.md'), 'w').write('\n'.join(md) + '\n'); print('\n'.join(md)); sys.exit(0)

CELLS = ((1440, 'dark'), (1440, 'light'), (390, 'dark'), (390, 'light'))
METRICS = (('cold_tbt', 'cold', 'tbt'), ('scroll_tbt', 'scroll', 'tbt'), ('fcp', 'cold', 'fcp'), ('lcp', 'cold', 'lcp'))
got = {(w, t): {side: {m: [] for m, _, _ in METRICS} for side in ('before', 'after')} for w, t in CELLS}; port = 9700
for k in range(a.runs):
    order = ('before', 'after') if k % 2 == 0 else ('after', 'before')
    for w, t in CELLS:
        for side in order:
            port += 1
            try: r = load(side, w, t, port, False)
            except Exception as e: r = {}; print(f'round {k + 1} {w} {t} {side}: load failed: {e}', flush=True)
            for m, stage, key in METRICS: got[(w, t)][side][m].append((r.get(stage) or {}).get(key))
            print(f"round {k + 1} {w} {t} {side}: " + ', '.join(f"{m} {got[(w, t)][side][m][-1]}" for m, _, _ in METRICS), flush=True)
md = [f"## Paired timing gate: {a.after_label} against {a.before_label}, {a.runs} alternating rounds on one runner" + (f' (a {a.inject_busy_ms} ms busy-wait injected on the after side)' if a.inject_busy_ms else ''), '',
      'A cell fails when at least 8 of 9 rounds show the branch slower and the median difference exceeds the threshold.', '',
      f'| Cell | Metric | {a.before_label} median | {a.after_label} median | Differences, branch minus main | Slower | Median difference | Threshold | Decision |', '|---|---|---|---|---|---|---|---|---|']
fails = errors = 0; out = {}
for (w, t) in CELLS:
    for m, _, _ in METRICS:
        b, f = got[(w, t)]['before'][m], got[(w, t)]['after'][m]
        diffs = [None if x is None or y is None else y - x for x, y in zip(b, f)]
        med = lambda xs: statistics.median(xs) if xs and None not in xs else 'missing'
        try: d = paired_failure(diffs, b, m); dec = 'FAIL' if d['fail'] else 'pass'; fails += d['fail']
        except ValueError as e: d = {'slower': '', 'median': '', 'threshold': ''}; dec = f'ERROR: {e}'; errors += 1
        out[f'{w} {t} {m}'] = {'before': b, 'after': f, 'diffs': diffs, **d, 'decision': dec}
        md.append(f"| {w} {t} | {m} | {med(b)} | {med(f)} | {', '.join(str(x) for x in diffs)} | {d['slower']} | {d['median']} | {d['threshold']} | {dec} |")
md += ['', f'{fails} failing, {errors} with missing data.']
json.dump(out, open(os.path.join(a.out, 'gate.json'), 'w'), indent=1)
open(os.path.join(a.out, 'gate.md'), 'w').write('\n'.join(md) + '\n'); print('\n'.join(md))
sys.exit(2 if errors else 1 if fails else 0)
