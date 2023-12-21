"""Tag to conditionally match cases."""

from typing import Any, List

from reflex.components.tags.tag import Tag
from reflex.vars import Var


class MatchTag(Tag):
    """A match tag."""

    # The condition to determine which case to match.
    cond: Var[Any]

    # The list of match cases to be matched.
    match_cases: List[Any]

    # The catchall case to match.
    default: Any
