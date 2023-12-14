"""Document components."""

from reflex.components.component import Component
from reflex.components.libs.chakra import ChakraComponent


class NextDocumentLib(Component):
    """Root document components."""

    library: str = "next/document"


class Html(NextDocumentLib):
    """The document html."""

    tag: str = "Html"


class DocumentHead(NextDocumentLib):
    """The document head."""

    tag: str = "Head"


class Main(NextDocumentLib):
    """The document main section."""

    tag: str = "Main"


class NextScript(NextDocumentLib):
    """The document main scripts."""

    tag: str = "NextScript"


class ColorModeScript(ChakraComponent):
    """Chakra color mode script."""

    tag: str = "ColorModeScript"
    initialColorMode: str = "light"
