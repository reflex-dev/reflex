"""A bare component."""

from __future__ import annotations

from typing import Any, Iterator

from reflex.components.component import Component
from reflex.components.tags import Tag
from reflex.components.tags.tagless import Tagless
from reflex.vars.base import Var


class Bare(Component):
    """A component with no tag."""

    contents: Var[Any]

    @classmethod
    def create(cls, contents: Any) -> Component:
        """Create a Bare component, with no tag.

        Args:
            contents: The contents of the component.

        Returns:
            The component.
        """
        if isinstance(contents, Var):
            return cls(contents=contents)
        else:
            contents = str(contents) if contents is not None else ""
        return cls(contents=contents)  # type: ignore

    def _render(self) -> Tag:
        if isinstance(self.contents, Var):
            return Tagless(contents=f"{{{str(self.contents)}}}")
        return Tagless(contents=str(self.contents))

    def _get_vars(self, include_children: bool = False) -> Iterator[Var]:
        """Walk all Vars used in this component.

        Args:
            include_children: Whether to include Vars from children.

        Yields:
            The contents if it is a Var, otherwise nothing.
        """
        yield self.contents
