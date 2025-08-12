"""Sonner toast component."""

from __future__ import annotations

from typing import Any, Literal

from reflex.base import Base
from reflex.components.component import Component, ComponentNamespace
from reflex.components.lucide.icon import Icon
from reflex.components.props import NoExtrasAllowedProps
from reflex.constants.base import Dirs
from reflex.event import EventSpec, run_script
from reflex.style import Style, resolved_color_mode
from reflex.utils import format
from reflex.utils.imports import ImportVar
from reflex.utils.serializers import serializer
from reflex.vars import VarData
from reflex.vars.base import LiteralVar, Var
from reflex.vars.function import FunctionVar
from reflex.vars.number import ternary_operation
from reflex.vars.object import ObjectVar

LiteralPosition = Literal[
    "top-left",
    "top-center",
    "top-right",
    "bottom-left",
    "bottom-center",
    "bottom-right",
]

toast_ref = Var(
    _js_expr="refs['__toast']",
    _var_data=VarData(imports={f"$/{Dirs.STATE_PATH}": [ImportVar(tag="refs")]}),
)


class ToastAction(Base):
    """A toast action that render a button in the toast."""

    label: str
    on_click: Any


@serializer
def serialize_action(action: ToastAction) -> dict:
    """Serialize a toast action.

    Args:
        action: The toast action to serialize.

    Returns:
        The serialized toast action with on_click formatted to queue the given event.
    """
    return {
        "label": action.label,
        "onClick": format.format_queue_events(action.on_click),
    }


def _toast_callback_signature(toast: Var) -> list[Var]:
    """The signature for the toast callback, stripping out unserializable keys.

    Args:
        toast: The toast variable.

    Returns:
        A function call stripping non-serializable members of the toast object.
    """
    return [
        Var(
            _js_expr=f"(() => {{let {{action, cancel, onDismiss, onAutoClose, ...rest}} = {toast!s}; return rest}})()"
        )
    ]


class ToastProps(NoExtrasAllowedProps):
    """Props for the toast component."""

    # Toast's title, renders above the description.
    title: str | Var | None

    # Toast's description, renders underneath the title.
    description: str | Var | None

    # Whether to show the close button.
    close_button: bool | None

    # Dark toast in light mode and vice versa.
    invert: bool | None

    # Control the sensitivity of the toast for screen readers
    important: bool | None

    # Time in milliseconds that should elapse before automatically closing the toast.
    duration: int | None

    # Position of the toast.
    position: LiteralPosition | None

    # If false, it'll prevent the user from dismissing the toast.
    dismissible: bool | None

    # TODO: fix serialization of icons for toast? (might not be possible yet)
    # Icon displayed in front of toast's text, aligned vertically.
    # icon: Icon | None = None # noqa: ERA001

    # TODO: fix implementation for action / cancel buttons
    # Renders a primary button, clicking it will close the toast.
    action: ToastAction | None

    # Renders a secondary button, clicking it will close the toast.
    cancel: ToastAction | None

    # Custom id for the toast.
    id: str | Var | None

    # Removes the default styling, which allows for easier customization.
    unstyled: bool | None

    # Custom style for the toast.
    style: Style | None

    # Class name for the toast.
    class_name: str | None

    # XXX: These still do not seem to work
    # Custom style for the toast primary button.
    action_button_styles: Style | None

    # Custom style for the toast secondary button.
    cancel_button_styles: Style | None

    # The function gets called when either the close button is clicked, or the toast is swiped.
    on_dismiss: Any | None

    # Function that gets called when the toast disappears automatically after it's timeout (duration` prop).
    on_auto_close: Any | None

    def dict(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        """Convert the object to a dictionary.

        Args:
            *args: The arguments to pass to the base class.
            **kwargs: The keyword arguments to pass to the base

        Returns:
            The object as a dictionary with ToastAction fields intact.
        """
        d = super().dict(*args, **kwargs)
        # Keep these fields as ToastAction so they can be serialized specially
        if "action" in d:
            d["action"] = self.action
            if isinstance(self.action, dict):
                d["action"] = ToastAction(**self.action)
        if "cancel" in d:
            d["cancel"] = self.cancel
            if isinstance(self.cancel, dict):
                d["cancel"] = ToastAction(**self.cancel)
        if "onDismiss" in d:
            d["onDismiss"] = format.format_queue_events(
                self.on_dismiss, _toast_callback_signature
            )
        if "onAutoClose" in d:
            d["onAutoClose"] = format.format_queue_events(
                self.on_auto_close, _toast_callback_signature
            )
        return d


class Toaster(Component):
    """A Toaster Component for displaying toast notifications."""

    library: str | None = "sonner@2.0.7"

    tag = "Toaster"

    # the theme of the toast
    theme: Var[str] = resolved_color_mode

    # whether to show rich colors
    rich_colors: Var[bool] = LiteralVar.create(True)

    # whether to expand the toast
    expand: Var[bool] = LiteralVar.create(True)

    # the number of toasts that are currently visible
    visible_toasts: Var[int]

    # the position of the toast
    position: Var[LiteralPosition] = LiteralVar.create("bottom-right")

    # whether to show the close button
    close_button: Var[bool] = LiteralVar.create(False)

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

    def add_hooks(self) -> list[Var | str]:
        """Add hooks for the toaster component.

        Returns:
            The hooks for the toaster component.
        """
        if self.library is None:
            return []
        hook = Var(
            _js_expr=f"{toast_ref} = toast",
            _var_data=VarData(
                imports={
                    "$/utils/state": [ImportVar(tag="refs")],
                    self.library: [ImportVar(tag="toast", install=False)],
                }
            ),
        )
        return [hook]

    @staticmethod
    def send_toast(
        message: str | Var = "",
        level: str | None = None,
        fallback_to_alert: bool = False,
        **props,
    ) -> EventSpec:
        """Send a toast message.

        Args:
            message: The message to display.
            level: The level of the toast.
            fallback_to_alert: Whether to fallback to an alert if the toaster is not created.
            **props: The options for the toast.

        Raises:
            ValueError: If the Toaster component is not created.

        Returns:
            The toast event.
        """
        toast_command = (
            ObjectVar.__getattr__(toast_ref.to(dict), level) if level else toast_ref
        ).to(FunctionVar)

        if isinstance(message, Var):
            props.setdefault("title", message)
            message = ""
        elif message == "" and "title" not in props and "description" not in props:
            msg = "Toast message or title or description must be provided."
            raise ValueError(msg)

        if props:
            args = LiteralVar.create(ToastProps(component_name="rx.toast", **props))  # pyright: ignore [reportCallIssue]
            toast = toast_command.call(message, args)
        else:
            toast = toast_command.call(message)

        if fallback_to_alert:
            toast = ternary_operation(
                toast_ref.bool(),
                toast,
                FunctionVar("window.alert").call(
                    Var.create(
                        message
                        if isinstance(message, str) and message
                        else props.get("title", props.get("description", ""))
                    )
                    .to(str)
                    .replace("<br/>", "\n")
                ),
            )

        return run_script(toast)

    @staticmethod
    def toast_info(message: str | Var = "", **kwargs: Any):
        """Display an info toast message.

        Args:
            message: The message to display.
            **kwargs: Additional toast props.

        Returns:
            The toast event.
        """
        return Toaster.send_toast(message, level="info", **kwargs)

    @staticmethod
    def toast_warning(message: str | Var = "", **kwargs: Any):
        """Display a warning toast message.

        Args:
            message: The message to display.
            **kwargs: Additional toast props.

        Returns:
            The toast event.
        """
        return Toaster.send_toast(message, level="warning", **kwargs)

    @staticmethod
    def toast_error(message: str | Var = "", **kwargs: Any):
        """Display an error toast message.

        Args:
            message: The message to display.
            **kwargs: Additional toast props.

        Returns:
            The toast event.
        """
        return Toaster.send_toast(message, level="error", **kwargs)

    @staticmethod
    def toast_success(message: str | Var = "", **kwargs: Any):
        """Display a success toast message.

        Args:
            message: The message to display.
            **kwargs: Additional toast props.

        Returns:
            The toast event.
        """
        return Toaster.send_toast(message, level="success", **kwargs)

    @staticmethod
    def toast_loading(message: str | Var = "", **kwargs: Any):
        """Display a loading toast message.

        Args:
            message: The message to display.
            **kwargs: Additional toast props.

        Returns:
            The toast event.
        """
        return Toaster.send_toast(message, level="loading", **kwargs)

    @staticmethod
    def toast_dismiss(id: Var | str | None = None):
        """Dismiss a toast.

        Args:
            id: The id of the toast to dismiss.

        Returns:
            The toast dismiss event.
        """
        dismiss_var_data = None

        if isinstance(id, Var):
            dismiss = f"{toast_ref}.dismiss({id!s})"
            dismiss_var_data = id._get_all_var_data()
        elif isinstance(id, str):
            dismiss = f"{toast_ref}.dismiss('{id}')"
        else:
            dismiss = f"{toast_ref}.dismiss()"
        dismiss_action = Var(
            _js_expr=dismiss, _var_data=VarData.merge(dismiss_var_data)
        )
        return run_script(dismiss_action)

    @classmethod
    def create(cls, *children: Any, **props: Any) -> Component:
        """Create a toaster component.

        Args:
            *children: The children of the toaster.
            **props: The properties of the toaster.

        Returns:
            The toaster component.
        """
        return super().create(*children, **props)


# TODO: figure out why loading toast stay open forever when using level="loading" in toast()


class ToastNamespace(ComponentNamespace):
    """Namespace for toast components."""

    provider = staticmethod(Toaster.create)
    options = staticmethod(ToastProps)
    info = staticmethod(Toaster.toast_info)
    warning = staticmethod(Toaster.toast_warning)
    error = staticmethod(Toaster.toast_error)
    success = staticmethod(Toaster.toast_success)
    loading = staticmethod(Toaster.toast_loading)
    dismiss = staticmethod(Toaster.toast_dismiss)
    __call__ = staticmethod(Toaster.send_toast)


toast = ToastNamespace()
