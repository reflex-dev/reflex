"""Tests for the shared documentation Markdown renderer."""

from pathlib import Path

import pytest
from reflex_site_shared.docs.markdown import (
    get_docgen_toc,
    get_markdown_toc,
    render_docgen_document,
    render_inline_markdown,
    render_markdown,
    render_markdown_with_toc,
)

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


def test_render_markdown_covers_core_blocks_and_spans() -> None:
    """Render every core block type with inline span formatting."""
    component = render_markdown(
        """# Top Title

## Section

### Subsection

#### Detail

A paragraph with **bold**, *italic*, ~~struck~~, `inline_code`,
[a link](/docs/target/), and ![alt](/image.png).

- first item
- item with `code` and [link](/somewhere/)

1. ordered one
2. ordered two

> A quoted insight.

| Name | Value |
| ---- | ----- |
| mode | `fast` |

---

```bash
echo "plain code block"
```
""",
        virtual_filepath="tests/kitchen-sink.md",
    )
    rendered = str(component)

    assert "Top Title" in rendered
    assert "Subsection" in rendered
    assert "Detail" in rendered
    assert "inline_code" in rendered
    assert "/docs/target/" in rendered
    assert "first item" in rendered
    assert "ordered two" in rendered
    assert "A quoted insight." in rendered
    assert "mode" in rendered
    assert "plain code block" in rendered


def test_render_markdown_renders_alert_directives() -> None:
    """Render collapsible, title-only, and text-only alert variants."""
    collapsible = str(
        render_markdown(
            "```md alert warning\n# Watch out\n\nDetails inside.\n```\n",
            virtual_filepath="tests/alert-collapsible.md",
        )
    )
    text_only = str(
        render_markdown(
            "```md alert\nJust a note.\n```\n",
            virtual_filepath="tests/alert-text.md",
        )
    )
    title_only = str(
        render_markdown(
            "```md alert success\n# All good\n```\n",
            virtual_filepath="tests/alert-title.md",
        )
    )

    assert "Watch out" in collapsible
    assert "Details inside." in collapsible
    assert "Just a note." in text_only
    assert "All good" in title_only


def test_render_markdown_renders_video_quote_and_tabs_directives() -> None:
    """Render the video, quote, and tabs directive shapes."""
    video = str(
        render_markdown(
            "```md video https://example.com/demo.mp4\n# Watch the demo\n```\n",
            virtual_filepath="tests/video.md",
        )
    )
    quote = str(
        render_markdown(
            "```md quote\n- name: Jane\n- role: CEO\nReflex is great.\n```\n",
            virtual_filepath="tests/quote.md",
        )
    )
    tabs = str(
        render_markdown(
            "```md tabs\n## First\n\nFirst body.\n\n## Second\n\nSecond body.\n```\n",
            virtual_filepath="tests/tabs.md",
        )
    )

    assert "https://example.com/demo.mp4" in video
    assert "Watch the demo" in video
    assert "Jane" in quote
    assert "CEO" in quote
    assert "Reflex is great." in quote
    assert "First body." in tabs
    assert "Second body." in tabs


def test_render_markdown_renders_definition_and_section_directives() -> None:
    """Render definition grids and section columns split by headings."""
    definition = str(
        render_markdown(
            "```md definition\n## Term\n\nMeaning.\n```\n",
            virtual_filepath="tests/definition.md",
        )
    )
    section = str(
        render_markdown(
            "```md section\n## Part One\n\nBody one.\n\n## Part Two\n\nBody two.\n```\n",
            virtual_filepath="tests/section.md",
        )
    )
    unknown = str(
        render_markdown(
            "```md mystery\nFallback content.\n```\n",
            virtual_filepath="tests/unknown-directive.md",
        )
    )

    assert "Term" in definition
    assert "Meaning." in definition
    assert "Part One" in section
    assert "Body two." in section
    assert "Fallback content." in unknown


def test_render_markdown_evaluates_exec_and_eval_blocks() -> None:
    """Populate the shared env with exec blocks and evaluate expressions."""
    component = render_markdown(
        """```python exec
import reflex as rx

def eval_target():
    return rx.text("Evaluated output")
```

```python eval
eval_target()
```

```python demo-only exec
import reflex as rx

def demo_only_example():
    return rx.text("Demo only output")
```""",
        virtual_filepath="tests/exec-eval.md",
    )
    rendered = str(component)

    assert "Evaluated output" in rendered
    assert "Demo only output" in rendered


def test_toc_helpers_extract_heading_levels() -> None:
    """Extract heading levels and labels from Markdown source."""
    source = "# One\n\n## Two\n\nBody text.\n\n### Three\n"

    assert get_markdown_toc(source) == [(1, "One"), (2, "Two"), (3, "Three")]

    toc, body = render_markdown_with_toc(source)
    assert toc == [(1, "One"), (2, "Two"), (3, "Three")]
    assert "Body text." in str(body)


def test_render_inline_markdown_handles_inline_and_block_content() -> None:
    """Keep short prop descriptions inline and fall back for block content."""
    assert isinstance(render_inline_markdown(""), rx.Fragment)

    inline = render_inline_markdown("Use `mode` or [docs](/docs/).")
    assert "mode" in str(inline)
    assert "/docs/" in str(inline)

    block = str(render_inline_markdown("# Heading\n\nParagraph."))
    assert "Heading" in block
    assert "Paragraph." in block


def test_render_docgen_document_extracts_faq_jsonld(tmp_path: Path) -> None:
    """Strip the FAQ block into JSON-LD and keep it out of the visible body."""
    doc = tmp_path / "faq.md"
    doc.write_text(
        """# FAQ Page

Intro text.

<!-- faqs-start -->

### What is Reflex?

A Python web framework.

### Is it fast?

Yes, quite fast.

<!-- faqs-end -->

Outro text.
""",
        encoding="utf-8",
    )

    body, faq_script = render_docgen_document(doc, doc)

    assert faq_script is not None
    faq_rendered = str(faq_script)
    assert "FAQPage" in faq_rendered
    assert "What is Reflex?" in faq_rendered
    assert "A Python web framework." in faq_rendered

    body_rendered = str(body)
    assert "Intro text." in body_rendered
    assert "What is Reflex?" not in body_rendered

    toc = get_docgen_toc(doc)
    assert (1, "FAQ Page") in toc
    assert all(text != "What is Reflex?" for _, text in toc)


def test_render_docgen_document_without_faq_markers(tmp_path: Path) -> None:
    """Return no JSON-LD script when a document has no FAQ block."""
    doc = tmp_path / "plain.md"
    doc.write_text("# Plain\n\nNo FAQs here.\n", encoding="utf-8")

    body, faq_script = render_docgen_document(doc, doc)

    assert faq_script is None
    assert "No FAQs here." in str(body)


def test_demo_block_reports_source_document_on_errors() -> None:
    """Surface the failing document path when a demo block raises."""
    with pytest.raises(NameError) as error:
        render_markdown(
            "```python demo\nundefined_component()\n```\n",
            virtual_filepath="tests/broken-demo.md",
        )

    assert "tests/broken-demo.md" in "".join(error.value.__notes__)
