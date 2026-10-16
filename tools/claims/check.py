#!/usr/bin/env python3
"""Every sentence with a digit or a percent sign on the seven pages must have a row in ledger.tsv.

    python3 tools/claims/check.py            # exit 1 when a sentence has no ledger row

The ledger has four tab-separated columns: page, sentence, source, line. A source of UNSOURCED is a row, so the check passes;
it is the report's job to list those. Sentences are compared after whitespace is collapsed.
"""
import html, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.abspath(os.path.join(HERE, '..', '..'))
PAGES = {'main': 'index.html', 'peatland': 'projects/peatland/index.html', 'yangtze': 'projects/yangtze/index.html',
         'carbon-trading': 'projects/carbon-trading/index.html', 'pv-thermal': 'projects/pv-thermal/index.html',
         'flare-efficiency': 'projects/flare-efficiency/index.html', 'maps': 'maps/index.html'}


def sentences(path):
    """Visible sentences of a page: text between block boundaries, split at sentence ends; caption-bar data attributes count as text."""
    t = open(path, encoding='utf-8').read()
    t = re.sub(r'<head\b.*?</head>|<nav\b.*?</nav>|<footer\b.*?</footer>|<script\b[^>]*>.*?</script>|<style\b[^>]*>.*?</style>|<svg\b[^>]*>.*?</svg>|<!--.*?-->', ' ', t, flags=re.S)
    t = re.sub(r'<label\b[^>]*>.*?</label>|<button\b[^>]*>.*?</button>|<div class="strip-pos">.*?</div>', ' ', t, flags=re.S)
    t = re.sub(r'data-(finding|measure|source|credit)="([^"]*)"', lambda m: '\n' + m.group(2) + '\n', t)
    t = re.sub(r'<(br|/p|/li|/h[1-6]|/figcaption|/dd|/dt|/div|/span|/td|/th|/caption|/summary|/a|/button|/label)[^>]*>', '\n', t)
    t = html.unescape(re.sub(r'<[^>]+>', ' ', t))
    out, seen = [], set()
    for block in t.split('\n'):
        block = re.sub(r'\s+', ' ', block).strip()
        for s in re.split(r'(?<=[.!?])\s+(?=[A-Z0-9(“"])', block):
            s = s.strip()
            if len(s) > 2 and s not in seen: seen.add(s); out.append(s)
    return out


def is_sentence(s): return len(re.findall(r'[A-Za-z]{2,}', s)) >= 3  # three words or more; bare years, counters and labels are not claims


def has_number(s): return is_sentence(s) and re.search(r'\d|%', s) is not None


def load_ledger():
    rows = {}
    with open(os.path.join(HERE, 'ledger.tsv'), encoding='utf-8') as f:
        next(f)
        for line in f:
            parts = line.rstrip('\n').split('\t')
            if len(parts) >= 4: rows.setdefault(parts[0], {})[re.sub(r'\s+', ' ', parts[1]).strip()] = (parts[2], parts[3])
    return rows


def main():
    ledger = load_ledger(); missing = []; total = sourced = unsourced = 0
    for page, rel in PAGES.items():
        for s in sentences(os.path.join(SITE, rel)):
            if not has_number(s): continue
            total += 1
            row = ledger.get(page, {}).get(s)
            if row is None: missing.append((page, s))
            elif row[0] == 'UNSOURCED': unsourced += 1
            else: sourced += 1
    print(f"{total} sentences with a digit or percent sign: {sourced} sourced, {unsourced} unsourced, {len(missing)} without a ledger row")
    for page, s in missing: print(f"  {page}: {s}")
    sys.exit(1 if missing else 0)


if __name__ == '__main__':
    main()
