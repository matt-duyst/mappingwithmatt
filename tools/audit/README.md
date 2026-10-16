# Site audit

`run.py` loads the seven pages (main, Peatland, Yangtze, Carbon Trading, photovoltaic, flare efficiency, archive index) at 1440 and 390 in the dark and light themes and writes `audit.json` with, for each: a cold load (requests, bytes by resource type, FCP, LCP, TBT, CLS), a full scroll (the same after scrolling the whole page), the hero sequence marks on the main page, axe violations, console errors, horizontal overflow, and a sweep of every internal link, fragment and srcset file in the repository.

Two network profiles are recorded for every page. The throttled profile (40 ms RTT, 10 Mbps, DPR 1) is the quoted figure and the one the baseline gates on; the local profile (no throttling, DPR 2 at 1440 and 3 at 390) is recorded beside it and labelled local. Chrome renders with the GPU; `--software` switches to SwiftShader, whose numbers are not comparable with the baseline.

## Run

    python3 -m pip install websocket-client
    python3 -m http.server 8000            # from the repository root, in another shell
    python3 tools/audit/run.py http://localhost:8000 --out tools/audit/audit.json
    python3 tools/audit/compare.py tools/audit/audit.json tools/audit/baseline.json

`run.py` needs Google Chrome (`--chrome` points at another binary) and takes about fifteen minutes. `compare.py` prints every metric beside the baseline and exits 1 when, on the throttled profile, requests or bytes rise more than 10 percent, FCP or LCP rise more than 100 ms, CLS exceeds 0.05 or TBT exceeds 50 ms, or when any page has an axe violation, a console error, horizontal overflow, or a broken internal link.

To accept a new state as the baseline, copy `audit.json` over `baseline.json` in the same commit as the change that moved the numbers.

`vendor/axe.min.js` is axe-core, Mozilla Public License 2.0, used only by the audit; the site itself does not load it.

## Continuous integration

`.github/workflows/check.yml` runs on every push and pull request to `main`: it serves the site, runs `tools/claims/check.py`, then `run.py --checks-only` (one load per page, width and theme, software rendering, no performance measurement) and `compare.py --checks-only`, failing the job on any unsourced sentence without a ledger row, broken internal link, axe violation, console error or horizontal overflow. Performance numbers are never taken in CI; they come from `run.py` on a workstation with GPU rendering, three throttled runs per page, the median quoted.
