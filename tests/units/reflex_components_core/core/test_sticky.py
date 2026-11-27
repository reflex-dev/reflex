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


def test_badge_has_accessible_name_when_visual_label_is_hidden():
    """Mobile readers can identify the logo-only link."""
    assert '"aria-label":"Built with Reflex"' in StickyBadge.create().render()["props"]


BADGE_CSS = (
    ".rx-sticky-badge{position:fixed;bottom:1rem;right:1rem;display:flex;flex-direction:row;gap:0.375rem;align-items:center;width:auto;border-radius:0.5rem;color:#E5E7EB;border:1px "
    "solid "
    "#27282B;background-color:#151618;padding:0.375rem;transition:background-color "
    "0.2s ease-in-out;box-shadow:0 1px 2px 0 rgba(0, 0, 0, "
    "0.05);z-index:9998;cursor:pointer;text-align:center}.dark "
    ".rx-sticky-badge{color:#27282B;border:1px solid "
    "#E5E7EB;background-color:#FCFCFD}.rx-sticky-logo{fill:white}.rx-sticky-logo-square{fill:#6E56CF}.rx-sticky-logo-letter{fill:white}@media "
    "screen and (min-width: 0){.rx-sticky-desktop-only{display:none}}@media "
    "screen and (min-width: "
    "62em){.rx-sticky-desktop-only{display:block}}.rx-sticky-label{color:var(--slate-1);font-weight:600;font-family:'Instrument "
    "Sans', sans-serif;--default-font-family:'Instrument Sans', "
    "sans-serif;font-size:0.875rem;line-height:1rem;letter-spacing:-0.00656rem}"
)


def test_badge_is_styled_without_a_css_prop(monkeypatch: pytest.MonkeyPatch):
    """The badge is plain elements and a stylesheet: it does not need Emotion."""
    monkeypatch.delenv("REFLEX_REFERRER_PARAM", raising=False)
    badge = StickyBadge.create()
    assert badge._get_all_imports(collapse=True) == {}
    assert badge.render() == {
        "name": '"a"',
        "props": [
            '"aria-label":"Built with Reflex"',
            'className:"rx-sticky-badge"',
            'href:"https://reflex.dev"',
            'target:"_blank"',
        ],
        "children": [
            {
                "name": '"style"',
                "props": [
                    'href:"rx-sticky-badge"',
                    'precedence:"reflex"',
                    "suppressHydrationWarning:true",
                ],
                "children": [{"contents": f'"{BADGE_CSS}"'}],
            },
            {
                "name": '"svg"',
                "props": [
                    'className:"rx-sticky-logo"',
                    'height:"16"',
                    'viewBox:"0 0 16 16"',
                    'width:"16"',
                    'xmlns:"http://www.w3.org/2000/svg"',
                ],
                "children": [
                    {
                        "name": '"rect"',
                        "props": [
                            'className:"rx-sticky-logo-square"',
                            'height:"16"',
                            'rx:"2"',
                            'width:"16"',
                        ],
                        "children": [],
                    },
                    {
                        "name": '"path"',
                        "props": [
                            'className:"rx-sticky-logo-letter"',
                            'd:"M10 9V13H12V9H10Z"',
                        ],
                        "children": [],
                    },
                    {
                        "name": '"path"',
                        "props": [
                            'className:"rx-sticky-logo-letter"',
                            'd:"M4 3V13H6V9H10V7H6V5H10V7H12V3H4Z"',
                        ],
                        "children": [],
                    },
                ],
            },
            {
                "name": '"div"',
                "props": ['className:"rx-sticky-desktop-only"'],
                "children": [
                    {
                        "name": '"span"',
                        "props": ['className:"rx-sticky-label"'],
                        "children": [{"contents": '"Built with Reflex"'}],
                    }
                ],
            },
        ],
    }
