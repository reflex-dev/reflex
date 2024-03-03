"""Document components."""

from typing import Optional

from reflex.components.component import Component


class NextDocumentLib(Component):
    """Root document components."""

    library = "next/document"


class Html(NextDocumentLib):
    """The document html."""

    tag = "Html"

    lang: Optional[str]


class DocumentHead(NextDocumentLib):
    """The document head."""

    tag = "Head"


class Main(NextDocumentLib):
    """The document main section."""

    tag = "Main"


class NextScript(NextDocumentLib):
    """The document main scripts."""

    tag = "NextScript"
