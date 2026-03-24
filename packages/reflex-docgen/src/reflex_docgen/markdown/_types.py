"""Markdown document types — spans, blocks, and document."""

from __future__ import annotations

import re
from dataclasses import dataclass

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

    def as_markdown(self) -> str:
        """Render back to markdown.

        Returns:
            A markdown string.
        """
        return self.text


@dataclass(frozen=True, slots=True, kw_only=True)
class BoldSpan:
    """Bold (strong) text.

    Attributes:
        children: The inline spans inside the bold.
    """

    children: tuple[Span, ...]

    def as_markdown(self) -> str:
        """Render back to markdown.

        Returns:
            A markdown string.
        """
        inner = "".join(c.as_markdown() for c in self.children)
        return f"**{inner}**"


@dataclass(frozen=True, slots=True, kw_only=True)
class ItalicSpan:
    """Italic (emphasis) text.

    Attributes:
        children: The inline spans inside the italic.
    """

    children: tuple[Span, ...]

    def as_markdown(self) -> str:
        """Render back to markdown.

        Returns:
            A markdown string.
        """
        inner = "".join(c.as_markdown() for c in self.children)
        return f"*{inner}*"


@dataclass(frozen=True, slots=True, kw_only=True)
class StrikethroughSpan:
    """Strikethrough text.

    Attributes:
        children: The inline spans inside the strikethrough.
    """

    children: tuple[Span, ...]

    def as_markdown(self) -> str:
        """Render back to markdown.

        Returns:
            A markdown string.
        """
        inner = "".join(c.as_markdown() for c in self.children)
        return f"~~{inner}~~"


@dataclass(frozen=True, slots=True, kw_only=True)
class CodeSpan:
    """Inline code.

    Attributes:
        code: The code text.
    """

    code: str

    def as_markdown(self) -> str:
        """Render back to markdown.

        Returns:
            A markdown string.
        """
        return f"`{self.code}`"


@dataclass(frozen=True, slots=True, kw_only=True)
class LinkSpan:
    """A hyperlink.

    Attributes:
        children: The inline spans forming the link text.
        target: The URL target.
    """

    children: tuple[Span, ...]
    target: str

    def as_markdown(self) -> str:
        """Render back to markdown.

        Returns:
            A markdown string.
        """
        inner = "".join(c.as_markdown() for c in self.children)
        return f"[{inner}]({self.target})"


@dataclass(frozen=True, slots=True, kw_only=True)
class ImageSpan:
    """An inline image.

    Attributes:
        children: The inline spans forming the alt text.
        src: The image source URL.
    """

    children: tuple[Span, ...]
    src: str

    def as_markdown(self) -> str:
        """Render back to markdown.

        Returns:
            A markdown string.
        """
        inner = "".join(c.as_markdown() for c in self.children)
        return f"![{inner}]({self.src})"


@dataclass(frozen=True, slots=True, kw_only=True)
class LineBreakSpan:
    """A line break.

    Attributes:
        soft: Whether this is a soft line break.
    """

    soft: bool

    def as_markdown(self) -> str:
        """Render back to markdown.

        Returns:
            A markdown string.
        """
        return "\n" if self.soft else "  \n"


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


def _spans_as_markdown(spans: tuple[Span, ...]) -> str:
    """Render a sequence of spans back to markdown.

    Args:
        spans: The inline spans to render.

    Returns:
        A markdown string.
    """
    return "".join(s.as_markdown() for s in spans)


_BACKTICK_FENCE_RE = re.compile(r"^(`{3,})", re.MULTILINE)


def _fence_for(content: str) -> str:
    """Return a backtick fence long enough to wrap *content* safely.

    Args:
        content: The code block content that may contain backtick fences.

    Returns:
        A backtick fence string (at least 3 backticks).
    """
    max_run = 3
    for m in _BACKTICK_FENCE_RE.finditer(content):
        max_run = max(max_run, len(m.group(1)) + 1)
    return "`" * max_run


# ---------------------------------------------------------------------------
# Block types
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True, kw_only=True)
class FrontMatter:
    """YAML frontmatter extracted from a markdown document.

    Attributes:
        raw: The raw YAML string (without delimiters).
    """

    raw: str

    def get_data(self) -> dict[str, object]:
        """Parse the raw YAML frontmatter into a dictionary.

        Returns:
            The parsed YAML data.
        """
        import yaml

        result = yaml.safe_load(self.raw)
        if result is None:
            return {}
        if not isinstance(result, dict):
            msg = f"Expected frontmatter to be a YAML mapping, got {type(result).__name__}"
            raise TypeError(msg)
        return result

    def as_markdown(self) -> str:
        """Render back to markdown.

        Returns:
            A markdown string.
        """
        return f"---\n{self.raw}\n---"


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

    def as_markdown(self) -> str:
        """Render back to markdown.

        Returns:
            A markdown string.
        """
        info = self.language or ""
        if self.flags:
            info = f"{info} {' '.join(self.flags)}" if info else " ".join(self.flags)
        fence = _fence_for(self.content)
        return f"{fence}{info}\n{self.content}\n{fence}"


@dataclass(frozen=True, slots=True, kw_only=True)
class DirectiveBlock:
    """A markdown directive block (```md <name> [args...] ```).

    Covers alert, video, definition, section, and any future md directives.

    Attributes:
        name: The directive name (e.g. "alert", "video", "definition", "section").
        args: Additional arguments after the name (e.g. ("info",) or ("https://...",)).
        content: The raw content inside the block.
    """

    name: str
    args: tuple[str, ...]
    content: str

    def as_markdown(self) -> str:
        """Render back to markdown.

        Returns:
            A markdown string.
        """
        info_parts = ["md", self.name, *self.args]
        fence = _fence_for(self.content)
        return f"{fence}{' '.join(info_parts)}\n{self.content}\n{fence}"


@dataclass(frozen=True, slots=True, kw_only=True)
class HeadingBlock:
    """A markdown heading.

    Attributes:
        level: The heading level (1-6).
        children: The inline spans forming the heading text.
    """

    level: int
    children: tuple[Span, ...]

    def as_markdown(self) -> str:
        """Render back to markdown.

        Returns:
            A markdown string.
        """
        return f"{'#' * self.level} {_spans_as_markdown(self.children)}"


@dataclass(frozen=True, slots=True, kw_only=True)
class TextBlock:
    """A block of markdown text (paragraph or other inline content).

    Attributes:
        children: The inline spans forming the text content.
    """

    children: tuple[Span, ...]

    def as_markdown(self) -> str:
        """Render back to markdown.

        Returns:
            A markdown string.
        """
        return _spans_as_markdown(self.children)


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

    def as_markdown(self) -> str:
        """Render back to markdown.

        Returns:
            A markdown string.
        """
        lines: list[str] = []
        for i, item in enumerate(self.items):
            prefix = f"{(self.start or 1) + i}. " if self.ordered else "- "
            item_md = "\n\n".join(child.as_markdown() for child in item.children)
            first, *rest = item_md.split("\n")
            lines.append(f"{prefix}{first}")
            indent = " " * len(prefix)
            lines.extend(f"{indent}{line}" if line else "" for line in rest)
        return "\n".join(lines)


@dataclass(frozen=True, slots=True, kw_only=True)
class QuoteBlock:
    """A block quote.

    Attributes:
        children: The block-level content inside the quote.
    """

    children: tuple[Block, ...]

    def as_markdown(self) -> str:
        """Render back to markdown.

        Returns:
            A markdown string.
        """
        inner = "\n\n".join(child.as_markdown() for child in self.children)
        return "\n".join(f"> {line}" if line else ">" for line in inner.split("\n"))


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

    def as_markdown(self) -> str:
        """Render back to markdown.

        Returns:
            A markdown string.
        """
        cells = " | ".join(_spans_as_markdown(cell.children) for cell in self.cells)
        return f"| {cells} |"


@dataclass(frozen=True, slots=True, kw_only=True)
class TableBlock:
    """A table.

    Attributes:
        header: The header row.
        rows: The body rows.
    """

    header: TableRow
    rows: tuple[TableRow, ...]

    def as_markdown(self) -> str:
        """Render back to markdown.

        Returns:
            A markdown string.
        """
        lines = [self.header.as_markdown()]
        sep_parts: list[str] = []
        for cell in self.header.cells:
            if cell.align == "left":
                sep_parts.append(":---")
            elif cell.align == "right":
                sep_parts.append("---:")
            elif cell.align == "center":
                sep_parts.append(":---:")
            else:
                sep_parts.append("---")
        lines.append(f"| {' | '.join(sep_parts)} |")
        lines.extend(row.as_markdown() for row in self.rows)
        return "\n".join(lines)


@dataclass(frozen=True, slots=True, kw_only=True)
class ThematicBreakBlock:
    """A thematic break (horizontal rule)."""

    def as_markdown(self) -> str:
        """Render back to markdown.

        Returns:
            A markdown string.
        """
        return "---"


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

    def as_markdown(self) -> str:
        """Render the full document back to markdown.

        Returns:
            A markdown string.
        """
        parts: list[str] = []
        if self.frontmatter:
            parts.append(self.frontmatter.as_markdown())
        parts.extend(block.as_markdown() for block in self.blocks)
        return "\n\n".join(parts) + "\n"
