"""A link component."""

from typing import Optional

from reflex.components.component import Component
from reflex.vars import Var


class NextLink(Component):
    """Links are accessible elements used primarily for navigation. This component is styled to resemble a hyperlink and semantically renders an <a>."""

    library = "next/link"

    tag: str = "NextLink"

    is_default = True

    # The page to link to.
    href: Optional[Var[str]] = None

    # Whether to pass the href prop to the child.
    pass_href: Var[bool] = True  # type: ignore
