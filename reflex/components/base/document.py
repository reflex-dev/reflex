"""Document components."""

from reflex.components.component import Component
from reflex.components.libs.chakra import ChakraComponent


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


class NextScript(NextDocumentLib):
    """The document main scripts."""

    tag = "NextScript"


class ColorModeScript(ChakraComponent):
    """Chakra color mode script."""

    tag = "ColorModeScript"
    initialColorMode = "light"
