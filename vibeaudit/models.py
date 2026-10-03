"""Data models shared across the fetcher, scorer, CLI, and API layers.

Keeping these as plain dataclasses (no framework dependency) means the same
objects work in a script, a test, or an API response without conversion.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone


@dataclass
class PatternHit:
    """A single UTST pattern that fired, with the evidence that triggered it."""

    pattern: str
    category: str
    trust_weight: int
    evidence: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class FetchResult:
    """Raw result of fetching a URL. Errors are represented, not raised,
    so callers (CLI, API) can decide how to present them."""

    url: str
    ok: bool
    status_code: int | None = None
    final_url: str | None = None
    html: str = ""
    text: str = ""
    headers: dict = field(default_factory=dict)
    error: str | None = None
    fetched_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


@dataclass
class SpcResult:
    """Automated portion of the Security Posture Checklist."""

    https: bool
    privacy_policy_link_found: bool
    security_headers_present: list[str] = field(default_factory=list)
    security_headers_checked: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class UtstResult:
    """Automated portion of the UI Trust Signal Taxonomy."""

    hits: list[PatternHit] = field(default_factory=list)
    automated_subtotal: int = 0

    def to_dict(self) -> dict:
        return {
            "hits": [h.to_dict() for h in self.hits],
            "automated_subtotal": self.automated_subtotal,
        }


@dataclass
class TsgaResult:
    """Automated TSGA score derived from the SPC + UTST subtotals.

    Normalization here is ABSOLUTE - each subtotal is divided by the maximum
    the *automated* checks could theoretically produce, then scaled to 0-10.
    That makes a single audit's number meaningful on its own, unlike Paper
    2's pilot which normalized within-sample. Batch/leaderboard consumers
    that want the sample-relative behaviour can re-run tsga.normalize() with
    their own max_observed.

    HRI (Habituation Risk Index) is never inferred. If the caller does not
    supply one, hri_source is "not_assessed" and the (1 + HRI) multiplier is
    treated as 1 - the number you get is the raw trust/security gap with no
    habituation amplification.
    """

    utst_raw: int
    spc_raw: float
    utst_max: float
    spc_max: float
    utst_normalized: float
    spc_normalized: float
    gap: float
    hri_normalized: float | None
    hri_source: str  # "manual" | "not_assessed"
    tsga_base: float
    band_label: str
    band_description: str
    projection_days: int | None = None
    projection_drift_rate: float | None = None
    tsga_projected: float | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class AuditResult:
    """Full result of auditing one URL: fetch + SPC + UTST + TSGA + notes.

    HRI (Habituation Risk Index) is intentionally NOT computed here. Per
    Paper 2's own design, habituation risk cannot be reliably inferred from
    static analysis alone - it requires a human judgment call. This tool
    surfaces UTST/SPC automatically, computes the TSGA gap with HRI treated
    as zero, and leaves a slot for HRI to be entered manually (see tsga.py).
    """

    app_name: str
    url: str
    fetch_ok: bool
    fetch_error: str | None
    spc: SpcResult | None
    utst: UtstResult | None
    likely_blank_page: bool
    tsga: TsgaResult | None = None
    final_url: str | None = None
    notes: list[str] = field(default_factory=list)
    audited_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict:
        return {
            "app_name": self.app_name,
            "url": self.url,
            "final_url": self.final_url,
            "fetch_ok": self.fetch_ok,
            "fetch_error": self.fetch_error,
            "spc": self.spc.to_dict() if self.spc else None,
            "utst": self.utst.to_dict() if self.utst else None,
            "tsga": self.tsga.to_dict() if self.tsga else None,
            "likely_blank_page": self.likely_blank_page,
            "notes": self.notes,
            "audited_at": self.audited_at,
        }
