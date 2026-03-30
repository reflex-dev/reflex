"""Tests for reflex-docgen markdown parsing."""

from pathlib import Path

import pytest
from reflex_docgen.markdown import (
    BoldSpan,
    CodeBlock,
    CodeSpan,
    ComponentPreview,
    DirectiveBlock,
    FrontMatter,
    HeadingBlock,
    ImageSpan,
    ItalicSpan,
    LineBreakSpan,
    LinkSpan,
    ListBlock,
    ListItem,
    QuoteBlock,
    StrikethroughSpan,
    TableBlock,
    TableCell,
    TableRow,
    TextBlock,
    TextSpan,
    ThematicBreakBlock,
    parse_document,
)
from reflex_docgen.markdown.transformer import MarkdownTransformer

_DOCS_DIR = Path(__file__).resolve().parents[3] / "reflex" / "docs"

_md = MarkdownTransformer()


def test_no_frontmatter():
    """Parsing a document without frontmatter returns None."""
    doc = parse_document("# Hello\n\nWorld\n")
    assert doc.frontmatter is None


def test_basic_frontmatter():
    """A simple YAML frontmatter block is extracted."""
    source = "---\ntitle: Test\n---\n# Hello\n"
    doc = parse_document(source)
    assert doc.frontmatter is not None
    assert doc.frontmatter.title == "Test"


def test_multiline_frontmatter():
    """Multi-line YAML frontmatter is preserved."""
    source = "---\ncomponents:\n  - rx.button\n\nButton: |\n  lambda **props: rx.button(**props)\n---\n# Button\n"
    doc = parse_document(source)
    assert doc.frontmatter is not None
    assert doc.frontmatter.components == ("rx.button",)
    assert len(doc.frontmatter.component_previews) == 1
    assert doc.frontmatter.component_previews[0].name == "Button"


def test_frontmatter_not_in_blocks():
    """Frontmatter should not appear in the blocks list."""
    source = "---\ntitle: Test\n---\n# Hello\n"
    doc = parse_document(source)
    assert not any(isinstance(b, FrontMatter) for b in doc.blocks)


def test_empty_frontmatter():
    """Empty frontmatter (no content between ---) is not recognized."""
    doc = parse_document("---\n---\n# Hello\n")
    assert doc.frontmatter is None


def test_only_low_level_list_true():
    """only_low_level as a YAML list with True is parsed."""
    source = "---\nonly_low_level:\n  - True\n---\n# Dialog\n"
    fm = parse_document(source).frontmatter
    assert fm is not None
    assert fm.only_low_level is True


def test_only_low_level_scalar():
    """only_low_level as a scalar boolean is parsed."""
    source = "---\nonly_low_level: true\n---\n# Dialog\n"
    fm = parse_document(source).frontmatter
    assert fm is not None
    assert fm.only_low_level is True


def test_only_low_level_default_false():
    """only_low_level defaults to False when absent."""
    source = "---\ncomponents:\n  - rx.box\n---\n# Box\n"
    fm = parse_document(source).frontmatter
    assert fm is not None
    assert fm.only_low_level is False


def test_component_previews():
    """A component preview lambda is extracted from frontmatter."""
    source = '---\ncomponents:\n  - rx.button\n\nButton: |\n  lambda **props: rx.button("Click me", **props)\n---\n# Button\n'
    fm = parse_document(source).frontmatter
    assert fm is not None
    assert len(fm.component_previews) == 1
    preview = fm.component_previews[0]
    assert preview.name == "Button"
    assert "rx.button" in preview.source
    assert preview.source.startswith("lambda")


def test_multiple_previews():
    """Multiple component preview lambdas are extracted."""
    source = "---\ncomponents:\n  - rx.input\n\nInput: |\n  lambda **props: rx.input(**props)\n\nInputSlot: |\n  lambda **props: rx.input(rx.input.slot(**props))\n---\n# Input\n"
    fm = parse_document(source).frontmatter
    assert fm is not None
    assert len(fm.component_previews) == 2
    names = [p.name for p in fm.component_previews]
    assert "Input" in names
    assert "InputSlot" in names


def test_transform_frontmatter_with_previews():
    """FrontMatter with component previews renders correctly."""
    fm = FrontMatter(
        components=("rx.button",),
        only_low_level=False,
        title=None,
        component_previews=(
            ComponentPreview(
                name="Button",
                source='lambda **props: rx.button("Click", **props)',
            ),
        ),
    )
    md = _md.frontmatter(fm)
    assert md.startswith("---\n")
    assert md.endswith("\n---")
    assert "rx.button" in md
    assert "Button:" in md


def test_transform_frontmatter_with_only_low_level():
    """FrontMatter with only_low_level renders the field."""
    fm = FrontMatter(
        components=(),
        only_low_level=True,
        title=None,
        component_previews=(),
    )
    assert "only_low_level" in _md.frontmatter(fm)


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
    assert d.children == (
        TextBlock(children=(TextSpan(text="Some definition content."),)),
    )


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
    assert doc.frontmatter.components == ("rx.button",)
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
    source = md_file.read_text(encoding="utf-8")
    doc = parse_document(source)
    # Sanity check: a non-empty file should produce at least one block.
    if source.strip():
        assert len(doc.blocks) > 0
    # Verify transform doesn't crash on any doc file.
    _md.transform(doc)


# ---------------------------------------------------------------------------
# MarkdownTransformer round-trip tests
# ---------------------------------------------------------------------------


def test_transform_text_span():
    """TextSpan renders back to plain text."""
    assert _md.text_span(TextSpan(text="hello")) == "hello"


def test_transform_code_span():
    """CodeSpan renders back with backticks."""
    assert _md.code_span(CodeSpan(code="rx.button")) == "`rx.button`"


def test_transform_bold_span():
    """BoldSpan renders back with double asterisks."""
    span = BoldSpan(children=(TextSpan(text="bold"),))
    assert _md.bold(span) == "**bold**"


def test_transform_italic_span():
    """ItalicSpan renders back with single asterisks."""
    span = ItalicSpan(children=(TextSpan(text="italic"),))
    assert _md.italic(span) == "*italic*"


def test_transform_strikethrough_span():
    """StrikethroughSpan renders back with tildes."""
    span = StrikethroughSpan(children=(TextSpan(text="struck"),))
    assert _md.strikethrough(span) == "~~struck~~"


def test_transform_link_span():
    """LinkSpan renders back as a markdown link."""
    span = LinkSpan(children=(TextSpan(text="click"),), target="http://x.com")
    assert _md.link(span) == "[click](http://x.com)"


def test_transform_image_span():
    """ImageSpan renders back as a markdown image."""
    span = ImageSpan(children=(TextSpan(text="alt"),), src="img.png")
    assert _md.image(span) == "![alt](img.png)"


def test_transform_line_break_soft():
    """Soft LineBreakSpan renders as a newline."""
    assert _md.line_break(LineBreakSpan(soft=True)) == "\n"


def test_transform_line_break_hard():
    """Hard LineBreakSpan renders as two spaces + newline."""
    assert _md.line_break(LineBreakSpan(soft=False)) == "  \n"


def test_transform_nested_spans():
    """Nested spans render correctly."""
    span = BoldSpan(children=(CodeSpan(code="x"), TextSpan(text=" = 1")))
    assert _md.bold(span) == "**`x` = 1**"


def test_transform_heading():
    """HeadingBlock renders with the correct number of hashes."""
    h1 = HeadingBlock(level=1, children=(TextSpan(text="Title"),))
    assert _md.heading(h1) == "# Title"
    h3 = HeadingBlock(level=3, children=(TextSpan(text="Sub"),))
    assert _md.heading(h3) == "### Sub"


def test_transform_heading_with_inline():
    """HeadingBlock with mixed spans renders correctly."""
    h = HeadingBlock(
        level=2,
        children=(
            TextSpan(text="The "),
            CodeSpan(code="rx.button"),
            TextSpan(text=" API"),
        ),
    )
    assert _md.heading(h) == "## The `rx.button` API"


def test_transform_text_block():
    """TextBlock renders its children as a paragraph."""
    block = TextBlock(
        children=(TextSpan(text="Hello "), BoldSpan(children=(TextSpan(text="world"),)))
    )
    assert _md.text_block(block) == "Hello **world**"


def test_transform_code_block():
    """CodeBlock renders as a fenced code block."""
    cb = CodeBlock(language="python", flags=("demo", "exec"), content="x = 1")
    assert _md.code_block(cb) == "```python demo exec\nx = 1\n```"


def test_transform_code_block_no_language():
    """CodeBlock without language renders with empty info string."""
    cb = CodeBlock(language=None, flags=(), content="plain")
    assert _md.code_block(cb) == "```\nplain\n```"


def test_transform_directive():
    """DirectiveBlock renders as a fenced md block."""
    d = DirectiveBlock(
        name="alert",
        args=("info",),
        children=(TextBlock(children=(TextSpan(text="Be careful."),)),),
    )
    assert _md.directive(d) == "```md alert info\nBe careful.\n```"


def test_transform_list_unordered():
    """Unordered ListBlock renders with dashes."""
    lb = ListBlock(
        ordered=False,
        start=None,
        items=(
            ListItem(children=(TextBlock(children=(TextSpan(text="one"),)),)),
            ListItem(children=(TextBlock(children=(TextSpan(text="two"),)),)),
        ),
    )
    assert _md.list_block(lb) == "- one\n- two"


def test_transform_list_ordered():
    """Ordered ListBlock renders with numbers."""
    lb = ListBlock(
        ordered=True,
        start=1,
        items=(
            ListItem(children=(TextBlock(children=(TextSpan(text="first"),)),)),
            ListItem(children=(TextBlock(children=(TextSpan(text="second"),)),)),
        ),
    )
    assert _md.list_block(lb) == "1. first\n2. second"


def test_transform_quote():
    """QuoteBlock renders with > prefix."""
    q = QuoteBlock(children=(TextBlock(children=(TextSpan(text="wise words"),)),))
    assert _md.quote(q) == "> wise words"


def test_transform_table():
    """TableBlock renders as a markdown table."""
    table = TableBlock(
        header=TableRow(
            cells=(
                TableCell(children=(TextSpan(text="Name"),), align=None),
                TableCell(children=(TextSpan(text="Value"),), align="right"),
            )
        ),
        rows=(
            TableRow(
                cells=(
                    TableCell(children=(TextSpan(text="a"),), align=None),
                    TableCell(children=(TextSpan(text="1"),), align="right"),
                )
            ),
        ),
    )
    expected = "| Name | Value |\n| --- | ---: |\n| a | 1 |"
    assert _md.table(table) == expected


def test_transform_thematic_break():
    """ThematicBreakBlock renders as ---."""
    assert _md.thematic_break(ThematicBreakBlock()) == "---"


def test_transform_frontmatter():
    """FrontMatter renders with --- delimiters."""
    fm = FrontMatter(
        components=(),
        only_low_level=False,
        title="Test",
        component_previews=(),
    )
    md = _md.frontmatter(fm)
    assert md.startswith("---\n")
    assert md.endswith("\n---")
    assert "title: Test" in md


def test_transform_document_roundtrip():
    """MarkdownTransformer produces valid markdown that re-parses consistently."""
    source = """\
---
title: Test
---

# Hello **world**

Use `rx.button` for [buttons](http://example.com).

```python demo exec
x = 1
```

```md alert info
# Warning
Be careful.
```

- item one
- item **two**

---
"""
    doc = parse_document(source)
    rendered = _md.transform(doc)
    doc2 = parse_document(rendered)
    # The re-parsed document should produce the same markdown.
    assert _md.transform(doc2) == rendered


def test_nested_code_block_in_directive():
    """A directive using more backticks can contain inner code fences."""
    source = "````md alert\n# Example\n\n```python\nx = 1\n```\n````\n"
    doc = parse_document(source)
    assert len(doc.directives) == 1
    d = doc.directives[0]
    assert d.name == "alert"
    # The directive's children should contain a parsed CodeBlock with the nested fence.
    code_blocks = [b for b in d.children if isinstance(b, CodeBlock)]
    assert len(code_blocks) == 1
    assert code_blocks[0].language == "python"
    assert "x = 1" in code_blocks[0].content


def test_nested_code_block_in_code_block():
    """A code block using more backticks can contain inner code fences."""
    source = "````python demo\nrx.markdown(\n    '''```python\nx = 1\n```'''\n)\n````\n"
    doc = parse_document(source)
    assert len(doc.code_blocks) == 1
    cb = doc.code_blocks[0]
    assert cb.language == "python"
    assert cb.flags == ("demo",)
    assert "```python" in cb.content


def test_nested_code_block_roundtrip():
    """Nested code blocks survive a parse-render-reparse cycle."""
    source = "````md alert warning\n# Note\n\n```python\nx = 1\n```\n````\n"
    doc = parse_document(source)
    rendered = _md.transform(doc)
    doc2 = parse_document(rendered)
    assert len(doc2.directives) == 1
    assert doc2.directives[0].children == doc.directives[0].children
