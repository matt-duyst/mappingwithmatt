# Claims ledger

`ledger.tsv` has one row per sentence on the seven pages (main, Peatland, Yangtze, Carbon Trading, photovoltaic, flare efficiency, archive index) that contains a number, a year, a percentage, a unit, a named institution or a title: the page, the sentence, the source (a README path, the CV, a figure file or an external URL) and the line or heading that states it. A source of `UNSOURCED` means no document was found; those sentences are listed with the open question for each in [UNSOURCED.md](UNSOURCED.md).

    python3 tools/claims/check.py

extracts every sentence with a digit or a percent sign from the seven pages and exits 1 when one has no ledger row. It passes with unsourced rows present; the report, not the check, tracks those. When a sentence changes on a page, its ledger row must change with it.

`pills.tsv` has one row per skill pill on the Experience cards of the main page: the role (the card's heading), the pill's text, the line of the CV's layout extraction (`pdftotext -layout assets/Duyst_CV.pdf`) that names that tool or method under that role, and the phrase on that line that supports it. The same check reads it and exits 1 when a pill on the page has no row. A tool the CV names only under another role, or only in its skills list, gets no row and no pill.

The place of the ledger in the wider process is described in [docs/WORKFLOW.md](../../docs/WORKFLOW.md).
