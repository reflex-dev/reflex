"""Tests for dynamic ``{expr}`` markdown link targets."""

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from reflex_docs.docgen_pipeline import _resolve_link_target


def test_resolve_link_target_brace_expr():
    """``{expr}`` is resolved against the doc exec environment and must yield str."""
    env = {
        "enterprise": SimpleNamespace(
            overview=SimpleNamespace(path="/enterprise/overview/")
        )
    }
    assert _resolve_link_target("{enterprise.overview.path}", env) == (
        "/enterprise/overview/"
    )


def test_resolve_link_target_plain_url_unchanged():
    """Normal hrefs are returned as-is (after strip)."""
    assert _resolve_link_target("  /docs/foo/  ", {}) == "/docs/foo/"


def test_resolve_link_target_with_anchor():
    """Brace expressions compose with surrounding url fragments."""
    env = {"page": SimpleNamespace(path="/docs/page/")}
    assert _resolve_link_target("{page.path}#section", env) == "/docs/page/#section"


def test_resolve_link_target_unknown_name_raises_value_error():
    """Missing head name surfaces with target + expr in the message."""
    with pytest.raises(ValueError, match=r"bogus\.path"):
        _resolve_link_target("{bogus.path}", {})


def test_resolve_link_target_unknown_attribute_raises_value_error():
    """Typo in a dotted segment surfaces with target + expr in the message."""
    env = {"page": SimpleNamespace(path="/docs/page/")}
    with pytest.raises(ValueError, match=r"page\.pth"):
        _resolve_link_target("{page.pth}", env)


def test_resolve_link_target_non_string_raises_type_error():
    """A brace expression resolving to a non-string raises TypeError."""
    env = {"obj": SimpleNamespace(path=42)}
    with pytest.raises(TypeError, match="must resolve to str"):
        _resolve_link_target("{obj.path}", env)
