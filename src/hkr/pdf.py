from __future__ import annotations

import hashlib
import logging
import shutil
import tempfile
from pathlib import Path

from pypdf import PdfReader

from hkr.client import HttpClient

logger = logging.getLogger(__name__)


def content_addressed_path(root: Path, committee_id: int, year: int, sha256: str) -> Path:
    return root / str(committee_id) / str(year) / sha256[:2] / f"{sha256}.pdf"


def download(
    client: HttpClient,
    url: str,
    *,
    pdf_root: Path,
    committee_id: int,
    year: int,
) -> tuple[Path, str, int]:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp_path = Path(tmp.name)
    try:
        bytes_written = client.stream_to(url, tmp_path)
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
    reader = PdfReader(str(pdf_path))
    parts: list[str] = []
    for page in reader.pages:
        try:
            parts.append(page.extract_text() or "")
        except Exception as exc:  # pypdf occasionally chokes on a single page
            logger.warning("extract_text failed for one page of %s: %s", pdf_path, exc)
    return "\n".join(parts).strip()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()
