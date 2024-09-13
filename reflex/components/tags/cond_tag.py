"""Tag to conditionally render components."""

import dataclasses
from typing import Any, Dict, Optional

from reflex.components.tags.tag import Tag
from reflex.vars.base import Var


@dataclasses.dataclass()
class CondTag(Tag):
    """A conditional tag."""

    # The condition to determine which component to render.
    cond: Var[Any] = dataclasses.field(default_factory=lambda: Var.create(True))

    # The code to render if the condition is true.
    true_value: Dict = dataclasses.field(default_factory=dict)

    # The code to render if the condition is false.
    false_value: Optional[Dict] = None
