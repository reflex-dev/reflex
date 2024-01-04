"""Base for all ArkUI components."""
from reflex.components.component import Component
from reflex.vars import Var


class BaseArkUIComponent(Component):
    """Base component for ArkUI."""

    library = "@ark-ui/react@^1.2.1"

    as_child: Var[bool]
