"""Generic document transformer — maps markdown AST nodes to arbitrary types."""

from __future__ import annotations

from typing import Generic, TypeVar

from reflex_docgen.markdown._types import (
    Block,
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

T = TypeVar("T")


def _not_impl(cls: type, method: str) -> NotImplementedError:
    msg = f"{cls.__name__}.{method}() is not implemented"
    return NotImplementedError(msg)


class DocumentTransformer(Generic[T]):
    r"""Base class for transforming a parsed markdown document into *T*.

    Subclass and override individual methods to produce the desired output.
    The dispatch methods (:meth:`transform_block` and :meth:`transform_span`)
    route each node to the correct handler via ``match``; you generally don't
    need to override them.

    Example::

        class ToHTML(DocumentTransformer[str]):
            def transform(self, document: Document) -> str:
                return "\n".join(self.transform_blocks(document.blocks))

            def heading(self, block: HeadingBlock) -> str:
                tag = f"h{block.level}"
                inner = "".join(self.transform_spans(block.children))
                return f"<{tag}>{inner}</{tag}>"

            def text_block(self, block: TextBlock) -> str:
                inner = "".join(self.transform_spans(block.children))
                return f"<p>{inner}</p>"

            def text_span(self, span: TextSpan) -> str:
                return span.text

            def bold(self, span: BoldSpan) -> str:
                inner = "".join(self.transform_spans(span.children))
                return f"<strong>{inner}</strong>"

            ...
    """

    # ------------------------------------------------------------------
    # Top-level entry point
    # ------------------------------------------------------------------

    def transform(self, document: Document) -> T:
        """Transform a full :class:`Document` into *T*.

        Override this to control how the document's frontmatter and blocks are
        combined into a single result.

        Args:
            document: The parsed document.

        Returns:
            The transformed result.
        """
        raise _not_impl(type(self), "transform")

    # ------------------------------------------------------------------
    # Block dispatch
    # ------------------------------------------------------------------

    def transform_block(self, block: Block) -> T:
        """Dispatch a single block to the appropriate handler.

        Args:
            block: The block to transform.

        Returns:
            The transformed result.
        """
        match block:
            case FrontMatter():
                return self.frontmatter(block)
            case CodeBlock():
                return self.code_block(block)
            case DirectiveBlock():
                return self.directive(block)
            case HeadingBlock():
                return self.heading(block)
            case TextBlock():
                return self.text_block(block)
            case ListBlock():
                return self.list_block(block)
            case QuoteBlock():
                return self.quote(block)
            case TableBlock():
                return self.table(block)
            case ThematicBreakBlock():
                return self.thematic_break(block)
            case _:  # pragma: no cover — future-proofing
                msg = f"Unknown block type: {type(block).__name__}"
                raise TypeError(msg)

    def transform_blocks(self, blocks: tuple[Block, ...]) -> tuple[T, ...]:
        """Transform a sequence of blocks.

        Args:
            blocks: The blocks to transform.

        Returns:
            A tuple of transformed results, one per block.
        """
        return tuple(self.transform_block(b) for b in blocks)

    # ------------------------------------------------------------------
    # Span dispatch
    # ------------------------------------------------------------------

    def transform_span(self, span: Span) -> T:
        """Dispatch a single span to the appropriate handler.

        Args:
            span: The span to transform.

        Returns:
            The transformed result.
        """
        match span:
            case TextSpan():
                return self.text_span(span)
            case BoldSpan():
                return self.bold(span)
            case ItalicSpan():
                return self.italic(span)
            case StrikethroughSpan():
                return self.strikethrough(span)
            case CodeSpan():
                return self.code_span(span)
            case LinkSpan():
                return self.link(span)
            case ImageSpan():
                return self.image(span)
            case LineBreakSpan():
                return self.line_break(span)
            case _:  # pragma: no cover — future-proofing
                msg = f"Unknown span type: {type(span).__name__}"
                raise TypeError(msg)

    def transform_spans(self, spans: tuple[Span, ...]) -> tuple[T, ...]:
        """Transform a sequence of spans.

        Args:
            spans: The spans to transform.

        Returns:
            A tuple of transformed results, one per span.
        """
        return tuple(self.transform_span(s) for s in spans)

    # ------------------------------------------------------------------
    # Composite node helpers
    # ------------------------------------------------------------------

    def transform_list_item(self, item: ListItem) -> T:
        """Transform a single list item.

        Args:
            item: The list item to transform.

        Returns:
            The transformed result.
        """
        raise _not_impl(type(self), "transform_list_item")

    def transform_table_row(self, row: TableRow) -> T:
        """Transform a single table row.

        Args:
            row: The table row to transform.

        Returns:
            The transformed result.
        """
        raise _not_impl(type(self), "transform_table_row")

    def transform_table_cell(self, cell: TableCell) -> T:
        """Transform a single table cell.

        Args:
            cell: The table cell to transform.

        Returns:
            The transformed result.
        """
        raise _not_impl(type(self), "transform_table_cell")

    # ------------------------------------------------------------------
    # Block handlers — override these in subclasses
    # ------------------------------------------------------------------

    def frontmatter(self, block: FrontMatter) -> T:
        """Transform a :class:`FrontMatter` block.

        Args:
            block: The frontmatter block.

        Returns:
            The transformed result.
        """
        raise _not_impl(type(self), "frontmatter")

    def code_block(self, block: CodeBlock) -> T:
        """Transform a :class:`CodeBlock`.

        Args:
            block: The code block.

        Returns:
            The transformed result.
        """
        raise _not_impl(type(self), "code_block")

    def directive(self, block: DirectiveBlock) -> T:
        """Transform a :class:`DirectiveBlock`.

        Args:
            block: The directive block.

        Returns:
            The transformed result.
        """
        raise _not_impl(type(self), "directive")

    def heading(self, block: HeadingBlock) -> T:
        """Transform a :class:`HeadingBlock`.

        Args:
            block: The heading block.

        Returns:
            The transformed result.
        """
        raise _not_impl(type(self), "heading")

    def text_block(self, block: TextBlock) -> T:
        """Transform a :class:`TextBlock`.

        Args:
            block: The text block.

        Returns:
            The transformed result.
        """
        raise _not_impl(type(self), "text_block")

    def list_block(self, block: ListBlock) -> T:
        """Transform a :class:`ListBlock`.

        Args:
            block: The list block.

        Returns:
            The transformed result.
        """
        raise _not_impl(type(self), "list_block")

    def quote(self, block: QuoteBlock) -> T:
        """Transform a :class:`QuoteBlock`.

        Args:
            block: The quote block.

        Returns:
            The transformed result.
        """
        raise _not_impl(type(self), "quote")

    def table(self, block: TableBlock) -> T:
        """Transform a :class:`TableBlock`.

        Args:
            block: The table block.

        Returns:
            The transformed result.
        """
        raise _not_impl(type(self), "table")

    def thematic_break(self, block: ThematicBreakBlock) -> T:
        """Transform a :class:`ThematicBreakBlock`.

        Args:
            block: The thematic break block.

        Returns:
            The transformed result.
        """
        raise _not_impl(type(self), "thematic_break")

    # ------------------------------------------------------------------
    # Span handlers — override these in subclasses
    # ------------------------------------------------------------------

    def text_span(self, span: TextSpan) -> T:
        """Transform a :class:`TextSpan`.

        Args:
            span: The text span.

        Returns:
            The transformed result.
        """
        raise _not_impl(type(self), "text_span")

    def bold(self, span: BoldSpan) -> T:
        """Transform a :class:`BoldSpan`.

        Args:
            span: The bold span.

        Returns:
            The transformed result.
        """
        raise _not_impl(type(self), "bold")

    def italic(self, span: ItalicSpan) -> T:
        """Transform an :class:`ItalicSpan`.

        Args:
            span: The italic span.

        Returns:
            The transformed result.
        """
        raise _not_impl(type(self), "italic")

    def strikethrough(self, span: StrikethroughSpan) -> T:
        """Transform a :class:`StrikethroughSpan`.

        Args:
            span: The strikethrough span.

        Returns:
            The transformed result.
        """
        raise _not_impl(type(self), "strikethrough")

    def code_span(self, span: CodeSpan) -> T:
        """Transform a :class:`CodeSpan`.

        Args:
            span: The code span.

        Returns:
            The transformed result.
        """
        raise _not_impl(type(self), "code_span")

    def link(self, span: LinkSpan) -> T:
        """Transform a :class:`LinkSpan`.

        Args:
            span: The link span.

        Returns:
            The transformed result.
        """
        raise _not_impl(type(self), "link")

    def image(self, span: ImageSpan) -> T:
        """Transform an :class:`ImageSpan`.

        Args:
            span: The image span.

        Returns:
            The transformed result.
        """
        raise _not_impl(type(self), "image")

    def line_break(self, span: LineBreakSpan) -> T:
        """Transform a :class:`LineBreakSpan`.

        Args:
            span: The line break span.

        Returns:
            The transformed result.
        """
        raise _not_impl(type(self), "line_break")
