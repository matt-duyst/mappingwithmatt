#!/usr/bin/env python3
"""Justified text: the widest inter-word gap on every line of every justified paragraph, as a multiple of that paragraph's own space width.

    python3 tools/audit/gaps.py [URL] [--width 1440[,1920,...]] [--chrome BINARY] [--open | --both] [--css "rules"]

--open presses every fold first; --both measures with the folds closed, then opens them and measures again; --css injects trial rules.
Several widths are measured in one headless session by resizing the viewport. Walks each word with Range.getClientRects, groups words by
line, measures the gap between neighbours, and measures a single space in the same font for the ratio. Lines above 2.0x are flagged and
lines above 2.5x counted. Also reports any line that ends in a hyphen the source text does not contain (hyphenation).
"""
import json, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__)); SITE = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, HERE); from run import Chrome
args = sys.argv[1:]; chrome = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'; widths = [1440]; css = ''
def opt(name):
    global args
    if name not in args: return None
    i = args.index(name); v = args[i + 1]; del args[i:i + 2]; return v
chrome = opt('--chrome') or chrome; widths = [int(w) for w in (opt('--width') or '1440').split(',')]; css = opt('--css') or ''
phases = ['open'] if '--open' in args else (['closed', 'open'] if '--both' in args else ['closed'])
args = [a for a in args if a not in ('--open', '--both')]
target = args[0] if args else 'http://localhost:8000/'
MEASURE = """JSON.stringify((() => {
  const out = [];
  const paras = [...document.querySelectorAll('p, .award-line')].filter(p => getComputedStyle(p).textAlign === 'justify' && p.getClientRects().length);
  paras.forEach((p, pi) => {
    const style = getComputedStyle(p); const span = document.createElement('span'); span.textContent = '\\u00a0'; span.style.font = style.font; span.style.whiteSpace = 'pre'; p.appendChild(span);
    const space = span.getBoundingClientRect().width; span.remove();
    const walker = document.createTreeWalker(p, NodeFilter.SHOW_TEXT); const words = []; let n;
    while ((n = walker.nextNode())) { const t = n.textContent; const re = /\\S+/g; let m; while ((m = re.exec(t))) { const r = document.createRange(); r.setStart(n, m.index); r.setEnd(n, m.index + m[0].length); const rects = [...r.getClientRects()]; if (rects.length) { const rc = rects[rects.length - 1];
      // a token that continues the previous one with no whitespace between (a link's text followed by punctuation) is the same word
      const prev = words[words.length - 1]; const joined = prev && prev.endNode && prev.endsNode && m.index === 0 && prev.endNode !== n && /^\\S/.test(t);
      if (joined && Math.round(rc.top) === prev.y) { prev.w += m[0]; prev.x2 = rc.right; prev.endNode = n; prev.endsNode = m.index + m[0].length === t.length; continue; }
      // the corner arrow after an outbound link is drawn by ::after and is not a word gap
      const a = n.parentElement.closest('a'); let arrow = 0; if (a && /^http/.test(a.getAttribute('href') || '') && m.index + m[0].length === t.length) { const ps = getComputedStyle(a, '::after'); arrow = (parseFloat(ps.width) || 0) + (parseFloat(ps.marginLeft) || 0); }
      words.push({ w: m[0], x1: rects[0].left, x2: rc.right + arrow, y: Math.round(rc.top), bottom: rc.bottom, endNode: n, endsNode: m.index + m[0].length === t.length }); } } }
    const lines = []; words.forEach(w => { const L = lines.find(l => Math.abs(l.y - w.y) < 3); if (L) L.words.push(w); else lines.push({ y: w.y, words: [w] }); });
    lines.sort((a, b) => a.y - b.y);
    const src = p.textContent;
    lines.forEach((L, li) => {
      let widest = 0, where = '';
      for (let i = 1; i < L.words.length; i++) { const g = L.words[i].x1 - L.words[i - 1].x2; if (g > widest) { widest = g; where = L.words[i - 1].w + ' ' + L.words[i].w; } }
      const last = L.words[L.words.length - 1].w, hyph = last.endsWith('-') && !src.includes(last + ' ') && !src.includes(last + '\\n') && !src.endsWith(last);
      out.push({ id: p.id || (p.closest('[id]') ? p.closest('[id]').id + ' > ' + p.tagName.toLowerCase() : 'p' + pi), line: li + 1, lines: lines.length, ratio: Math.round(widest / space * 100) / 100, words: L.words.slice(0, 6).map(w => w.w).join(' '), hyph, lastLine: li === lines.length - 1 });
    });
  });
  return out;
})())"""
def report(rows, label):
    by = {}
    for r in rows: by.setdefault(r['id'], []).append(r)
    print(f"== {label}"); print(f"{'paragraph':34s} {'lines':>5s} {'widest':>7s}  line  first words"); flagged = []; hyph = []; widest = 0
    for pid, rs in by.items():
        full = [r for r in rs if not r['lastLine']] or rs; w = max(full, key=lambda r: r['ratio']); widest = max(widest, w['ratio'])
        print(f"{pid:34s} {len(rs):5d} {w['ratio']:6.2f}x  {w['line']:4d}  {w['words']}")
        flagged += [r for r in full if r['ratio'] > 2.0]; hyph += [r for r in rs if r['hyph']]
    over25 = sum(1 for r in flagged if r['ratio'] > 2.5)
    print(f"\n{len(by)} justified paragraphs, {len(rows)} lines; {len(flagged)} line(s) above 2.0x, {over25} above 2.5x, widest {widest:.2f}x (last lines of paragraphs are ragged and not counted); {len(hyph)} hyphenated line end(s)")
    for r in flagged: print(f"  {r['id']} line {r['line']}: {r['ratio']}x  {r['words']}")
    for r in hyph: print(f"  hyphen: {r['id']} line {r['line']}: {r['words']}")
    print(f"SUMMARY\t{label}\t{len(flagged)}\t{over25}\t{widest:.2f}\t{len(hyph)}\n")
c = Chrome(chrome, 9978, os.path.join(HERE, '.gaps-profile'), widths[0], 900, False)
try:
    for m in ('Page.enable', 'Runtime.enable'): c.send(m)
    c.send('Emulation.setDeviceMetricsOverride', {'width': widths[0], 'height': 900, 'deviceScaleFactor': 1, 'mobile': False})
    c.send('Page.navigate', {'url': target}); c.pump(3.0)
    if css: c.js(f"const st = document.createElement('style'); st.textContent = {json.dumps(css)}; document.head.appendChild(st); true"); c.pump(0.3)
    for phase in phases:
        if phase == 'open': c.js("document.querySelectorAll('.fold-btn').forEach(b => { if (b.getAttribute('aria-expanded') !== 'true') b.click(); }); true"); c.pump(0.8)
        for w in widths:
            c.send('Emulation.setDeviceMetricsOverride', {'width': w, 'height': 900, 'deviceScaleFactor': 1, 'mobile': False}); c.pump(0.8)
            report(json.loads(c.js(MEASURE)), f"{w} folds {phase}")
finally: c.close()
