"""Base class definition for raw HTML elements."""

from typing import ClassVar

from reflex_base.components.component import Component


class Element(Component):
    """The base class for all raw HTML elements."""

    _is_tag_in_global_scope: ClassVar[bool] = True

    def __eq__(self, value: object):
        """Two elements are equal if they have the same tag.

        Args:
            value: The other element.

        Returns:
            True if the elements have the same tag, False otherwise.
        """
        return isinstance(value, Element) and self.tag == value.tag
