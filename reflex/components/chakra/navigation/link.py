"""A link component."""

from reflex.components.chakra import ChakraComponent
from reflex.components.component import Component
from reflex.components.next.link import NextLink
from reflex.ivars.base import ImmutableVar
from reflex.utils.imports import ImportDict
from reflex.vars import Var

next_link = NextLink.create()


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
    as_: Var[Component] = ImmutableVar(_var_name="NextLink", _var_type=Component)

    # If true, the link will open in new tab.
    is_external: Var[bool]

    def add_imports(self) -> ImportDict:
        """Add imports for the link component.

        Returns:
            The import dict.
        """
        return next_link._get_imports()  # type: ignore

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
