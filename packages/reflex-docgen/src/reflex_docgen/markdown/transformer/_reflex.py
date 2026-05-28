"""Reflex-component transformer — renders a Document to ``rx.Component`` trees.

This is the default way to turn parsed markdown into Reflex components. It
covers the lean element set the content sites actually use and exposes two
customization layers that together replace the old flexdown ``component_map``:

* **Subclassing** — override any block/span handler (``heading``, ``link``, …)
  to fully control how a node renders. This is the primary mechanism.
* **Overrides dict** — pass ``overrides={element_name: builder}`` to swap a
  single element's builder without subclassing, giving near drop-in parity with
  the old ``component_map``.

Builder signatures (the value side of ``overrides``) receive the node's
already-transformed children plus any scalar attributes, so they only need to
assemble the container:

============  ===========================================================
element key   builder signature
============  ===========================================================
``h1``-``h6`` ``(level: int, children: tuple[rx.Component, ...])``
``p``         ``(children: tuple[rx.Component, ...])``
``ul``/``ol`` ``(items: list[rx.Component])``
``blockquote````(children: tuple[rx.Component, ...])``
``pre``       ``(content: str, language: str | None)``
``table``     ``(thead: rx.Component, tbody: rx.Component)``
``hr``        ``()``
``span``      ``(text: str)``
``strong``    ``(children: tuple[rx.Component, ...])``
``em``        ``(children: tuple[rx.Component, ...])``
``s``         ``(children: tuple[rx.Component, ...])``
``code``      ``(code: str)``
``a``         ``(children: tuple[rx.Component, ...], href: str)``
``img``       ``(src: str, alt: str)``
``br``        ``()``
============  ===========================================================

Directive blocks are keyed by their directive name (e.g. ``"alert"``) and the
builder receives the :class:`DirectiveBlock` itself — read ``block.content``
for line-oriented (non-markdown) bodies (e.g. ``md quote``'s ``- name:``/
``- role:`` lines) to avoid CommonMark reflowing them, or call
``self.transform_blocks(block.children)`` to render the parsed children.
Without an override a directive falls back to a plain ``<div>``.
"""

from __future__ import annotations

from collections.abc import Callable

import reflex as rx
from reflex_docgen.markdown._types import (
    BoldSpan,
    CodeBlock,
    CodeSpan,
    DirectiveBlock,
    Document,
    FrontMatter,
    HeadingBlock,
    ImageSpan,
    ItalicSpan,
    LineBreakSpan,
    LinkSpan,
    ListBlock,
    ListItem,
    QuoteBlock,
    Span,
    StrikethroughSpan,
    TableBlock,
    TableCell,
    TableRow,
    TextBlock,
    TextSpan,
    ThematicBreakBlock,
)
from reflex_docgen.markdown.transformer._base import DocumentTransformer


def _plain_text(spans: tuple[Span, ...]) -> str:
    """Flatten inline spans into their plain text content.

    Used for attributes that must be strings (e.g. an image's ``alt``).

    Args:
        spans: The inline spans to flatten.

    Returns:
        The concatenated text of the spans, ignoring formatting.
    """
    parts: list[str] = []
    for span in spans:
        if isinstance(span, TextSpan):
            parts.append(span.text)
        elif isinstance(span, CodeSpan):
            parts.append(span.code)
        elif isinstance(
            span, BoldSpan | ItalicSpan | StrikethroughSpan | LinkSpan | ImageSpan
        ):
            parts.append(_plain_text(span.children))
        elif isinstance(span, LineBreakSpan):
            parts.append(" ")
    return "".join(parts)


class ReflexComponentTransformer(DocumentTransformer["rx.Component"]):
    """Transforms a :class:`Document` into a tree of Reflex components.

    Every handler renders with plain ``rx.el.*`` elements by default. Pass
    ``overrides`` to replace individual element builders, or subclass and
    override handlers for full control. See the module docstring for the
    builder signatures keyed by element name.
    """

    def __init__(self, overrides: dict[str, Callable[..., rx.Component]] | None = None):
        """Initialize the transformer.

        Args:
            overrides: Element-name -> builder map (the ``component_map``
                analog). Each builder is consulted at the top of the matching
                handler; absent keys fall through to the default ``rx.el.*``
                rendering.
        """
        self._overrides = overrides or {}

    def transform(self, document: Document) -> rx.Component:
        """Render a full document to a fragment of its blocks.

        Frontmatter is not part of ``document.blocks`` and renders nothing.

        Args:
            document: The parsed document.

        Returns:
            A fragment wrapping the transformed blocks.
        """
        return rx.fragment(*self.transform_blocks(document.blocks))

    def frontmatter(self, block: FrontMatter) -> rx.Component:
        return rx.fragment()

    def heading(self, block: HeadingBlock) -> rx.Component:
        level = min(max(block.level, 1), 6)
        children = self.transform_spans(block.children)
        if builder := self._overrides.get(f"h{level}"):
            return builder(level, children)
        return getattr(rx.el, f"h{level}")(*children)

    def text_block(self, block: TextBlock) -> rx.Component:
        children = self.transform_spans(block.children)
        if builder := self._overrides.get("p"):
            return builder(children)
        return rx.el.p(*children)

    def list_block(self, block: ListBlock) -> rx.Component:
        items = [self.transform_list_item(item) for item in block.items]
        if builder := self._overrides.get("ol" if block.ordered else "ul"):
            return builder(items)
        tag = rx.el.ol if block.ordered else rx.el.ul
        return tag(*items)

    def transform_list_item(self, item: ListItem) -> rx.Component:
        return rx.el.li(*self.transform_blocks(item.children))

    def quote(self, block: QuoteBlock) -> rx.Component:
        children = self.transform_blocks(block.children)
        if builder := self._overrides.get("blockquote"):
            return builder(children)
        return rx.el.blockquote(*children)

    def code_block(self, block: CodeBlock) -> rx.Component:
        if builder := self._overrides.get("pre"):
            return builder(block.content, block.language)
        return rx.el.pre(rx.el.code(block.content))

    def directive(self, block: DirectiveBlock) -> rx.Component:
        if builder := self._overrides.get(block.name):
            return builder(block)
        return rx.el.div(*self.transform_blocks(block.children))

    def table(self, block: TableBlock) -> rx.Component:
        thead = rx.el.thead(self.transform_table_row(block.header, header=True))
        tbody = rx.el.tbody(*(self.transform_table_row(row) for row in block.rows))
        if builder := self._overrides.get("table"):
            return builder(thead, tbody)
        return rx.el.table(thead, tbody)

    def transform_table_row(
        self, row: TableRow, *, header: bool = False
    ) -> rx.Component:
        return rx.el.tr(
            *(self.transform_table_cell(cell, header=header) for cell in row.cells)
        )

    def transform_table_cell(
        self, cell: TableCell, *, header: bool = False
    ) -> rx.Component:
        children = self.transform_spans(cell.children)
        tag = rx.el.th if header else rx.el.td
        if cell.align is not None:
            return tag(*children, text_align=cell.align)
        return tag(*children)

    def thematic_break(self, block: ThematicBreakBlock) -> rx.Component:
        if builder := self._overrides.get("hr"):
            return builder()
        return rx.el.hr()

    def text_span(self, span: TextSpan) -> rx.Component:
        if builder := self._overrides.get("span"):
            return builder(span.text)
        return rx.el.span(span.text)

    def bold(self, span: BoldSpan) -> rx.Component:
        children = self.transform_spans(span.children)
        if builder := self._overrides.get("strong"):
            return builder(children)
        return rx.el.strong(*children)

    def italic(self, span: ItalicSpan) -> rx.Component:
        children = self.transform_spans(span.children)
        if builder := self._overrides.get("em"):
            return builder(children)
        return rx.el.em(*children)

    def strikethrough(self, span: StrikethroughSpan) -> rx.Component:
        children = self.transform_spans(span.children)
        if builder := self._overrides.get("s"):
            return builder(children)
        return rx.el.s(*children)

    def code_span(self, span: CodeSpan) -> rx.Component:
        if builder := self._overrides.get("code"):
            return builder(span.code)
        return rx.el.code(span.code)

    def link(self, span: LinkSpan) -> rx.Component:
        children = self.transform_spans(span.children)
        if builder := self._overrides.get("a"):
            return builder(children, span.target)
        return rx.el.a(*children, href=span.target)

    def image(self, span: ImageSpan) -> rx.Component:
        alt = _plain_text(span.children)
        if builder := self._overrides.get("img"):
            return builder(span.src, alt)
        return rx.el.img(src=span.src, alt=alt)

    def line_break(self, span: LineBreakSpan) -> rx.Component:
        if builder := self._overrides.get("br"):
            return builder()
        return rx.el.br()
