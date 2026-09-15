"""A tag with no tag."""

import dataclasses
from collections.abc import Sequence
from typing import Any

from reflex_base.components.tags import Tag
from reflex_base.utils import format


@dataclasses.dataclass(frozen=True, kw_only=True)
class Tagless(Tag):
    """A tag with no tag."""

    # The inner contents of the tag.
    contents: str

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

    def __iter__(self):
        """Iterate over the tag's fields.

        Yields:
            tuple[str, Any]: The field name and value.
        """
        yield "contents", self.contents

    def render(self, children: Sequence[Any]) -> dict[str, Any]:
        """Render the tag into the dictionary consumed by the templates.

        Args:
            children: The already rendered children.

        Returns:
            The rendered tag dictionary.
        """
        return dict(self)
