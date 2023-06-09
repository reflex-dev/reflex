"""A link component."""

from typing import Optional

from pynecone.components.component import Component
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
        return {**super()._get_imports(), **NextLink.create()._get_imports()}

    @classmethod
    def create(
        cls, *children, href: Optional[Var] = None, rel: Optional[Var] = None, **props
    ) -> Component:
        """Create a Link component.

        Args:
            *children: The children of the component.
            href (Var): The href attribute of the link. Defaults to None.
            rel (Var): The rel attribute of the link. Defaults to None.
            **props: The props of the component.

        Raises:
            ValueError: in case of missing children
            ValueError: in case of missing href

        Returns:
            Component: The link component
        """
        if href and not len(children):
            raise ValueError("Link without a child will not display")
        elif href is None and len(children):
            raise ValueError("Link without 'href' props will not work.")
        else:
            props.update({"href": href})
        if rel:
            props.update({"rel": rel})
        return super().create(*children, **props)
