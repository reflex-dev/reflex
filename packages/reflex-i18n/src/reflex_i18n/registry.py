"""Compile-time registry of messages used via :func:`reflex_i18n.vars.t`.

Every ``rx.t`` call records its message here. After all pages have been
evaluated, the registry is the complete set of static messages the app uses;
the compiler emits per-locale catalog modules containing only these entries
(tree-shaking) and the extraction tooling turns them into ``.pot`` entries.

The registry is intentionally never reset between compiles: components built
at module import time register before the compiler runs, and a fresh process
(any prod compile) starts empty anyway. In dev hot-reload this can retain
stale entries, which only makes dev catalogs slightly larger.
"""

from __future__ import annotations

from typing import NamedTuple

# gettext's msgctxt separator, used to build unique catalog keys.
CONTEXT_SEPARATOR = "\x04"


class MessageKey(NamedTuple):
    """A translatable message collected from an ``rx.t`` call."""

    message: str
    plural: str | None = None
    context: str | None = None

    @property
    def catalog_key(self) -> str:
        """The key identifying this message in a compiled catalog module.

        Returns:
            The msgid, prefixed with the gettext context convention if a
            context is set.
        """
        if self.context:
            return f"{self.context}{CONTEXT_SEPARATOR}{self.message}"
        return self.message


_collected: dict[MessageKey, None] = {}


def register(key: MessageKey) -> None:
    """Record a message used by the app.

    Args:
        key: The message to record.
    """
    _collected[key] = None


def collected_messages() -> tuple[MessageKey, ...]:
    """Get all messages registered so far, in first-use order.

    Returns:
        The registered messages.
    """
    return tuple(_collected)


def clear_messages() -> None:
    """Clear the registry. Only intended for tests."""
    _collected.clear()
