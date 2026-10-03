"""TSGA math tests - pure functions, no network, no fixtures needed."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from vibeaudit import tsga


def test_normalize_bounds():
    assert tsga.normalize(0, 10) == 0.0
    assert tsga.normalize(10, 10) == 10.0
    assert tsga.normalize(20, 10) == 10.0  # clamped, never above 10
    assert tsga.normalize(-5, 10) == 0.0  # clamped, never below 0
    assert tsga.normalize(5, 0) == 0.0  # guard against divide-by-zero


def test_classify_band_covers_negative_and_low():
    # A negative gap (SPC beats UTST) is the healthiest case - must NOT
    # fall through to the "Severe" default.
    assert tsga.classify_band(-4.0).label == "Low"
    assert tsga.classify_band(0.0).label == "Low"
    assert tsga.classify_band(3.0).label == "Moderate"
    assert tsga.classify_band(6.0).label == "High"
    assert tsga.classify_band(50.0).label == "Severe"


def test_score_tsga_without_hri_leaves_multiplier_at_one():
    out = tsga.score_tsga(utst_raw=tsga.UTST_MAX_POINTS, spc_raw=0.0)
    assert out["hri_source"] == "not_assessed"
    assert out["hri_normalized"] is None
    # gap == tsga_base when HRI is unassessed
    assert out["tsga_base"] == pytest.approx(out["gap"])
    assert out["utst_normalized"] == 10.0


def test_score_tsga_with_hri_amplifies():
    base = tsga.score_tsga(utst_raw=9, spc_raw=1.0)["tsga_base"]
    amp = tsga.score_tsga(utst_raw=9, spc_raw=1.0, hri_normalized=1.0)["tsga_base"]
    # HRI=1.0 doubles the (1 + HRI) multiplier; allow for 3-dp rounding.
    assert amp == pytest.approx(base * 2.0, abs=0.01)


def test_score_tsga_clamps_hri_to_unit_interval():
    out = tsga.score_tsga(utst_raw=9, spc_raw=1.0, hri_normalized=5.0)
    assert out["hri_normalized"] == 1.0


def test_projection_refuses_without_drift_rate():
    out = tsga.score_tsga(utst_raw=9, spc_raw=1.0, hri_normalized=0.5, projection_days=30)
    assert out["tsga_projected"] is None

    out2 = tsga.score_tsga(
        utst_raw=9, spc_raw=1.0, hri_normalized=0.5, projection_days=30, drift_rate=0.01
    )
    assert out2["tsga_projected"] is not None
    assert out2["tsga_projected"] > out2["tsga_base"]


def test_spc_raw_points_matches_scale():
    assert tsga.spc_raw_points(True, True, 5) == tsga.SPC_MAX_POINTS
    assert tsga.spc_raw_points(False, False, 0) == 0.0
    assert tsga.spc_raw_points(True, False, 2) == 3.0
