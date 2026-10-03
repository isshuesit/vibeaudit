"""Fetches a URL and extracts visible text for scoring.

This module needs a normal internet connection to work - there is no way
around that for a tool whose whole job is auditing live websites. It will
not work inside network-restricted sandboxes; it will work fine on a normal
laptop or CI runner.
"""

from __future__ import annotations

import re

import requests
from bs4 import BeautifulSoup

from .models import FetchResult

DEFAULT_TIMEOUT_SECONDS = 10
USER_AGENT = "VibeAudit/0.2 (+https://github.com/YOUR_USERNAME/vibeaudit)"

# Stop reading a response after this many bytes. Audit pages are text; a
# multi-megabyte body is either a misconfigured server or a download, and
# either way we don't want to hold it all in memory.
MAX_RESPONSE_BYTES = 3_000_000

# Content types we can meaningfully extract text from. Anything else is
# fetched (so headers/HTTPS are still scored) but text extraction is
# skipped and noted.
_TEXTUAL_CONTENT_TYPES = ("text/html", "application/xhtml", "text/plain", "application/xml", "text/xml")


def _extract_visible_text(html: str) -> str:
    """Strip scripts/styles and collapse whitespace, matching what a human
    skimming the rendered page (not the raw HTML source) would actually see.
    Note: this does NOT execute JavaScript, so JS-rendered content will
    correctly show up as near-empty - that is a real finding (see the
    'likely_blank_page' flag), not a bug to hide.
    """
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "template"]):
        tag.decompose()
    text = soup.get_text(separator=" ")
    return re.sub(r"\s+", " ", text).strip()


def _read_capped(resp: requests.Response, limit: int = MAX_RESPONSE_BYTES) -> tuple[str, bool]:
    """Read up to `limit` bytes of the response body and decode it. Returns
    (text, truncated)."""
    chunks: list[bytes] = []
    total = 0
    truncated = False
    for chunk in resp.iter_content(chunk_size=65536):
        if not chunk:
            continue
        chunks.append(chunk)
        total += len(chunk)
        if total >= limit:
            truncated = True
            break
    raw = b"".join(chunks)[:limit]
    # Only trust an encoding the server actually declared. Do NOT fall back
    # to resp.apparent_encoding here - it reads resp.content, which is
    # already consumed once we've streamed the body ourselves.
    encoding = resp.encoding or "utf-8"
    try:
        return raw.decode(encoding, errors="replace"), truncated
    except (LookupError, TypeError):
        return raw.decode("utf-8", errors="replace"), truncated


def fetch(url: str, timeout: int = DEFAULT_TIMEOUT_SECONDS) -> FetchResult:
    """Fetch a URL and return a FetchResult. Never raises - network and
    parsing errors are captured in the result so callers can decide how to
    surface them (CLI prints a message, API returns a JSON error field, UI
    shows the network-error state)."""
    try:
        resp = requests.get(
            url,
            timeout=timeout,
            headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"},
            allow_redirects=True,
            stream=True,
        )
    except requests.exceptions.Timeout:
        return FetchResult(url=url, ok=False, error=f"Timed out after {timeout}s")
    except requests.exceptions.TooManyRedirects as exc:
        return FetchResult(url=url, ok=False, error=f"Too many redirects: {exc}")
    except requests.exceptions.ConnectionError as exc:
        return FetchResult(url=url, ok=False, error=f"Connection failed: {exc}")
    except requests.exceptions.RequestException as exc:
        return FetchResult(url=url, ok=False, error=f"Request failed: {exc}")

    final_url = str(resp.url)
    headers = dict(resp.headers)
    content_type = resp.headers.get("Content-Type", "").split(";")[0].strip().lower()

    try:
        body, truncated = _read_capped(resp)
    except requests.exceptions.RequestException as exc:
        resp.close()
        return FetchResult(
            url=url, ok=False, status_code=resp.status_code, final_url=final_url,
            headers=headers, error=f"Failed while reading response body: {exc}",
        )
    finally:
        resp.close()

    notes: list[str] = []
    if truncated:
        notes.append(f"response body truncated at {MAX_RESPONSE_BYTES} bytes")

    is_textual = (not content_type) or any(content_type.startswith(t) for t in _TEXTUAL_CONTENT_TYPES)
    if not is_textual:
        return FetchResult(
            url=url,
            ok=resp.ok,
            status_code=resp.status_code,
            final_url=final_url,
            html=body,
            text="",
            headers=headers,
            error=(
                f"Content-Type is {content_type!r}, not HTML - headers and HTTPS "
                "were still checked but no text was extracted"
            ),
        )

    try:
        text = _extract_visible_text(body)
    except Exception as exc:  # malformed HTML shouldn't crash the audit
        return FetchResult(
            url=url,
            ok=True,
            status_code=resp.status_code,
            final_url=final_url,
            html=body,
            text="",
            headers=headers,
            error=f"HTML parsed but text extraction failed: {exc}",
        )

    err = None if resp.ok else f"HTTP {resp.status_code}"
    if notes:
        err = "; ".join(notes) if err is None else err + "; " + "; ".join(notes)

    return FetchResult(
        url=url,
        ok=resp.ok,
        status_code=resp.status_code,
        final_url=final_url,
        html=body,
        text=text,
        headers=headers,
        error=err,
    )
