"""A link component."""


from reflex.components.component import Component
from reflex.components.libs.chakra import ChakraComponent
from reflex.components.navigation.nextlink import NextLink
from reflex.utils import imports
from reflex.vars import BaseVar, Var

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
    as_: Var[str] = BaseVar.create(value="{NextLink}", _var_is_local=False)  # type: ignore

    # If true, the link will open in new tab.
    is_external: Var[bool]

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
