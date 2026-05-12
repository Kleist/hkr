from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Literal

MeetingKind = Literal["dagsorden", "referat"]


@dataclass(frozen=True)
class Committee:
    id: int
    name: str
    slug: str | None = None
    url: str | None = None


@dataclass(frozen=True)
class Document:
    url: str
    title: str
    item_no: str | None = None


@dataclass(frozen=True)
class MeetingRef:
    agenda_id: int
    committee_id: int
    title: str
    meeting_date: date
    kind: MeetingKind
    url: str | None = None


@dataclass(frozen=True)
class ParsedAgenda:
    meeting: MeetingRef
    documents: list[Document] = field(default_factory=list)
    scraped_at: datetime = field(default_factory=datetime.utcnow)
