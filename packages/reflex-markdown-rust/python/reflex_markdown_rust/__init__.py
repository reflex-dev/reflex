"""Rust acceleration wheel for Reflex's Markdown pipeline (pulldown-cmark).

The legacy Reflex Markdown path uses Python's ``mistletoe`` (~0.79s of the
10.1s docs-app cold-compile baseline). This wheel exposes a near drop-in
``markdown_to_html`` that's 15-30× faster on equivalent inputs.

Usage::

    from reflex_markdown_rust import markdown_to_html, OPT_TABLES, OPT_FOOTNOTES

    html = markdown_to_html("# Hello\\nworld")
    html = markdown_to_html_with(text, OPT_TABLES | OPT_FOOTNOTES)
"""

from reflex_markdown_rust._native import (  # noqa: F401
    DEFAULT_OPTS,
    OPT_FOOTNOTES,
    OPT_HEADING_ATTRIBUTES,
    OPT_SMART_PUNCTUATION,
    OPT_STRIKETHROUGH,
    OPT_TABLES,
    OPT_TASKLISTS,
    OPT_YAML_STYLE_METADATA_BLOCKS,
    event_count,
    markdown_to_html,
    markdown_to_html_with,
)

__all__ = [
    "DEFAULT_OPTS",
    "OPT_FOOTNOTES",
    "OPT_HEADING_ATTRIBUTES",
    "OPT_SMART_PUNCTUATION",
    "OPT_STRIKETHROUGH",
    "OPT_TABLES",
    "OPT_TASKLISTS",
    "OPT_YAML_STYLE_METADATA_BLOCKS",
    "event_count",
    "markdown_to_html",
    "markdown_to_html_with",
]
