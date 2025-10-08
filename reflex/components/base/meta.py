"""Display the title of the current page."""

from __future__ import annotations

from reflex.components.base.bare import Bare
from reflex.components.el import elements
from reflex.components.el.elements.metadata import Meta as Meta  # for compatibility
from reflex.vars.base import Var


class Title(elements.Title):
    """A component that displays the title of the current page."""

    def render(self) -> dict:
        """Render the title component.

        Raises:
            ValueError: If the title is not a single string.

        Returns:
            The rendered title component.
        """
        # Make sure the title is a single string.
        if len(self.children) != 1 or not isinstance(self.children[0], Bare):
            msg = "Title must be a single string."
            raise ValueError(msg)
        return super().render()


class Description(elements.Meta):
    """A component that displays the title of the current page."""

    # The type of the description.
    name: Var[str] = Var.create("description")


class Image(elements.Meta):
    """A component that displays the title of the current page."""

    # The type of the image.
    property: Var[str] = Var.create("og:image")
