"""JSON -> dataclass mappers for the FirstAgenda Publication payloads.

These are intentionally pure: they take a parsed JSON ``dict``/``list`` and
return ``hkr.models`` dataclasses, so they can be unit-tested against fixtures
without any HTTP. The concrete key names are finalised once the captured
payloads land in ``tests/fixtures/json/``.
"""

from __future__ import annotations

from typing import Any

from hkr.models import Committee, Document, MeetingRef, ParsedAgenda


class UnknownStructureError(ValueError):
    """Raised when a payload doesn't match the expected FirstAgenda shape."""


def parse_committees(payload: Any) -> list[Committee]:
    raise NotImplementedError(
        "Implement once docs/api-capture.md contains a sample committees response."
    )


def parse_meeting_list(payload: Any, *, committee_id: int) -> list[MeetingRef]:
    raise NotImplementedError(
        "Implement once docs/api-capture.md contains a sample meetings response."
    )


def parse_agenda(payload: Any) -> ParsedAgenda:
    raise NotImplementedError(
        "Implement once docs/api-capture.md contains a sample agenda/meeting response."
    )


__all__ = [
    "Committee",
    "Document",
    "MeetingRef",
    "ParsedAgenda",
    "UnknownStructureError",
    "parse_agenda",
    "parse_committees",
    "parse_meeting_list",
]
