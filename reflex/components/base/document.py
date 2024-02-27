"""Document components."""

from typing import Any, Optional, Union

from reflex.components.component import Component
from reflex.vars import Var


class NextDocumentLib(Component):
    """Root document components."""

    library = "next/document"


class Html(NextDocumentLib):
    """The document html."""

    tag = "Html"

    lang: Var[str]

    @classmethod
    def create(
        cls, *args: Any, lang: Optional[Union[str, Var[str]]] = None, **props: Any
    ) -> Component:
        """Create an Html root element.

        Args:
            *args: The args of the component.
            lang: The language of the document.
            **props:The props of the component.

        Returns:
            Html component.
        """
        if lang is not None and not isinstance(lang, Var):
            lang = Var.create(value=lang, _var_is_string=True)
        props["lang"] = lang

        return super().create(*args, **props)


class DocumentHead(NextDocumentLib):
    """The document head."""

    tag = "Head"


class Main(NextDocumentLib):
    """The document main section."""

    tag = "Main"


class NextScript(NextDocumentLib):
    """The document main scripts."""

    tag = "NextScript"
