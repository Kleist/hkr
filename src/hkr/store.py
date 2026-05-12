from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterator

from hkr.models import Committee, Document, MeetingRef

SCHEMA = """
CREATE TABLE IF NOT EXISTS committees (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    period          TEXT,
    organisation_id TEXT,
    historisk       INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS meetings (
    id               TEXT PRIMARY KEY,
    committee_id     TEXT NOT NULL REFERENCES committees(id),
    title            TEXT NOT NULL,
    meeting_date     DATE NOT NULL,
    kind             TEXT NOT NULL CHECK (kind IN ('dagsorden', 'referat')),
    location         TEXT,
    is_supplementary INTEGER NOT NULL DEFAULT 0,
    is_closed        INTEGER NOT NULL DEFAULT 0,
    released_at      TIMESTAMP,
    scraped_at       TIMESTAMP NOT NULL,
    agenda_fetched_at TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_meetings_committee_date
    ON meetings (committee_id, meeting_date);

CREATE TABLE IF NOT EXISTS documents (
    id            TEXT PRIMARY KEY,
    meeting_id    TEXT NOT NULL REFERENCES meetings(id),
    kind          TEXT NOT NULL CHECK (kind IN ('bilag', 'felt')),
    title         TEXT,
    url           TEXT NOT NULL,
    item_no       TEXT,
    item_title    TEXT,
    "order"       INTEGER,
    sha256        TEXT,
    path          TEXT,
    bytes         INTEGER,
    downloaded_at TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_documents_meeting ON documents (meeting_id);
CREATE INDEX IF NOT EXISTS ix_documents_sha256 ON documents (sha256);

CREATE TABLE IF NOT EXISTS doc_text (
    document_id   TEXT PRIMARY KEY REFERENCES documents(id),
    text          TEXT NOT NULL,
    extracted_at  TIMESTAMP NOT NULL
);

CREATE VIRTUAL TABLE IF NOT EXISTS doc_fts
    USING fts5(document_id UNINDEXED, text);
"""


def _now() -> str:
    return datetime.now(UTC).isoformat()


class Store:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path)
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    @contextmanager
    def tx(self) -> Iterator[sqlite3.Connection]:
        try:
            yield self._conn
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise

    def upsert_committee(self, c: Committee) -> None:
        with self.tx() as conn:
            conn.execute(
                """
                INSERT INTO committees (id, name, period, organisation_id, historisk)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name            = excluded.name,
                    period          = excluded.period,
                    organisation_id = excluded.organisation_id,
                    historisk       = excluded.historisk
                """,
                (c.id, c.name, c.period, c.organisation_id, int(c.historisk)),
            )

    def upsert_meeting(self, m: MeetingRef) -> None:
        with self.tx() as conn:
            conn.execute(
                """
                INSERT INTO meetings (
                    id, committee_id, title, meeting_date, kind, location,
                    is_supplementary, is_closed, released_at, scraped_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    committee_id     = excluded.committee_id,
                    title            = excluded.title,
                    meeting_date     = excluded.meeting_date,
                    kind             = excluded.kind,
                    location         = excluded.location,
                    is_supplementary = excluded.is_supplementary,
                    is_closed        = excluded.is_closed,
                    released_at      = excluded.released_at,
                    scraped_at       = excluded.scraped_at
                """,
                (
                    m.id,
                    m.committee_id,
                    m.title,
                    m.meeting_date.isoformat(),
                    m.kind,
                    m.location,
                    int(m.is_supplementary),
                    int(m.is_closed),
                    m.released_at.isoformat() if m.released_at else None,
                    _now(),
                ),
            )

    def mark_agenda_fetched(self, meeting_id: str) -> None:
        with self.tx() as conn:
            conn.execute(
                "UPDATE meetings SET agenda_fetched_at = ? WHERE id = ?",
                (_now(), meeting_id),
            )

    def upsert_document(self, meeting_id: str, d: Document) -> None:
        with self.tx() as conn:
            conn.execute(
                """
                INSERT INTO documents (id, meeting_id, kind, title, url, item_no, item_title, "order")
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    meeting_id = excluded.meeting_id,
                    kind       = excluded.kind,
                    title      = excluded.title,
                    url        = excluded.url,
                    item_no    = excluded.item_no,
                    item_title = excluded.item_title,
                    "order"    = excluded."order"
                """,
                (d.id, meeting_id, d.kind, d.title, d.url, d.item_no, d.item_title, d.order),
            )

    def clear_download(self, document_id: str) -> None:
        with self.tx() as conn:
            conn.execute(
                "UPDATE documents SET sha256 = NULL, path = NULL, bytes = NULL, downloaded_at = NULL WHERE id = ?",
                (document_id,),
            )

    def record_download(self, document_id: str, *, sha256: str, path: Path, size: int) -> None:
        with self.tx() as conn:
            conn.execute(
                """
                UPDATE documents
                   SET sha256 = ?, path = ?, bytes = ?, downloaded_at = ?
                 WHERE id = ?
                """,
                (sha256, str(path), size, _now(), document_id),
            )

    def store_text(self, document_id: str, text: str) -> None:
        with self.tx() as conn:
            conn.execute(
                """
                INSERT INTO doc_text (document_id, text, extracted_at)
                VALUES (?, ?, ?)
                ON CONFLICT(document_id) DO UPDATE SET
                    text         = excluded.text,
                    extracted_at = excluded.extracted_at
                """,
                (document_id, text, _now()),
            )
            conn.execute("DELETE FROM doc_fts WHERE document_id = ?", (document_id,))
            conn.execute(
                "INSERT INTO doc_fts (document_id, text) VALUES (?, ?)",
                (document_id, text),
            )

    def recorded_downloads(self) -> list[tuple[str, str]]:
        cur = self._conn.execute(
            "SELECT id, path FROM documents WHERE path IS NOT NULL"
        )
        return [(row[0], row[1]) for row in cur.fetchall()]

    def documents_missing_download(self) -> list[tuple[str, str, str]]:
        cur = self._conn.execute(
            "SELECT id, meeting_id, url FROM documents WHERE path IS NULL"
        )
        return [(row[0], row[1], row[2]) for row in cur.fetchall()]

    def documents_missing_text(self) -> list[tuple[str, str]]:
        cur = self._conn.execute(
            """
            SELECT d.id, d.path FROM documents d
            LEFT JOIN doc_text t ON t.document_id = d.id
            WHERE d.path IS NOT NULL AND t.document_id IS NULL
            """
        )
        return [(row[0], row[1]) for row in cur.fetchall()]
