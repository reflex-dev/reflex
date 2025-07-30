"""Tag to conditionally render components."""

import dataclasses
from collections.abc import Mapping
from typing import Any

from reflex.components.tags.tag import Tag
from reflex.vars.base import Var


@dataclasses.dataclass(frozen=True)
class CondTag(Tag):
    """A conditional tag."""

    # The condition to determine which component to render.
    cond: Var[Any] = dataclasses.field(default_factory=lambda: Var.create(True))

    # The code to render if the condition is true.
    true_value: Mapping = dataclasses.field(default_factory=dict)

    # The code to render if the condition is false.
    false_value: Mapping | None = None
