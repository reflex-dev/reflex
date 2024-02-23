"""Document components."""

from typing import Optional, Union

from reflex.components.component import Component
from reflex.vars import Var


class NextDocumentLib(Component):
    """Root document components."""

    library = "next/document"


class Html(NextDocumentLib):
    """The document html."""

    tag = "Html"

    lang: Optional[Var[Union[str, int, bool]]] = None


class DocumentHead(NextDocumentLib):
    """The document head."""

    tag = "Head"


class Main(NextDocumentLib):
    """The document main section."""

    tag = "Main"


class NextScript(NextDocumentLib):
    """The document main scripts."""

    tag = "NextScript"
