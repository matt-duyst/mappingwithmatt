#!/usr/bin/env python3
"""Paired cold-load timing of two servings of the main page on one runner, for CI.

    python3 tools/audit/paired.py BEFORE_URL AFTER_URL --chrome BINARY --out DIR [--runs 9] [--before-label X] [--after-label Y]

At 1440 x 900, dark and light, with the audit's network throttling, each serving's main page is loaded cold RUNS times. The two servings
alternate, and the order flips every round (before then after, then after then before), so drift on the runner falls on both sides alike.
DIR/paired.md and DIR/paired.json give each side's total blocking time per run, its median and its minimum-to-maximum spread, and whether
the after side's median is lower than the before side's by more than the larger of the two spreads (the keep test for a change).
"""
import argparse, json, os, statistics, sys, types
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from run import audit_page

ap = argparse.ArgumentParser()
ap.add_argument('before'); ap.add_argument('after')
ap.add_argument('--chrome', default='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')
ap.add_argument('--out', default=os.path.join(HERE, 'paired')); ap.add_argument('--runs', type=int, default=9)
ap.add_argument('--before-label', default='before'); ap.add_argument('--after-label', default='after')
a = ap.parse_args(); os.makedirs(a.out, exist_ok=True)
sides = {'before': a.before.rstrip('/'), 'after': a.after.rstrip('/')}
res = {t: {'before': [], 'after': []} for t in ('dark', 'light')}; port = 9700
for k in range(a.runs):
    order = ('before', 'after') if k % 2 == 0 else ('after', 'before')
    for theme in ('dark', 'light'):
        for side in order:
            port += 1
            ns = types.SimpleNamespace(chrome=a.chrome, tmp=os.path.join(HERE, '.tmp', 'paired'), software=True, root=sides[side])
            r = audit_page(ns, '/', 1440, theme, 'throttled', port, None, cold_only=True)
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
open(os.path.join(a.out, 'paired.md'), 'w').write('\n'.join(md) + '\n'); print('\n'.join(md))
