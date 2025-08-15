"""Tag to conditionally render components."""

import dataclasses
from collections.abc import Iterator, Mapping
from typing import Any

from reflex.components.tags.tag import Tag


@dataclasses.dataclass(frozen=True, kw_only=True)
class CondTag(Tag):
    """A conditional tag."""

    # The condition to determine which component to render.
    cond_state: str

    # The code to render if the condition is true.
    true_value: Mapping

    # The code to render if the condition is false.
    false_value: Mapping | None = None

    def __iter__(self) -> Iterator[tuple[str, Any]]:
        """Iterate over the tag's attributes.

        Yields:
            An iterator over the tag's attributes.
        """
        yield ("cond_state", self.cond_state)
        yield ("true_value", self.true_value)
        yield ("false_value", self.false_value)
