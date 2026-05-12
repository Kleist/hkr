from __future__ import annotations

import hashlib
import html
import logging
import re
import shutil
import tempfile
from pathlib import Path

from pypdf import PdfReader

from hkr.client import HttpClient

logger = logging.getLogger(__name__)

PDF_MAGIC = b"%PDF-"

# The /Vis/Pdf/bilag/{id} endpoint returns an HTML "Dokumentvisning" page whose
# iframe src is a short-lived (~5 min) presigned S3 URL serving the real PDF.
_IFRAME_SRC_RE = re.compile(r'<iframe[^>]*\bsrc="([^"]+)"', re.IGNORECASE)


class NotAPdfError(ValueError):
    """Downloaded body is not a PDF, or the viewer wrapper didn't expose one."""


def is_pdf(path: Path) -> bool:
    try:
        with path.open("rb") as fh:
            return fh.read(5) == PDF_MAGIC
    except OSError:
        return False


def resolve_pdf_url(viewer_html: str) -> str:
    """Extract the presigned PDF URL from a FirstAgenda viewer HTML page."""
    match = _IFRAME_SRC_RE.search(viewer_html)
    if not match:
        raise NotAPdfError("no <iframe src> in viewer HTML")
    return html.unescape(match.group(1))


def content_addressed_path(root: Path, committee_id: str, year: int, sha256: str) -> Path:
    return root / committee_id / str(year) / sha256[:2] / f"{sha256}.pdf"


def download(
    client: HttpClient,
    viewer_url: str,
    *,
    pdf_root: Path,
    committee_id: str,
    year: int,
) -> tuple[Path, str, int]:
    """Resolve the FirstAgenda viewer wrapper to its real PDF URL, then download.

    ``viewer_url`` is ``/Vis/Pdf/bilag/{document_id}``. That endpoint returns
    an HTML page; the binary lives in a presigned S3 URL inside its iframe.
    The presigned URL is valid for ~5 minutes so we resolve and download
    in immediate succession.
    """
    viewer_html = client.get_text(viewer_url)
    pdf_url = resolve_pdf_url(viewer_html)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp_path = Path(tmp.name)
    try:
        bytes_written = client.stream_to(pdf_url, tmp_path)
        if not is_pdf(tmp_path):
            raise NotAPdfError(f"response from {pdf_url} is not a PDF")
        sha256 = _sha256_file(tmp_path)
        final = content_addressed_path(pdf_root, committee_id, year, sha256)
        if not final.exists():
            final.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(tmp_path, final)
        else:
            tmp_path.unlink(missing_ok=True)
        return final, sha256, bytes_written
    finally:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)


def extract_text(pdf_path: Path) -> str:
    if not is_pdf(pdf_path):
        raise NotAPdfError(f"{pdf_path} is not a PDF")
    reader = PdfReader(str(pdf_path))
    parts: list[str] = []
    for page in reader.pages:
        try:
            parts.append(page.extract_text() or "")
        except Exception as exc:
            logger.warning("extract_text failed for one page of %s: %s", pdf_path, exc)
    return "\n".join(parts).strip()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()

