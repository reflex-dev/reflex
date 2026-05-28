"""Tests for the reflex-docgen ReflexComponentTransformer."""

from reflex_docgen.markdown import HeadingBlock, TextSpan, parse_document
from reflex_docgen.markdown.transformer import ReflexComponentTransformer

import reflex as rx
from reflex.components.component import BaseComponent

_rx = ReflexComponentTransformer()


def _tags(component: BaseComponent) -> list[str | None]:
    """Return the html tag of each direct child of a component."""
    return [getattr(c, "tag", None) for c in component.children]


def test_transform_returns_fragment():
    """The document transforms into a fragment of its blocks."""
    doc = parse_document("# Hi\n\nWorld\n")
    tree = _rx.transform(doc)
    assert isinstance(tree, rx.Fragment)
    assert _tags(tree) == ["h1", "p"]


def test_heading_levels():
    """Heading levels map to h1-h6."""
    doc = parse_document("# A\n\n## B\n\n### C\n")
    assert _tags(_rx.transform(doc)) == ["h1", "h2", "h3"]


def test_heading_level_clamped():
    """Heading levels above 6 clamp to h6."""
    h = _rx.heading(HeadingBlock(level=7, children=(TextSpan(text="x"),)))
    assert h.tag == "h6"


def test_paragraph():
    """A paragraph renders as a <p>."""
    doc = parse_document("Hello world.\n")
    assert _tags(_rx.transform(doc)) == ["p"]


def test_inline_spans():
    """Inline formatting maps to the matching inline elements."""
    doc = parse_document("A **b** *i* ~~s~~ `c` [l](http://x.com) ![a](i.png) end.\n")
    para = _rx.transform(doc).children[0]
    tags = [getattr(c, "tag", None) for c in para.children]
    # The anchor (rx.el.a) renders as reflex's routing Link element.
    assert {"span", "strong", "em", "s", "code", "img", "Link"} <= set(tags)


def test_unordered_list():
    """An unordered list renders as <ul> with <li> items."""
    ul = _rx.transform(parse_document("- one\n- two\n")).children[0]
    assert getattr(ul, "tag", None) == "ul"
    assert _tags(ul) == ["li", "li"]


def test_ordered_list():
    """An ordered list renders as <ol> with <li> items."""
    ol = _rx.transform(parse_document("1. a\n2. b\n")).children[0]
    assert getattr(ol, "tag", None) == "ol"
    assert _tags(ol) == ["li", "li"]


def test_nested_list():
    """A nested list is rendered inside its parent list item."""
    ul = _rx.transform(parse_document("- outer\n    - inner\n")).children[0]
    li = ul.children[0]
    assert getattr(li, "tag", None) == "li"
    assert "ul" in _tags(li)


def test_blockquote():
    """A blockquote renders as <blockquote>."""
    bq = _rx.transform(parse_document("> wise words\n")).children[0]
    assert getattr(bq, "tag", None) == "blockquote"


def test_code_block():
    """A fenced code block renders as <pre><code>."""
    pre = _rx.transform(parse_document("```python\nx = 1\n```\n")).children[0]
    assert getattr(pre, "tag", None) == "pre"
    assert _tags(pre) == ["code"]


def test_thematic_break():
    """A thematic break renders as <hr>."""
    assert "hr" in _tags(_rx.transform(parse_document("text\n\n---\n")))


def test_table():
    """A table renders as <table> with <thead>/<tbody>, th headers, td cells."""
    doc = parse_document("| Name | Val |\n| :--- | ---: |\n| a | 1 |\n")
    table = _rx.transform(doc).children[0]
    assert getattr(table, "tag", None) == "table"
    assert _tags(table) == ["thead", "tbody"]
    header_row = table.children[0].children[0]
    assert _tags(header_row) == ["th", "th"]
    body_row = table.children[1].children[0]
    assert _tags(body_row) == ["td", "td"]


def test_image_renders_img():
    """An image renders as <img>; its alt is flattened to plain text."""
    img = (
        _rx.transform(parse_document("![the **alt**](i.png)\n")).children[0].children[0]
    )
    assert getattr(img, "tag", None) == "img"


def test_image_alt_flattened():
    """Formatted alt text is flattened to a plain string for the alt attribute."""
    from reflex_docgen.markdown import BoldSpan, CodeSpan, LinkSpan
    from reflex_docgen.markdown.transformer._reflex import _plain_text

    spans = (
        TextSpan(text="a "),
        BoldSpan(children=(TextSpan(text="b"),)),
        CodeSpan(code="c"),
        LinkSpan(children=(TextSpan(text="d"),), target="http://x.com"),
    )
    assert _plain_text(spans) == "a bcd"


def test_hard_line_break_renders_br():
    """A hard line break inside a paragraph renders as <br>."""
    para = _rx.transform(parse_document("a  \nb\n")).children[0]
    assert "br" in [getattr(c, "tag", None) for c in para.children]


def test_default_directive_renders_div():
    """A directive without an override renders its children inside a <div>."""
    div = _rx.transform(parse_document("```md alert\nBody.\n```\n")).children[0]
    assert getattr(div, "tag", None) == "div"


def test_quote_directive_falls_through_to_div():
    """`md quote` has no special default; it renders as a generic <div>.

    Consumers that want styled quotes override the ``quote`` directive (by name)
    and read the raw line-oriented body from ``DirectiveBlock.content``.
    """
    src = "```md quote\n- name: Jane\nReflex is great.\n```\n"
    div = _rx.transform(parse_document(src)).children[0]
    assert getattr(div, "tag", None) == "div"


def test_frontmatter_renders_nothing():
    """Frontmatter is not part of the rendered blocks."""
    doc = parse_document("---\ntitle: T\n---\n# Hi\n")
    assert _tags(_rx.transform(doc)) == ["h1"]


def test_overrides_heading():
    """An overrides entry for a heading is honored."""
    sentinel = rx.el.div("custom")

    def my_h1(level: int, children: tuple[rx.Component, ...]) -> rx.Component:
        return sentinel

    transformer = ReflexComponentTransformer(overrides={"h1": my_h1})
    assert transformer.transform(parse_document("# Title\n")).children[0] is sentinel


def test_overrides_link():
    """An overrides entry for a link receives children and href."""
    captured: dict[str, object] = {}

    def my_link(children: tuple[rx.Component, ...], href: str) -> rx.Component:
        captured["href"] = href
        return rx.el.span(*children)

    transformer = ReflexComponentTransformer(overrides={"a": my_link})
    transformer.transform(parse_document("[click](http://x.com)\n"))
    assert captured["href"] == "http://x.com"


def test_overrides_code_block():
    """An overrides entry for a code block receives content and language."""
    captured: dict[str, object] = {}

    def my_pre(content: str, language: str | None) -> rx.Component:
        captured["content"] = content
        captured["language"] = language
        return rx.el.div(content)

    transformer = ReflexComponentTransformer(overrides={"pre": my_pre})
    transformer.transform(parse_document("```python\nx = 1\n```\n"))
    assert captured["content"] == "x = 1"
    assert captured["language"] == "python"


def test_overrides_directive_by_name():
    """A directive override keyed by name receives the DirectiveBlock itself."""
    from reflex_docgen.markdown._types import DirectiveBlock

    captured: dict[str, object] = {}

    def my_alert(block: DirectiveBlock) -> rx.Component:
        captured["args"] = block.args
        captured["content"] = block.content
        return rx.el.div()

    transformer = ReflexComponentTransformer(overrides={"alert": my_alert})
    transformer.transform(parse_document("```md alert info\nBe careful.\n```\n"))
    assert captured["args"] == ("info",)
    assert captured["content"] == "Be careful."


def test_overrides_directive_reads_raw_content():
    """A line-oriented directive override can read the unreflowed raw body."""
    from reflex_docgen.markdown._types import DirectiveBlock

    captured: dict[str, object] = {}

    def my_quote(block: DirectiveBlock) -> rx.Component:
        captured["content"] = block.content
        return rx.el.div()

    transformer = ReflexComponentTransformer(overrides={"quote": my_quote})
    src = "```md quote\n- name: Jane\n- role: CEO\nGreat product.\n```\n"
    transformer.transform(parse_document(src))
    assert captured["content"] == "- name: Jane\n- role: CEO\nGreat product."
