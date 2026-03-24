"""Tests for reflex-docgen markdown parsing."""

from pathlib import Path

import pytest
from reflex_docgen import (
    BoldSpan,
    CodeSpan,
    FrontMatter,
    ImageSpan,
    ItalicSpan,
    LinkSpan,
    StrikethroughSpan,
    TextBlock,
    TextSpan,
    parse_document,
)

_DOCS_DIR = Path(__file__).resolve().parents[3] / "docs"


def test_no_frontmatter():
    """Parsing a document without frontmatter returns None."""
    doc = parse_document("# Hello\n\nWorld\n")
    assert doc.frontmatter is None


def test_basic_frontmatter():
    """A simple YAML frontmatter block is extracted."""
    source = "---\ntitle: Test\n---\n# Hello\n"
    doc = parse_document(source)
    assert doc.frontmatter is not None
    assert doc.frontmatter.raw == "title: Test"


def test_multiline_frontmatter():
    """Multi-line YAML frontmatter is preserved."""
    source = "---\ncomponents:\n  - rx.button\n\nButton: |\n  lambda **props: rx.button(**props)\n---\n# Button\n"
    doc = parse_document(source)
    assert doc.frontmatter is not None
    assert "components:" in doc.frontmatter.raw
    assert "rx.button" in doc.frontmatter.raw


def test_frontmatter_not_in_blocks():
    """Frontmatter should not appear in the blocks list."""
    source = "---\ntitle: Test\n---\n# Hello\n"
    doc = parse_document(source)
    assert not any(isinstance(b, FrontMatter) for b in doc.blocks)


def test_h1():
    """A level-1 heading is parsed correctly."""
    doc = parse_document("# Title\n")
    assert len(doc.headings) == 1
    assert doc.headings[0].level == 1
    assert doc.headings[0].children == (TextSpan(text="Title"),)


def test_multiple_heading_levels():
    """Headings at different levels are all captured."""
    source = "# H1\n\n## H2\n\n### H3\n"
    doc = parse_document(source)
    assert len(doc.headings) == 3
    assert [h.level for h in doc.headings] == [1, 2, 3]
    assert [h.children for h in doc.headings] == [
        (TextSpan(text="H1"),),
        (TextSpan(text="H2"),),
        (TextSpan(text="H3"),),
    ]


def test_heading_with_inline_code():
    """Inline code in headings is preserved as a CodeSpan."""
    doc = parse_document("# The `rx.button` Component\n")
    children = doc.headings[0].children
    assert children == (
        TextSpan(text="The "),
        CodeSpan(code="rx.button"),
        TextSpan(text=" Component"),
    )


def test_plain_code_block():
    """A fenced code block with only a language is parsed."""
    source = "```python\nx = 1\n```\n"
    doc = parse_document(source)
    assert len(doc.code_blocks) == 1
    cb = doc.code_blocks[0]
    assert cb.language == "python"
    assert cb.flags == ()
    assert cb.content == "x = 1"


def test_code_block_with_flags():
    """A fenced code block with demo and exec flags is parsed."""
    source = "```python demo exec\nclass Foo:\n    pass\n```\n"
    doc = parse_document(source)
    assert len(doc.code_blocks) == 1
    cb = doc.code_blocks[0]
    assert cb.language == "python"
    assert cb.flags == ("demo", "exec")


def test_code_block_demo_only():
    """A fenced code block with only the demo flag is parsed."""
    source = "```python demo\nrx.button('Click')\n```\n"
    doc = parse_document(source)
    cb = doc.code_blocks[0]
    assert cb.language == "python"
    assert cb.flags == ("demo",)


def test_code_block_exec_only():
    """A fenced code block with only the exec flag is parsed."""
    source = "```python exec\nimport reflex as rx\n```\n"
    doc = parse_document(source)
    cb = doc.code_blocks[0]
    assert cb.language == "python"
    assert cb.flags == ("exec",)


def test_code_block_eval():
    """A fenced code block with the eval flag is parsed."""
    source = "```python eval\nrx.text('hello')\n```\n"
    doc = parse_document(source)
    cb = doc.code_blocks[0]
    assert cb.language == "python"
    assert cb.flags == ("eval",)


def test_code_block_no_language():
    """A fenced code block without a language is parsed."""
    source = "```\nplain text\n```\n"
    doc = parse_document(source)
    assert len(doc.code_blocks) == 1
    cb = doc.code_blocks[0]
    assert cb.language is None
    assert cb.flags == ()


def test_directive_alert():
    """An md alert directive is parsed as a DirectiveBlock."""
    source = "```md alert\n# Warning Title\n\nThis is the body.\n```\n"
    doc = parse_document(source)
    assert len(doc.directives) == 1
    d = doc.directives[0]
    assert d.name == "alert"
    assert d.args == ()


def test_directive_alert_with_variant():
    """An md alert with a variant like 'info' preserves the variant as an arg."""
    source = "```md alert info\n# Note\nSome info.\n```\n"
    doc = parse_document(source)
    d = doc.directives[0]
    assert d.name == "alert"
    assert d.args == ("info",)


def test_directive_alert_warning():
    """An md alert warning directive preserves the warning arg."""
    source = "```md alert warning\nDo not do this.\n```\n"
    doc = parse_document(source)
    d = doc.directives[0]
    assert d.name == "alert"
    assert d.args == ("warning",)


def test_directive_video():
    """An md video directive captures the URL as an arg."""
    source = "```md video https://youtube.com/embed/abc123\n```\n"
    doc = parse_document(source)
    d = doc.directives[0]
    assert d.name == "video"
    assert d.args == ("https://youtube.com/embed/abc123",)


def test_directive_definition():
    """An md definition directive is parsed."""
    source = "```md definition\nSome definition content.\n```\n"
    doc = parse_document(source)
    d = doc.directives[0]
    assert d.name == "definition"
    assert d.args == ()
    assert d.content == "Some definition content."


def test_directive_section():
    """An md section directive is parsed."""
    source = "```md section\nSection content here.\n```\n"
    doc = parse_document(source)
    d = doc.directives[0]
    assert d.name == "section"
    assert d.args == ()


def test_directive_not_in_code_blocks():
    """Directive blocks should not appear in the code_blocks list."""
    source = "```md alert\nBody\n```\n"
    doc = parse_document(source)
    assert len(doc.code_blocks) == 0
    assert len(doc.directives) == 1


def test_simple_paragraph():
    """A plain paragraph is captured as a TextBlock with a TextSpan."""
    doc = parse_document("Hello world.\n")
    text_blocks = [b for b in doc.blocks if isinstance(b, TextBlock)]
    assert len(text_blocks) == 1
    assert text_blocks[0].children == (TextSpan(text="Hello world."),)


def test_paragraph_with_inline_code():
    """Inline code in paragraphs is preserved as a CodeSpan."""
    doc = parse_document("Use `rx.button` for buttons.\n")
    text_blocks = [b for b in doc.blocks if isinstance(b, TextBlock)]
    assert text_blocks[0].children == (
        TextSpan(text="Use "),
        CodeSpan(code="rx.button"),
        TextSpan(text=" for buttons."),
    )


def test_bold_text():
    """Bold text is parsed into a BoldSpan."""
    doc = parse_document("This is **bold** text.\n")
    text_blocks = [b for b in doc.blocks if isinstance(b, TextBlock)]
    assert text_blocks[0].children == (
        TextSpan(text="This is "),
        BoldSpan(children=(TextSpan(text="bold"),)),
        TextSpan(text=" text."),
    )


def test_italic_text():
    """Italic text is parsed into an ItalicSpan."""
    doc = parse_document("This is *italic* text.\n")
    text_blocks = [b for b in doc.blocks if isinstance(b, TextBlock)]
    assert text_blocks[0].children == (
        TextSpan(text="This is "),
        ItalicSpan(children=(TextSpan(text="italic"),)),
        TextSpan(text=" text."),
    )


def test_strikethrough_text():
    """Strikethrough text is parsed into a StrikethroughSpan."""
    doc = parse_document("This is ~~struck~~ text.\n")
    text_blocks = [b for b in doc.blocks if isinstance(b, TextBlock)]
    assert text_blocks[0].children == (
        TextSpan(text="This is "),
        StrikethroughSpan(children=(TextSpan(text="struck"),)),
        TextSpan(text=" text."),
    )


def test_link():
    """Links are parsed into LinkSpans."""
    doc = parse_document("Click [here](http://example.com) now.\n")
    text_blocks = [b for b in doc.blocks if isinstance(b, TextBlock)]
    assert text_blocks[0].children == (
        TextSpan(text="Click "),
        LinkSpan(children=(TextSpan(text="here"),), target="http://example.com"),
        TextSpan(text=" now."),
    )


def test_image():
    """Images are parsed into ImageSpans."""
    doc = parse_document("See ![alt text](image.png) here.\n")
    text_blocks = [b for b in doc.blocks if isinstance(b, TextBlock)]
    assert text_blocks[0].children == (
        TextSpan(text="See "),
        ImageSpan(children=(TextSpan(text="alt text"),), src="image.png"),
        TextSpan(text=" here."),
    )


def test_nested_spans():
    """Bold containing code is parsed as nested spans."""
    doc = parse_document("Use **`rx.button`** here.\n")
    text_blocks = [b for b in doc.blocks if isinstance(b, TextBlock)]
    assert text_blocks[0].children == (
        TextSpan(text="Use "),
        BoldSpan(children=(CodeSpan(code="rx.button"),)),
        TextSpan(text=" here."),
    )


def test_mixed_document():
    """A document with frontmatter, headings, code, and directives is fully parsed."""
    source = (
        "---\ntitle: Test\n---\n"
        "# Title\n\n"
        "Some text.\n\n"
        "```python demo\ncode()\n```\n\n"
        "```md alert\nAlert body.\n```\n\n"
        "## Section\n"
    )
    doc = parse_document(source)
    assert doc.frontmatter is not None
    assert len(doc.headings) == 2
    assert len(doc.code_blocks) == 1
    assert len(doc.directives) == 1


def test_empty_document():
    """An empty string produces an empty Document."""
    doc = parse_document("")
    assert doc.frontmatter is None
    assert doc.blocks == ()


def test_realistic_doc_structure():
    """Verify parsing of a realistic Reflex doc structure."""
    source = """\
---
components:
  - rx.button
---

```python exec
import reflex as rx
```

# Button

Buttons trigger events.

```python demo exec
class State(rx.State):
    count: int = 0

def button_demo():
    return rx.button("Click", on_click=State.increment)
```

```md alert info
# Important

Use `on_click` for click events.
```

```md video https://youtube.com/embed/abc123

```

## Variants
"""
    doc = parse_document(source)
    assert doc.frontmatter is not None
    assert "rx.button" in doc.frontmatter.raw
    assert len(doc.headings) == 2
    assert doc.headings[0].children == (TextSpan(text="Button"),)
    assert doc.headings[1].children == (TextSpan(text="Variants"),)
    assert len(doc.code_blocks) == 2
    assert doc.code_blocks[0].flags == ("exec",)
    assert doc.code_blocks[1].flags == ("demo", "exec")
    assert len(doc.directives) == 2
    assert doc.directives[0].name == "alert"
    assert doc.directives[0].args == ("info",)
    assert doc.directives[1].name == "video"


_ALL_MD_FILES = sorted(_DOCS_DIR.rglob("*.md"))


@pytest.mark.parametrize(
    "md_file", _ALL_MD_FILES, ids=lambda p: str(p.relative_to(_DOCS_DIR))
)
def test_parse_all_doc_files(md_file: Path):
    """Every markdown file in docs/ should parse without errors."""
    source = md_file.read_text()
    doc = parse_document(source)
    # Sanity check: a non-empty file should produce at least one block.
    if source.strip():
        assert len(doc.blocks) > 0
