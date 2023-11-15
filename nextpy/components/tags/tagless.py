"""A tag with no tag."""

from nextpy.components.tags import Tag
from nextpy.utils import format


class Tagless(Tag):
    """A tag with no tag."""

    def __str__(self) -> str:
        """Return the string representation of the tag.

        Returns:
            The string representation of the tag.
        """
        out = self.contents
        space = format.wrap(" ", "{")
        if len(self.contents) > 0 and self.contents[0] == " ":
            out = space + out
        if len(self.contents) > 0 and self.contents[-1] == " ":
            out = out + space
        return out
