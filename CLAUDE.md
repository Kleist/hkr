# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

Project uses [uv](https://docs.astral.sh/uv/) and Python 3.12+.

```sh
uv sync --all-extras            # install runtime + dev deps
uv run pytest                   # full test suite (no live network — uses tests/fixtures/json/)
uv run pytest tests/test_parser.py::test_parse_agenda_extracts_meeting_and_documents
uv run ruff check src tests
uv run mypy src
uv run hkr --help               # CLI entry point (declared in pyproject as `hkr = "hkr.cli:app"`)
```

Quick end-to-end smoke test against the live API (writes to `data/`):

```sh
uv run hkr scrape --from-year 2026 --limit 5 --rps 0.5 --save-raw
```

`--save-raw` dumps each JSON response under `data/raw/` (gitignored) for debugging parser drift.

## Architecture

The scraper targets **FirstAgenda Publication** at `https://dagsordener-referater.hvidovre.dk/`. It is a SPA, but we never render JS — we call the JSON backend directly. Three endpoints are enough for the whole dataset (see `docs/api-capture.md` for shapes):

1. `GET /api/agenda/udvalgsliste` — every committee grouped by election period (`"Udvalg 2026-2029"`, `"Udvalg 2022-2025"`, ...) with all of that committee's meetings **inlined**. This is the discovery hub — one call, ~34 committees, ~1400 meetings.
2. `GET /api/agenda/dagsorden/{meeting_id}` — one meeting's `Dagsordenpunkter` with two PDF sources per item: `Felter[]` (case-presentation fields, each with `DocumentId` + `Link`) and `Bilag[]` (attachments, each with `Id` + `Navn` + `Order`).
3. `GET /Vis/Pdf/bilag/{document_id}` — streams `application/pdf`. Both `Felter[].DocumentId` and `Bilag[].Id` resolve here.

All entity IDs are **GUIDs (strings)**, not integers. `Moede.Id` inside an agenda payload is a zero-GUID and must be ignored — the real meeting id is the top-level `Id`. The zero-GUID `"00000000-0000-0000-0000-000000000000"` also appears as a placeholder in `Felter[].DocumentId` and must be skipped.

### Scrape pipeline (in `hkr.cli.scrape`)

```
udvalgsliste → upsert committees + meetings  (one HTTP call)
   ↓
for each selected meeting:
    GET /api/agenda/dagsorden/{id}
    parser.parse_agenda → upsert meeting + documents
    mark agenda_fetched_at
   ↓
documents_missing_download → pdf.download (sha256 dedup) → record_download
   ↓
documents_missing_text → pdf.extract_text → store_text (syncs doc_fts)
```

Each stage is idempotent and resumable: re-running `hkr scrape` is safe; per-stage flags (`--skip-pdfs`, `--skip-text`) let you re-run only what's needed. `--committee` takes committee GUIDs (repeatable); `--from-year` filters by `meeting_date.year`.

### Module responsibilities (`src/hkr/`)

- **`sources.py`** — URL builders for the three endpoints. `BASE_URL` is a constant.
- **`client.py`** — `HttpClient` wraps `httpx.Client` with tenacity retries on 5xx/transport errors, a token-bucket rate limiter (`rps`), and optional `save_raw_dir` snapshotting per call (`label` arg becomes the filename).
- **`parser.py`** — pure JSON→dataclass mappers. `parse_udvalgsliste` returns `list[tuple[Committee, list[MeetingRef]]]`; `parse_agenda` returns a `ParsedAgenda`. Both raise `UnknownStructureError` on shape drift. Meeting `kind` is inferred from `Navn` (`"Referat"`/`"Lukket referat"` → `referat`, else → `dagsorden`).
- **`store.py`** — SQLite layer. All IDs are `TEXT`. Tables: `committees`, `meetings`, `documents`, `doc_text`, plus a **standalone** FTS5 virtual table `doc_fts(document_id UNINDEXED, text)`. The FTS table is intentionally not `content='doc_text'` linked — TEXT primary keys don't align with the integer rowid that contentless FTS expects. Search joins via `doc_fts.document_id`.
- **`pdf.py`** — streams downloads to a temp file, computes sha256, then moves to `data/pdfs/{committee_id}/{year}/{sha256[:2]}/{sha256}.pdf`. Content-addressing means PDFs referenced from multiple items dedupe automatically. `extract_text` uses pypdf and is page-fault-tolerant.

### Testing

`tests/fixtures/json/` contains real response bodies extracted from `docs/har-capture.json` (`udvalgsliste.json`, `agenda.json`, etc.). Parser tests load these directly — **no live HTTP** in the test suite. If the upstream API drifts, you'll typically see `UnknownStructureError` first; capture a new HAR, refresh fixtures, and adjust the parser.

### Dataset-as-repo

`data/hkr.db` and `data/pdfs/**` are **committed** — the repo is the dataset. The weekly GitHub Actions cron (`.github/workflows/scrape.yml`) runs `hkr scrape --from-year 2022`, then `git add data/ && git commit && git push` if anything changed. `data/raw/` is gitignored.

### README caveat

The committed `README.md` still says "Project scaffold. Parser implementation is blocked on capturing the FirstAgenda Publication JSON endpoints" — that's outdated. The HAR has been captured (`docs/har-capture.json`), the API is fully wired, and the scraper runs end-to-end.
