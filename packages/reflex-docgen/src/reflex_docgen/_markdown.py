"""Parse Reflex documentation markdown files using mistletoe."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mistletoe.block_token import BlockToken

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


#: Union of all inline span types.
Span = (
    TextSpan
    | BoldSpan
    | ItalicSpan
    | StrikethroughSpan
    | CodeSpan
    | LinkSpan
    | ImageSpan
)

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
        content: The raw content inside the block.
    """

    name: str
    args: tuple[str, ...]
    content: str


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


#: Union of all block types that can appear in a parsed document.
Block = FrontMatter | CodeBlock | DirectiveBlock | HeadingBlock | TextBlock


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


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

_FRONTMATTER_RE = re.compile(r"\A---\n(.*?\n)---\n", re.DOTALL)


def _extract_frontmatter(source: str) -> tuple[FrontMatter | None, str]:
    """Extract YAML frontmatter from the beginning of a markdown string.

    Args:
        source: The raw markdown source.

    Returns:
        A tuple of (FrontMatter or None, remaining source).
    """
    m = _FRONTMATTER_RE.match(source)
    if m is None:
        return None, source
    return FrontMatter(raw=m.group(1).strip()), source[m.end() :]


def _convert_span(token: object) -> Span:
    """Convert a mistletoe span token into a Span.

    Args:
        token: A mistletoe span token.

    Returns:
        The corresponding Span.
    """
    from mistletoe.span_token import (
        Emphasis,
        Image,
        InlineCode,
        Link,
        RawText,
        Strikethrough,
        Strong,
    )

    if isinstance(token, RawText):
        return TextSpan(text=token.content)

    if isinstance(token, InlineCode):
        # InlineCode.children is a tuple of one RawText element.
        children = token.children
        if (
            not isinstance(children, tuple)
            or len(children) != 1
            or not isinstance(children[0], RawText)
        ):
            msg = f"Expected InlineCode to have a single RawText child, got {children!r}"
            raise TypeError(msg)
        return CodeSpan(code=children[0].content)

    if isinstance(token, Strong):
        return BoldSpan(children=_convert_children(token))

    if isinstance(token, Emphasis):
        return ItalicSpan(children=_convert_children(token))

    if isinstance(token, Strikethrough):
        return StrikethroughSpan(children=_convert_children(token))

    if isinstance(token, Link):
        return LinkSpan(children=_convert_children(token), target=token.target)

    if isinstance(token, Image):
        return ImageSpan(children=_convert_children(token), src=token.src)

    # Unknown span type — render as plain text via its content or repr.
    content = getattr(token, "content", None) or str(token)
    return TextSpan(text=content)


def _convert_children(token: object) -> tuple[Span, ...]:
    """Convert the children of a mistletoe token into Spans.

    Args:
        token: A mistletoe token with a children attribute.

    Returns:
        A tuple of Span objects.
    """
    children = getattr(token, "children", None)
    if children is None:
        return ()
    return tuple(_convert_span(child) for child in children)


def _parse_info_string(info: str) -> tuple[str | None, tuple[str, ...]]:
    """Parse a fenced code block info string into language and flags.

    Args:
        info: The info string (e.g. "python demo exec").

    Returns:
        A tuple of (language, flags).
    """
    parts = info.strip().split()
    if not parts:
        return None, ()
    return parts[0], tuple(parts[1:])


def _convert_block(token: BlockToken) -> Block | None:
    """Convert a mistletoe block token into a docgen Block.

    Args:
        token: The mistletoe block token.

    Returns:
        A Block, or None if the token should be skipped.
    """
    from mistletoe.block_token import BlockCode, CodeFence, Heading, Paragraph
    from mistletoe.span_token import RawText

    if isinstance(token, Heading):
        return HeadingBlock(level=token.level, children=_convert_children(token))

    if isinstance(token, (BlockCode, CodeFence)):
        if isinstance(token, CodeFence):
            # CodeFence.info_string contains the full info string including language.
            info = token.info_string or ""
        else:
            info = getattr(token, "language", "") or ""
        language, flags = _parse_info_string(info)

        # CodeFence/BlockCode.children is a tuple of one RawText element.
        children = token.children
        if not children:
            content = ""
        elif (
            not isinstance(children, tuple)
            or len(children) != 1
            or not isinstance(children[0], RawText)
        ):
            msg = f"Expected code block to have a single RawText child, got {children!r}"
            raise TypeError(msg)
        else:
            content = children[0].content
        # Strip trailing newline that mistletoe adds.
        content = content.rstrip("\n")

        # ```md <directive> [args...]``` blocks become DirectiveBlocks.
        if language == "md" and flags:
            return DirectiveBlock(
                name=flags[0],
                args=flags[1:],
                content=content,
            )

        return CodeBlock(language=language, flags=flags, content=content)

    if isinstance(token, Paragraph):
        spans = _convert_children(token)
        if spans:
            return TextBlock(children=spans)
        return None

    # For other block types (lists, blockquotes, etc.), convert children
    # or fall back to a TextSpan of the raw content.
    spans = _convert_children(token)
    if spans:
        return TextBlock(children=spans)
    return None


def parse_document(source: str) -> Document:
    """Parse a Reflex documentation markdown file into a Document.

    Args:
        source: The raw markdown source string.

    Returns:
        A parsed Document with frontmatter and content blocks.
    """
    from mistletoe.block_token import BlockToken
    from mistletoe.block_token import Document as MistletoeDocument

    frontmatter, remaining = _extract_frontmatter(source)
    doc = MistletoeDocument(remaining)

    blocks: list[Block] = []
    if doc.children:
        for child in doc.children:
            # mistletoe.block_token.Document guarantees children are BlockToken
            # instances (see its docstring: "Its children are block tokens").
            if not isinstance(child, BlockToken):
                msg = f"Expected BlockToken, got {type(child).__name__}"
                raise TypeError(msg)
            block = _convert_block(child)
            if block is not None:
                blocks.append(block)

    return Document(frontmatter=frontmatter, blocks=tuple(blocks))
