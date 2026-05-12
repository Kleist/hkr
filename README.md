# hkr — Hvidovre Kommune referat-scraper

Scrapes Hvidovre Kommune's "Dagsordener og referater" from
<https://dagsordener-referater.hvidovre.dk/> (powered by FirstAgenda Publication)
into a SQLite database, with original PDFs and extracted full-text stored
alongside in `data/`. The repo is the dataset — weekly GitHub Actions cron
re-runs the scraper and commits new rows/PDFs back.

## Status

Project scaffold. Parser implementation is blocked on capturing the
FirstAgenda Publication JSON endpoints — see `docs/api-capture.md`.

## Setup

Requires Python 3.12+. Using [uv](https://docs.astral.sh/uv/):

```sh
uv sync
uv run hkr --help
```

## Usage (planned)

```sh
hkr scrape          --from-year 2024 --committee 88 --limit 50 --save-raw
hkr list-committees
hkr download-pdfs   --missing-only
hkr extract-text    --missing-only
hkr search "byggetilladelse"
```

## Layout

- `src/hkr/` — scraper package (`cli`, `client`, `sources`, `parser`, `models`, `store`, `pdf`)
- `tests/` — pytest tests with committed JSON / PDF fixtures (no live network)
- `data/hkr.db` — SQLite dataset (committed)
- `data/pdfs/{committee_id}/{year}/{sha256[:2]}/{sha256}.pdf` — content-addressed PDFs (committed)
- `data/raw/` — raw API snapshots from `--save-raw` (gitignored)
- `docs/api-capture.md` — DevTools Network captures of the FirstAgenda Publication API
- `.github/workflows/scrape.yml` — weekly cron + commit-back

## Next step

Open <https://dagsordener-referater.hvidovre.dk/> with browser DevTools (Network
tab, XHR/Fetch filter), navigate through committees/meetings, and paste the
observed requests + response bodies into `docs/api-capture.md`.
