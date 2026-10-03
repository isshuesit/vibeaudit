"""Tests run entirely against local fixture HTML - no network required.
This is deliberate: CI and reviewers should be able to run `pytest` with
zero setup and get a real answer about whether the scoring logic works,
independent of whether any particular website is up.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from vibeaudit.fetcher import _extract_visible_text
from vibeaudit.models import FetchResult
from vibeaudit.scorer import score

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def load_fixture_as_fetch_result(filename: str, url: str = "https://example.com/") -> FetchResult:
    with open(os.path.join(FIXTURES, filename)) as f:
        html = f.read()
    text = _extract_visible_text(html)
    return FetchResult(url=url, ok=True, status_code=200, html=html, text=text, headers={})


def test_inflated_page_triggers_expected_patterns():
    fetch_result = load_fixture_as_fetch_result("inflated_page.html")
    result = score("InflatedApp", fetch_result)

    assert result.fetch_ok
    assert result.spc.privacy_policy_link_found is True
    assert result.spc.https is True

    hit_names = {h.pattern for h in result.utst.hits}
    assert "Confidence score displays" in hit_names
    assert "User review or rating displays" in hit_names
    assert "Third-party launch/recognition badges" in hit_names
    assert result.utst.automated_subtotal > 0


def test_blank_page_is_flagged():
    fetch_result = load_fixture_as_fetch_result("blank_page.html")
    result = score("BlankApp", fetch_result)

    assert result.fetch_ok
    assert result.likely_blank_page is True
    assert any("JS-rendered" in n for n in result.notes)


def test_clean_page_does_not_trigger_false_positives():
    fetch_result = load_fixture_as_fetch_result("clean_page.html")
    result = score("CleanApp", fetch_result)

    assert result.fetch_ok
    assert result.spc.privacy_policy_link_found is True
    # Specific, named security claims (TOTP, row-level security, region
    # choice) should NOT trip the vague "security badge" or "unverified
    # claim" patterns - this mirrors the real Consile finding from the
    # Paper 2 re-audit.
    assert result.utst.automated_subtotal == 0


def test_http_url_is_not_https():
    fetch_result = load_fixture_as_fetch_result("clean_page.html", url="http://example.com/")
    result = score("HttpApp", fetch_result)
    assert result.spc.https is False


def test_failed_fetch_produces_safe_result():
    fetch_result = FetchResult(url="https://nonexistent.invalid/", ok=False, error="Connection failed")
    result = score("DeadApp", fetch_result)
    assert result.fetch_ok is False
    assert result.spc is None
    assert result.utst is None
    assert result.tsga is None


def test_tsga_is_computed_for_successful_audit():
    result = score("InflatedApp", load_fixture_as_fetch_result("inflated_page.html"))
    assert result.tsga is not None
    # Inflated page: lots of UTST, only https+privacy on SPC -> positive gap.
    assert result.tsga.gap > 0
    assert result.tsga.hri_source == "not_assessed"
    assert result.tsga.band_label in {"Low", "Moderate", "High", "Severe"}


def test_clean_page_has_non_positive_gap():
    result = score("CleanApp", load_fixture_as_fetch_result("clean_page.html"))
    # No trust inflation + https + privacy link => SPC should keep pace.
    assert result.tsga.gap <= 0
    assert result.tsga.band_label == "Low"


def test_manual_hri_amplifies_tsga_base():
    fr = load_fixture_as_fetch_result("inflated_page.html")
    baseline = score("A", fr).tsga.tsga_base
    amplified = score("A", fr, hri=1.0).tsga.tsga_base
    assert amplified > baseline
    assert score("A", fr, hri=1.0).tsga.hri_source == "manual"


def test_https_scored_on_final_url_after_downgrade():
    fr = load_fixture_as_fetch_result("clean_page.html", url="https://example.com/")
    fr.final_url = "http://example.com/"
    result = score("DowngradeApp", fr)
    assert result.spc.https is False
    assert any("downgrade" in n.lower() for n in result.notes)


def test_https_upgrade_via_redirect_is_credited():
    fr = load_fixture_as_fetch_result("clean_page.html", url="http://example.com/")
    fr.final_url = "https://example.com/"
    result = score("UpgradeApp", fr)
    assert result.spc.https is True
