"""Base class definition for raw HTML elements."""

from pynecone.components.component import Component
from pynecone.utils import path_ops


class Element(Component):
    """The base class for all raw HTML elements.

    The key difference between `Element` and `Component` is that elements do not
    use Chakra's `sx` prop, instead passing styles directly to the React style
    prop.
    """

    def render(self) -> str:
        """Render the element.

        Returns:
            The code to render the element.
        """
        tag = self._render()
        return str(
            tag.add_props(
                **self.event_triggers,
                key=self.key,
                id=self.id,
                style=self.style,
                class_name=self.class_name,
            ).set(
                contents=path_ops.join(
                    [str(tag.contents)] + [child.render() for child in self.children]
                ).strip(),
            )
        )

    def __eq__(self, other):
        """Two elements are equal if they have the same tag.

        Args:
            other: The other element.

        Returns:
            True if the elements have the same tag, False otherwise.
        """
        return isinstance(other, Element) and self.tag == other.tag
