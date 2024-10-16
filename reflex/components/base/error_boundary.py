"""A React Error Boundary component that catches unhandled frontend exceptions."""

from __future__ import annotations

from typing import Dict, List, Tuple

from reflex.compiler.compiler import _compile_component
from reflex.components.component import Component
from reflex.components.el import div, p
from reflex.constants import Hooks, Imports
from reflex.event import EventChain, EventHandler
from reflex.utils.imports import ImportVar
from reflex.vars.base import Var
from reflex.vars.function import FunctionVar


def on_error_spec(error: Var, info: Var[Dict[str, str]]) -> Tuple[Var[str]]:
    """The spec for the on_error event handler.

    Args:
        error: The error message.
        info: Additional information about the error.

    Returns:
        The arguments for the event handler.
    """
    return (info.componentStack,)


LOG_FRONTEND_ERROR = Var("logFrontendError").to(FunctionVar, EventChain)


class ErrorBoundary(Component):
    """A React Error Boundary component that catches unhandled frontend exceptions."""

    library = "react-error-boundary"
    tag = "ErrorBoundary"

    # Fired when the boundary catches an error.
    on_error: EventHandler[on_error_spec] = LOG_FRONTEND_ERROR  # type: ignore

    # Rendered instead of the children when an error is caught.
    Fallback_component: Var[Component] = Var(_js_expr="Fallback")._replace(
        _var_type=Component
    )

    def add_imports(self) -> dict[str, list[ImportVar]]:
        """Add imports for the component.

        Returns:
            The imports to add.
        """
        return Imports.EVENTS

    def add_hooks(self) -> List[str | Var]:
        """Add hooks for the component.

        Returns:
            The hooks to add.
        """
        return (
            [Hooks.EVENTS, Hooks.FRONTEND_ERRORS]
            if "on_error" not in self.event_triggers
            else []
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


error_boundary = ErrorBoundary.create
