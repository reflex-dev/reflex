"""A React Error Boundary component that catches unhandled frontend exceptions."""

from reflex.components.component import Component

# from reflex.constants import Hooks
# import reflex as rx


class ErrorBoundary(Component):
    """A React Error Boundary component that catches unhandled frontend exceptions."""

    library = "react-error-boundary"
    tag = "ErrorBoundary"

    # fallback: rx.Var[Component] = rx.button("Reload Page", on_click=lambda: rx.event.call_script("window.location.reload()"))

    # on_error: rx.EventHandler[lambda error, info: [info]] = rx.EventHandler(fn=lambda error, info: [info], state_full_name="state")

    # def _get_events_hooks(self) -> dict[str, None]:
    #     """Get the hooks required by events referenced in this component.

    #     Returns:
    #         The hooks for the events.
    #     """
    #     return {Hooks.EVENTS: None}


error_boundary = ErrorBoundary.create
