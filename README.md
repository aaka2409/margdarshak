# Margdarshak report engine

Builds the personalised yearly prediction PDF (about 100 pages) for any customer, from a Moon sign / ascendant / Mulank
lookup over a **content pack** (all the text the astrologer writes, as plain JSON).

## Set up (once, on your computer)

Needs Python 3.10+.

    python -m venv .venv
    .venv\Scripts\activate          # Windows      (macOS/Linux: source .venv/bin/activate)
    pip install -r requirements.txt
    playwright install chromium     # the browser that prints the PDF
    copy .env.example .env          # macOS/Linux: cp .env.example .env   then fill it in

## Use it (2027 only)

    python chart_check.py req.json                       # live test of the VedicAstroAPI lookup (needs the key in .env)
    python pack.py check 2027                            # what 2027 text is still missing
    python generate.py req.json --out out/report.pdf     # refuses until check is clean
    python batch.py customers.csv --out-dir reports --workers 3
    python app.py                                        # POST /generate-2027-report

`content/2027` holds empty TODO placeholders only (no 2026 text). Fill them with the real 2027 text.
Put your key in `.env`:  VEDIC_ASTRO_API_KEY=...   (copy .env.example to .env first).
`content/2027/year.json` has the transit calendar: confirm those dates with the astrologer.

## Safety checks built in

- **Strict layout mode** (default): if any text overflows a page or a font/image is missing, no PDF is produced.
  `--draft` overrides this for design work only.
- Transit houses are always counted from the ascendant; the Jupiter headings in the text are checked against that.
- `python -m pytest -q tests` renders a full report and validates the 2026 pack (about 10 s).

## Known gaps to review (nothing here is hidden)

- `content/2026/_review.json`: 8 duplicate texts, 16 sections the 2026 PDF did not print, 12 repairs, and one empty
  page of text (Mulank 4 + Aquarius, second overview page).
- The constellation drawings are redrawn from star positions, so they differ slightly from the 2026 artwork.

## Secrets

Everything secret is read from environment variables / `.env` (never from code; `.env` is git-ignored). The 2026 service
had API keys, a database password and an e-mail password written into its source files: **rotate those**, and use a Gmail
app password for `SMTP_PASSWORD`.

Fonts (Cormorant Garamond, DM Sans, Noto Serif Devanagari) are SIL Open Font License; licences are in `report/static/fonts`.
