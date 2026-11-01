#!/usr/bin/env python3
"""Every sentence with a digit, a percent sign or a claim word (largest, highest, top, first, only, longest, inaugural, most, best,
leading, award, awarded, recognized, selected, chosen, funded) on the seven pages must have a row in ledger.tsv, and every skill pill on the
Experience cards and every tag on the record of the main page must have a row in pills.tsv.

    python3 tools/claims/check.py            # exit 1 when a sentence has no ledger row or a pill has no pills row

The ledger has four tab-separated columns: page, sentence, source, line. A source of UNSOURCED is a row, so the check passes;
it is the report's job to list those. Sentences are compared after whitespace is collapsed. The pills file has four columns:
role (the card's heading, or the record entry's data-role), pill (its text), line (the line of the CV's layout extraction that names it for that
role, as "CV N" or "resume N" inside that role's own sections (SECTIONS below), "owner, YYYY-MM-DD" for an owner statement, "site PATH/" or
"repo NAME FILE" among the role's other allowed sources (OTHER below), or "not verified" when nothing names it) and phrase (the words on
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


# Each role's own sections of the CV and resume layout extractions (pdftotext -layout), by line range. A pill citing a line outside its
# role's sections fails, so the Technical Skills lists (CV 242 to 250, resume 101 to 112) count for no pill.
SECTIONS = {
    'Grassroots Carbon': {'CV': [(91, 129)], 'resume': [(31, 46)]},
    'SeekOps': {'CV': [(130, 166)], 'resume': [(48, 63)]},
    'University of Minnesota': {'CV': [(197, 225)], 'resume': [(81, 90)]},
    'Cydcor': {'resume': [(92, 99)]},
    'Yale School of the Environment': {'CV': [(35, 56), (167, 196)], 'resume': [(15, 22), (65, 79)]},
    'University of California, Los Angeles': {'CV': [(57, 80)], 'resume': [(23, 28)]},
}
# Each role's other allowed sources: public repository files cited by name, and the site's own pages (by path prefix), whose text must
# carry the cited phrase.
OTHER = {
    'University of Minnesota': ['repo Peatland-Flux-Forecasting writeup/Forecasting_Methane_Flux_2022.pdf', 'site projects/peatland/'],
    'Yale School of the Environment': ['repo Yangtze-Landcover-Methane Duyst_Thesis_Final.ipynb', 'repo UAV-PV-Assessment README.md', 'site projects/yangtze/', 'site projects/pv-thermal/'],
    'University of California, Los Angeles': ['site maps/'],
}


def page_text(rel):
    t = open(os.path.join(SITE, rel, 'index.html'), encoding='utf-8').read()
    t = re.sub(r'<script\b.*?</script>|<style\b.*?</style>|<head\b.*?</head>', ' ', t, flags=re.S)
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', t)))


def citation_problem(role, src, phrase):
    """None when the pill's citation is allowed for its role, else why not."""
    m = re.match(r'^(CV|resume) (\d+)$', src)
    if m:
        n = int(m.group(2)); spans = SECTIONS.get(role, {}).get(m.group(1), [])
        return None if any(a <= n <= b for a, b in spans) else f'{src} is outside the {role} sections of the {m.group(1)}'
    if re.match(r'^owner, \d{4}-\d{2}-\d{2}$', src) or src == 'not verified': return None
    if src.startswith('repo '): return None if src in OTHER.get(role, []) else f'{src} is not an allowed source for {role}'
    if src.startswith('site '):
        rel = src[5:]
        if not any(('site ' + rel).startswith(o) for o in OTHER.get(role, []) if o.startswith('site ')): return f'{src} is not an allowed page for {role}'
        if not os.path.exists(os.path.join(SITE, rel, 'index.html')): return f'{src} does not exist'
        return None if re.sub(r'\s+', ' ', phrase).strip() in page_text(rel) else f'{src} does not carry "{phrase}"'
    return f'"{src}" is not a citation'


def load_pills():
    rows = {}
    with open(os.path.join(HERE, 'pills.tsv'), encoding='utf-8') as f:
        next(f)
        for line in f:
            parts = line.rstrip('\n').split('\t')
            if len(parts) >= 4: rows[(parts[0].strip(), parts[1].strip())] = (parts[2].strip(), parts[3].strip())
    return rows


def pills():
    """(role, pill) for every skill pill on the main page's Experience cards; the role is the card's heading."""
    t = open(os.path.join(SITE, PAGES['main']), encoding='utf-8').read(); out = []
    for card in re.findall(r'<article class="exp"[^>]*>.*?</article>', t, flags=re.S):
        head = re.search(r'<h3>(.*?)</h3>', card, flags=re.S)
        role = html.unescape(re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', head.group(1)))).strip() if head else ''
        for tag in re.findall(r'<span class="tag">(.*?)</span>', card, flags=re.S): out.append((role, html.unescape(tag.strip())))
    for role, block in re.findall(r'<div class="tags"[^>]*data-role="([^"]+)"[^>]*>(.*?)</div></article></li>', t, flags=re.S):
        for tag in re.findall(r'<span class="tag"[^>]*>(.*?)</span>', block, flags=re.S): out.append((html.unescape(role), html.unescape(tag.strip())))
    return out


def stray_pills():
    """Pills on the main page that no role reads: every span of class "tag" must sit in a card or a role's tag block."""
    t = open(os.path.join(SITE, PAGES['main']), encoding='utf-8').read()
    return len(re.findall(r'<span class="tag"[\s>]', t)) - len(pills())


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
    # report only: ledger rows sourced in part, whose source or evidence still marks a piece "not verified"
    partial = [(pg, s) for pg, rows in ledger.items() for s, (src, line) in rows.items() if 'not verified' in (src + ' ' + line).lower()]
    print(f"{len(partial)} ledger row(s) not verified in part")
    for pg, s in partial: print(f"  {pg}: {s[:110]}")
    known = load_pills(); found = pills(); unpilled = [(r, p) for r, p in found if (r, p) not in known]
    bad = [(r, p, citation_problem(r, *known[(r, p)])) for r, p in found if (r, p) in known]; bad = [x for x in bad if x[2]]
    unverified = [(r, p) for r, p in found if known.get((r, p), ('',))[0] == 'not verified']
    print(f"{len(found)} skill pills and tags on the main page: {len(found) - len(unpilled) - len(bad)} cited within their role, {len(unverified)} not verified, "
          f"{len(unpilled)} without a pills row, {len(bad)} with a citation outside their role")
    for r, p in unpilled: print(f"  no row: {r}: {p}")
    for r, p, why in bad: print(f"  {r}: {p}: {why}")
    unpilled += [(r, p) for r, p, _ in bad]
    stray = stray_pills()
    if stray: print(f"  {stray} pill(s) on the page sit outside any role's tag block")
    sys.exit(1 if missing or unpilled or stray else 0)


if __name__ == '__main__':
    main()
