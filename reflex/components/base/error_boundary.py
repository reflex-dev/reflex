"""A React Error Boundary component that catches unhandled frontend exceptions."""

from __future__ import annotations

from typing import Dict, List, Tuple

from reflex.compiler.compiler import _compile_component
from reflex.components.component import Component
from reflex.components.el import div, p
from reflex.event import EventHandler
from reflex.state import FrontendEventExceptionState
from reflex.vars.base import Var


def on_error_spec(
    error: Var[Dict[str, str]], info: Var[Dict[str, str]]
) -> Tuple[Var[str], Var[str]]:
    """The spec for the on_error event handler.

    Args:
        error: The error message.
        info: Additional information about the error.

    Returns:
        The arguments for the event handler.
    """
    return (
        error.stack,
        info.componentStack,
    )


class ErrorBoundary(Component):
    """A React Error Boundary component that catches unhandled frontend exceptions."""

    library = "react-error-boundary"
    tag = "ErrorBoundary"

    # Fired when the boundary catches an error.
    on_error: EventHandler[on_error_spec]

    # Rendered instead of the children when an error is caught.
    Fallback_component: Var[Component] = Var(_js_expr="Fallback")._replace(
        _var_type=Component
    )

    def add_custom_code(self) -> List[str]:
        """Add custom Javascript code into the page that contains this component.

        Custom code is inserted at module level, after any imports.

        Returns:
            The custom code to add.
        """
        fallback_container = div(
            p("Ooops...Unknown Reflex error has occured:"),
            p(
                Var(_js_expr="error.message"),
                color="red",
            ),
            p("Please contact the support."),
        )

        compiled_fallback = _compile_component(fallback_container)

        return [
            f"""
                function Fallback({{ error, resetErrorBoundary }}) {{
                    return (
                        {compiled_fallback}
                    );
                }}
            """
        ]

    @classmethod
    def create(cls, *children, **props):
        """Create an ErrorBoundary component.

        Args:
            *children: The children of the component.
            **props: The props of the component.

        Returns:
            The ErrorBoundary component.
        """
        if "on_error" not in props:
            props["on_error"] = FrontendEventExceptionState.handle_frontend_exception
        return super().create(*children, **props)


error_boundary = ErrorBoundary.create
