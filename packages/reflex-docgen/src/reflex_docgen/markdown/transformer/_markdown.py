"""Markdown-string transformer — renders a Document back to markdown text."""

from __future__ import annotations

import re

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
    StrikethroughSpan,
    TableBlock,
    TableCell,
    TableRow,
    TextBlock,
    TextSpan,
    ThematicBreakBlock,
)
from reflex_docgen.markdown.transformer._base import DocumentTransformer

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


class MarkdownTransformer(DocumentTransformer[str]):
    """Transforms a :class:`Document` back into a markdown string.

    This is the reference implementation of :class:`DocumentTransformer` that
    renders every AST node back to its canonical markdown representation.
    """

    # ------------------------------------------------------------------
    # Top-level
    # ------------------------------------------------------------------

    def transform(self, document: Document) -> str:
        """Render a full document to markdown.

        Args:
            document: The parsed document.

        Returns:
            A markdown string.
        """
        parts: list[str] = []
        if document.frontmatter is not None:
            parts.append(self.frontmatter(document.frontmatter))
        parts.extend(self.transform_blocks(document.blocks))
        return "\n\n".join(parts) + "\n"

    # ------------------------------------------------------------------
    # Spans
    # ------------------------------------------------------------------

    def text_span(self, span: TextSpan) -> str:
        return span.text

    def bold(self, span: BoldSpan) -> str:
        inner = "".join(self.transform_spans(span.children))
        return f"**{inner}**"

    def italic(self, span: ItalicSpan) -> str:
        inner = "".join(self.transform_spans(span.children))
        return f"*{inner}*"

    def strikethrough(self, span: StrikethroughSpan) -> str:
        inner = "".join(self.transform_spans(span.children))
        return f"~~{inner}~~"

    def code_span(self, span: CodeSpan) -> str:
        return f"`{span.code}`"

    def link(self, span: LinkSpan) -> str:
        inner = "".join(self.transform_spans(span.children))
        return f"[{inner}]({span.target})"

    def image(self, span: ImageSpan) -> str:
        inner = "".join(self.transform_spans(span.children))
        return f"![{inner}]({span.src})"

    def line_break(self, span: LineBreakSpan) -> str:
        return "\n" if span.soft else "  \n"

    # ------------------------------------------------------------------
    # Blocks
    # ------------------------------------------------------------------

    def frontmatter(self, block: FrontMatter) -> str:
        import yaml

        data: dict[str, object] = {}
        if block.components:
            data["components"] = list(block.components)
        if block.only_low_level:
            data["only_low_level"] = [True]
        if block.title is not None:
            data["title"] = block.title
        for preview in block.component_previews:
            data[preview.name] = preview.source
        return f"---\n{yaml.dump(data, default_flow_style=False, sort_keys=False).rstrip()}\n---"

    def code_block(self, block: CodeBlock) -> str:
        info = block.language or ""
        if block.flags:
            info = f"{info} {' '.join(block.flags)}" if info else " ".join(block.flags)
        fence = _fence_for(block.content)
        return f"{fence}{info}\n{block.content}\n{fence}"

    def directive(self, block: DirectiveBlock) -> str:
        info_parts = ["md", block.name, *block.args]
        content = "\n\n".join(self.transform_blocks(block.children))
        fence = _fence_for(content)
        return f"{fence}{' '.join(info_parts)}\n{content}\n{fence}"

    def heading(self, block: HeadingBlock) -> str:
        inner = "".join(self.transform_spans(block.children))
        return f"{'#' * block.level} {inner}"

    def text_block(self, block: TextBlock) -> str:
        return "".join(self.transform_spans(block.children))

    def list_block(self, block: ListBlock) -> str:
        lines: list[str] = []
        for i, item in enumerate(block.items):
            prefix = f"{(block.start or 1) + i}. " if block.ordered else "- "
            item_md = self.transform_list_item(item)
            first, *rest = item_md.split("\n")
            lines.append(f"{prefix}{first}")
            indent = " " * len(prefix)
            lines.extend(f"{indent}{line}" if line else "" for line in rest)
        return "\n".join(lines)

    def transform_list_item(self, item: ListItem) -> str:
        return "\n\n".join(self.transform_blocks(item.children))

    def quote(self, block: QuoteBlock) -> str:
        inner = "\n\n".join(self.transform_blocks(block.children))
        return "\n".join(f"> {line}" if line else ">" for line in inner.split("\n"))

    def table(self, block: TableBlock) -> str:
        lines = [self.transform_table_row(block.header)]
        sep_parts: list[str] = []
        for cell in block.header.cells:
            if cell.align == "left":
                sep_parts.append(":---")
            elif cell.align == "right":
                sep_parts.append("---:")
            elif cell.align == "center":
                sep_parts.append(":---:")
            else:
                sep_parts.append("---")
        lines.append(f"| {' | '.join(sep_parts)} |")
        lines.extend(self.transform_table_row(row) for row in block.rows)
        return "\n".join(lines)

    def transform_table_row(self, row: TableRow) -> str:
        cells = " | ".join(self.transform_table_cell(cell) for cell in row.cells)
        return f"| {cells} |"

    def transform_table_cell(self, cell: TableCell) -> str:
        return "".join(self.transform_spans(cell.children))

    def thematic_break(self, block: ThematicBreakBlock) -> str:
        return "---"
