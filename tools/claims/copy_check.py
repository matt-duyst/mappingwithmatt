#!/usr/bin/env python3
"""The About and the three record bands must read, word for word, as tools/claims/copy/section3.txt.

    python3 tools/claims/copy_check.py [URL or path] [--chrome BINARY]      # default: the repository's index.html over file://

Loads the page in the headless profile at 1440 wide, presses every fold control open, extracts the text of each copy-bearing element
(data-copy) in DOM order, with a tag row read as its label and its tags joined by "; ", normalizes whitespace only, and diffs the blocks
against the copy file. Any difference fails the check and prints the first differing block in both versions.
"""
import json, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__)); SITE = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(SITE, 'tools', 'audit')); from run import Chrome
args = sys.argv[1:]; chrome = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
if '--chrome' in args: i = args.index('--chrome'); chrome = args[i + 1]; del args[i:i + 2]
target = args[0] if args else 'file://' + os.path.join(SITE, 'index.html')
if not re.match(r'^(https?|file)://', target): target = 'file://' + os.path.abspath(target)
EXTRACT = """JSON.stringify((() => {
  document.querySelectorAll('.fold-btn').forEach(b => { if (b.getAttribute('aria-expanded') !== 'true') b.click(); });
  const out = [];
  for (const el of document.querySelectorAll('#about [data-copy], #record [data-copy]')) {
    if (el.classList.contains('tag-row')) out.push(el.querySelector('.tag-label').textContent + ' ' + [...el.querySelectorAll('.tag')].map(t => t.textContent).join('; '));
    else out.push(el.textContent);
  }
  return out;
})())"""
def norm(s): return re.sub(r'\s+', ' ', s).strip()
want = [norm(b) for b in open(os.path.join(HERE, 'copy', 'section3.txt'), encoding='utf-8').read().split('\n\n') if b.strip()]
c = Chrome(chrome, 9977, os.path.join(SITE, 'tools', 'claims', '.copy-profile'), 1440, 900, True)
try:
    for m in ('Page.enable', 'Runtime.enable'): c.send(m)
    c.send('Emulation.setDeviceMetricsOverride', {'width': 1440, 'height': 900, 'deviceScaleFactor': 1, 'mobile': False})
    c.send('Page.navigate', {'url': target}); c.pump(2.5)
    got = [norm(b) for b in json.loads(c.js(EXTRACT))]
finally: c.close()
print(f'copy: {len(got)} blocks on the page, {len(want)} in section3.txt')
for i in range(max(len(got), len(want))):
    g = got[i] if i < len(got) else '(missing on the page)'; w = want[i] if i < len(want) else '(missing in section3.txt)'
    if g != w:
        print(f'block {i + 1} differs\n  page: {g}\n  copy: {w}'); sys.exit(1)
print('copy matches'); sys.exit(0)
