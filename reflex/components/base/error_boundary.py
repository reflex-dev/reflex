"""A React Error Boundary component that catches unhandled frontend exceptions."""

from __future__ import annotations

from reflex.components.component import Component
from reflex.components.datadisplay.logo import svg_logo
from reflex.components.el import a, button, div, h2, hr, p, pre, svg
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
                                svg(
                                    svg.circle(cx="12", cy="12", r="10"),
                                    svg.path(d="M16 16s-1.5-2-4-2-4 2-4 2"),
                                    svg.line(x1="9", x2="9.01", y1="9", y2="9"),
                                    svg.line(x1="15", x2="15.01", y1="9", y2="9"),
                                    xmlns="http://www.w3.org/2000/svg",
                                    width="25vmin",
                                    view_box="0 0 24 24",
                                    class_name="lucide lucide-frown-icon lucide-frown",
                                    custom_attrs={
                                        "fill": "none",
                                        "stroke": "currentColor",
                                        "stroke-width": "2",
                                        "stroke-linecap": "round",
                                        "stroke-linejoin": "round",
                                    },
                                ),
                                h2(
                                    "An error occurred while rendering this page.",
                                    font_size="5vmin",
                                    font_weight="bold",
                                ),
                                opacity="0.5",
                                display="flex",
                                gap="4vmin",
                                align_items="center",
                            ),
                            p(
                                "This is an error with the application itself. Refreshing the page might help.",
                                opacity="0.75",
                                margin_block="1rem",
                            ),
                            div(
                                div(
                                    pre(
                                        Var(_js_expr=_ERROR_DISPLAY),
                                        word_break="break-word",
                                        white_space="pre-wrap",
                                    ),
                                    padding="0.5rem",
                                ),
                                width="100%",
                                background="color-mix(in srgb, currentColor 5%, transparent)",
                                max_height="15rem",
                                overflow="auto",
                                border_radius="0.4rem",
                            ),
                            button(
                                "Copy",
                                on_click=set_clipboard(Var(_js_expr=_ERROR_DISPLAY)),
                                padding="0.35rem 1.35rem",
                                margin_block="0.5rem",
                                margin_inline_start="auto",
                                background="color-mix(in srgb, currentColor 15%, transparent)",
                                border_radius="0.4rem",
                                width="fit-content",
                                _hover={
                                    "background": "color-mix(in srgb, currentColor 25%, transparent)"
                                },
                                _active={
                                    "background": "color-mix(in srgb, currentColor 35%, transparent)"
                                },
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
                            gap="0.5rem",
                            max_width="min(80ch, 90vw)",
                            border_radius="0.25rem",
                            padding="1rem",
                        ),
                        height="100%",
                        width="100%",
                        position="absolute",
                        background_color="#fff",
                        color="#000",
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
