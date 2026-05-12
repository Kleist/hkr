"""URL builders for the FirstAgenda Publication backend used by
https://dagsordener-referater.hvidovre.dk/.

The concrete endpoint paths are filled in once DevTools captures land in
``docs/api-capture.md``. Until then, the constants below are placeholders and
the builders raise ``NotImplementedError`` so callers fail fast.
"""

from __future__ import annotations

# TODO(api-capture): replace with the actual host/base path seen in DevTools.
# Likely something like https://publication.firstagenda.com/api/...
BASE_URL: str | None = None


def _require_base() -> str:
    if BASE_URL is None:
        raise NotImplementedError(
            "FirstAgenda Publication base URL not configured yet. "
            "Capture the XHR/fetch traffic from "
            "https://dagsordener-referater.hvidovre.dk/ and populate "
            "hkr.sources.BASE_URL (see docs/api-capture.md)."
        )
    return BASE_URL


def committees_url() -> str:
    return f"{_require_base()}/committees"


def meetings_url(committee_id: int) -> str:
    return f"{_require_base()}/committees/{committee_id}/meetings"


def agenda_url(agenda_id: int) -> str:
    return f"{_require_base()}/meetings/{agenda_id}"
