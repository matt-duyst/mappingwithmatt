#!/usr/bin/env python3
"""Write the deployed commit's short hash into the seven pages as <meta name="build">, so the live check can tell which commit is being served.

    python3 tools/stamp.py <short-hash>

Run by the deploy workflow on its checkout, never committed: the repository's pages carry no stamp.
"""
import re, sys, os
SITE = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
PAGES = ['index.html', 'maps/index.html', 'projects/peatland/index.html', 'projects/yangtze/index.html', 'projects/carbon-trading/index.html', 'projects/pv-thermal/index.html', 'projects/flare-efficiency/index.html']
sha = sys.argv[1][:7]
for p in PAGES:
    path = os.path.join(SITE, p); s = open(path, encoding='utf-8').read()
    s = re.sub(r'<meta name="build" content="[^"]*">\n', '', s)
    s = s.replace('<meta charset="utf-8">\n', f'<meta charset="utf-8">\n<meta name="build" content="{sha}">\n', 1)
    open(path, 'w', encoding='utf-8').write(s)
print('stamped', len(PAGES), 'pages with', sha)
