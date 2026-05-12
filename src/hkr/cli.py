from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

import typer

from hkr import __version__
from hkr import parser as agenda_parser
from hkr import pdf as pdfmod
from hkr import sources
from hkr.client import HttpClient
from hkr.store import Store

app = typer.Typer(no_args_is_help=True, add_completion=False, help="Hvidovre Kommune referat-scraper.")
logger = logging.getLogger("hkr")

DEFAULT_DB = Path("data/hkr.db")
DEFAULT_PDFS = Path("data/pdfs")
DEFAULT_RAW = Path("data/raw")


def _version_callback(show: bool) -> None:
    if show:
        typer.echo(f"hkr {__version__}")
        raise typer.Exit()


@app.callback()
def _main(
    version: bool = typer.Option(
        False, "--version", callback=_version_callback, is_eager=True, help="Print version and exit."
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable debug logging."),
) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


@app.command()
def scrape(
    from_year: int = typer.Option(None, "--from-year", help="Only scrape meetings on/after this year."),
    committee: list[str] = typer.Option(
        None, "--committee", help="Restrict to these committee GUIDs (repeatable)."
    ),
    limit: int = typer.Option(None, "--limit", help="Stop after this many meetings (debug)."),
    skip_pdfs: bool = typer.Option(False, "--skip-pdfs", help="Don't download PDFs."),
    skip_text: bool = typer.Option(False, "--skip-text", help="Don't extract PDF text."),
    save_raw: bool = typer.Option(False, "--save-raw", help="Save raw JSON responses under data/raw/."),
    rps: float = typer.Option(1.0, "--rps", help="Requests per second."),
    db_path: Path = typer.Option(DEFAULT_DB, "--db"),
    pdf_root: Path = typer.Option(DEFAULT_PDFS, "--pdf-root"),
) -> None:
    """Discover committees + meetings, fetch each agenda, download PDFs, extract text."""
    raw_dir = DEFAULT_RAW if save_raw else None
    store = Store(db_path)
    try:
        with HttpClient(rps=rps, save_raw_dir=raw_dir) as client:
            committees_meetings = _discover(client, store)
            scheduled = list(
                _select_meetings(
                    committees_meetings,
                    from_year=from_year,
                    committees=set(committee) if committee else None,
                    limit=limit,
                )
            )
            typer.echo(f"Scheduled {len(scheduled)} meetings across {len(committees_meetings)} committees")
            for i, m in enumerate(scheduled, 1):
                logger.info("[%d/%d] %s %s %s", i, len(scheduled), m.meeting_date, m.kind, m.title)
                _fetch_agenda(client, store, m.id, m.committee_id)
            if not skip_pdfs:
                _validate_existing_downloads(store)
                _download_pdfs(client, store, pdf_root)
            if not skip_text:
                _extract_texts(store)
    finally:
        store.close()


def _discover(client: HttpClient, store: Store) -> list[tuple[object, list]]:
    payload = client.get_json(sources.udvalgsliste_url(), label="udvalgsliste")
    parsed = agenda_parser.parse_udvalgsliste(payload)
    for committee, meetings in parsed:
        store.upsert_committee(committee)
        for m in meetings:
            store.upsert_meeting(m)
    return parsed


def _select_meetings(
    committees_meetings,
    *,
    from_year: int | None,
    committees: set[str] | None,
    limit: int | None,
):
    seen = 0
    for committee, meetings in committees_meetings:
        if committees and committee.id not in committees:
            continue
        for m in sorted(meetings, key=lambda x: x.meeting_date, reverse=True):
            if from_year is not None and m.meeting_date.year < from_year:
                continue
            yield m
            seen += 1
            if limit is not None and seen >= limit:
                return


def _fetch_agenda(client: HttpClient, store: Store, meeting_id: str, committee_id: str) -> None:
    payload = client.get_json(sources.agenda_url(meeting_id), label=f"agenda/{meeting_id}")
    parsed = agenda_parser.parse_agenda(payload, committee_id=committee_id)
    store.upsert_meeting(parsed.meeting)
    for doc in parsed.documents:
        store.upsert_document(parsed.meeting.id, doc)
    store.mark_agenda_fetched(meeting_id)


def _validate_existing_downloads(store: Store) -> None:
    """Drop on-disk files that aren't real PDFs and clear their download record.

    Earlier versions of the scraper recorded auth-challenge HTML pages as if
    they were PDFs. This pass cleans those up so the subsequent download stage
    can retry them in the same run.
    """
    bad = 0
    for doc_id, path in store.recorded_downloads():
        pdf_path = Path(path)
        if not pdfmod.is_pdf(pdf_path):
            pdf_path.unlink(missing_ok=True)
            store.clear_download(doc_id)
            bad += 1
    if bad:
        typer.echo(f"Discarded {bad} non-PDF file(s) from previous runs.")


def _download_pdfs(client: HttpClient, store: Store, pdf_root: Path) -> None:
    pending = store.documents_missing_download()
    typer.echo(f"Downloading {len(pending)} PDFs...")
    for doc_id, meeting_id, url in pending:
        row = store._conn.execute(  # noqa: SLF001
            "SELECT committee_id, strftime('%Y', meeting_date) FROM meetings WHERE id = ?",
            (meeting_id,),
        ).fetchone()
        if not row:
            logger.warning("orphan document %s (meeting %s not in DB)", doc_id, meeting_id)
            continue
        committee_id, year_str = row
        try:
            path, sha256, size = pdfmod.download(
                client, url, pdf_root=pdf_root, committee_id=committee_id, year=int(year_str)
            )
        except Exception as exc:
            logger.warning("download failed for %s (%s): %s", doc_id, url, exc)
            continue
        store.record_download(doc_id, sha256=sha256, path=path, size=size)


def _extract_texts(store: Store) -> None:
    pending = store.documents_missing_text()
    typer.echo(f"Extracting text from {len(pending)} PDFs...")
    for doc_id, path in pending:
        pdf_path = Path(path)
        try:
            text = pdfmod.extract_text(pdf_path)
        except Exception as exc:
            logger.warning("extract_text failed for %s: %s", doc_id, exc)
            continue
        if text:
            store.store_text(doc_id, text)


@app.command(name="list-committees")
def list_committees(db_path: Path = typer.Option(DEFAULT_DB, "--db")) -> None:
    """List committees currently stored in the database."""
    if not db_path.exists():
        typer.echo("(no database yet — run `hkr scrape` first)")
        raise typer.Exit()
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT period, id, name FROM committees ORDER BY period DESC, name"
        ).fetchall()
    if not rows:
        typer.echo("(no committees stored)")
        return
    for period, cid, name in rows:
        typer.echo(f"{period or '-':35} {cid}  {name}")


@app.command()
def search(
    query: str = typer.Argument(..., help="FTS5 query string."),
    committee: str = typer.Option(None, "--committee", help="Restrict to a committee GUID."),
    db_path: Path = typer.Option(DEFAULT_DB, "--db"),
) -> None:
    """Full-text search across extracted PDF text."""
    if not db_path.exists():
        typer.echo("(no database yet)")
        raise typer.Exit(code=1)
    with sqlite3.connect(db_path) as conn:
        sql = """
            SELECT m.meeting_date, c.name, m.title, d.title, d.id
            FROM doc_fts f
            JOIN documents d ON d.id = f.document_id
            JOIN meetings  m ON m.id = d.meeting_id
            JOIN committees c ON c.id = m.committee_id
            WHERE doc_fts MATCH ?
        """
        params: list[object] = [query]
        if committee is not None:
            sql += " AND c.id = ?"
            params.append(committee)
        sql += " ORDER BY m.meeting_date DESC LIMIT 50"
        for row in conn.execute(sql, params):
            typer.echo("\t".join(str(x) for x in row))


@app.command(name="db-path")
def db_path_cmd(db_path: Path = typer.Option(DEFAULT_DB, "--db")) -> None:
    """Print the resolved database path."""
    typer.echo(str(db_path.resolve()))


@app.command(name="probe-pdf")
def probe_pdf(
    document_id: str = typer.Argument(..., help="A document GUID seen in `documents` table."),
    rps: float = typer.Option(1.0, "--rps"),
) -> None:
    """Diagnose what /Vis/Pdf/bilag/{id} actually returns (status, content-type, first 300 bytes)."""
    import httpx

    from hkr.sources import bilag_pdf_url

    url = bilag_pdf_url(document_id)
    with HttpClient(rps=rps) as client:
        # Bootstrap the session cookie via a known-working API call first.
        client.get_json(sources.udvalgsliste_url(), label=None)
        # Now probe the PDF URL using the underlying httpx client directly so we
        # can see redirect history and headers without saving anything.
        resp = client._client.get(url)  # noqa: SLF001
    typer.echo(f"Final status: {resp.status_code}")
    typer.echo(f"Final URL:    {resp.url}")
    typer.echo(f"Content-Type: {resp.headers.get('content-type')}")
    typer.echo(f"Content-Length: {resp.headers.get('content-length')}")
    typer.echo("Redirect chain:")
    for h in resp.history:
        typer.echo(f"  {h.status_code} {h.url} -> {h.headers.get('location')}")
    body = resp.content
    typer.echo(f"\nFirst 5 bytes: {body[:5]!r}  (PDF would be b'%PDF-')")
    typer.echo("First 300 bytes:")
    typer.echo(body[:300].decode("utf-8", errors="replace"))


if __name__ == "__main__":
    app()
