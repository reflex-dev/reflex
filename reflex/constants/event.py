"""Event-related constants."""
from enum import Enum
from types import SimpleNamespace


class Endpoint(Enum):
    """Endpoints for the reflex backend API."""

    PING = "ping"
    EVENT = "_event"
    UPLOAD = "_upload"

    def __str__(self) -> str:
        """Get the string representation of the endpoint.

        Returns:
            The path for the endpoint.
        """
        return f"/{self.value}"

    def get_url(self) -> str:
        """Get the URL for the endpoint.

        Returns:
            The full URL for the endpoint.
        """
        # Import here to avoid circular imports.
        from reflex.config import get_config

        # Get the API URL from the config.
        config = get_config()
        url = "".join([config.api_url, str(self)])

        # The event endpoint is a websocket.
        if self == Endpoint.EVENT:
            # Replace the protocol with ws.
            url = url.replace("https://", "wss://").replace("http://", "ws://")

        # Return the url.
        return url


class SocketEvent(SimpleNamespace):
    """Socket events sent by the reflex backend API."""

    PING = "ping"
    EVENT = "event"

    def __str__(self) -> str:
        """Get the string representation of the event name.

        Returns:
            The event name string.
        """
        return str(self.value)


class EventTriggers(SimpleNamespace):
    """All trigger names used in Reflex."""

    ON_FOCUS = "on_focus"
    ON_BLUR = "on_blur"
    ON_CANCEL = "on_cancel"
    ON_CLICK = "on_click"
    ON_CHANGE = "on_change"
    ON_CHANGE_END = "on_change_end"
    ON_CHANGE_START = "on_change_start"
    ON_CHECKED_CHANGE = "on_checked_change"
    ON_COMPLETE = "on_complete"
    ON_CONTEXT_MENU = "on_context_menu"
    ON_DOUBLE_CLICK = "on_double_click"
    ON_DROP = "on_drop"
    ON_EDIT = "on_edit"
    ON_KEY_DOWN = "on_key_down"
    ON_KEY_UP = "on_key_up"
    ON_MOUSE_DOWN = "on_mouse_down"
    ON_MOUSE_ENTER = "on_mouse_enter"
    ON_MOUSE_LEAVE = "on_mouse_leave"
    ON_MOUSE_MOVE = "on_mouse_move"
    ON_MOUSE_OUT = "on_mouse_out"
    ON_MOUSE_OVER = "on_mouse_over"
    ON_MOUSE_UP = "on_mouse_up"
    ON_SCROLL = "on_scroll"
    ON_SUBMIT = "on_submit"
    ON_MOUNT = "on_mount"
    ON_UNMOUNT = "on_unmount"
