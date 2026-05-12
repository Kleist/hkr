from pathlib import Path

import pytest

from hkr.pdf import NotAPdfError, resolve_pdf_url

FIXTURES = Path(__file__).parent / "fixtures" / "html"


def test_resolve_pdf_url_returns_iframe_src_decoded() -> None:
    html = (FIXTURES / "vispdf_bilag.html").read_text()
    url = resolve_pdf_url(html)
    assert url.startswith("https://firstagenda-4.s3.eu-west-1.amazonaws.com/")
    # HTML entities must be decoded back to & for the query params
    assert "&X-Amz-Signature=" in url
    assert "&amp;" not in url


def test_resolve_pdf_url_raises_when_no_iframe() -> None:
    with pytest.raises(NotAPdfError):
        resolve_pdf_url("<html><body>no iframe here</body></html>")
