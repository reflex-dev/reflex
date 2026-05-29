"""Parse Reflex documentation markdown files using mistletoe."""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import TYPE_CHECKING, cast

from reflex_docgen.markdown._types import (
    Block,
    BoldSpan,
    CodeBlock,
    CodeSpan,
    ComponentPreview,
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

if TYPE_CHECKING:
    from mistletoe.block_token import BlockToken

_FRONTMATTER_RE = re.compile(r"\A---\n(.*?\n)---\n", re.DOTALL)


#: Known frontmatter keys that are not component preview lambdas.
_KNOWN_KEYS = frozenset({"components", "only_low_level", "title"})


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

    import yaml

    data = yaml.safe_load(m.group(1))
    if not isinstance(data, dict):
        data = {}

    # components
    raw_components = data.get("components", [])
    if not isinstance(raw_components, list):
        raw_components = []
    components = tuple(str(c) for c in raw_components)

    # only_low_level
    raw_oll = data.get("only_low_level", [])
    if isinstance(raw_oll, list):
        only_low_level = bool(raw_oll and raw_oll[0])
    else:
        only_low_level = bool(raw_oll)

    # title
    raw_title = data.get("title")
    title = str(raw_title) if raw_title is not None else None

    # component previews — any key not in _KNOWN_KEYS with a string value
    previews: list[ComponentPreview] = []
    for key, value in data.items():
        if key not in _KNOWN_KEYS and isinstance(value, str):
            previews.append(ComponentPreview(name=key, source=value.strip()))

    return (
        FrontMatter(
            components=components,
            only_low_level=only_low_level,
            title=title,
            component_previews=tuple(previews),
        ),
        source[m.end() :],
    )


def _convert_span(token: object) -> Span:
    """Convert a mistletoe span token into a Span.

    Args:
        token: A mistletoe span token.

    Returns:
        The corresponding Span.
    """
    from mistletoe.span_token import (
        Emphasis,
        EscapeSequence,
        Image,
        InlineCode,
        LineBreak,
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
            msg = (
                f"Expected InlineCode to have a single RawText child, got {children!r}"
            )
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

    if isinstance(token, LineBreak):
        return LineBreakSpan(soft=token.soft)

    if isinstance(token, EscapeSequence):
        # EscapeSequence.children is a tuple of one RawText with the escaped char.
        children = token.children
        if (
            not isinstance(children, tuple)
            or len(children) != 1
            or not isinstance(children[0], RawText)
        ):
            msg = f"Expected EscapeSequence to have a single RawText child, got {children!r}"
            raise TypeError(msg)
        return TextSpan(text=children[0].content)

    msg = f"Unsupported span token type: {type(token).__name__}"
    raise TypeError(msg)


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
    from mistletoe.block_token import BlockCode as MistletoeBlockCode
    from mistletoe.block_token import CodeFence as MistletoeCodeFence
    from mistletoe.block_token import Heading as MistletoeHeading
    from mistletoe.block_token import List as MistletoeList
    from mistletoe.block_token import ListItem as MistletoeListItem
    from mistletoe.block_token import Paragraph as MistletoeParagraph
    from mistletoe.block_token import Quote as MistletoeQuote
    from mistletoe.block_token import SetextHeading as MistletoeSetextHeading
    from mistletoe.block_token import Table as MistletoeTable
    from mistletoe.block_token import ThematicBreak as MistletoeThematicBreak
    from mistletoe.span_token import RawText as MistletoeRawText

    if isinstance(token, (MistletoeHeading, MistletoeSetextHeading)):
        return HeadingBlock(level=token.level, children=_convert_children(token))

    if isinstance(token, (MistletoeBlockCode, MistletoeCodeFence)):
        if isinstance(token, MistletoeCodeFence):
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
            or not isinstance(children[0], MistletoeRawText)
        ):
            msg = (
                f"Expected code block to have a single RawText child, got {children!r}"
            )
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
                children=_parse_blocks(content),
            )

        return CodeBlock(language=language, flags=flags, content=content)

    if isinstance(token, MistletoeParagraph):
        spans = _convert_children(token)
        if spans:
            return TextBlock(children=spans)
        return None

    if isinstance(token, MistletoeList):
        items: list[ListItem] = []
        if token.children:
            for item_token in token.children:
                if not isinstance(item_token, MistletoeListItem):
                    msg = f"Expected ListItem, got {type(item_token).__name__}"
                    raise TypeError(msg)
                item_blocks = _convert_block_children(item_token)
                items.append(ListItem(children=item_blocks))
        # List.start is an instance attribute (int | None) but the type checker sees
        # the classmethod start(cls, line) instead.
        list_start = cast("int | None", token.start)
        return ListBlock(
            ordered=list_start is not None,
            start=list_start,
            items=tuple(items),
        )

    if isinstance(token, MistletoeQuote):
        return QuoteBlock(children=_convert_block_children(token))

    if isinstance(token, MistletoeTable):
        header = _convert_table_row(token.header, token.column_align)
        rows = [
            _convert_table_row(row_token, token.column_align)
            for row_token in (token.children or ())
        ]
        return TableBlock(header=header, rows=tuple(rows))

    if isinstance(token, MistletoeThematicBreak):
        return ThematicBreakBlock()

    msg = f"Unsupported block token type: {type(token).__name__}"
    raise TypeError(msg)


def _convert_block_children(token: BlockToken) -> tuple[Block, ...]:
    """Convert the block-level children of a container token.

    Args:
        token: A mistletoe container block token.

    Returns:
        A tuple of Block objects.
    """
    from mistletoe.block_token import BlockToken

    if not token.children:
        return ()
    result: list[Block] = []
    for child in token.children:
        if not isinstance(child, BlockToken):
            msg = f"Expected BlockToken, got {type(child).__name__}"
            raise TypeError(msg)
        block = _convert_block(child)
        if block is not None:
            result.append(block)
    return tuple(result)


def _convert_table_row(
    row_token: object, column_align: Sequence[int | None]
) -> TableRow:
    """Convert a mistletoe TableRow into a TableRow.

    Args:
        row_token: A mistletoe TableRow token.
        column_align: The column alignment list from the Table.

    Returns:
        A TableRow.
    """
    align_map = {None: None, 0: None, 1: "left", 2: "right", 3: "center"}
    children = getattr(row_token, "children", None) or ()
    cells = [
        TableCell(
            children=_convert_children(cell_token),
            align=align_map.get(column_align[i] if i < len(column_align) else None),
        )
        for i, cell_token in enumerate(children)
    ]
    return TableRow(cells=tuple(cells))


def _parse_blocks(source: str) -> tuple[Block, ...]:
    """Parse a markdown string into a tuple of Blocks.

    Args:
        source: The raw markdown source string.

    Returns:
        A tuple of parsed Block objects.
    """
    from mistletoe.block_token import BlockToken
    from mistletoe.block_token import Document as MistletoeDocument

    doc = MistletoeDocument(source)
    result: list[Block] = []
    if doc.children:
        for child in doc.children:
            if not isinstance(child, BlockToken):
                msg = f"Expected BlockToken, got {type(child).__name__}"
                raise TypeError(msg)
            block = _convert_block(child)
            if block is not None:
                result.append(block)
    return tuple(result)


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
