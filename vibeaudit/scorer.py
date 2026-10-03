"""Scores a fetched page against the automated SPC/UTST checks.

Scope is deliberately limited to what Paper 2 itself claims can be
automated (Section 4.2, "VibeAudit Prototype"). Anything requiring a human
eye (visual professionalism, iconography, feature attribution, habituation
risk) is out of scope here by design, not by oversight.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

from . import tsga
from .models import (
    AuditResult,
    FetchResult,
    PatternHit,
    SpcResult,
    TsgaResult,
    UtstResult,
)
from .patterns import (
    BLANK_PAGE_TEXT_LENGTH_THRESHOLD,
    PRIVACY_LINK_REGEX,
    SECURITY_HEADERS_TO_CHECK,
    TEXT_PATTERNS,
)


def _effective_url(fetch: FetchResult) -> str:
    """The URL the response actually came from - the post-redirect one when
    the fetcher captured it, so an http:// link that 301s to https:// is
    scored on where it landed, not where it started."""
    return fetch.final_url or fetch.url


def _score_spc(fetch: FetchResult) -> SpcResult:
    https = urlparse(_effective_url(fetch)).scheme == "https"
    privacy_found = bool(re.search(PRIVACY_LINK_REGEX, fetch.text, re.IGNORECASE))

    lower_headers = {k.lower(): v for k, v in fetch.headers.items()}
    present = [h for h in SECURITY_HEADERS_TO_CHECK if h in lower_headers]

    return SpcResult(
        https=https,
        privacy_policy_link_found=privacy_found,
        security_headers_present=present,
        security_headers_checked=list(SECURITY_HEADERS_TO_CHECK),
    )


def _score_utst(fetch: FetchResult) -> UtstResult:
    hits: list[PatternHit] = []
    subtotal = 0
    for pattern in TEXT_PATTERNS:
        match = re.search(pattern.regex, fetch.text, re.IGNORECASE)
        if match:
            start = max(0, match.start() - 30)
            end = min(len(fetch.text), match.end() + 30)
            hits.append(
                PatternHit(
                    pattern=pattern.name,
                    category=pattern.category,
                    trust_weight=pattern.trust_weight,
                    evidence=fetch.text[start:end].strip(),
                )
            )
            subtotal += pattern.trust_weight
    return UtstResult(hits=hits, automated_subtotal=subtotal)


def _score_tsga(spc: SpcResult, utst: UtstResult, hri: float | None) -> TsgaResult:
    spc_raw = tsga.spc_raw_points(
        spc.https,
        spc.privacy_policy_link_found,
        len(spc.security_headers_present),
    )
    data = tsga.score_tsga(
        utst_raw=utst.automated_subtotal,
        spc_raw=spc_raw,
        hri_normalized=hri,
    )
    return TsgaResult(**data)


def score(
    app_name: str,
    fetch: FetchResult,
    *,
    hri: float | None = None,
) -> AuditResult:
    """Score a fetched page. If the fetch failed, returns an AuditResult
    with fetch_ok=False and spc/utst/tsga left as None - callers should
    check fetch_ok before reading those fields.

    hri is an optional 0-1 Habituation Risk Index judgement supplied by a
    human. It is never inferred; omitting it leaves the (1 + HRI) multiplier
    at 1 and marks the TSGA result hri_source="not_assessed".
    """
    if not fetch.ok and not fetch.text:
        return AuditResult(
            app_name=app_name,
            url=fetch.url,
            final_url=fetch.final_url,
            fetch_ok=False,
            fetch_error=fetch.error,
            spc=None,
            utst=None,
            tsga=None,
            likely_blank_page=False,
            notes=[fetch.error] if fetch.error else [],
        )

    spc = _score_spc(fetch)
    utst = _score_utst(fetch)
    tsga_result = _score_tsga(spc, utst, hri)
    likely_blank = len(fetch.text) < BLANK_PAGE_TEXT_LENGTH_THRESHOLD

    notes = []
    if likely_blank:
        notes.append(
            "Visible text is very short - page is likely JS-rendered and "
            "this fetch did not execute JavaScript. This is a real signal "
            "(the app relies on client-side rendering with no fallback "
            "content), not a tool failure. Confirm manually if unsure."
        )

    started = urlparse(fetch.url)
    landed = urlparse(_effective_url(fetch))
    if started.scheme == "https" and landed.scheme == "http":
        notes.append(
            "Request started on HTTPS but the response came from an HTTP URL "
            "after redirects - the site downgraded the connection. SPC HTTPS "
            "is scored on the final URL and is therefore marked absent."
        )
    if fetch.error:
        notes.append(fetch.error)

    return AuditResult(
        app_name=app_name,
        url=fetch.url,
        final_url=fetch.final_url,
        fetch_ok=True,
        fetch_error=None,
        spc=spc,
        utst=utst,
        tsga=tsga_result,
        likely_blank_page=likely_blank,
        notes=notes,
    )
