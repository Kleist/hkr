from datetime import date
from pathlib import Path

from hkr.models import Committee, Document, MeetingRef
from hkr.store import Store


def test_upsert_is_idempotent(tmp_path: Path) -> None:
    store = Store(tmp_path / "hkr.db")
    committee = Committee(id=88, name="Bygge- og Planudvalget")
    meeting = MeetingRef(
        agenda_id=2877,
        committee_id=88,
        title="Møde i Bygge- og Planudvalget",
        meeting_date=date(2024, 5, 6),
        kind="referat",
        url="https://dagsordener-referater.hvidovre.dk/#/meeting/2877",
    )
    doc = Document(
        url="https://example.invalid/doc.pdf",
        title="Punkt 1: Byggetilladelse",
        item_no="1",
    )

    for _ in range(2):
        store.upsert_committee(committee)
        store.upsert_meeting(meeting)
        store.register_document(meeting.agenda_id, doc)

    conn = store._conn  # noqa: SLF001 — test-only access
    assert conn.execute("SELECT COUNT(*) FROM committees").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM meetings").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0] == 1
    store.close()
