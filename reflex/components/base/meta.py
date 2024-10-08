"""Display the title of the current page."""

from __future__ import annotations

from typing import Optional

from reflex.components.base.bare import Bare
from reflex.components.component import Component


class Title(Component):
    """A component that displays the title of the current page."""

    tag = "title"

    def render(self) -> dict:
        """Render the title component.

        Raises:
            ValueError: If the title is not a single string.

        Returns:
            The rendered title component.
        """
        # Make sure the title is a single string.
        if len(self.children) != 1 or not isinstance(self.children[0], Bare):
            raise ValueError("Title must be a single string.")
        return super().render()


class Meta(Component):
    """A component that displays metadata for the current page."""

    tag = "meta"

    # The description of character encoding.
    char_set: Optional[str] = None

    # The value of meta.
    content: Optional[str] = None

    # The name of metadata.
    name: Optional[str] = None

    # The type of metadata value.
    property: Optional[str] = None

    # The type of metadata value.
    http_equiv: Optional[str] = None


class Description(Meta):
    """A component that displays the title of the current page."""

    # The type of the description.
    name: str = "description"


class Image(Meta):
    """A component that displays the title of the current page."""

    # The type of the image.
    property: str = "og:image"
