from __future__ import annotations

import hashlib
import logging
import shutil
import tempfile
from pathlib import Path

from pypdf import PdfReader

from hkr.client import HttpClient

logger = logging.getLogger(__name__)

PDF_MAGIC = b"%PDF-"


class NotAPdfError(ValueError):
    """The downloaded body is not a PDF (e.g. an auth-challenge HTML page)."""


def is_pdf(path: Path) -> bool:
    try:
        with path.open("rb") as fh:
            return fh.read(5) == PDF_MAGIC
    except OSError:
        return False


def content_addressed_path(root: Path, committee_id: str, year: int, sha256: str) -> Path:
    return root / committee_id / str(year) / sha256[:2] / f"{sha256}.pdf"


def download(
    client: HttpClient,
    url: str,
    *,
    pdf_root: Path,
    committee_id: str,
    year: int,
) -> tuple[Path, str, int]:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp_path = Path(tmp.name)
    try:
        bytes_written = client.stream_to(url, tmp_path)
        if not is_pdf(tmp_path):
            # /Vis/Pdf/bilag/{id} sometimes returns 200 OK with an HTML body
            # (e.g. the anonymous-auth challenge page) for bilag without a PDF
            # version. Don't record this as a successful download.
            raise NotAPdfError(f"response from {url} is not a PDF")
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
