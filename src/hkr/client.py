from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, httpx.TransportError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500
    return False

logger = logging.getLogger(__name__)

DEFAULT_UA = "hkr-scraper/0.1 (+https://github.com/kleist/hkr)"


class HttpClient:
    def __init__(
        self,
        *,
        rps: float = 1.0,
        user_agent: str = DEFAULT_UA,
        save_raw_dir: Path | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        headers = {"User-Agent": user_agent, "Accept": "application/json"}
        if extra_headers:
            headers.update(extra_headers)
        # follow_redirects=True is required: the API issues a 302 to
        # /Home/AnonymousAuthentication?callback=<original> on the first hit,
        # which sets a .AspNet.Cookies session cookie and redirects back.
        # httpx.Client persists cookies across the redirect chain automatically.
        self._client = httpx.Client(
            timeout=30.0,
            headers=headers,
            follow_redirects=True,
        )
        self._min_interval = 1.0 / rps if rps > 0 else 0.0
        self._last_request_at = 0.0
        self._save_raw_dir = save_raw_dir

    def __enter__(self) -> HttpClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self._client.close()

    @retry(
        reraise=True,
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=1, max=30),
        retry=retry_if_exception(_is_retryable),
    )
    def get_json(self, url: str, *, label: str | None = None) -> Any:
        self._throttle()
        logger.info("GET %s", url)
        response = self._client.get(url)
        response.raise_for_status()
        payload = response.json()
        if self._save_raw_dir is not None and label is not None:
            self._snapshot(label, payload)
        return payload

    def stream_to(self, url: str, dest: Path) -> int:
        self._throttle()
        logger.info("GET (stream) %s", url)
        bytes_written = 0
        with self._client.stream("GET", url) as response:
            response.raise_for_status()
            dest.parent.mkdir(parents=True, exist_ok=True)
            with dest.open("wb") as fh:
                for chunk in response.iter_bytes():
                    fh.write(chunk)
                    bytes_written += len(chunk)
        return bytes_written

    def _throttle(self) -> None:
        if self._min_interval <= 0:
            return
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_request_at = time.monotonic()

    def _snapshot(self, label: str, payload: Any) -> None:
        assert self._save_raw_dir is not None
        path = self._save_raw_dir / f"{label}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
