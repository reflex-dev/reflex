"""Banner components."""

from __future__ import annotations

from reflex import constants
from reflex.components.base.fragment import Fragment
from reflex.components.component import Component
from reflex.components.core.cond import cond
from reflex.components.el.elements.typography import Div
from reflex.components.lucide.icon import Icon
from reflex.components.radix.themes.components.dialog import (
    DialogContent,
    DialogRoot,
    DialogTitle,
)
from reflex.components.radix.themes.layout.flex import Flex
from reflex.components.radix.themes.typography.text import Text
from reflex.components.sonner.toast import ToastProps, toast_ref
from reflex.constants import Dirs, Hooks, Imports
from reflex.constants.compiler import CompileVars
from reflex.environment import environment
from reflex.utils.imports import ImportVar
from reflex.vars import VarData
from reflex.vars.base import LiteralVar, Var
from reflex.vars.function import FunctionStringVar
from reflex.vars.number import BooleanVar
from reflex.vars.sequence import LiteralArrayVar

connect_error_var_data: VarData = VarData(
    imports=Imports.EVENTS,
    hooks={Hooks.EVENTS: None},
)

connect_errors = Var(
    _js_expr=CompileVars.CONNECT_ERROR, _var_data=connect_error_var_data
)

connection_error = Var(
    _js_expr="((connectErrors.length > 0) ? connectErrors[connectErrors.length - 1].message : '')",
    _var_data=connect_error_var_data,
)

connection_errors_count = Var(
    _js_expr="connectErrors.length", _var_data=connect_error_var_data
)

has_connection_errors = Var(
    _js_expr="(connectErrors.length > 0)", _var_data=connect_error_var_data
).to(BooleanVar)

has_too_many_connection_errors = Var(
    _js_expr="(connectErrors.length >= 2)", _var_data=connect_error_var_data
).to(BooleanVar)


class WebsocketTargetURL(Var):
    """A component that renders the websocket target URL."""

    @classmethod
    def create(cls) -> Var:
        """Create a websocket target URL component.

        Returns:
            The websocket target URL component.
        """
        return Var(
            _js_expr="getBackendURL(env.EVENT).href",
            _var_data=VarData(
                imports={
                    "$/env.json": [ImportVar(tag="env", is_default=True)],
                    f"$/{Dirs.STATE_PATH}": [ImportVar(tag="getBackendURL")],
                },
            ),
            _var_type=WebsocketTargetURL,
        )


def default_connection_error() -> list[str | Var | Component]:
    """Get the default connection error message.

    Returns:
        The default connection error message.
    """
    return [
        "Cannot connect to server: ",
        connection_error,
        ". Check if server is reachable at ",
        WebsocketTargetURL.create(),
    ]


class ConnectionToaster(Fragment):
    """A connection toaster component."""

    def add_hooks(self) -> list[str | Var]:
        """Add the hooks for the connection toaster.

        Returns:
            The hooks for the connection toaster.
        """
        toast_id = "websocket-error"
        target_url = WebsocketTargetURL.create()
        props = ToastProps(
            description=LiteralVar.create(
                f"Check if server is reachable at {target_url}",
            ),
            close_button=True,
            duration=120000,
            id=toast_id,
        )  # pyright: ignore [reportCallIssue]

        if environment.REFLEX_DOES_BACKEND_COLD_START.get():
            loading_message = Var.create("Backend is starting.")
            backend_is_loading_toast_var = Var(
                f"toast?.loading({loading_message!s}, {{...toast_props, description: '', closeButton: false, onDismiss: () => setUserDismissed(true)}},)"
            )
            backend_is_not_responding = Var.create("Backend is not responding.")
            backend_is_down_toast_var = Var(
                f"toast?.error({backend_is_not_responding!s}, {{...toast_props, description: '', onDismiss: () => setUserDismissed(true)}},)"
            )
            toast_var = Var(
                f"""
if (waitedForBackend) {{
    {backend_is_down_toast_var!s}
}} else {{
    {backend_is_loading_toast_var!s};
}}
setTimeout(() => {{
    if ({has_too_many_connection_errors!s}) {{
        setWaitedForBackend(true);
    }}
}}, {environment.REFLEX_BACKEND_COLD_START_TIMEOUT.get() * 1000});
"""
            )
        else:
            loading_message = Var.create(
                f"Cannot connect to server: {connection_error}."
            )
            toast_var = Var(
                f"toast?.error({loading_message!s}, {{...toast_props, onDismiss: () => setUserDismissed(true)}},)"
            )

        individual_hooks = [
            Var(f"const toast = {toast_ref};"),
            f"const toast_props = {LiteralVar.create(props)!s};",
            "const [userDismissed, setUserDismissed] = useState(false);",
            "const [waitedForBackend, setWaitedForBackend] = useState(false);",
            FunctionStringVar(
                "useEffect",
                _var_data=VarData(
                    imports={
                        "react": ("useEffect", "useState"),
                        **(
                            dict(var_data.imports)
                            if (var_data := target_url._get_all_var_data()) is not None
                            else {}
                        ),
                    }
                ),
            ).call(
                # TODO: This breaks the assumption that Vars are JS expressions
                Var(
                    _js_expr=f"""
() => {{
    if ({has_too_many_connection_errors!s}) {{
        if (!userDismissed) {{
            {toast_var!s}
        }}
    }} else {{
        toast?.dismiss("{toast_id}");
        setUserDismissed(false);  // after reconnection reset dismissed state
    }}
}}
"""
                ),
                LiteralArrayVar.create([connect_errors, Var("waitedForBackend")]),
            ),
        ]

        return [
            Hooks.EVENTS,
            *individual_hooks,
        ]

    @classmethod
    def create(cls, *children, **props) -> Component:
        """Create a connection toaster component.

        Args:
            *children: The children of the component.
            **props: The properties of the component.

        Returns:
            The connection toaster component.
        """
        return super().create(*children, **props)


class ConnectionBanner(Component):
    """A connection banner component."""

    @classmethod
    def create(cls, comp: Component | None = None) -> Component:
        """Create a connection banner component.

        Args:
            comp: The component to render when there's a server connection error.

        Returns:
            The connection banner component.
        """
        if not comp:
            comp = Flex.create(
                Text.create(
                    *default_connection_error(),
                    color="black",
                    size="4",
                ),
                justify="center",
                background_color="crimson",
                width="100vw",
                padding="5px",
                position="fixed",
            )

        return cond(has_connection_errors, comp)


class ConnectionModal(Component):
    """A connection status modal window."""

    @classmethod
    def create(cls, comp: Component | None = None) -> Component:
        """Create a connection banner component.

        Args:
            comp: The component to render when there's a server connection error.

        Returns:
            The connection banner component.
        """
        if not comp:
            comp = Text.create(*default_connection_error())
        return cond(
            has_too_many_connection_errors,
            DialogRoot.create(
                DialogContent.create(
                    DialogTitle.create("Connection Error"),
                    comp,
                ),
                open=has_too_many_connection_errors,
                z_index=9999,
            ),
        )


class WifiOffPulse(Icon):
    """A wifi_off icon with an animated opacity pulse."""

    @classmethod
    def create(cls, *children, **props) -> Icon:
        """Create a wifi_off icon with an animated opacity pulse.

        Args:
            *children: The children of the component.
            **props: The properties of the component.

        Returns:
            The icon component with default props applied.
        """
        pulse_var = Var(r"keyframes({ from: { opacity: 0 }, to: { opacity: 1 } })").to(
            str
        )
        return super().create(
            "wifi_off",
            color=props.pop("color", "crimson"),
            size=props.pop("size", 32),
            z_index=props.pop("z_index", 9999),
            position=props.pop("position", "fixed"),
            bottom=props.pop("bottom", "33px"),
            right=props.pop("right", "33px"),
            animation=LiteralVar.create(f"{pulse_var} 1s infinite"),
            **props,
        )

    def add_imports(self) -> dict[str, str | ImportVar | list[str | ImportVar]]:
        """Add imports for the WifiOffPulse component.

        Returns:
            The import dict.
        """
        return {"@emotion/react": [ImportVar(tag="keyframes")]}


class ConnectionPulser(Div):
    """A connection pulser component."""

    @classmethod
    def create(cls, **props) -> Component:
        """Create a connection pulser component.

        Args:
            **props: The properties of the component.

        Returns:
            The connection pulser component.
        """
        return super().create(
            cond(
                has_connection_errors,
                WifiOffPulse.create(**props),
            ),
            title=f"Connection Error: {connection_error}",
            position="fixed",
            width="100vw",
            height="0",
        )


class BackendDisabled(Div):
    """A component that displays a message when the backend is disabled."""

    @classmethod
    def create(cls, **props) -> Component:
        """Create a backend disabled component.

        Args:
            **props: The properties of the component.

        Returns:
            The backend disabled component.
        """
        import reflex as rx

        is_backend_disabled = Var(
            "backendDisabled",
            _var_type=bool,
            _var_data=VarData(
                hooks={
                    "const [backendDisabled, setBackendDisabled] = useState(false);": None,
                    "useEffect(() => { setBackendDisabled(isBackendDisabled()); }, []);": None,
                },
                imports={
                    f"$/{constants.Dirs.STATE_PATH}": [
                        ImportVar(tag="isBackendDisabled")
                    ],
                },
            ),
        )

        return super().create(
            rx.cond(
                is_backend_disabled,
                rx.box(
                    rx.el.link(
                        rel="preconnect",
                        href="https://fonts.googleapis.com",
                    ),
                    rx.el.link(
                        rel="preconnect",
                        href="https://fonts.gstatic.com",
                        crossorigin="",
                    ),
                    rx.el.link(
                        href="https://fonts.googleapis.com/css2?family=Instrument+Sans:ital,wght@0,500;0,600&display=swap",
                        rel="stylesheet",
                    ),
                    rx.box(
                        rx.vstack(
                            rx.text(
                                "This app is paused",
                                font_size="1.5rem",
                                font_weight="600",
                                line_height="1.25rem",
                                letter_spacing="-0.0375rem",
                            ),
                            rx.hstack(
                                rx.el.svg(
                                    rx.el.path(
                                        d="M6.90816 1.34341C7.61776 1.10786 8.38256 1.10786 9.09216 1.34341C9.7989 1.57799 10.3538 2.13435 10.9112 2.91605C11.4668 3.69515 12.0807 4.78145 12.872 6.18175L12.9031 6.23672C13.6946 7.63721 14.3085 8.72348 14.6911 9.60441C15.0755 10.4896 15.267 11.2539 15.1142 11.9881C14.9604 12.7275 14.5811 13.3997 14.0287 13.9079C13.4776 14.4147 12.7273 14.6286 11.7826 14.7313C10.8432 14.8334 9.6143 14.8334 8.0327 14.8334H7.9677C6.38604 14.8334 5.15719 14.8334 4.21778 14.7313C3.27301 14.6286 2.52269 14.4147 1.97164 13.9079C1.41924 13.3997 1.03995 12.7275 0.88613 11.9881C0.733363 11.2539 0.92483 10.4896 1.30926 9.60441C1.69184 8.72348 2.30573 7.63721 3.09722 6.23671L3.12828 6.18175C3.91964 4.78146 4.53355 3.69515 5.08914 2.91605C5.64658 2.13435 6.20146 1.57799 6.90816 1.34341ZM7.3335 11.3334C7.3335 10.9652 7.63063 10.6667 7.99716 10.6667H8.00316C8.3697 10.6667 8.66683 10.9652 8.66683 11.3334C8.66683 11.7016 8.3697 12.0001 8.00316 12.0001H7.99716C7.63063 12.0001 7.3335 11.7016 7.3335 11.3334ZM7.3335 8.66675C7.3335 9.03495 7.63196 9.33341 8.00016 9.33341C8.36836 9.33341 8.66683 9.03495 8.66683 8.66675V6.00008C8.66683 5.63189 8.36836 5.33341 8.00016 5.33341C7.63196 5.33341 7.3335 5.63189 7.3335 6.00008V8.66675Z",
                                        fill_rule="evenodd",
                                        clip_rule="evenodd",
                                        fill=rx.color("amber", 11),
                                    ),
                                    width="16",
                                    height="16",
                                    viewBox="0 0 16 16",
                                    fill="none",
                                    xmlns="http://www.w3.org/2000/svg",
                                    margin_top="0.125rem",
                                    flex_shrink="0",
                                ),
                                rx.text(
                                    "If you are the owner of this app, visit ",
                                    rx.link(
                                        "Reflex Cloud",
                                        color=rx.color("amber", 11),
                                        underline="always",
                                        _hover={
                                            "color": rx.color("amber", 11),
                                            "text_decoration_color": rx.color(
                                                "amber", 11
                                            ),
                                        },
                                        text_decoration_color=rx.color("amber", 10),
                                        href="https://cloud.reflex.dev/",
                                        font_weight="600",
                                        is_external=True,
                                    ),
                                    " for more information on how to resume your app.",
                                    font_size="0.875rem",
                                    font_weight="500",
                                    line_height="1.25rem",
                                    letter_spacing="-0.01094rem",
                                    color=rx.color("amber", 11),
                                ),
                                align="start",
                                gap="0.625rem",
                                border_radius="0.75rem",
                                border_width="1px",
                                border_color=rx.color("amber", 5),
                                background_color=rx.color("amber", 3),
                                padding="0.625rem",
                            ),
                            rx.link(
                                rx.el.button(
                                    "Resume app",
                                    color="rgba(252, 252, 253, 1)",
                                    font_size="0.875rem",
                                    font_weight="600",
                                    line_height="1.25rem",
                                    letter_spacing="-0.01094rem",
                                    height="2.5rem",
                                    padding="0rem 0.75rem",
                                    width="100%",
                                    border_radius="0.75rem",
                                    background=f"linear-gradient(180deg, {rx.color('violet', 9)} 0%, {rx.color('violet', 10)} 100%)",
                                    _hover={
                                        "background": f"linear-gradient(180deg, {rx.color('violet', 10)} 0%, {rx.color('violet', 10)} 100%)",
                                    },
                                ),
                                width="100%",
                                underline="none",
                                href="https://cloud.reflex.dev/",
                                is_external=True,
                            ),
                            gap="1rem",
                        ),
                        font_family='"Instrument Sans", "Helvetica", "Arial", sans-serif',
                        position="fixed",
                        top="50%",
                        left="50%",
                        transform="translate(-50%, -50%)",
                        width="60ch",
                        max_width="90vw",
                        border_radius="0.75rem",
                        border_width="1px",
                        border_color=rx.color("slate", 4),
                        padding="1.5rem",
                        background_color=rx.color("slate", 1),
                        box_shadow="0px 2px 5px 0px light-dark(rgba(28, 32, 36, 0.03), rgba(0, 0, 0, 0.00))",
                    ),
                    position="fixed",
                    z_index=9999,
                    backdrop_filter="grayscale(1) blur(5px)",
                    width="100dvw",
                    height="100dvh",
                ),
            )
        )


connection_banner = ConnectionBanner.create
connection_modal = ConnectionModal.create
connection_toaster = ConnectionToaster.create
connection_pulser = ConnectionPulser.create
backend_disabled = BackendDisabled.create
