"""Tests for docs sidebar wiring."""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))


def test_sidebar_renders_without_tutorials_index_arg():
    """Sidebar should render without requiring a tutorials index argument."""
    from reflex_docs.templates.docpage.sidebar.sidebar import sidebar

    component = sidebar(url="/docs/getting-started/introduction/")

    assert component is not None
