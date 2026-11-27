"""A React Error Boundary component that catches unhandled frontend exceptions."""

from __future__ import annotations

from reflex_base.components.component import Component, field
from reflex_base.event import EventHandler, set_clipboard
from reflex_base.vars.base import Var
from reflex_base.vars.function import ArgsFunctionOperation
from reflex_base.vars.object import ObjectVar

from reflex_components_core.base.static_style import static_style
from reflex_components_core.datadisplay.logo import svg_logo
from reflex_components_core.el import a, button, div, h2, hr, p, pre, svg


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


# The look of the default fallback. Plain rules, not ``css`` props: the
# boundary wraps every app, and an app should not need Emotion to draw it.
_FALLBACK_CSS = (
    ".rx-error-boundary{height:100%;width:100%;position:absolute;"
    "background-color:#fff;color:#000;display:flex;align-items:center;"
    "justify-content:center}"
    ".rx-error-boundary-content{display:flex;flex-direction:column;gap:0.5rem;"
    "max-width:min(80ch, 90vw);border-radius:0.25rem;padding:1rem}"
    ".rx-error-boundary-heading{opacity:0.5;display:flex;gap:4vmin;"
    "align-items:center}"
    ".rx-error-boundary-title{font-size:5vmin;font-weight:bold}"
    ".rx-error-boundary-hint{opacity:0.75;margin-block:1rem}"
    ".rx-error-boundary-details{width:100%;"
    "background:color-mix(in srgb, currentColor 5%, transparent);"
    "max-height:15rem;overflow:auto;border-radius:0.4rem}"
    ".rx-error-boundary-details-body{padding:0.5rem}"
    ".rx-error-boundary-trace{word-break:break-word;white-space:pre-wrap}"
    ".rx-error-boundary-copy{padding:0.35rem 1.35rem;margin-block:0.5rem;"
    "margin-inline-start:auto;"
    "background:color-mix(in srgb, currentColor 15%, transparent);"
    "border-radius:0.4rem;width:fit-content}"
    ".rx-error-boundary-copy:hover"
    "{background:color-mix(in srgb, currentColor 25%, transparent)}"
    ".rx-error-boundary-copy:active"
    "{background:color-mix(in srgb, currentColor 35%, transparent)}"
    ".rx-error-boundary-rule{border-color:currentColor;opacity:0.25}"
    ".rx-error-boundary-credit{display:flex;align-items:baseline;"
    "justify-content:center;font-family:monospace;"
    "--default-font-family:monospace;gap:0.5rem}"
    ".rx-error-boundary-logo{fill:currentColor}"
)

_ERROR_DISPLAY: str = r"""event_args.error.name + ': ' + event_args.error.message + '\n' + event_args.error.stack"""


class ErrorBoundary(Component):
    """A React Error Boundary component that catches unhandled frontend exceptions."""

    library = "react-error-boundary@6.1.6"
    tag = "ErrorBoundary"

    on_error: EventHandler[on_error_spec] = field(
        doc="Fired when the boundary catches an error."
    )

    fallback_render: Var[Component] = field(
        doc="Rendered instead of the children when an error is caught."
    )

    @classmethod
    def create(cls, *children, **props):
        """Create an ErrorBoundary component.

        Args:
            *children: The children of the component.
            **props: The props of the component.

        Returns:
            The ErrorBoundary component.
        """
        from reflex.state import FrontendEventExceptionState

        if "on_error" not in props:
            props["on_error"] = FrontendEventExceptionState.handle_frontend_exception
        if "fallback_render" not in props:
            props["fallback_render"] = ArgsFunctionOperation.create(
                ("event_args",),
                Var.create(
                    div(
                        static_style("rx-error-boundary", _FALLBACK_CSS),
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
                                        "strokeWidth": "2",
                                        "strokeLinecap": "round",
                                        "strokeLinejoin": "round",
                                    },
                                ),
                                h2(
                                    "An error occurred while rendering this page.",
                                    class_name="rx-error-boundary-title",
                                ),
                                class_name="rx-error-boundary-heading",
                            ),
                            p(
                                "This is an error with the application itself. Refreshing the page might help.",
                                class_name="rx-error-boundary-hint",
                            ),
                            div(
                                div(
                                    pre(
                                        Var(_js_expr=_ERROR_DISPLAY),
                                        class_name="rx-error-boundary-trace",
                                    ),
                                    class_name="rx-error-boundary-details-body",
                                ),
                                class_name="rx-error-boundary-details",
                            ),
                            button(
                                "Copy",
                                on_click=set_clipboard(Var(_js_expr=_ERROR_DISPLAY)),
                                class_name="rx-error-boundary-copy",
                            ),
                            hr(class_name="rx-error-boundary-rule"),
                            a(
                                div(
                                    "Built with ",
                                    svg_logo(
                                        None, class_name="rx-error-boundary-logo"
                                    ),
                                    class_name="rx-error-boundary-credit",
                                ),
                                href="https://reflex.dev",
                            ),
                            class_name="rx-error-boundary-content",
                        ),
                        class_name="rx-error-boundary",
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
