"""Display the title of the current page."""

from __future__ import annotations

from reflex_base.components.component import field
from reflex_base.vars.base import Var

from reflex_components_core.base.bare import Bare
from reflex_components_core.el import elements
from reflex_components_core.el.elements.metadata import (
    Meta as Meta,
)  # for compatibility


class Title(elements.Title):
    """A component that displays the title of the current page."""

    def render(self) -> dict:
        """Render the title component.

        Returns:
            The rendered title component.

        Raises:
            ValueError: If the title is not a single string.
        """
        # Make sure the title is a single string.
        if len(self.children) != 1 or not isinstance(self.children[0], Bare):
            msg = "Title must be a single string."
            raise ValueError(msg)
        return super().render()


class Description(elements.Meta):
    """A component that displays the title of the current page."""

    name: Var[str] = field(
        default=Var.create("description"), doc="The type of the description."
    )


class Image(elements.Meta):
    """A component that displays the title of the current page."""

    property: Var[str] = field(
        default=Var.create("og:image"), doc="The type of the image."
    )
