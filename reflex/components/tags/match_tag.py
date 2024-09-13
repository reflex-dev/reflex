"""Tag to conditionally match cases."""

import dataclasses
from typing import Any, List

from reflex.components.tags.tag import Tag
from reflex.ivars.base import LiteralVar
from reflex.vars import Var


@dataclasses.dataclass()
class MatchTag(Tag):
    """A match tag."""

    # The condition to determine which case to match.
    cond: Var[Any] = dataclasses.field(default_factory=lambda: LiteralVar.create(True))

    # The list of match cases to be matched.
    match_cases: List[Any] = dataclasses.field(default_factory=list)

    # The catchall case to match.
    default: Any = dataclasses.field(default=LiteralVar.create(None))
