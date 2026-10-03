"""Coverage for the individual UTST text patterns and multilingual regexes.

Uses local fixtures only - no network.
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from vibeaudit.fetcher import _extract_visible_text
from vibeaudit.models import FetchResult
from vibeaudit.patterns import PRIVACY_LINK_REGEX, TEXT_PATTERNS
from vibeaudit.scorer import score

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def _score(filename, url="https://example.com/"):
    with open(os.path.join(FIXTURES, filename), encoding="utf-8") as f:
        html = f.read()
    fr = FetchResult(
        url=url, ok=True, status_code=200, final_url=url,
        html=html, text=_extract_visible_text(html), headers={},
    )
    return score("X", fr)


def test_all_regexes_compile():
    for p in TEXT_PATTERNS:
        re.compile(p.regex, re.IGNORECASE)


def test_pattern_names_are_unique():
    names = [p.name for p in TEXT_PATTERNS]
    assert len(names) == len(set(names))


def test_urgency_fixture_hits_the_new_patterns():
    result = _score("urgency_page.html")
    hits = {h.pattern for h in result.utst.hits}
    for expected in (
        "Manufactured urgency / scarcity",
        "Live-activity social proof ticker",
        "Guarantee / risk-reversal language",
        "Security theater phrasing",
        "Superlative authority claims",
        "Press / media endorsement (text form)",
        "Vague AI capability claims",
    ):
        assert expected in hits, f"missing {expected!r}; got {sorted(hits)}"
    assert result.utst.automated_subtotal >= 12


def test_clean_page_still_scores_zero_after_new_patterns():
    # The whole point of the new patterns is that they don't fire on
    # specific, real security language (row-level security, TOTP, regions).
    result = _score("clean_page.html")
    assert result.utst.automated_subtotal == 0


@pytest.mark.parametrize(
    "snippet",
    [
        "Datenschutzerklärung",
        "politique de confidentialité",
        "Política de Privacidade",
        "informativa sulla privacy",
        "polityka prywatności",
        "gizlilik politikası",
    ],
)
def test_privacy_regex_multilingual(snippet):
    assert re.search(PRIVACY_LINK_REGEX, snippet, re.IGNORECASE)


def test_multilingual_fixture_detects_privacy_and_social_proof():
    result = _score("multilingual_page.html")
    assert result.spc.privacy_policy_link_found is True
    hits = {h.pattern for h in result.utst.hits}
    assert "User review or rating displays" in hits  # "8,000 Nutzern" / "Bewertungen"
    assert "Superlative authority claims" in hits  # "Marktführer"
    assert "Guarantee / risk-reversal language" in hits  # "Geld-zurück-Garantie"


def test_evidence_snippet_is_populated_and_bounded():
    result = _score("urgency_page.html")
    for hit in result.utst.hits:
        assert hit.evidence
        assert len(hit.evidence) <= 200
