"""Plugins API reference page."""

from reflex_docs.templates.docpage import docpage

import reflex as rx


@docpage("/docs/api-reference/plugins/")
def plugins():
    """Plugins API reference page."""
    with open("docs/api-reference/plugins.md", encoding="utf-8") as f:
        content = f.read()
    return rx.markdown(content)
