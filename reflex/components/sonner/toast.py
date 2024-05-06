"""Sonner toast component."""

from __future__ import annotations

from typing import Literal

from reflex.base import Base
from reflex.components.component import Component, ComponentNamespace
from reflex.components.lucide.icon import Icon
from reflex.event import EventSpec, call_script
from reflex.style import Style, color_mode
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

    # Toast's description, renders underneath the title.
    description: str = ""

    # Whether to show the close button.
    close_button: bool = False

    # Dark toast in light mode and vice versa.
    invert: bool = False

    # Control the sensitivity of the toast for screen readers
    important: bool = False

    # Time in milliseconds that should elapse before automatically closing the toast.
    duration: int = 4000

    # Position of the toast.
    position: LiteralPosition = "bottom-right"

    # If false, it'll prevent the user from dismissing the toast.
    dismissible: bool = True

    # TODO: fix serialization of icons for toast? (might not be possible yet)
    # Icon displayed in front of toast's text, aligned vertically.
    # icon: Optional[Icon] = None

    # TODO: fix implementation for action / cancel buttons
    # Renders a primary button, clicking it will close the toast.
    # action: str = ""

    # Renders a secondary button, clicking it will close the toast.
    # cancel: str = ""

    # Custom id for the toast.
    id: str = ""

    # Removes the default styling, which allows for easier customization.
    unstyled: bool = False

    # Custom style for the toast.
    style: Style = Style()

    # Custom style for the toast primary button.
    # action_button_styles: Style = Style()

    # Custom style for the toast secondary button.
    # cancel_button_styles: Style = Style()


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
    visible_toasts: Var[int]

    # the position of the toast
    position: Var[LiteralPosition] = Var.create_safe("bottom-right")

    # whether to show the close button
    close_button: Var[bool] = Var.create_safe(False)

    # offset of the toast
    offset: Var[str]

    # directionality of the toast (default: ltr)
    dir: Var[str]

    # Keyboard shortcut that will move focus to the toaster area.
    hotkey: Var[str]

    # Dark toasts in light mode and vice versa.
    invert: Var[bool]

    # These will act as default options for all toasts. See toast() for all available options.
    toast_options: Var[ToastProps]

    # Gap between toasts when expanded
    gap: Var[int]

    # Changes the default loading icon
    loading_icon: Var[Icon]

    # Pauses toast timers when the page is hidden, e.g., when the tab is backgrounded, the browser is minimized, or the OS is locked.
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

    def toast_dismiss(self, id: str | None):
        """Dismiss a toast.

        Args:
            id: The id of the toast to dismiss.

        Returns:
            The toast dismiss event.
        """
        if id is None:
            dismiss = f"{toast_ref}.dismiss()"
        else:
            dismiss = f"{toast_ref}.dismiss({id})"
        dismiss_action = Var.create(dismiss, _var_is_string=False, _var_is_local=True)
        return call_script(dismiss_action)  # type: ignore


# TODO: figure out why loading toast stay open forever
# def toast_loading(message: str, **kwargs):
#     return _toast(message, level="loading", **kwargs)


class ToastNamespace(ComponentNamespace):
    """Namespace for toast components."""

    provider = staticmethod(Toaster.create)
    options = staticmethod(ToastProps)
    info = staticmethod(Toaster.toast_info)
    warning = staticmethod(Toaster.toast_warning)
    error = staticmethod(Toaster.toast_error)
    success = staticmethod(Toaster.toast_success)
    dismiss = staticmethod(Toaster.toast_dismiss)
    # loading = staticmethod(toast_loading)
    __call__ = staticmethod(Toaster.send_toast)


toast = ToastNamespace()
