"""A link component."""

from typing import Optional

from reflex.components.component import Component
from reflex.components.libs.chakra import ChakraComponent
from reflex.components.navigation.nextlink import NextLink
from reflex.utils import imports
from reflex.vars import BaseVar, Var


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
        return {**super()._get_imports(), **NextLink.create()._get_imports()}

    @classmethod
    def create(cls, *children, href: Optional[Var] = None, **props) -> Component:
        """Create a Link component.

        Args:
            *children: The children of the component.
            href: The href attribute of the link.
            **props: The props of the component.

        Raises:
            ValueError: in case of missing children

        Returns:
            Component: The link component
        """
        if href and not len(children):
            raise ValueError("Link without a child will not display")
        elif href is None and len(children):
            # Don't use a NextLink if there is no href.
            props["as_"] = ""
        if href:
            props["href"] = href
        return super().create(*children, **props)
