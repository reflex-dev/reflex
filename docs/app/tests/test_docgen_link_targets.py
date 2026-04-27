"""Tests for dynamic ``{expr}`` markdown link targets."""

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent.parent))

from reflex_docs.docgen_pipeline import _resolve_link_target


def test_resolve_link_target_brace_expr():
    """``{expr}`` is evaluated in the doc exec environment and must yield str."""
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
