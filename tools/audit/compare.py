#!/usr/bin/env python3
"""Compare an audit.json with the baseline and fail on regressions.

    python3 tools/audit/compare.py tools/audit/audit.json [tools/audit/baseline.json]
    python3 tools/audit/compare.py --checks-only audit.json      # axe, errors, overflow and links only; no baseline
    python3 tools/audit/compare.py audit.json baseline.json --write-baseline            # copies audit.json over baseline.json, only when every gate passes
    python3 tools/audit/compare.py audit.json baseline.json --force-baseline "reason"    # writes it anyway, recording the reason and the failing metrics in the file

The quoted figure for each throttled metric is the median of the audit's runs (five by default); all runs are printed beside it. For the timed
metrics (FCP, LCP, TBT) a trend column compares the median with the baseline's spread: a direction when it lies outside the baseline's minimum-to-maximum
range across its runs ("down from X to Y" or "up from X to Y", X the baseline median), "within noise" otherwise. The trend is a report,
not a gate.

Fails (exit 1) when, on the throttled profile, requests or bytes rise more than 10 percent (--bytes-allowance=0.15, at most, widens the
byte gate, and --requests-allowance=N, at most 2, adds N requests, for a review the owner has approved), FCP or LCP rise more than 100 ms,
CLS exceeds 0.05 or TBT exceeds 50 ms (--gate=absolute, the default, for local runs against the GPU baseline); with --gate=relative, for
the review workflow's GPU-less runner, TBT fails instead when it exceeds the CI baseline's maximum for the cell by more than 25 percent; and when any axe violation, console error, overflow or broken internal link is present.
The local profile is printed beside the quoted figure and does not gate.
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from trend import trend as trend_text, tbt_failure, bytes_failure, requests_failure

HERE = os.path.dirname(os.path.abspath(__file__))
args = sys.argv[1:]; CHECKS = '--checks-only' in args; WRITE = '--write-baseline' in args; FORCE = None
GATE = next((a.split('=', 1)[1] for a in args if a.startswith('--gate=')), 'absolute'); args = [a for a in args if not a.startswith('--gate=')]
if GATE not in ('absolute', 'relative'): sys.exit(f'--gate must be absolute or relative, not {GATE}')
ALLOW = float(next((a.split('=', 1)[1] for a in args if a.startswith('--bytes-allowance=')), '0.10')); args = [a for a in args if not a.startswith('--bytes-allowance=')]
if not 0 < ALLOW <= 0.15: sys.exit('--bytes-allowance must be above 0 and at most 0.15')
EXTRA = next((a.split('=', 1)[1] for a in args if a.startswith('--requests-allowance=')), '0'); args = [a for a in args if not a.startswith('--requests-allowance=')]
if not EXTRA.isdigit() or int(EXTRA) > 2: sys.exit('--requests-allowance must be a whole number from 0 to 2')
EXTRA = int(EXTRA)
if '--force-baseline' in args:
    i = args.index('--force-baseline'); FORCE = args[i + 1] if i + 1 < len(args) else ''
    if not FORCE.strip(): sys.exit('--force-baseline needs a reason')
    del args[i:i + 2]
argv = [a for a in args if a not in ('--checks-only', '--write-baseline')]
cur = json.load(open(argv[0] if argv else os.path.join(HERE, 'audit.json')))
fails = []
if CHECKS:
    for path, widths in cur['pages'].items():
        for width, themes in widths.items():
            for theme, e in themes.items():
                for v in e.get('axe', []): fails.append(f"{path} {width} {theme}: axe {v['id']} ({v['impact']}) on {', '.join(v['nodes'][:3])}")
                for err in e.get('errors', []): fails.append(f"{path} {width} {theme}: {err}")
                if e.get('overflow'): fails.append(f"{path} {width} {theme}: horizontal overflow")
    for p in cur['links']['problems']: fails.append(f"link: {p['page']} {p['url']} {p['problem']}")
    print(f"checks at {cur['meta']['commit']}: {sum(len(t.get('axe', [])) for w in cur['pages'].values() for t in w.values() for t in [t] for t in t.values())} axe violations, {len(cur['links']['problems'])} link problems over {cur['links']['references']} references")
    if fails: print('\nFAILURES'); [print(' -', f) for f in fails]; sys.exit(1)
    print('all checks pass'); sys.exit(0)
base = json.load(open(argv[1] if len(argv) > 1 else os.path.join(HERE, 'baseline.json')))

def cell(v): return '-' if v is None else v
TIMED = ('fcp', 'lcp', 'tbt')
def spread(e, stage, metric):
    """(min, max) of a timed metric on the throttled profile: the recorded spread, or for an older file the range of its stored runs."""
    t = e.get('throttled', {}); s = t.get(stage, {})
    if s.get(metric + '_min') is not None and s.get(metric + '_max') is not None: return s[metric + '_min'], s[metric + '_max']
    vals = [r.get(stage, {}).get(metric) for r in t.get('runs', [])]; vals = [v for v in vals if isinstance(v, (int, float))]
    return (min(vals), max(vals)) if vals else (None, None)
moved = []
print(f"audit {cur['meta']['date']} at {cur['meta']['commit']} ({cur['meta']['renderer']}) vs baseline {base['meta']['date']} at {base['meta']['commit']} ({base['meta']['renderer']})")
if cur['meta']['renderer'] != base['meta']['renderer']: fails.append('renderer differs from the baseline; numbers are not comparable')
print(f"{'page':26s} {'w':>4s} {'theme':5s} {'metric':9s} {'quoted':>9s} {'baseline':>9s} {'local':>9s} {'base local':>10s}  {'spread':>11s} {'base spread':>11s}  {'trend':22s}  runs")
for path, widths in cur['pages'].items():
    for width, themes in widths.items():
        for theme, e in themes.items():
            b = base['pages'].get(path, {}).get(width, {}).get(theme, {})
            for stage in ('cold', 'scroll'):
                for metric in ('requests', 'bytes', 'fcp', 'lcp', 'tbt', 'cls'):
                    if stage == 'scroll' and metric in ('fcp', 'lcp'): continue
                    q = e.get('throttled', {}).get(stage, {}).get(metric); bq = b.get('throttled', {}).get(stage, {}).get(metric)
                    l = e.get('local', {}).get(stage, {}).get(metric); bl = b.get('local', {}).get(stage, {}).get(metric)
                    runs = ' '.join(str(cell(r.get(stage, {}).get(metric))) for r in e.get('throttled', {}).get('runs', []))
                    sp, bsp, trend = '', '', ''
                    if metric in TIMED and q is not None:
                        lo, hi = spread(e, stage, metric); blo, bhi = spread(b, stage, metric)
                        sp = f"{lo}-{hi}" if lo is not None else ''; bsp = f"{blo}-{bhi}" if blo is not None else ''
                        if blo is not None:
                            trend = trend_text(q, bq, blo, bhi)
                            if trend != 'within noise': moved.append(f"{path} {width} {theme} {stage} {metric}: {trend}, outside the baseline's {blo}-{bhi}")
                    print(f"{path:26s} {width:>4s} {theme:5s} {stage[:1] + ' ' + metric:9s} {cell(q):>9} {cell(bq):>9} {cell(l):>9} {cell(bl):>10}  {sp:>11s} {bsp:>11s}  {trend:22s}  {runs}")
                    tag = f"{path} {width} {theme} {stage} {metric}"
                    if q is None: continue
                    if metric == 'requests':
                        why = requests_failure(q, bq, EXTRA)
                        if why: fails.append(f"{tag}: {why}")
                    if metric == 'bytes':
                        why = bytes_failure(q, bq, ALLOW)
                        if why: fails.append(f"{tag}: {why}")
                    if metric in ('fcp', 'lcp') and bq is not None and q is not None and q > bq + 100: fails.append(f"{tag}: {q} ms is more than 100 ms over the baseline {bq}")
                    if metric == 'cls' and q > 0.05: fails.append(f"{tag}: {q} is above 0.05")
                    if metric == 'tbt':
                        why = tbt_failure(q, spread(b, stage, metric)[1], GATE)
                        if why: fails.append(f"{tag}: {why}")
            for v in e.get('axe', []): fails.append(f"{path} {width} {theme}: axe {v['id']} ({v['impact']}) on {', '.join(v['nodes'][:3])}")
            for profile in ('throttled', 'local'):
                for err in e.get(profile, {}).get('errors', []): fails.append(f"{path} {width} {theme} {profile}: {err}")
                if e.get(profile, {}).get('overflow'): fails.append(f"{path} {width} {theme} {profile}: horizontal overflow")
for p in cur['links']['problems']: fails.append(f"link: {p['page']} {p['url']} {p['problem']}")
print(f"links: {cur['links']['references']} references, {len(cur['links']['problems'])} problems")
print(f"\ntrend: {len(moved)} timed metric(s) moved outside the baseline's spread" + (':' if moved else ''))
for m in moved: print(' -', m)
if fails: print('\nREGRESSIONS'); [print(' -', f) for f in fails]
else: print('\nno regressions')
baseline_path = argv[1] if len(argv) > 1 else os.path.join(HERE, 'baseline.json')
if WRITE or FORCE is not None:
    if fails and FORCE is None:
        print(f'\nbaseline not written: {len(fails)} gate(s) fail; pass --force-baseline "reason" to write it anyway'); sys.exit(1)
    cur['meta']['note'] = f"Baseline taken at commit {cur['meta']['commit']} on {cur['meta']['date']}: {cur['meta']['renderer']} rendering, {cur['meta'].get('runs', 1)} throttled run(s) per page with the median quoted."
    if FORCE is not None and fails: cur['meta']['forced'] = {'reason': FORCE, 'failing': fails}
    elif 'forced' in cur['meta']: del cur['meta']['forced']
    json.dump(cur, open(baseline_path, 'w'), indent=1)
    print(f"baseline written to {baseline_path}" + (f" (forced: {FORCE}; {len(fails)} failing metric(s) recorded)" if FORCE is not None and fails else ''))
sys.exit(1 if fails else 0)
