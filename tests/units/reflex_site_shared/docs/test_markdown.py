"""Tests for the shared documentation Markdown renderer."""

from reflex_site_shared.docs.markdown import render_markdown

import reflex as rx


def test_render_markdown_executes_demo_block() -> None:
    """Executable demos should render through the shared docgen pipeline."""
    component = render_markdown(
        """```python demo exec
import reflex as rx

def example():
    return rx.text("Shared live example")
```""",
        virtual_filepath="tests/shared-live-example.md",
    )

    assert isinstance(component, rx.Component)
    assert "Shared live example" in str(component)
