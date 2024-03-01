"""A link component."""
from typing import Optional

from reflex.components.chakra import ChakraComponent
from reflex.components.component import Component
from reflex.components.next.link import NextLink
from reflex.utils import imports
from reflex.vars import BaseVar, Var

next_link = NextLink.create()


class Link(ChakraComponent):
    """Link to another page."""

    tag: str = "Link"

    # The rel.
    rel: Optional[Var[str]] = None

    # The page to link to.
    href: Optional[Var[str]] = None

    # The text to display.
    text: Optional[Var[str]] = None

    # What the link renders to.
    as_: Var[str] = BaseVar.create(value="{NextLink}", _var_is_local=False)  # type: ignore

    # If true, the link will open in new tab.
    is_external: Optional[Var[bool]] = None

    def _get_imports(self) -> imports.ImportDict:
        return {**super()._get_imports(), **next_link._get_imports()}

    @classmethod
    def create(cls, *children, **props) -> Component:
        """Create a Link component.

        Args:
            *children: The children of the component.
            **props: The props of the component.

        Raises:
            ValueError: in case of missing children

        Returns:
            Component: The link component
        """
        if props.get("href") is not None:
            if not len(children):
                raise ValueError("Link without a child will not display")
        else:
            # Don't use a NextLink if there is no href.
            props["as_"] = ""
        return super().create(*children, **props)
