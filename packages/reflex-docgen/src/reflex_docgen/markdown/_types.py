"""Markdown document types — spans, blocks, and document."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Span types — inline content without exposing mistletoe
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True, kw_only=True)
class TextSpan:
    """Plain text.

    Attributes:
        text: The text content.
    """

    text: str


@dataclass(frozen=True, slots=True, kw_only=True)
class BoldSpan:
    """Bold (strong) text.

    Attributes:
        children: The inline spans inside the bold.
    """

    children: tuple[Span, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class ItalicSpan:
    """Italic (emphasis) text.

    Attributes:
        children: The inline spans inside the italic.
    """

    children: tuple[Span, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class StrikethroughSpan:
    """Strikethrough text.

    Attributes:
        children: The inline spans inside the strikethrough.
    """

    children: tuple[Span, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class CodeSpan:
    """Inline code.

    Attributes:
        code: The code text.
    """

    code: str


@dataclass(frozen=True, slots=True, kw_only=True)
class LinkSpan:
    """A hyperlink.

    Attributes:
        children: The inline spans forming the link text.
        target: The URL target.
    """

    children: tuple[Span, ...]
    target: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ImageSpan:
    """An inline image.

    Attributes:
        children: The inline spans forming the alt text.
        src: The image source URL.
    """

    children: tuple[Span, ...]
    src: str


@dataclass(frozen=True, slots=True, kw_only=True)
class LineBreakSpan:
    """A line break.

    Attributes:
        soft: Whether this is a soft line break.
    """

    soft: bool


#: Union of all inline span types.
Span = (
    TextSpan
    | BoldSpan
    | ItalicSpan
    | StrikethroughSpan
    | CodeSpan
    | LinkSpan
    | ImageSpan
    | LineBreakSpan
)


# ---------------------------------------------------------------------------
# Block types
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True, kw_only=True)
class ComponentPreview:
    """A component preview lambda from frontmatter.

    Attributes:
        name: The component class name (e.g. "Button", "DialogRoot").
        source: The lambda source string.
    """

    name: str
    source: str


@dataclass(frozen=True, slots=True, kw_only=True)
class FrontMatter:
    """YAML frontmatter extracted from a markdown document.

    Attributes:
        components: Component paths to document (e.g. ``["rx.button"]``).
        only_low_level: Whether to show only low-level component variants.
        title: An optional page title.
        component_previews: Preview lambdas keyed by component class name.
        metadata: The full raw frontmatter mapping, including the keys modeled
            by the fields above plus any arbitrary keys a site defines (e.g.
            ``author``, ``tags``, ``order``).
    """

    components: tuple[str, ...]
    only_low_level: bool
    title: str | None
    component_previews: tuple[ComponentPreview, ...]
    metadata: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True, kw_only=True)
class CodeBlock:
    """A fenced code block with optional language and flags.

    Attributes:
        language: The language identifier (e.g. "python").
        flags: Additional flags after the language (e.g. ("demo", "exec")).
        content: The code content inside the block.
    """

    language: str | None
    flags: tuple[str, ...]
    content: str


@dataclass(frozen=True, slots=True, kw_only=True)
class DirectiveBlock:
    """A markdown directive block (```md <name> [args...] ```).

    Covers alert, video, definition, section, and any future md directives.

    Attributes:
        name: The directive name (e.g. "alert", "video", "definition", "section").
        args: Additional arguments after the name (e.g. ("info",) or ("https://...",)).
        children: The parsed block-level content inside the directive.
        content: The raw (unparsed) inner text. Directives whose body is
            line-oriented rather than markdown (e.g. a ``quote`` block's
            ``- name:``/``- role:`` lines) should read this instead of
            ``children`` to avoid CommonMark reflowing the lines.
    """

    name: str
    args: tuple[str, ...]
    children: tuple[Block, ...]
    content: str = ""


@dataclass(frozen=True, slots=True, kw_only=True)
class HeadingBlock:
    """A markdown heading.

    Attributes:
        level: The heading level (1-6).
        children: The inline spans forming the heading text.
    """

    level: int
    children: tuple[Span, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class TextBlock:
    """A block of markdown text (paragraph or other inline content).

    Attributes:
        children: The inline spans forming the text content.
    """

    children: tuple[Span, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class ListItem:
    """A single item in a list.

    Attributes:
        children: The block-level content of the list item.
    """

    children: tuple[Block, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class ListBlock:
    """An ordered or unordered list.

    Attributes:
        ordered: Whether the list is ordered.
        start: The starting number for ordered lists, or None for unordered.
        items: The list items.
    """

    ordered: bool
    start: int | None
    items: tuple[ListItem, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class QuoteBlock:
    """A block quote.

    Attributes:
        children: The block-level content inside the quote.
    """

    children: tuple[Block, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class TableCell:
    """A single cell in a table.

    Attributes:
        children: The inline spans forming the cell content.
        align: The column alignment ("left", "right", "center", or None).
    """

    children: tuple[Span, ...]
    align: str | None


@dataclass(frozen=True, slots=True, kw_only=True)
class TableRow:
    """A row in a table.

    Attributes:
        cells: The cells in the row.
    """

    cells: tuple[TableCell, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class TableBlock:
    """A table.

    Attributes:
        header: The header row.
        rows: The body rows.
    """

    header: TableRow
    rows: tuple[TableRow, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class ThematicBreakBlock:
    """A thematic break (horizontal rule)."""


#: Union of all block types that can appear in a parsed document.
Block = (
    FrontMatter
    | CodeBlock
    | DirectiveBlock
    | HeadingBlock
    | TextBlock
    | ListBlock
    | QuoteBlock
    | TableBlock
    | ThematicBreakBlock
)


@dataclass(frozen=True, slots=True, kw_only=True)
class Document:
    """A parsed Reflex documentation markdown file.

    Attributes:
        frontmatter: The YAML frontmatter, if present.
        blocks: The sequence of content blocks in document order.
    """

    frontmatter: FrontMatter | None
    blocks: tuple[Block, ...]

    @property
    def metadata(self) -> Mapping[str, object]:
        """Return the raw frontmatter mapping, or an empty mapping if absent."""
        return self.frontmatter.metadata if self.frontmatter is not None else {}

    @property
    def headings(self) -> tuple[HeadingBlock, ...]:
        """Return all headings in the document."""
        return tuple(b for b in self.blocks if isinstance(b, HeadingBlock))

    @property
    def code_blocks(self) -> tuple[CodeBlock, ...]:
        """Return all code blocks in the document."""
        return tuple(b for b in self.blocks if isinstance(b, CodeBlock))

    @property
    def directives(self) -> tuple[DirectiveBlock, ...]:
        """Return all directive blocks in the document."""
        return tuple(b for b in self.blocks if isinstance(b, DirectiveBlock))
