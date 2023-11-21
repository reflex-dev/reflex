"""A bare component."""
from __future__ import annotations

from typing import Any, Iterator

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
        if isinstance(contents, Var) and contents._var_data:
            contents = contents.to(str)
        else:
            contents = str(contents)
        return cls(contents=contents)  # type: ignore

    def _render(self) -> Tag:
        return Tagless(contents=str(self.contents))

    def _get_vars(self) -> Iterator[Var]:
        """Walk all Vars used in this component.

        Yields:
            The contents if it is a Var, otherwise nothing.
        """
        if isinstance(self.contents, Var):
            # Fast path for Bare text components.
            yield self.contents
