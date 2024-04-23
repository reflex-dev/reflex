"""Sonner toast component."""

from typing import Literal

from reflex.base import Base
from reflex.components.component import Component, ComponentNamespace
from reflex.components.core.cond import color_mode_cond
from reflex.components.lucide.icon import Icon
from reflex.event import call_script
from reflex.utils import format
from reflex.utils.imports import ImportVar
from reflex.utils.serializers import serialize
from reflex.vars import Var

LiteralPosition = Literal[
    "top-left",
    "top-center",
    "top-right",
    "bottom-left",
    "bottom-center",
    "bottom-right",
]


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
    icon: Icon = None
    action: str = ""
    cancel: str = ""
    id: str = ""
    unstyled: bool = False
    action_button_styles: dict[str, str] = {}
    cancel_button_styles: dict[str, str] = {}


class Toaster(Component):
    """A Toaster Component for displaying toast notifications."""

    library = "sonner@1.4.41"

    tag = "Toaster"

    theme: Var[str] = color_mode_cond(light="light", dark="dark")

    rich_colors: Var[bool] = True

    expand: Var[bool] = True

    visibleToasts: Var[int]

    position: Var[LiteralPosition] = "bottom-right"

    close_button: Var[bool] = False

    offset: Var[str]

    # directionality of the toast (default: ltr)
    dir: Var[str]

    hotkey: Var[str]

    invert: Var[bool]

    toast_options: Var[ToastProps]

    gap: Var[int]

    loadingIcon: Var[Icon]

    pause_when_page_is_hidden: Var[bool]

    def _get_imports(self) -> dict[str, list[ImportVar]]:
        return super()._get_imports() | {
            "sonner": [ImportVar(tag="toast")],
        }


def toast_info(message: str, **kwargs):
    """Display an info toast message."""
    return _toast(message, level="info", **kwargs)


def toast_warning(message: str, **kwargs):
    """Display a warning toast message."""
    return _toast(message, level="warning", **kwargs)


def toast_error(message: str, **kwargs):
    """Display an error toast message."""
    return _toast(message, level="error", **kwargs)


def toast_success(message: str, **kwargs):
    """Display a success toast message."""
    return _toast(message, level="success", **kwargs)


# TODO: figure out why loading toast stay open forever
# def toast_loading(message: str, **kwargs):
#     return _toast(message, level="loading", **kwargs)


def _toast(message: str, **toast_args):
    level = toast_args.pop("level", None)
    toast_command = f"toast.{level}" if level is not None else "toast"
    if toast_args:
        args = serialize(ToastProps(**toast_args))
        toast = f"{toast_command}(`{message}`, {args})"
    else:
        toast = f"{toast_command}(`{message}`)"

    toast_action = Var.create(toast, _var_is_string=False, _var_is_local=True)
    return call_script(toast_action)


class ToastNamespace(ComponentNamespace):
    """Namespace for toast components."""

    provider = staticmethod(Toaster.create)
    options = staticmethod(ToastProps)
    info = staticmethod(toast_info)
    warning = staticmethod(toast_warning)
    error = staticmethod(toast_error)
    success = staticmethod(toast_success)
    # loading = staticmethod(toast_loading)
    __call__ = staticmethod(_toast)


toast = ToastNamespace()
