"""URL builders for the FirstAgenda Publication backend used by
https://dagsordener-referater.hvidovre.dk/.

Discovered from the captured HAR (see docs/api-capture.md). Three endpoints
are enough to crawl the whole dataset:

- ``GET /api/agenda/udvalgsliste`` returns every committee, grouped by election
  period, with all of that committee's meetings inlined.
- ``GET /api/agenda/dagsorden/{meeting_id}`` returns one meeting's agenda items
  ("Dagsordenpunkter") with attachments ("Bilag") and case-presentation fields
  ("Felter") that link to the PDF storage.
- ``GET /Vis/Pdf/bilag/{document_id}`` serves the PDF for any document GUID
  (used for both "Felter[].DocumentId" case presentations and "Bilag[].Id"
  attachments).
"""

from __future__ import annotations

BASE_URL = "https://dagsordener-referater.hvidovre.dk"


def udvalgsliste_url() -> str:
    return f"{BASE_URL}/api/agenda/udvalgsliste"


def agenda_url(meeting_id: str) -> str:
    return f"{BASE_URL}/api/agenda/dagsorden/{meeting_id}"


def bilag_pdf_url(document_id: str) -> str:
    return f"{BASE_URL}/Vis/Pdf/bilag/{document_id}"
