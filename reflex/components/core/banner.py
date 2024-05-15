"""Banner components."""

from __future__ import annotations

from typing import Optional

from reflex.components.base.bare import Bare
from reflex.components.component import Component
from reflex.components.core.cond import cond
from reflex.components.el.elements.typography import Div
from reflex.components.lucide.icon import Icon
from reflex.components.radix.themes.components.dialog import (
    DialogContent,
    DialogRoot,
    DialogTitle,
)
from reflex.components.radix.themes.layout import Flex
from reflex.components.radix.themes.typography.text import Text
from reflex.components.sonner.toast import Toaster, ToastProps
from reflex.constants import Dirs, Hooks, Imports
from reflex.constants.compiler import CompileVars
from reflex.utils import imports
from reflex.utils.serializers import serialize
from reflex.vars import Var, VarData

connect_error_var_data: VarData = VarData(  # type: ignore
    imports=Imports.EVENTS,
    hooks={Hooks.EVENTS: None},
)

connect_errors: Var = Var.create_safe(
    value=CompileVars.CONNECT_ERROR,
    _var_is_local=True,
    _var_is_string=False,
)._replace(merge_var_data=connect_error_var_data)


connection_error: Var = Var.create_safe(
    value="(connectErrors.length > 0) ? connectErrors[connectErrors.length - 1].message : ''",
    _var_is_local=False,
    _var_is_string=False,
    _var_data=connect_error_var_data,
)

connection_errors_count: Var = Var.create_safe(
    value="connectErrors.length",
    _var_is_string=False,
    _var_is_local=False,
    _var_data=connect_error_var_data,
)

has_connection_errors: Var = Var.create_safe(
    value="connectErrors.length > 0",
    _var_is_string=False,
    _var_data=connect_error_var_data,
).to(bool)

has_too_many_connection_errors: Var = Var.create_safe(
    value="connectErrors.length >= 2",
    _var_is_string=False,
    _var_data=connect_error_var_data,
).to(bool)


class WebsocketTargetURL(Bare):
    """A component that renders the websocket target URL."""

    def _get_imports(self) -> imports.ImportDict:
        return {
            f"/{Dirs.STATE_PATH}": [imports.ImportVar(tag="getBackendURL")],
            "/env.json": [imports.ImportVar(tag="env", is_default=True)],
        }

    @classmethod
    def create(cls) -> Component:
        """Create a websocket target URL component.

        Returns:
            The websocket target URL component.
        """
        return super().create(contents="{getBackendURL(env.EVENT).href}")


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


class ConnectionToaster(Toaster):
    """A connection toaster component."""

    def add_imports(self) -> dict[str, list[str | imports.ImportVar]]:
        """Add the imports for the connection toaster.

        Returns:
            The imports for the connection toaster.
        """
        imports_ = {**Imports.EVENTS}  # type: ignore
        imports_["react"].append("useEffect")  # type: ignore # remove when 3248 is merged
        (imports_.setdefault(f"/{Dirs.STATE_PATH}", []).append("getBackendURL"))  # type: ignore
        imports_.setdefault("/env.json", []).append(
            imports.ImportVar(tag="env", is_default=True)
        )
        return imports_  # type: ignore

    def add_hooks(self) -> list[str]:
        """Add the hooks for the connection toaster.

        Returns:
            The hooks for the connection toaster.
        """
        util_hook = """const getLastMessage = (connectErrors) => {
    if (connectErrors.length > 0)
      return connectErrors[connectErrors.length - 1].message;
    else
        return '';
};"""
        props = ToastProps(
            description=f"Check if server is reachable at ${{getBackendURL(env.EVENT).href}}",
            id="websocket-error",
        )
        hook = Var.create(
            f"""useEffect(() => {{
    toast.error(
        `Cannot connect to server: ${{getLastMessage({connect_errors})}}.`, {serialize(props)},)
}}, [{connect_errors}]);"""
        )

        # can uncomment when 3248 is merged
        # hook._var_data = VarData.merge(
        #     connect_errors._var_data, VarData(imports={"react": ["useEffect"]})
        # )
        return [
            Hooks.EVENTS,
            util_hook,
            hook,
        ]


class ConnectionBanner(Component):
    """A connection banner component."""

    @classmethod
    def create(cls, comp: Optional[Component] = None) -> Component:
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
    def create(cls, comp: Optional[Component] = None) -> Component:
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
    def create(cls, **props) -> Component:
        """Create a wifi_off icon with an animated opacity pulse.

        Args:
            **props: The properties of the component.

        Returns:
            The icon component with default props applied.
        """
        return super().create(
            "wifi_off",
            color=props.pop("color", "crimson"),
            size=props.pop("size", 32),
            z_index=props.pop("z_index", 9999),
            position=props.pop("position", "fixed"),
            bottom=props.pop("botton", "30px"),
            right=props.pop("right", "30px"),
            animation=Var.create(f"${{pulse}} 1s infinite", _var_is_string=True),
            **props,
        )

    def _get_imports(self) -> imports.ImportDict:
        return imports.merge_imports(
            super()._get_imports(),
            {"@emotion/react": [imports.ImportVar(tag="keyframes")]},
        )

    def _get_custom_code(self) -> str | None:
        return """
const pulse = keyframes`
    0% {
        opacity: 0;
    }
    100% {
        opacity: 1;
    }
`
"""


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
            position="fixed",
            width="100vw",
            height="0",
        )
