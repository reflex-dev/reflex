"""Display the title of the current page."""

from __future__ import annotations

from reflex.components.base.bare import Bare
from reflex.components.el import elements


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


class Meta(elements.Meta):
    """A component that displays metadata for the current page."""

    # The description of character encoding.
    char_set: str | None = None

    # The value of meta.
    content: str | None = None

    # The name of metadata.
    name: str | None = None

    # The type of metadata value.
    property: str | None = None

    # The type of metadata value.
    http_equiv: str | None = None


class Description(elements.Meta):
    """A component that displays the title of the current page."""

    # The type of the description.
    name: str | None = "description"


class Image(elements.Meta):
    """A component that displays the title of the current page."""

    # The type of the image.
    property: str | None = "og:image"
