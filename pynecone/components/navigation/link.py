"""A link component."""

from pynecone.components.component import Component
from pynecone.components.libs.chakra import ChakraComponent
from pynecone.components.navigation.nextlink import NextLink
from pynecone.var import Var


class Link(ChakraComponent):
    """Component the provides a link."""

    tag = "Link"

    # The rel.
    rel: Var[str]

    # The page to link to.
    href: Var[str]

    # The text to display.
    text: Var[str]

    # If true, the link will open in new tab.
    is_external: Var[bool]

    @classmethod
    def create(cls, *children, **props) -> Component:
        """Create a NextJS link component, wrapping a Chakra link component.

        Args:
            *children: The children to pass to the component.
            **props: The attributes to pass to the component.

        Returns:
            The component.
        """
        kwargs = {}
        if "href" in props:
            kwargs["href"] = props.pop("href")
        else:
            kwargs["href"] = "#"
        return NextLink.create(super().create(*children, **props), **kwargs)
