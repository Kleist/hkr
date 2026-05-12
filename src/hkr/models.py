from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Literal

MeetingKind = Literal["dagsorden", "referat"]
DocumentKind = Literal["bilag", "felt"]


@dataclass(frozen=True)
class Committee:
    id: str
    name: str
    period: str | None = None
    organisation_id: str | None = None
    historisk: bool = False


@dataclass(frozen=True)
class MeetingRef:
    id: str
    committee_id: str
    title: str
    meeting_date: date
    kind: MeetingKind
    location: str | None = None
    is_supplementary: bool = False
    is_closed: bool = False
    released_at: datetime | None = None


@dataclass(frozen=True)
class Document:
    id: str
    kind: DocumentKind
    title: str
    url: str
    item_no: str | None = None
    item_title: str | None = None
    order: int | None = None


@dataclass(frozen=True)
class ParsedAgenda:
    meeting: MeetingRef
    documents: list[Document] = field(default_factory=list)
    scraped_at: datetime = field(default_factory=lambda: datetime.now(UTC))
