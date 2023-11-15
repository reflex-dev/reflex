"""Base class definition for raw HTML elements."""

from typing import Dict

from nextpy.components.component import Component


class Element(Component):
    """The base class for all raw HTML elements.

    The key difference between `Element` and `Component` is that elements do not
    use Chakra's `sx` prop, instead passing styles directly to the React style
    prop.
    """

    def render(self) -> Dict:
        """Render the element.

        Returns:
            The code to render the element.
        """
        tag = self._render()
        return dict(
            tag.add_props(
                **self.event_triggers,
                key=self.key,
                id=self.id,
                style=self.style,
                class_name=self.class_name,
                **self.custom_attrs,
            ).set(
                contents=str(tag.contents),
                children=[child.render() for child in self.children],
                props=tag.format_props(),
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
