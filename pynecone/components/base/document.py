"""Document components."""

from pynecone.components.component import Component
from pynecone.components.libs.chakra import ChakraComponent


class NextDocumentLib(Component):
    """Root document components."""

    library = "next/document"


class Html(NextDocumentLib):
    """The document html."""

    tag = "Html"


class DocumentHead(NextDocumentLib):
    """The document head."""

    tag = "Head"


class Main(NextDocumentLib):
    """The document main section."""

    tag = "Main"


class Script(NextDocumentLib):
    """The document main scripts."""

    tag = "NextScript"


class ColorModeScript(ChakraComponent):
    """Chakra color mode script."""

    tag = "ColorModeScript"
    initialColorMode = "light"
