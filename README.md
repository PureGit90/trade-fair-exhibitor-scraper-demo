# Trade Fair Exhibitor Extractor -- Working Demo

## What This Does
Give it a region and a sector. It identifies the relevant trade fairs happening in that
region/sector, pulls exhibitor records with the four fields the client asked for -- company
name, country, official website, corporate email address -- and flags anything it can't verify
instead of guessing. The output is a downloadable Excel file structured exactly like what gets
uploaded to the client's Drive folder each month.

The pipeline is region/sector-agnostic: the same code runs for any combination, not a script
hand-tuned to one trade fair. That's the actual ask in the job post -- a repeatable monthly
process, not a one-off scrape.

## How It Works
Region + sector selected -> identify relevant trade fairs for that criteria -> extract exhibitor
records (real CSV parsing for the captured sample directory, deterministic templated generation
for every other combination) -> verify each email against its listed official website domain,
flagging missing or mismatched entries rather than presenting them as fact -> clean, source-
linked table plus a two-sheet Excel export (clean records + a flagged-for-review sheet).

## Run Locally
```bash
pip install -r requirements.txt
streamlit run app.py
```
Pick a region and sector in the sidebar. Germany + Manufacturing loads a captured sample
exhibitor directory for HANNOVER MESSE via real pandas CSV parsing
(`sample_data/hannover_messe_exhibitors_sample.csv`); every other region/sector pair uses a
deterministic generator so the full pipeline is explorable for any combination with zero setup
and no live scraping target.

## Configuration
- `ANTHROPIC_API_KEY` (optional) -- when set (via the sidebar field or the environment
  variable), the QA summary at the top of the results is written by Claude. Without it, the
  summary is a rule-based version built from the same counts, so the demo runs fully
  self-contained with no API key required.

## Try It Yourself
- Leave the defaults (Germany + Manufacturing) to see real CSV parsing against the captured
  sample directory.
- Switch region/sector (e.g. Vietnam + Textiles, Brazil + Packaging) to see the templated
  generator produce a fresh, deterministic exhibitor set for a combination with no captured
  sample file.
- Check the "Flagged for Review" tab -- every batch includes a mix of missing emails and
  domain-mismatch emails, held out of the clean export rather than guessed.
- Download the Excel file and open the second sheet to see exactly what was held back and why.

## Demo Limitations
- There's no live scraping target here on purpose -- there's no single "official exhibitor
  directory" API to hit generically across organizers and regions, so this demo proves the
  extraction/formatting/verification pipeline against sample and templated data, not a live
  crawl. Production version points the same pipeline at each month's real directories via
  Thunderbit/Browse AI/Octoparse (or a direct scrape where the directory allows it).
- Trade fair identification outside the small built-in catalog falls back to a generic
  templated name rather than inventing a specific fake event -- production version replaces
  this with a real monthly search against fair-listing sites and organizer calendars.
- Email verification is domain-match only (does the email's domain resolve back to the listed
  website), not a live mailbox/MX check. That's intentional -- it catches the two failure modes
  that matter most (missing, mismatched) without pretending to guarantee deliverability.
- Sample and generated company names are fictional -- built for demo purposes only, not scraped
  from any real trade fair.
