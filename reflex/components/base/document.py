"""Document components."""

from reflex.components.component import Component


class NextDocumentLib(Component):
    """Root document components."""

    library = "next/document"


class Html(NextDocumentLib):
    """The document html."""

    tag = "Html"

    lang: str | None


class DocumentHead(NextDocumentLib):
    """The document head."""

    tag = "Head"


class Main(NextDocumentLib):
    """The document main section."""

    tag = "Main"


class NextScript(NextDocumentLib):
    """The document main scripts."""

    tag = "NextScript"
