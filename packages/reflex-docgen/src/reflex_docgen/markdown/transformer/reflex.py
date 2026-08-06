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

__all__ = ["ReflexComponentTransformer"]


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
        """Render frontmatter as nothing (an empty fragment).

        Args:
            block: The frontmatter block.

        Returns:
            An empty fragment.
        """
        return rx.fragment()

    def heading(self, block: HeadingBlock) -> rx.Component:
        """Render a heading as an ``<h1>``-``<h6>`` element.

        Args:
            block: The heading block.

        Returns:
            The heading component.
        """
        level = min(max(block.level, 1), 6)
        children = self.transform_spans(block.children)
        if builder := self._overrides.get(f"h{level}"):
            return builder(level, children)
        return getattr(rx.el, f"h{level}")(*children)

    def text_block(self, block: TextBlock) -> rx.Component:
        """Render a paragraph as a ``<p>`` element.

        Args:
            block: The text block.

        Returns:
            The paragraph component.
        """
        children = self.transform_spans(block.children)
        if builder := self._overrides.get("p"):
            return builder(children)
        return rx.el.p(*children)

    def list_block(self, block: ListBlock) -> rx.Component:
        """Render a list as a ``<ul>`` or ``<ol>`` element.

        Args:
            block: The list block.

        Returns:
            The list component.
        """
        items = [self.transform_list_item(item) for item in block.items]
        if builder := self._overrides.get("ol" if block.ordered else "ul"):
            return builder(items)
        tag = rx.el.ol if block.ordered else rx.el.ul
        return tag(*items)

    def transform_list_item(self, item: ListItem) -> rx.Component:
        """Render a single list item as an ``<li>`` element.

        Args:
            item: The list item.

        Returns:
            The list-item component.
        """
        return rx.el.li(*self.transform_blocks(item.children))

    def quote(self, block: QuoteBlock) -> rx.Component:
        """Render a block quote as a ``<blockquote>`` element.

        Args:
            block: The quote block.

        Returns:
            The blockquote component.
        """
        children = self.transform_blocks(block.children)
        if builder := self._overrides.get("blockquote"):
            return builder(children)
        return rx.el.blockquote(*children)

    def code_block(self, block: CodeBlock) -> rx.Component:
        """Render a fenced code block as a ``<pre><code>`` element.

        Args:
            block: The code block.

        Returns:
            The preformatted code component.
        """
        if builder := self._overrides.get("pre"):
            return builder(block.content, block.language)
        return rx.el.pre(rx.el.code(block.content))

    def directive(self, block: DirectiveBlock) -> rx.Component:
        """Render a directive, falling back to a plain ``<div>``.

        Args:
            block: The directive block.

        Returns:
            The component produced by the matching override, or a ``<div>``
            wrapping the directive's children.
        """
        if builder := self._overrides.get(block.name):
            return builder(block)
        return rx.el.div(*self.transform_blocks(block.children))

    def table(self, block: TableBlock) -> rx.Component:
        """Render a table as a ``<table>`` element.

        Args:
            block: The table block.

        Returns:
            The table component.
        """
        thead = rx.el.thead(self.transform_table_row(block.header, header=True))
        tbody = rx.el.tbody(*(self.transform_table_row(row) for row in block.rows))
        if builder := self._overrides.get("table"):
            return builder(thead, tbody)
        return rx.el.table(thead, tbody)

    def transform_table_row(
        self, row: TableRow, *, header: bool = False
    ) -> rx.Component:
        """Render a single table row as a ``<tr>`` element.

        Args:
            row: The table row.
            header: Whether the row belongs to the table header.

        Returns:
            The table-row component.
        """
        return rx.el.tr(
            *(self.transform_table_cell(cell, header=header) for cell in row.cells)
        )

    def transform_table_cell(
        self, cell: TableCell, *, header: bool = False
    ) -> rx.Component:
        """Render a single table cell as a ``<th>`` or ``<td>`` element.

        Args:
            cell: The table cell.
            header: Whether the cell belongs to the table header.

        Returns:
            The table-cell component.
        """
        children = self.transform_spans(cell.children)
        tag = rx.el.th if header else rx.el.td
        if cell.align is not None:
            return tag(*children, text_align=cell.align)
        return tag(*children)

    def thematic_break(self, block: ThematicBreakBlock) -> rx.Component:
        """Render a thematic break as an ``<hr>`` element.

        Args:
            block: The thematic-break block.

        Returns:
            The horizontal-rule component.
        """
        if builder := self._overrides.get("hr"):
            return builder()
        return rx.el.hr()

    def text_span(self, span: TextSpan) -> rx.Component:
        """Render plain text as a ``<span>`` element.

        Args:
            span: The text span.

        Returns:
            The span component.
        """
        if builder := self._overrides.get("span"):
            return builder(span.text)
        return rx.el.span(span.text)

    def bold(self, span: BoldSpan) -> rx.Component:
        """Render bold text as a ``<strong>`` element.

        Args:
            span: The bold span.

        Returns:
            The strong component.
        """
        children = self.transform_spans(span.children)
        if builder := self._overrides.get("strong"):
            return builder(children)
        return rx.el.strong(*children)

    def italic(self, span: ItalicSpan) -> rx.Component:
        """Render italic text as an ``<em>`` element.

        Args:
            span: The italic span.

        Returns:
            The emphasis component.
        """
        children = self.transform_spans(span.children)
        if builder := self._overrides.get("em"):
            return builder(children)
        return rx.el.em(*children)

    def strikethrough(self, span: StrikethroughSpan) -> rx.Component:
        """Render struck-through text as an ``<s>`` element.

        Args:
            span: The strikethrough span.

        Returns:
            The strikethrough component.
        """
        children = self.transform_spans(span.children)
        if builder := self._overrides.get("s"):
            return builder(children)
        return rx.el.s(*children)

    def code_span(self, span: CodeSpan) -> rx.Component:
        """Render inline code as a ``<code>`` element.

        Args:
            span: The code span.

        Returns:
            The inline-code component.
        """
        if builder := self._overrides.get("code"):
            return builder(span.code)
        return rx.el.code(span.code)

    def link(self, span: LinkSpan) -> rx.Component:
        """Render a link as an ``<a>`` element.

        Args:
            span: The link span.

        Returns:
            The anchor component.
        """
        children = self.transform_spans(span.children)
        if builder := self._overrides.get("a"):
            return builder(children, span.target)
        return rx.el.a(*children, href=span.target)

    def image(self, span: ImageSpan) -> rx.Component:
        """Render an image as an ``<img>`` element.

        Args:
            span: The image span.

        Returns:
            The image component.
        """
        alt = _plain_text(span.children)
        if builder := self._overrides.get("img"):
            return builder(span.src, alt)
        return rx.el.img(src=span.src, alt=alt)

    def line_break(self, span: LineBreakSpan) -> rx.Component:
        """Render a line break as a ``<br>`` element.

        Args:
            span: The line-break span.

        Returns:
            The line-break component.
        """
        if builder := self._overrides.get("br"):
            return builder()
        return rx.el.br()
