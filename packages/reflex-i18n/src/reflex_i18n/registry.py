"""Compile-time registry of messages used via :func:`reflex_i18n.vars.t`.

Every ``rx.t`` call records its message here. After all pages have been
evaluated, the registry is the complete set of static messages the app uses;
the compiler emits per-locale catalog modules containing only these entries
(tree-shaking) and the extraction tooling turns them into ``.pot`` entries.

The registry is intentionally never reset between compiles: components built
at module import time register before the compiler runs, and every compile
happens in a fresh process anyway (a dev hot reload boots a new backend
worker), so entries never outlive the source they were collected from.
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

    @property
    def msgid(self) -> str | tuple[str, str]:
        """The babel catalog msgid: a string, or (singular, plural) tuple.

        Returns:
            The plural pair if this is a plural message, else the message.
        """
        return self.message if self.plural is None else (self.message, self.plural)


_collected: dict[MessageKey, None] = {}
# (context, message) -> plural. gettext keys entries by msgctxt + msgid, so
# one msgid cannot carry both a singular and a plural (or two plurals).
_plural_by_msgid: dict[tuple[str | None, str], str | None] = {}


def register(key: MessageKey) -> None:
    """Record a message used by the app.

    Args:
        key: The message to record.

    Raises:
        ValueError: If the same msgid (and context) was already registered
            with a different plural form.
    """
    previous = _plural_by_msgid.setdefault((key.context, key.message), key.plural)
    if previous != key.plural:
        msg = (
            f"Message {key.message!r} is used both with plural {previous!r} and "
            f"{key.plural!r}; gettext keys catalog entries by msgid, so a message "
            "must be either singular or plural. Disambiguate with context=."
        )
        raise ValueError(msg)
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
    _plural_by_msgid.clear()
