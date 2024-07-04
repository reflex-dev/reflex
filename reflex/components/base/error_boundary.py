"""A React Error Boundary component that catches unhandled frontend exceptions."""

from __future__ import annotations

from typing import List

from reflex.compiler.compiler import _compile_component
from reflex.components.component import Component
from reflex.components.el import div, p
from reflex.constants import Hooks, Imports
from reflex.event import EventChain, EventHandler
from reflex.utils.imports import ImportVar
from reflex.vars import Var


class ErrorBoundary(Component):
    """A React Error Boundary component that catches unhandled frontend exceptions."""

    library = "react-error-boundary"
    tag = "ErrorBoundary"

    # Fired when the boundary catches an error.
    on_error: EventHandler[lambda error, info: [error, info]] = Var.create_safe(  # type: ignore
        "logFrontendError", _var_is_string=False, _var_is_local=False
    ).to(EventChain)

    # Rendered instead of the children when an error is caught.
    Fallback_component: Var[Component] = Var.create_safe(
        "Fallback", _var_is_string=False, _var_is_local=False
    ).to(Component)

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
        return [Hooks.EVENTS, Hooks.FRONTEND_ERRORS]

    def add_custom_code(self) -> List[str]:
        """Add custom Javascript code into the page that contains this component.

        Custom code is inserted at module level, after any imports.

        Returns:
            The custom code to add.
        """
        fallback_container = div(
            p("Ooops...Unknown Reflex error has occured:"),
            p(
                Var.create("error.message", _var_is_local=False, _var_is_string=False),
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
