#!/usr/bin/env python3
"""Every sentence with a digit, a percent sign or a claim word (largest, highest, top, first, only, longest, inaugural, most, best,
leading, award, awarded, recognized, selected, chosen, funded) on the seven pages must have a row in ledger.tsv, and every skill pill on the
Experience cards and every tag on the record of the main page must have a row in pills.tsv.

    python3 tools/claims/check.py            # exit 1 when a sentence has no ledger row or a pill has no pills row

The ledger has four tab-separated columns: page, sentence, source, line. A source of UNSOURCED is a row, so the check passes;
it is the report's job to list those. Sentences are compared after whitespace is collapsed. The pills file has four columns:
role (the card's heading, or the record entry's data-role), pill (its text), line (the line of the CV's layout extraction that names it for that
role, as a bare number or "CV N", or "resume N" for the resume's extraction; "owner, YYYY-MM-DD" for an owner statement; "not verified"
when nothing names it) and phrase (the words on
that line that support it).
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


CLAIM_WORDS = re.compile(r'\b(largest|highest|top|first|only|longest|inaugural|most|best|leading|award|awarded|recognized|selected|chosen|funded)\b', re.I)


def has_number(s):
    """A claim: a digit or percent sign, or a superlative, first or award word that asserts rank or recognition."""
    return is_sentence(s) and (re.search(r'\d|%', s) is not None or CLAIM_WORDS.search(s) is not None)


def load_ledger():
    rows = {}
    with open(os.path.join(HERE, 'ledger.tsv'), encoding='utf-8') as f:
        next(f)
        for line in f:
            parts = line.rstrip('\n').split('\t')
            if len(parts) >= 4: rows.setdefault(parts[0], {})[re.sub(r'\s+', ' ', parts[1]).strip()] = (parts[2], parts[3])
    return rows


def load_pills():
    rows = set()
    with open(os.path.join(HERE, 'pills.tsv'), encoding='utf-8') as f:
        next(f)
        for line in f:
            parts = line.rstrip('\n').split('\t')
            if len(parts) >= 4 and re.match(r'^(\d+|(CV|resume) \d+|owner, \d{4}-\d{2}-\d{2}|not verified)$', parts[2].strip()): rows.add((parts[0].strip(), parts[1].strip()))
    return rows


def pills():
    """(role, pill) for every skill pill on the main page's Experience cards; the role is the card's heading."""
    t = open(os.path.join(SITE, PAGES['main']), encoding='utf-8').read(); out = []
    for card in re.findall(r'<article class="exp"[^>]*>.*?</article>', t, flags=re.S):
        head = re.search(r'<h3>(.*?)</h3>', card, flags=re.S)
        role = html.unescape(re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', head.group(1)))).strip() if head else ''
        for tag in re.findall(r'<span class="tag">(.*?)</span>', card, flags=re.S): out.append((role, html.unescape(tag.strip())))
    for role, block in re.findall(r'<div class="tags"[^>]*data-role="([^"]+)"[^>]*>(.*?)</div></article>', t, flags=re.S):
        for tag in re.findall(r'<span class="tag">(.*?)</span>', block, flags=re.S): out.append((html.unescape(role), html.unescape(tag.strip())))
    return out


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
    print(f"{total} sentences with a digit, percent sign or claim word: {sourced} sourced, {unsourced} unsourced, {len(missing)} without a ledger row")
    for page, s in missing: print(f"  {page}: {s}")
    known = load_pills(); found = pills(); unpilled = [(r, p) for r, p in found if (r, p) not in known]
    print(f"{len(found)} skill pills and tags on the main page: {len(found) - len(unpilled)} sourced to the CV, {len(unpilled)} without a pills row")
    for r, p in unpilled: print(f"  {r}: {p}")
    sys.exit(1 if missing or unpilled else 0)


if __name__ == '__main__':
    main()
