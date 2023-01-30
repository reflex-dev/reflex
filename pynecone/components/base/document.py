"""Document components."""

from pynecone.components.component import Component


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


class ChakraUiReactLib(Component):
    """Chakra UI React document components."""

    library = "@chakra-ui/react"


class ColorModeScript(ChakraUiReactLib):
    """Chakra color mode script."""

    tag = "ColorModeScript"
    initialColorMode = "light"
