"""Tests for the "Built with Reflex" sticky badge."""

import pytest
from reflex_components_core.core.sticky import StickyBadge


def _badge_href() -> str:
    """Render a fresh badge and extract its href prop.

    Returns:
        The rendered href value, without surrounding quotes.
    """
    props = StickyBadge.create().render()["props"]
    href_prop = next(p for p in props if p.startswith("href:"))
    return href_prop.removeprefix("href:").strip('"')


def test_badge_href_default(monkeypatch: pytest.MonkeyPatch):
    """Without a referrer param, the badge links to the plain reflex.dev URL."""
    monkeypatch.delenv("REFLEX_REFERRER_PARAM", raising=False)
    assert _badge_href() == "https://reflex.dev"


def test_badge_href_with_referrer(monkeypatch: pytest.MonkeyPatch):
    """A referrer param is appended as a ref query parameter."""
    monkeypatch.setenv("REFLEX_REFERRER_PARAM", "owner-123")
    assert _badge_href() == "https://reflex.dev/?ref=owner-123"


def test_badge_href_urlencodes_referrer(monkeypatch: pytest.MonkeyPatch):
    """Special characters in the referrer param are urlencoded."""
    monkeypatch.setenv("REFLEX_REFERRER_PARAM", "a b&c/d?e=f")
    assert _badge_href() == "https://reflex.dev/?ref=a%20b%26c%2Fd%3Fe%3Df"


def test_badge_href_empty_referrer(monkeypatch: pytest.MonkeyPatch):
    """An empty referrer param falls back to the default URL."""
    monkeypatch.setenv("REFLEX_REFERRER_PARAM", "")
    assert _badge_href() == "https://reflex.dev"
