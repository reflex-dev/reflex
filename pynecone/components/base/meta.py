"""Display the title of the current page."""

from pynecone.components.base.bare import Bare
from pynecone.components.component import Component
from pynecone.components.tags import Tag


class Title(Component):
    """A component that displays the title of the current page."""

    def _render(self) -> Tag:
        return Tag(name="title")

    def render(self) -> str:
        """Render the title component.

        Returns:
            The rendered title component.
        """
        tag = self._render()
        # Make sure the title is a single string.
        assert len(self.children) == 1 and isinstance(
            self.children[0], Bare
        ), "Title must be a single string."
        return str(tag.set(contents=str(self.children[0].contents)))

class Meta(Component):
    """A component that displays metadata for the current page."""
    def render(self) -> Tag:
        tag = self._render()
        return str(tag.set())

class Description(Meta):
    """A component that displays the title of the current page."""

    content: str = "" 

    name: str = "description"

    def _render(self) -> Tag:
        return Tag(name="meta")

class Image(Meta):
    """A component that displays the title of the current page."""

    content: str = "" 

    property: str = "og:image"

    def _render(self) -> Tag:
        return Tag(name="meta")

