"""A bare component."""
from __future__ import annotations

from typing import Any

from reflex.components.component import Component
from reflex.components.tags import Tag
from reflex.components.tags.tagless import Tagless
from reflex.vars import Var


class Bare(Component):
    """A component with no tag."""

    contents: Var[str]

    @classmethod
    def create(cls, contents: Any) -> Component:
        """Create a Bare component, with no tag.

        Args:
            contents: The contents of the component.

        Returns:
            The component.
        """
        if not isinstance(contents, Var):
            contents = str(contents)
        else:
            contents = contents.to(str)
        return cls(contents=contents)  # type: ignore

    def _render(self) -> Tag:
        return Tagless(contents=str(self.contents))
