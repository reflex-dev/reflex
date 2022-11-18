"""A tag with no tag."""

from pynecone import utils
from pynecone.components.tags import Tag


class Tagless(Tag):
    """A tag with no tag."""

    def __str__(self) -> str:
        """Return the string representation of the tag.

        Returns:
            The string representation of the tag.
        """
        out = self.contents
        space = utils.wrap(" ", "{")
        if len(self.contents) > 0 and self.contents[0] == " ":
            out = space + out
        if len(self.contents) > 0 and self.contents[-1] == " ":
            out = out + space
        return out
