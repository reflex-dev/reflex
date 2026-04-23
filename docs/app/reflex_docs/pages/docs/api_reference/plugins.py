"""Plugins API reference page."""

import reflex as rx

from reflex_docs.templates.docpage import docpage


@docpage("/api-reference/plugins/")
def plugins():
    """Plugins API reference page."""
    with open("docs/api-reference/plugins.md", encoding="utf-8") as f:
        content = f.read()
    return rx.markdown(content)
