"""Document components."""

from typing import Optional

from reflex.components.component import Component


class NextDocumentLib(Component):
    """Root document components."""

    library: str = "next/document"


class Html(NextDocumentLib):
    """The document html."""

    tag: str = "Html"

    lang: Optional[str]


class DocumentHead(NextDocumentLib):
    """The document head."""

    tag: str = "Head"


class Main(NextDocumentLib):
    """The document main section."""

    tag: str = "Main"


class NextScript(NextDocumentLib):
    """The document main scripts."""

    tag: str = "NextScript"
