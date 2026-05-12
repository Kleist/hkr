import json
from pathlib import Path

from hkr.parser import parse_agenda, parse_udvalgsliste

FIXTURES = Path(__file__).parent / "fixtures" / "json"


def _load(name: str):
    return json.loads((FIXTURES / name).read_text())


def test_parse_udvalgsliste_groups_by_period() -> None:
    result = parse_udvalgsliste(_load("udvalgsliste.json"))
    assert len(result) > 0
    periods = {c.period for c, _ in result}
    assert "Udvalg 2026-2029" in periods
    assert "Udvalg 2022-2025" in periods

    boerne = next(c for c, _ in result if c.id == "4ad448f3-5628-48d9-9412-e48acd19b5fd")
    assert boerne.name == "Børne- og Uddannelsesudvalget"
    assert boerne.period == "Udvalg 2022-2025"


def test_parse_udvalgsliste_extracts_meetings() -> None:
    result = parse_udvalgsliste(_load("udvalgsliste.json"))
    total_meetings = sum(len(meetings) for _, meetings in result)
    assert total_meetings > 1000

    by_plan_2026 = next(c for c, _ in result if c.id == "ac4bbfca-65b5-4a1a-9ff3-0e9717ed6adf")
    meetings = next(ms for c, ms in result if c.id == by_plan_2026.id)
    assert all(m.committee_id == by_plan_2026.id for m in meetings)
    assert all(m.meeting_date.year >= 2025 for m in meetings)


def test_meeting_kind_inferred_from_navn() -> None:
    result = parse_udvalgsliste(_load("udvalgsliste.json"))
    kinds = {m.kind for _, meetings in result for m in meetings}
    assert kinds == {"dagsorden", "referat"}


def test_parse_agenda_extracts_meeting_and_documents() -> None:
    parsed = parse_agenda(_load("agenda.json"))
    assert parsed.meeting.id == "0cad2b4d-c4a2-4583-a053-60704b2da0e5"
    assert parsed.meeting.committee_id == "5dd92504-8e21-4dc9-90cc-1584b1ca0882"
    assert parsed.meeting.kind == "dagsorden"
    assert parsed.meeting.meeting_date.year == 2026

    assert len(parsed.documents) > 0
    bilag = [d for d in parsed.documents if d.kind == "bilag"]
    felter = [d for d in parsed.documents if d.kind == "felt"]
    assert bilag, "expected at least one Bilag"
    assert felter, "expected at least one Felt with a real DocumentId"

    sample = bilag[0]
    assert sample.url.startswith("https://dagsordener-referater.hvidovre.dk/Vis/Pdf/bilag/")
    assert sample.item_no is not None


def test_parse_agenda_skips_zero_guid_documents() -> None:
    parsed = parse_agenda(_load("agenda.json"))
    zero = "00000000-0000-0000-0000-000000000000"
    assert all(d.id != zero for d in parsed.documents)
