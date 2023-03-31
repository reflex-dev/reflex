"""Tag to conditionally render components."""

from typing import Any

from pynecone.components.tags.tag import Tag
from pynecone.var import Var


class CondTag(Tag):
    """A conditional tag."""

    # The condition to determine which component to render.
    cond: Var[Any]

    # The code to render if the condition is true.
    true_value: dict

    # The code to render if the condition is false.
    false_value: dict
