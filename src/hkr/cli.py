from __future__ import annotations

import logging
from pathlib import Path

import typer

from hkr import __version__

app = typer.Typer(no_args_is_help=True, add_completion=False, help="Hvidovre Kommune referat-scraper.")


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
    from_year: int = typer.Option(None, "--from-year", help="Only scrape meetings from this year onwards."),
    committee: list[int] = typer.Option(None, "--committee", help="Restrict to these committee IDs (repeatable)."),
    limit: int = typer.Option(None, "--limit", help="Stop after this many meetings (debug)."),
    save_raw: bool = typer.Option(False, "--save-raw", help="Save raw JSON responses under data/raw/."),
    rps: float = typer.Option(1.0, "--rps", help="Requests per second."),
    db_path: Path = typer.Option(Path("data/hkr.db"), "--db"),
) -> None:
    """Discover committees and meetings, persist metadata, fetch PDFs."""
    typer.echo(
        "scrape: not yet implemented — waiting for FirstAgenda Publication API "
        "captures in docs/api-capture.md before sources.py and parser.py can be filled in.",
        err=True,
    )
    raise typer.Exit(code=2)


@app.command(name="list-committees")
def list_committees(db_path: Path = typer.Option(Path("data/hkr.db"), "--db")) -> None:
    """List committees currently stored in the database."""
    import sqlite3

    if not db_path.exists():
        typer.echo("(no database yet — run `hkr scrape` first)")
        raise typer.Exit()
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute("SELECT id, name FROM committees ORDER BY name").fetchall()
    if not rows:
        typer.echo("(no committees stored)")
        return
    for cid, name in rows:
        typer.echo(f"{cid}\t{name}")


@app.command()
def search(
    query: str = typer.Argument(..., help="FTS5 query string."),
    committee: int = typer.Option(None, "--committee", help="Restrict to a committee."),
    db_path: Path = typer.Option(Path("data/hkr.db"), "--db"),
) -> None:
    """Full-text search across extracted PDF text."""
    import sqlite3

    if not db_path.exists():
        typer.echo("(no database yet)")
        raise typer.Exit(code=1)
    with sqlite3.connect(db_path) as conn:
        sql = """
            SELECT m.meeting_date, c.name, m.title, d.title
            FROM doc_fts
            JOIN documents d ON d.id = doc_fts.rowid
            JOIN meetings  m ON m.agenda_id = d.agenda_id
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
def db_path_cmd(db_path: Path = typer.Option(Path("data/hkr.db"), "--db")) -> None:
    """Print the resolved database path."""
    typer.echo(str(db_path.resolve()))


if __name__ == "__main__":
    app()
