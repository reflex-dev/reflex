"""A React Error Boundary component that catches unhandled frontend exceptions."""

from __future__ import annotations

from reflex.components.component import Component
from reflex.components.datadisplay.logo import svg_logo
from reflex.components.el import a, button, details, div, h2, hr, p, pre, summary
from reflex.event import EventHandler, set_clipboard
from reflex.state import FrontendEventExceptionState
from reflex.vars.base import Var
from reflex.vars.function import ArgsFunctionOperation
from reflex.vars.object import ObjectVar


def on_error_spec(
    error: ObjectVar[dict[str, str]], info: ObjectVar[dict[str, str]]
) -> tuple[Var[str], Var[str]]:
    """The spec for the on_error event handler.

    Args:
        error: The error message.
        info: Additional information about the error.

    Returns:
        The arguments for the event handler.
    """
    return (
        error.name.to(str) + ": " + error.message.to(str) + "\n" + error.stack.to(str),
        info.componentStack,
    )


_ERROR_DISPLAY: str = r"""event_args.error.name + ': ' + event_args.error.message + '\n' + event_args.error.stack"""


class ErrorBoundary(Component):
    """A React Error Boundary component that catches unhandled frontend exceptions."""

    library = "react-error-boundary@6.0.0"
    tag = "ErrorBoundary"

    # Fired when the boundary catches an error.
    on_error: EventHandler[on_error_spec]

    # Rendered instead of the children when an error is caught.
    fallback_render: Var[Component]

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
        if "fallback_render" not in props:
            props["fallback_render"] = ArgsFunctionOperation.create(
                ("event_args",),
                Var.create(
                    div(
                        div(
                            div(
                                h2(
                                    "An error occurred while rendering this page.",
                                    font_size="1.25rem",
                                    font_weight="bold",
                                ),
                                p(
                                    "This is an error with the application itself.",
                                    opacity="0.75",
                                ),
                                details(
                                    summary("Error message", padding="0.5rem"),
                                    div(
                                        div(
                                            pre(
                                                Var(_js_expr=_ERROR_DISPLAY),
                                            ),
                                            padding="0.5rem",
                                            width="fit-content",
                                        ),
                                        width="100%",
                                        max_height="50vh",
                                        overflow="auto",
                                        background="#000",
                                        color="#fff",
                                        border_radius="0.25rem",
                                    ),
                                    button(
                                        "Copy",
                                        on_click=set_clipboard(
                                            Var(_js_expr=_ERROR_DISPLAY)
                                        ),
                                        padding="0.35rem 0.75rem",
                                        margin="0.5rem",
                                        background="#fff",
                                        color="#000",
                                        border="1px solid #000",
                                        border_radius="0.25rem",
                                        font_weight="bold",
                                    ),
                                ),
                                display="flex",
                                flex_direction="column",
                                gap="1rem",
                                max_width="50ch",
                                border="1px solid #888888",
                                border_radius="0.25rem",
                                padding="1rem",
                            ),
                            hr(
                                border_color="currentColor",
                                opacity="0.25",
                            ),
                            a(
                                div(
                                    "Built with ",
                                    svg_logo("currentColor"),
                                    display="flex",
                                    align_items="baseline",
                                    justify_content="center",
                                    font_family="monospace",
                                    gap="0.5rem",
                                ),
                                href="https://reflex.dev",
                            ),
                            display="flex",
                            flex_direction="column",
                            gap="1rem",
                        ),
                        height="100%",
                        width="100%",
                        position="absolute",
                        display="flex",
                        align_items="center",
                        justify_content="center",
                    )
                ),
                _var_type=Component,
            )
        else:
            props["fallback_render"] = ArgsFunctionOperation.create(
                ("event_args",),
                props["fallback_render"],
                _var_type=Component,
            )
        return super().create(*children, **props)


error_boundary = ErrorBoundary.create
