"""Tag to conditionally match cases."""

import dataclasses
from collections.abc import Sequence
from typing import Any

from reflex.components.tags.tag import Tag
from reflex.vars.base import Var


@dataclasses.dataclass(frozen=True)
class MatchTag(Tag):
    """A match tag."""

    # The condition to determine which case to match.
    cond: Var[Any] = dataclasses.field(default_factory=lambda: Var.create(True))

    # The list of match cases to be matched.
    match_cases: Sequence[Any] = dataclasses.field(default_factory=list)

    # The catchall case to match.
    default: Any = dataclasses.field(default=Var.create(None))
