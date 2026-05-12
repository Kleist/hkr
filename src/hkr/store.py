from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterator

from hkr.models import Committee, Document, MeetingRef

SCHEMA = """
CREATE TABLE IF NOT EXISTS committees (
    id   INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    slug TEXT,
    url  TEXT
);

CREATE TABLE IF NOT EXISTS meetings (
    agenda_id    INTEGER PRIMARY KEY,
    committee_id INTEGER NOT NULL REFERENCES committees(id),
    title        TEXT NOT NULL,
    meeting_date DATE NOT NULL,
    kind         TEXT NOT NULL CHECK (kind IN ('dagsorden', 'referat')),
    url          TEXT,
    scraped_at   TIMESTAMP NOT NULL,
    raw_html_sha TEXT
);
CREATE INDEX IF NOT EXISTS ix_meetings_committee_date
    ON meetings (committee_id, meeting_date);

CREATE TABLE IF NOT EXISTS documents (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    agenda_id     INTEGER NOT NULL REFERENCES meetings(agenda_id),
    item_no       TEXT,
    title         TEXT,
    url           TEXT NOT NULL,
    sha256        TEXT UNIQUE,
    path          TEXT,
    bytes         INTEGER,
    downloaded_at TIMESTAMP,
    UNIQUE (agenda_id, url)
);

CREATE TABLE IF NOT EXISTS doc_text (
    document_id   INTEGER PRIMARY KEY REFERENCES documents(id),
    text          TEXT NOT NULL,
    extracted_at  TIMESTAMP NOT NULL
);

CREATE VIRTUAL TABLE IF NOT EXISTS doc_fts
    USING fts5(text, content='doc_text', content_rowid='document_id');
"""


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
                INSERT INTO committees (id, name, slug, url)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    slug = excluded.slug,
                    url  = excluded.url
                """,
                (c.id, c.name, c.slug, c.url),
            )

    def upsert_meeting(self, m: MeetingRef, *, raw_html_sha: str | None = None) -> None:
        with self.tx() as conn:
            conn.execute(
                """
                INSERT INTO meetings (
                    agenda_id, committee_id, title, meeting_date, kind, url,
                    scraped_at, raw_html_sha
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(agenda_id) DO UPDATE SET
                    committee_id = excluded.committee_id,
                    title        = excluded.title,
                    meeting_date = excluded.meeting_date,
                    kind         = excluded.kind,
                    url          = excluded.url,
                    scraped_at   = excluded.scraped_at,
                    raw_html_sha = excluded.raw_html_sha
                """,
                (
                    m.agenda_id,
                    m.committee_id,
                    m.title,
                    m.meeting_date.isoformat(),
                    m.kind,
                    m.url,
                    datetime.now(UTC).isoformat(),
                    raw_html_sha,
                ),
            )

    def register_document(self, agenda_id: int, d: Document) -> int:
        with self.tx() as conn:
            row = conn.execute(
                "SELECT id FROM documents WHERE agenda_id = ? AND url = ?",
                (agenda_id, d.url),
            ).fetchone()
            if row is not None:
                return int(row[0])
            cur = conn.execute(
                """
                INSERT INTO documents (agenda_id, item_no, title, url)
                VALUES (?, ?, ?, ?)
                """,
                (agenda_id, d.item_no, d.title, d.url),
            )
            assert cur.lastrowid is not None
            return int(cur.lastrowid)
