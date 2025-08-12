"""Base class definition for raw HTML elements."""

from typing import ClassVar

from reflex.components.component import Component


class Element(Component):
    """The base class for all raw HTML elements."""

    _is_tag_in_global_scope: ClassVar[bool] = True

    def __eq__(self, other: object):
        """Two elements are equal if they have the same tag.

        Args:
            other: The other element.

        Returns:
            True if the elements have the same tag, False otherwise.
        """
        return isinstance(other, Element) and self.tag == other.tag
