"""Tag to conditionally match cases."""

import dataclasses
from collections.abc import Iterator, Mapping, Sequence
from typing import Any

from reflex.components.tags.tag import Tag


@dataclasses.dataclass(frozen=True, kw_only=True)
class MatchTag(Tag):
    """A match tag."""

    # The condition to determine which case to match.
    cond: str

    # The list of match cases to be matched.
    match_cases: Sequence[tuple[Sequence[str], Mapping]]

    # The catchall case to match.
    default: Any

    def __iter__(self) -> Iterator[tuple[str, Any]]:
        """Iterate over the tag's attributes.

        Yields:
            An iterator over the tag's attributes.
        """
        yield ("cond", self.cond)
        yield ("match_cases", self.match_cases)
        yield ("default", self.default)
