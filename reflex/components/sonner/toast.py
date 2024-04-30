"""Sonner toast component."""

from __future__ import annotations

from typing import Dict, Literal, Optional

from reflex.base import Base
from reflex.components.component import Component, ComponentNamespace
from reflex.components.lucide.icon import Icon
from reflex.event import EventSpec, call_script
from reflex.style import color_mode
from reflex.utils import format
from reflex.utils.imports import ImportVar
from reflex.utils.serializers import serialize
from reflex.vars import Var, VarData

LiteralPosition = Literal[
    "top-left",
    "top-center",
    "top-right",
    "bottom-left",
    "bottom-center",
    "bottom-right",
]


toast_ref = Var.create_safe("refs['__toast']")


class PropsBase(Base):
    """Base class for all props classes."""

    def json(self) -> str:
        """Convert the object to a json string.

        Returns:
            The object as a json string.
        """
        from reflex.utils.serializers import serialize

        return self.__config__.json_dumps(
            {format.to_camel_case(key): value for key, value in self.dict().items()},
            default=serialize,
        )


class ToastProps(PropsBase):
    """Props for the toast component."""

    description: str = ""
    close_button: bool = False
    invert: bool = False
    important: bool = False
    duration: int = 4000
    position: LiteralPosition = "bottom-right"
    dismissible: bool = True
    icon: Optional[Icon] = None
    action: str = ""
    cancel: str = ""
    id: str = ""
    unstyled: bool = False
    action_button_styles: Dict[str, str] = {}
    cancel_button_styles: Dict[str, str] = {}


class Toaster(Component):
    """A Toaster Component for displaying toast notifications."""

    library = "sonner@1.4.41"

    tag = "Toaster"

    # the theme of the toast
    theme: Var[str] = color_mode

    # whether to show rich colors
    rich_colors: Var[bool] = Var.create_safe(True)

    # whether to expand the toast
    expand: Var[bool] = Var.create_safe(True)

    # the number of toasts that are currently visible
    visibleToasts: Var[int]

    # the position of the toast
    position: Var[LiteralPosition] = Var.create_safe("bottom-right")

    # whether to show the close button
    close_button: Var[bool] = Var.create_safe(False)

    # offset of the toast
    offset: Var[str]

    # directionality of the toast (default: ltr)
    dir: Var[str]

    hotkey: Var[str]

    invert: Var[bool]

    toast_options: Var[ToastProps]

    gap: Var[int]

    loadingIcon: Var[Icon]

    pause_when_page_is_hidden: Var[bool]

    def _get_hooks(self) -> Var[str]:
        hook = Var.create_safe(f"{toast_ref} = toast", _var_is_local=True)
        hook._var_data = VarData(  # type: ignore
            imports={
                "/utils/state": [ImportVar(tag="refs")],
                self.library: [ImportVar(tag="toast", install=False)],
            }
        )
        return hook

    @staticmethod
    def send_toast(message: str, level: str | None = None, **props) -> EventSpec:
        """Send a toast message.

        Args:
            message: The message to display.
            level: The level of the toast.
            **props: The options for the toast.

        Returns:
            The toast event.
        """
        toast_command = f"{toast_ref}.{level}" if level is not None else toast_ref
        if props:
            args = serialize(ToastProps(**props))
            toast = f"{toast_command}(`{message}`, {args})"
        else:
            toast = f"{toast_command}(`{message}`)"

        toast_action = Var.create(toast, _var_is_string=False, _var_is_local=True)
        return call_script(toast_action)  # type: ignore

    @staticmethod
    def toast_info(message: str, **kwargs):
        """Display an info toast message.

        Args:
            message: The message to display.
            kwargs: Additional toast props.

        Returns:
            The toast event.
        """
        return Toaster.send_toast(message, level="info", **kwargs)

    @staticmethod
    def toast_warning(message: str, **kwargs):
        """Display a warning toast message.

        Args:
            message: The message to display.
            kwargs: Additional toast props.

        Returns:
            The toast event.
        """
        return Toaster.send_toast(message, level="warning", **kwargs)

    @staticmethod
    def toast_error(message: str, **kwargs):
        """Display an error toast message.

        Args:
            message: The message to display.
            kwargs: Additional toast props.

        Returns:
            The toast event.
        """
        return Toaster.send_toast(message, level="error", **kwargs)

    @staticmethod
    def toast_success(message: str, **kwargs):
        """Display a success toast message.

        Args:
            message: The message to display.
            kwargs: Additional toast props.

        Returns:
            The toast event.
        """
        return Toaster.send_toast(message, level="success", **kwargs)


# TODO: figure out why loading toast stay open forever
# def toast_loading(message: str, **kwargs):
#     return _toast(message, level="loading", **kwargs)


# def _toast(message: str, level: str | None = None, **toast_args):
#     toast_command = f"{toast_ref}.{level}" if level is not None else toast_ref
#     if toast_args:
#         args = serialize(ToastProps(**toast_args))
#         toast = f"{toast_command}(`{message}`, {args})"
#     else:
#         toast = f"{toast_command}(`{message}`)"

#     toast_action = Var.create(toast, _var_is_string=False, _var_is_local=True)
#     return call_script(toast_action)  # type: ignore


class ToastNamespace(ComponentNamespace):
    """Namespace for toast components."""

    provider = staticmethod(Toaster.create)
    options = staticmethod(ToastProps)
    info = staticmethod(Toaster.toast_info)
    warning = staticmethod(Toaster.toast_warning)
    error = staticmethod(Toaster.toast_error)
    success = staticmethod(Toaster.toast_success)
    # loading = staticmethod(toast_loading)
    __call__ = staticmethod(Toaster.send_toast)


toast = ToastNamespace()
