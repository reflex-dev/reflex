"""A link component."""

from pynecone.components.libs.chakra import ChakraComponent
from pynecone.components.navigation.nextlink import NextLink
from pynecone.utils import imports
from pynecone.vars import BaseVar, Var


class Link(ChakraComponent):
    """Link to another page."""

    tag = "Link"

    # The rel.
    rel: Var[str]

    # The page to link to.
    href: Var[str]

    # The text to display.
    text: Var[str]

    # What the link renders to.
    as_: Var[str] = BaseVar.create("{NextLink}", is_local=False)  # type: ignore

    # If true, the link will open in new tab.
    is_external: Var[bool]

    def _get_imports(self) -> imports.ImportDict:
        return {**super()._get_imports(), **NextLink(href=self.href)._get_imports()}
