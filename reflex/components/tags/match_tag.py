"""Tag to conditionally render components."""

from typing import Any, Dict, Optional, List

from reflex.components.tags.tag import Tag
from reflex.vars import Var


class MatchTag(Tag):
    """A conditional tag."""

    # The condition to determine which component to render.
    cond: Any

    # The code to render if the condition is true.
    match_cases: List[Any]

    # The code to render if the condition is false.
    default: Any
