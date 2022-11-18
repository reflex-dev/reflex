"""A link component."""

from pynecone.components.component import Component
from pynecone.var import Var


class NextLinkLib(Component):
    """A component that inherits from next/link."""

    library = "next/link"


class NextLink(NextLinkLib):
    """Links are accessible elements used primarily for navigation. This component is styled to resemble a hyperlink and semantically renders an <a>."""

    tag = "NextLink"

    # The page to link to.
    href: Var[str]

    # Whether to pass the href prop to the child.
    pass_href: Var[bool] = True  # type: ignore
