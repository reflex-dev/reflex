"""Sonner toast component."""

from __future__ import annotations

from typing import Any, ClassVar, Literal, Optional, Union

from pydantic import ValidationError

from reflex.base import Base
from reflex.components.component import Component, ComponentNamespace
from reflex.components.lucide.icon import Icon
from reflex.components.props import PropsBase
from reflex.event import (
    EventSpec,
    call_script,
)
from reflex.style import Style, resolved_color_mode
from reflex.utils import format
from reflex.utils.imports import ImportVar
from reflex.utils.serializers import serialize, serializer
from reflex.vars import Var, VarData

LiteralPosition = Literal[
    "top-left",
    "top-center",
    "top-right",
    "bottom-left",
    "bottom-center",
    "bottom-right",
]

toast_ref = Var.create_safe("refs['__toast']", _var_is_string=False)


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
        Var.create_safe(
            f"(() => {{let {{action, cancel, onDismiss, onAutoClose, ...rest}} = {toast}; return rest}})()",
            _var_is_string=False,
        )
    ]


class ToastProps(PropsBase):
    """Props for the toast component."""

    # Toast's description, renders underneath the title.
    description: Optional[Union[str, Var]]

    # Whether to show the close button.
    close_button: Optional[bool]

    # Dark toast in light mode and vice versa.
    invert: Optional[bool]

    # Control the sensitivity of the toast for screen readers
    important: Optional[bool]

    # Time in milliseconds that should elapse before automatically closing the toast.
    duration: Optional[int]

    # Position of the toast.
    position: Optional[LiteralPosition]

    # If false, it'll prevent the user from dismissing the toast.
    dismissible: Optional[bool]

    # TODO: fix serialization of icons for toast? (might not be possible yet)
    # Icon displayed in front of toast's text, aligned vertically.
    # icon: Optional[Icon] = None

    # TODO: fix implementation for action / cancel buttons
    # Renders a primary button, clicking it will close the toast.
    action: Optional[ToastAction]

    # Renders a secondary button, clicking it will close the toast.
    cancel: Optional[ToastAction]

    # Custom id for the toast.
    id: Optional[Union[str, Var]]

    # Removes the default styling, which allows for easier customization.
    unstyled: Optional[bool]

    # Custom style for the toast.
    style: Optional[Style]

    # XXX: These still do not seem to work
    # Custom style for the toast primary button.
    action_button_styles: Optional[Style]

    # Custom style for the toast secondary button.
    cancel_button_styles: Optional[Style]

    # The function gets called when either the close button is clicked, or the toast is swiped.
    on_dismiss: Optional[Any]

    # Function that gets called when the toast disappears automatically after it's timeout (duration` prop).
    on_auto_close: Optional[Any]

    def __init__(self, **kwargs):
        """Initialize the props.

        Args:
            kwargs: Kwargs to initialize the props.

        Raises:
            ValueError: If invalid props are passed on instantiation.
        """
        try:
            super().__init__(**kwargs)
        except ValidationError as e:
            invalid_fields = ", ".join([error["loc"][0] for error in e.errors()])  # type: ignore
            supported_props_str = ", ".join(f'"{field}"' for field in self.get_fields())
            raise ValueError(
                f"Invalid prop(s) {invalid_fields} for rx.toast. Supported props are {supported_props_str}"
            ) from None

    def dict(self, *args, **kwargs) -> dict[str, Any]:
        """Convert the object to a dictionary.

        Args:
            *args: The arguments to pass to the base class.
            **kwargs: The keyword arguments to pass to the base

        Returns:
            The object as a dictionary with ToastAction fields intact.
        """
        kwargs.setdefault("exclude_none", True)  # type: ignore
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
        if "on_dismiss" in d:
            d["on_dismiss"] = format.format_queue_events(
                self.on_dismiss, _toast_callback_signature
            )
        if "on_auto_close" in d:
            d["on_auto_close"] = format.format_queue_events(
                self.on_auto_close, _toast_callback_signature
            )
        return d

    class Config:
        """Pydantic config."""

        arbitrary_types_allowed = True
        use_enum_values = True
        extra = "forbid"


class Toaster(Component):
    """A Toaster Component for displaying toast notifications."""

    library: str = "sonner@1.4.41"

    tag = "Toaster"

    # the theme of the toast
    theme: Var[str] = resolved_color_mode

    # whether to show rich colors
    rich_colors: Var[bool] = Var.create_safe(True)

    # whether to expand the toast
    expand: Var[bool] = Var.create_safe(True)

    # the number of toasts that are currently visible
    visible_toasts: Var[int]

    # the position of the toast
    position: Var[LiteralPosition] = Var.create_safe(
        "bottom-right", _var_is_string=True
    )

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

    # Marked True when any Toast component is created.
    is_used: ClassVar[bool] = False

    def add_hooks(self) -> list[Var | str]:
        """Add hooks for the toaster component.

        Returns:
            The hooks for the toaster component.
        """
        hook = Var.create_safe(
            f"{toast_ref} = toast",
            _var_is_local=True,
            _var_is_string=False,
            _var_data=VarData(
                imports={
                    "/utils/state": [ImportVar(tag="refs")],
                    self.library: [ImportVar(tag="toast", install=False)],
                }
            ),
        )
        return [hook]

    @staticmethod
    def send_toast(message: str = "", level: str | None = None, **props) -> EventSpec:
        """Send a toast message.

        Args:
            message: The message to display.
            level: The level of the toast.
            **props: The options for the toast.

        Raises:
            ValueError: If the Toaster component is not created.

        Returns:
            The toast event.
        """
        if not Toaster.is_used:
            raise ValueError(
                "Toaster component must be created before sending a toast. (use `rx.toast.provider()`)"
            )
        toast_command = f"{toast_ref}.{level}" if level is not None else toast_ref
        if message == "" and ("title" not in props or "description" not in props):
            raise ValueError("Toast message or title or description must be provided.")
        if props:
            args = serialize(ToastProps(**props))  # type: ignore
            toast = f"{toast_command}(`{message}`, {args})"
        else:
            toast = f"{toast_command}(`{message}`)"

        toast_action = Var.create_safe(toast, _var_is_string=False, _var_is_local=True)
        return call_script(toast_action)

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
            dismiss = f"{toast_ref}.dismiss({id._var_name_unwrapped})"
            dismiss_var_data = id._var_data
        elif isinstance(id, str):
            dismiss = f"{toast_ref}.dismiss('{id}')"
        else:
            dismiss = f"{toast_ref}.dismiss()"
        dismiss_action = Var.create_safe(
            dismiss,
            _var_is_string=False,
            _var_is_local=True,
            _var_data=dismiss_var_data,
        )
        return call_script(dismiss_action)

    @classmethod
    def create(cls, *children, **props) -> Component:
        """Create a toaster component.

        Args:
            *children: The children of the toaster.
            **props: The properties of the toaster.

        Returns:
            The toaster component.
        """
        cls.is_used = True
        return super().create(*children, **props)


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
