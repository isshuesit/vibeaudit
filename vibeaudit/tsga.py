"""Implements the TSGA scoring formulas from Paper 2, Sections 3.4-3.5.

TSGA_base = (UTST_normalized - SPC_normalized) x (1 + HRI_normalized)
TSGA_projected(t) = TSGA_base + (HRI_normalized x drift_rate x t)

Important honesty note: `drift_rate` has NO empirically validated value.
Paper 2 states this explicitly - it is a placeholder pending the (not yet
run) longitudinal user study. This module defaults it to None and REFUSES
to project forward in time unless the caller explicitly supplies a rate
and acknowledges it is speculative. This is a deliberate design choice to
stop the tool from quietly manufacturing false precision.
"""

from __future__ import annotations

from dataclasses import dataclass

from .patterns import SECURITY_HEADERS_TO_CHECK, TEXT_PATTERNS

# Absolute ceilings for the automated checks. UTST_MAX_POINTS tracks the
# pattern table, so adding a pattern rescales every score consistently.
UTST_MAX_POINTS: int = sum(p.trust_weight for p in TEXT_PATTERNS)
# SPC automated points: HTTPS (1) + privacy-policy link (1) + one per
# security header we look for.
SPC_MAX_POINTS: int = 2 + len(SECURITY_HEADERS_TO_CHECK)


@dataclass(frozen=True)
class TsgaBandInfo:
    label: str
    description: str


TSGA_BANDS: list[tuple[float, float, TsgaBandInfo]] = [
    (0.0, 2.0, TsgaBandInfo(
        "Low",
        "Trust signals are broadly consistent with the security posture.",
    )),
    (2.0, 5.0, TsgaBandInfo(
        "Moderate",
        "Some inflation of perceived trust relative to actual security.",
    )),
    (5.0, 8.0, TsgaBandInfo(
        "High",
        "Significant mismatch between how the interface looks and what it does.",
    )),
    (8.0, float("inf"), TsgaBandInfo(
        "Severe",
        "The interface actively misleads users about its security.",
    )),
]


def classify_band(tsga_score: float) -> TsgaBandInfo:
    # A negative or sub-threshold score means SPC keeps pace with (or beats)
    # UTST - that is the healthiest case, so it belongs in the lowest band,
    # not the fall-through "Severe" default.
    if tsga_score < TSGA_BANDS[0][0]:
        return TSGA_BANDS[0][2]
    for lo, hi, info in TSGA_BANDS:
        if lo <= tsga_score < hi:
            return info
    return TSGA_BANDS[-1][2]


def normalize(raw_score: float, max_observed: float) -> float:
    """Normalize a raw UTST/SPC/HRI subtotal to a 0-10 scale relative to
    the maximum observed in the current sample. This mirrors how Paper 2's
    pilot audit derived comparable scores across apps of different sizes -
    it is sample-relative, not an absolute universal scale. Document this
    when reporting scores: they are only comparable WITHIN one audit run
    that used the same max_observed value.
    """
    if max_observed <= 0:
        return 0.0
    return max(0.0, min(10.0, (raw_score / max_observed) * 10))


def compute_tsga_base(utst_normalized: float, spc_normalized: float, hri_normalized: float) -> float:
    return (utst_normalized - spc_normalized) * (1 + hri_normalized)


def compute_tsga_projection(
    tsga_base: float,
    hri_normalized: float,
    drift_rate: float | None,
    days: int,
) -> float | None:
    """Returns None (not a fabricated number) if drift_rate is not supplied.
    Paper 2 is explicit that drift_rate has no empirical basis yet - do not
    let this tool imply otherwise by silently defaulting to some number.
    """
    if drift_rate is None:
        return None
    return tsga_base + (hri_normalized * drift_rate * days)


def spc_raw_points(https: bool, privacy_link: bool, headers_present: int) -> float:
    """Collapse the automated SPC findings into a single raw point total on
    the same scale as SPC_MAX_POINTS."""
    return (1.0 if https else 0.0) + (1.0 if privacy_link else 0.0) + float(headers_present)


def score_tsga(
    *,
    utst_raw: int,
    spc_raw: float,
    hri_normalized: float | None = None,
    utst_max: float = UTST_MAX_POINTS,
    spc_max: float = SPC_MAX_POINTS,
    projection_days: int | None = None,
    drift_rate: float | None = None,
) -> dict:
    """One call that turns raw UTST/SPC subtotals into a full TSGA picture.

    hri_normalized is a 0-1 judgement (0 = no habituation risk, 1 = maximum);
    pass None to leave it unassessed, in which case the (1 + HRI) multiplier
    is 1. Returns a plain dict so callers with no dataclass dependency (a
    notebook, a quick script) can use it too; scorer.py wraps it in a
    TsgaResult.
    """
    utst_normalized = normalize(utst_raw, utst_max)
    spc_normalized = normalize(spc_raw, spc_max)
    gap = utst_normalized - spc_normalized

    if hri_normalized is None:
        hri_for_math = 0.0
        hri_source = "not_assessed"
        hri_out: float | None = None
    else:
        hri_for_math = max(0.0, min(1.0, float(hri_normalized)))
        hri_source = "manual"
        hri_out = hri_for_math

    tsga_base = compute_tsga_base(utst_normalized, spc_normalized, hri_for_math)
    band = classify_band(tsga_base)

    projected = None
    if projection_days is not None:
        projected = compute_tsga_projection(
            tsga_base, hri_for_math, drift_rate, projection_days
        )

    return {
        "utst_raw": utst_raw,
        "spc_raw": spc_raw,
        "utst_max": float(utst_max),
        "spc_max": float(spc_max),
        "utst_normalized": round(utst_normalized, 3),
        "spc_normalized": round(spc_normalized, 3),
        "gap": round(gap, 3),
        "hri_normalized": hri_out,
        "hri_source": hri_source,
        "tsga_base": round(tsga_base, 3),
        "band_label": band.label,
        "band_description": band.description,
        "projection_days": projection_days,
        "projection_drift_rate": drift_rate,
        "tsga_projected": round(projected, 3) if projected is not None else None,
    }
