"""JSON -> dataclass mappers for FirstAgenda Publication payloads.

Pure functions: take a parsed JSON ``dict`` and return ``hkr.models`` dataclasses,
so they can be unit-tested against fixtures in ``tests/fixtures/json/`` without
any HTTP. Shapes are documented inline; if a payload drifts, an
``UnknownStructureError`` is raised so the offending response can be inspected.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Iterable

from hkr.models import (
    Committee,
    Document,
    DocumentKind,
    MeetingKind,
    MeetingRef,
    ParsedAgenda,
)
from hkr.sources import bilag_pdf_url


class UnknownStructureError(ValueError):
    """Raised when a payload doesn't match the expected FirstAgenda shape."""


def _require(payload: Any, key: str) -> Any:
    if not isinstance(payload, dict) or key not in payload:
        raise UnknownStructureError(f"missing key {key!r} in payload")
    return payload[key]


def _kind_from_navn(navn: str | None) -> MeetingKind:
    # Observed Navn values: "Referat", "Dagsorden", "Tillægsdagsorden",
    # "Lukket referat", "Referat 1. behandling budget", or None.
    if navn and navn.lower().startswith(("referat", "lukket referat")):
        return "referat"
    return "dagsorden"


def _parse_iso_date(value: str | None) -> date:
    if not value:
        raise UnknownStructureError("missing meeting date")
    # Format observed: "2026-05-04T14:00:00+02:00"
    return datetime.fromisoformat(value).date()


def _parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)


def parse_udvalgsliste(payload: Any) -> list[tuple[Committee, list[MeetingRef]]]:
    """Map ``GET /api/agenda/udvalgsliste`` into committees + their meetings.

    The response shape is ``{"Udvalg": {"<period name>": [committee, ...], ...}}``.
    Each committee has a ``Moeder`` list with meeting summaries we can use as
    ``MeetingRef`` without making any additional HTTP calls.
    """
    udvalg = _require(payload, "Udvalg")
    if not isinstance(udvalg, dict):
        raise UnknownStructureError("Udvalg should be a mapping of period -> list")

    out: list[tuple[Committee, list[MeetingRef]]] = []
    for period, committees in udvalg.items():
        if not isinstance(committees, list):
            raise UnknownStructureError(f"period {period!r} should map to a list")
        for c in committees:
            committee = Committee(
                id=_require(c, "Id"),
                name=_require(c, "Navn"),
                period=period,
                organisation_id=c.get("OrganisationId"),
                historisk=bool(c.get("Historisk", False)),
            )
            meetings = [_meeting_from_moede(m, committee.id) for m in (c.get("Moeder") or [])]
            out.append((committee, meetings))
    return out


def _meeting_from_moede(m: dict, committee_id: str) -> MeetingRef:
    navn = m.get("Navn")
    return MeetingRef(
        id=_require(m, "Id"),
        committee_id=committee_id,
        title=navn or "Dagsorden",
        meeting_date=_parse_iso_date(m.get("Dato") or m.get("MeetingBeginUtc")),
        kind=_kind_from_navn(navn),
        location=m.get("Sted"),
        is_supplementary=bool(m.get("IsSupplementaryAgenda", False))
        or (navn or "").lower().startswith("tillæg"),
        is_closed=(navn or "").lower().startswith("lukket"),
        released_at=_parse_iso_datetime(m.get("ReleasedDate")),
    )


def parse_agenda(payload: Any, *, committee_id: str | None = None) -> ParsedAgenda:
    """Map ``GET /api/agenda/dagsorden/{meeting_id}`` into a ParsedAgenda.

    The top-level ``Id`` is the meeting id (the path param). ``Udvalg.Id`` is
    the committee id; ``Moede.Id`` in this payload is a zero-GUID and should be
    ignored. ``Dagsordenpunkter[]`` contains items with ``Felter[]`` (case
    presentation PDFs) and ``Bilag[]`` (attachment PDFs).
    """
    meeting_id = _require(payload, "Id")
    udvalg = _require(payload, "Udvalg")
    moede = _require(payload, "Moede")
    cid = committee_id or _require(udvalg, "Id")
    navn = moede.get("Navn") or udvalg.get("Navn") or "Dagsorden"
    meeting = MeetingRef(
        id=meeting_id,
        committee_id=cid,
        title=navn,
        meeting_date=_parse_iso_date(moede.get("Dato") or moede.get("MeetingBeginUtc")),
        kind=_kind_from_navn(moede.get("Navn")),
        location=moede.get("Sted"),
        is_supplementary=bool(payload.get("TillaegsDagsorden", False))
        or bool(moede.get("IsSupplementaryAgenda", False)),
        is_closed=(moede.get("Navn") or "").lower().startswith("lukket"),
        released_at=_parse_iso_datetime(moede.get("ReleasedDate")),
    )
    documents = list(_documents_from_punkter(payload.get("Dagsordenpunkter") or []))
    return ParsedAgenda(meeting=meeting, documents=documents)


def _documents_from_punkter(punkter: Iterable[dict]) -> Iterable[Document]:
    zero_guid = "00000000-0000-0000-0000-000000000000"
    for p in punkter:
        item_no = p.get("Punktnummer") or p.get("Number")
        item_title = p.get("Navn") or p.get("Caption")
        for felt in p.get("Felter") or []:
            doc_id = felt.get("DocumentId")
            link = felt.get("Link")
            if not doc_id or doc_id == zero_guid:
                continue
            yield Document(
                id=doc_id,
                kind="felt",
                title=felt.get("Navn") or item_title or "",
                url=link or bilag_pdf_url(doc_id),
                item_no=str(item_no) if item_no is not None else None,
                item_title=item_title,
            )
        for b in p.get("Bilag") or []:
            doc_id = b.get("Id")
            if not doc_id or doc_id == zero_guid:
                continue
            yield Document(
                id=doc_id,
                kind="bilag",
                title=b.get("Navn") or "",
                url=bilag_pdf_url(doc_id),
                item_no=str(item_no) if item_no is not None else None,
                item_title=item_title,
                order=b.get("Order"),
            )


__all__ = [
    "Committee",
    "Document",
    "MeetingRef",
    "ParsedAgenda",
    "UnknownStructureError",
    "parse_agenda",
    "parse_udvalgsliste",
]
