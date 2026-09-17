"""Components with inheritance hierarchy.

This module tests:
- Props from parent classes appear in create() via MRO traversal
- Overridden props are not duplicated
- Multiple levels of inheritance
"""

from reflex_base.components.component import Component, field
from reflex_base.event import EventHandler, passthrough_event_spec
from reflex_base.vars.base import Var


class BaseWidget(Component):
    """A base widget with common props."""

    # Widget color.
    color: Var[str] = field(doc="The widget color.")

    # Whether the widget is disabled.
    disabled: Var[bool] = field(doc="Whether the widget is disabled.")


class InteractiveWidget(BaseWidget):
    """An interactive widget extending BaseWidget."""

    # The placeholder text.
    placeholder: Var[str] = field(doc="Placeholder text.")

    on_value_change: EventHandler[passthrough_event_spec(str)] = field(
        doc="Fired when value changes.",
    )


class FancyWidget(InteractiveWidget):
    """A fancy widget with extra styling, three levels deep."""

    # Border radius.
    border_radius: Var[str] = field(doc="The border radius.")
