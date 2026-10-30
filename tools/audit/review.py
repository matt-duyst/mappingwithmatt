#!/usr/bin/env python3
"""Review measurements for the About and record, one headless session per width, for CI.

    python3 tools/audit/review.py URL --chrome BINARY --out DIR

Writes DIR/review.json and DIR/review.md: axe with every fold closed and then open (1440 and 390); Tab order through the About and record
(1440); the layout at 1440 (container, About columns and characters per line, --justify-min, the Experience grid and paragraph measure, each
entry's tag block width and lines per tag row, the Awards grid, the Education columns); which column holds each About paragraph at 1100, 1280,
1440 and 1920; whether every pill is visible at 1440, 1100 and 390; and whether the two longest pills stay inside their entry at 390. Exits 1 on
any axe violation, console error, overflow, a paragraph in the wrong column, a hidden pill, or a pill outside its entry.
"""
import json, os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); from run import Chrome, errors
args = sys.argv[1:]
def opt(name, default=None):
    if name not in args: return default
    i = args.index(name); v = args[i + 1]; del args[i:i + 2]; return v
chrome = opt('--chrome', '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'); out = opt('--out', os.path.join(HERE, 'review')); root = args[0] if args else 'http://localhost:8000/'
os.makedirs(out, exist_ok=True); AXE = open(os.path.join(HERE, 'vendor', 'axe.min.js'), encoding='utf-8').read()
AXE_RUN = "axe.run(document, {resultTypes: ['violations']}).then(r => JSON.stringify(r.violations.map(v => ({id: v.id, impact: v.impact, nodes: v.nodes.map(n => n.target.join(' '))}))))"
OPEN = "document.querySelectorAll('.fold-btn').forEach(b => { if (b.getAttribute('aria-expanded') !== 'true') b.click(); }); true"
def session(w, h):
    c = Chrome(chrome, 9990, os.path.join(HERE, '.tmp', f'review-{w}'), w, h, True)
    for m in ('Page.enable', 'Runtime.enable', 'Log.enable', 'Network.enable'): c.send(m)
    c.send('Emulation.setDeviceMetricsOverride', {'width': w, 'height': h, 'deviceScaleFactor': 1, 'mobile': w < 600})
    c.send('Page.navigate', {'url': root}); t0 = time.time()
    while time.time() - t0 < 40 and not c.js("performance.getEntriesByName('hero-ready').length > 0"): c.pump(0.2)
    c.pump(1.5); return c
def axe(c):
    c.send('Runtime.evaluate', {'expression': AXE}); return json.loads(c.js(AXE_RUN, wait=True))
COLUMNS = """JSON.stringify((() => { const x = id => Math.round(document.getElementById(id).getBoundingClientRect().left);
  const left = ['about-p1', 'about-p2', 'about-p3'].map(x), right = ['about-p4', 'about-p5', 'about-p6'].map(x);
  return { left, right, ok: new Set(left).size === 1 && new Set(right).size === 1 && right[0] > left[0] }; })())"""
LAYOUT = """JSON.stringify((() => { const r = el => el.getBoundingClientRect(), $ = s => document.querySelector(s), $$ = s => [...document.querySelectorAll(s)];
  const probe = document.createElement('span'); const p2 = $('#about-p2'); probe.textContent = p2.textContent.slice(0, 55); const cs = getComputedStyle(p2);
  probe.style.cssText = 'position:absolute;white-space:nowrap;font:' + cs.font + ';letter-spacing:' + cs.letterSpacing; document.body.appendChild(probe); const w55 = r(probe).width; probe.remove();
  const cols = $$('.about-col').map(c => Math.round(r(c).width));
  const tags = $$('#band-experience .chapter, #band-education .chapter').map(ch => ({ entry: ch.querySelector('.ch-place').textContent, paragraph: Math.round(r(ch.querySelector('.entry-body p')).width), block: Math.round(r(ch.querySelector('.tags')).width),
    rows: [...ch.querySelectorAll('.tag-row')].map(row => ({ label: row.querySelector('.tag-label').textContent, pills: row.querySelectorAll('.tag').length, lines: new Set([...row.querySelectorAll('.tag')].map(p => Math.round(r(p).top))).size })) }));
  return { container: Math.round(r($('#record')).width), aboutWidth: Math.round(r($('#about')).width), aboutColumns: cols, charsPerLine: cols.map(w => Math.round(w / (w55 / 55))),
    justifyMin: getComputedStyle(document.documentElement).getPropertyValue('--justify-min').trim(), experienceGrid: getComputedStyle($('#band-experience .chapter')).gridTemplateColumns, tags,
    awardsGrid: getComputedStyle($('#band-awards .chapter')).gridTemplateColumns, awardsEntry: getComputedStyle($('#band-awards .aw-entry')).gridTemplateColumns,
    educationColumns: $$('#band-education .chapter').map(c => Math.round(r(c).width)) }; })())"""
HIDDEN = """JSON.stringify([...document.querySelectorAll('#record .tag')].filter(p => { const b = p.getBoundingClientRect(); return p.hidden || b.width === 0 || b.height === 0; }).map(p => p.textContent).concat([document.querySelectorAll('#record .tag').length + ' pills']))"""
KEYS = """(() => { const a = document.activeElement; if (!a || !(a.closest('#about') || a.closest('#record'))) return 'OUT';
  return a.tagName === 'A' ? 'link: ' + a.textContent.trim().slice(0, 30) : a.classList.contains('award') ? 'entry: ' + a.querySelector('.entry-title').textContent.trim().slice(0, 30) : 'button: ' + (a.getAttribute('aria-label') || a.textContent.trim()); })()"""
EXPECT = """JSON.stringify([...document.querySelectorAll('#about a, #about button, #record a, #record button, #record [tabindex="0"]')].filter(e => e.offsetParent && e.tabIndex >= 0)
  .map(a => a.tagName === 'A' ? 'link: ' + a.textContent.trim().slice(0, 30) : a.classList.contains('award') ? 'entry: ' + a.querySelector('.entry-title').textContent.trim().slice(0, 30) : 'button: ' + (a.getAttribute('aria-label') || a.textContent.trim())))"""
res = {'columns': {}, 'hiddenPills': {}, 'axe': {}}; problems = []
for w in (1100, 1280, 1440, 1920, 390):
    c = session(w, 844 if w < 600 else 900)
    try:
        if w >= 600:
            res['columns'][w] = json.loads(c.js(COLUMNS))
            if w > 1064 and not res['columns'][w]['ok']: problems.append(f'{w}: About paragraphs are not 1 to 3 left and 4 to 6 right')
        if w in (1440, 1100, 390):
            h = json.loads(c.js(HIDDEN)); res['hiddenPills'][w] = h; problems += [f'{w}: pill "{t}" is not visible' for t in h[:-1]]
        if w == 1440: res['layout'] = json.loads(c.js(LAYOUT))
        if w in (1440, 390):
            closed = axe(c); c.js(OPEN); c.pump(0.8); opened = axe(c); res['axe'][w] = {'closed': closed, 'open': opened}
            problems += [f'{w} axe {v["id"]} on {", ".join(v["nodes"][:3])}' for v in closed + opened]
        if w == 390:
            res['pillsInside'] = json.loads(c.js("""JSON.stringify(['soil organic carbon from field cores', 'gradient-boosted residual correction'].map(t => { const p = [...document.querySelectorAll('.tag')].find(x => x.textContent === t);
              const e = p.closest('.chapter').querySelector('.entry'), a = p.getBoundingClientRect(), b = e.getBoundingClientRect(); return { pill: t, right: Math.round(a.right), entryRight: Math.round(b.right), inside: a.right <= b.right + 0.5, lines: Math.round(a.height / 12.6) }; }))"""))
            problems += [f'390: "{p["pill"]}" overruns its entry' for p in res['pillsInside'] if not p['inside']]
        if w == 1440:
            c.js("location.reload(); true"); c.pump(4.0)
            c.js("const s = document.createElement('button'); s.id = 'tab-start'; document.getElementById('about').insertAdjacentElement('beforebegin', s); s.focus(); true")
            order = []
            for _ in range(120):
                for t in ('keyDown', 'keyUp'): c.send('Input.dispatchKeyEvent', {'type': t, 'key': 'Tab', 'code': 'Tab', 'windowsVirtualKeyCode': 9})
                f = c.js(KEYS)
                if f == 'OUT' and order: break
                if f != 'OUT': order.append(f)
            expected = json.loads(c.js(EXPECT)); res['keyboard'] = {'order': order, 'matchesDom': order == expected}
            if order != expected: problems.append('1440: Tab order differs from DOM order')
        res.setdefault('overflow', {})[w] = c.js('document.documentElement.scrollWidth > document.documentElement.clientWidth')
        if res['overflow'][w]:
            wide = json.loads(c.js("JSON.stringify([...document.querySelectorAll('body *')].filter(e => e.getBoundingClientRect().right > document.documentElement.clientWidth + 0.5).slice(0, 8).map(e => (e.id ? '#' + e.id : e.tagName.toLowerCase() + '.' + String(e.className.baseVal ?? e.className).split(' ')[0]) + ' ' + Math.round(e.getBoundingClientRect().right)))"))
            problems.append(f'{w}: horizontal overflow from ' + ', '.join(wide))
        errs = errors(c); res.setdefault('errors', {})[w] = errs; problems += [f'{w}: {e}' for e in errs]
    finally: c.close()
res['problems'] = problems
json.dump(res, open(os.path.join(out, 'review.json'), 'w'), indent=1)
L = res.get('layout', {}); md = ['## Review', '', f"Container {L.get('container')} px; About columns {L.get('aboutColumns')} px at {L.get('charsPerLine')} characters per line; --justify-min {L.get('justifyMin')}.",
     f"Experience grid {L.get('experienceGrid')}; Awards grid {L.get('awardsGrid')} with the entry as {L.get('awardsEntry')}; Education columns {L.get('educationColumns')} px.", '',
     '| Entry | Paragraph | Tag block | data: | methods: | tools: |', '|---|---|---|---|---|---|']
md += [f"| {t['entry']} | {t['paragraph']} | {t['block']} | " + ' | '.join(f"{x['pills']} pills, {x['lines']} line(s)" for x in t['rows']) + ' |' for t in L.get('tags', [])]
md += ['', '| Width | About columns 1-3 / 4-6 x | holds |', '|---|---|---|'] + [f"| {w} | {v['left']} / {v['right']} | {'yes' if v['ok'] else 'NO'} |" for w, v in res['columns'].items()]
md += ['', 'Pills not visible: ' + '; '.join(f"{w}: {len(v) - 1} of {v[-1]}" for w, v in res['hiddenPills'].items())]
md += ['', '| Width | axe closed | axe open |', '|---|---|---|'] + [f"| {w} | {len(v['closed'])} | {len(v['open'])} |" for w, v in res['axe'].items()]
md += ['', f"Keyboard at 1440: {len(res.get('keyboard', {}).get('order', []))} stops, matches DOM order: {res.get('keyboard', {}).get('matchesDom')}.",
       f"Pills at 390: " + '; '.join(f"{p['pill']} {'inside' if p['inside'] else 'OUTSIDE'} ({p['lines']} line(s))" for p in res.get('pillsInside', [])), '', 'Problems: ' + ('none' if not problems else '; '.join(problems))]
open(os.path.join(out, 'review.md'), 'w').write('\n'.join(md) + '\n'); print('\n'.join(md))
sys.exit(1 if problems else 0)
