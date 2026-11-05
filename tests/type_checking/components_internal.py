"""Props of `reflex_components_internal` components that must accept what callers pass."""

from reflex_base.event import call_function, event, set_value
from reflex_components_internal.components.base.input import input as ui_input

from reflex.state import State


class _InputState(State):
    @event
    def cleared(self) -> None: ...

    @event
    def cleared_to(self, value: str) -> None: ...


# The clear button fires these after clearing the field, like any `on_click`: a
# bound handler, a handler with its arguments, or an event spec.
ui_input(
    clear_events=[
        _InputState.cleared,
        _InputState.cleared_to(""),
        set_value("other", ""),
        call_function("() => {}"),
    ]
)
