from datetime import date
from pathlib import Path

from hkr.models import Committee, Document, MeetingRef
from hkr.store import Store


def test_upsert_is_idempotent(tmp_path: Path) -> None:
    store = Store(tmp_path / "hkr.db")
    committee = Committee(
        id="4ad448f3-5628-48d9-9412-e48acd19b5fd",
        name="Børne- og Uddannelsesudvalget",
        period="Udvalg 2022-2025",
    )
    meeting = MeetingRef(
        id="0cad2b4d-c4a2-4583-a053-60704b2da0e5",
        committee_id=committee.id,
        title="Referat",
        meeting_date=date(2026, 5, 4),
        kind="referat",
        location="Sollentuna II",
    )
    doc = Document(
        id="7410e4a3-b07a-44c2-ba27-1a06cbb1f453",
        kind="bilag",
        title="Ansøgningsskrivelse skema A Grenhusene",
        url="https://dagsordener-referater.hvidovre.dk/Vis/Pdf/bilag/7410e4a3-b07a-44c2-ba27-1a06cbb1f453",
        item_no="3",
    )

    for _ in range(2):
        store.upsert_committee(committee)
        store.upsert_meeting(meeting)
        store.upsert_document(meeting.id, doc)

    conn = store._conn  # noqa: SLF001 — test-only access
    assert conn.execute("SELECT COUNT(*) FROM committees").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM meetings").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0] == 1
    store.close()


def test_store_text_round_trips_through_fts(tmp_path: Path) -> None:
    store = Store(tmp_path / "hkr.db")
    committee = Committee(id="C", name="Committee", period="P")
    meeting = MeetingRef(
        id="M",
        committee_id="C",
        title="t",
        meeting_date=date(2026, 1, 1),
        kind="dagsorden",
    )
    doc = Document(id="D", kind="felt", title="t", url="http://x", item_no="1")
    store.upsert_committee(committee)
    store.upsert_meeting(meeting)
    store.upsert_document("M", doc)
    store.store_text("D", "byggetilladelse til opførelse af tilbygning")

    rows = list(
        store._conn.execute(  # noqa: SLF001
            "SELECT document_id FROM doc_fts WHERE doc_fts MATCH 'byggetilladelse'"
        )
    )
    assert rows == [("D",)]
    store.close()
