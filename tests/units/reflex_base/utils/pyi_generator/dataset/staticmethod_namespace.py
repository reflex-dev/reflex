"""Namespace with staticmethod __call__ that is not Component.create.

This module tests:
- _generate_staticmethod_call_functiondef path
- Namespace __call__ with custom function (not wrapping .create)
- The fallback where __call__.__func__.__name__ != "create"
"""

from reflex_base.components.component import Component, ComponentNamespace, field
from reflex_base.event import EventSpec
from reflex_base.vars.base import Var


class NotifyComponent(Component):
    """A notification component."""

    message: Var[str] = field(doc="The notification message.")

    level: Var[str] = field(doc="The notification level.")


def send_notification(message: str, level: str = "info") -> EventSpec:
    """Send a notification event.

    Args:
        message: The message to send.
        level: The notification level.

    Returns:
        The event spec.
    """
    return EventSpec()  # type: ignore[call-arg]


class Notify(ComponentNamespace):
    """Notification namespace."""

    component = staticmethod(NotifyComponent.create)
    __call__ = staticmethod(send_notification)


notify = Notify()
