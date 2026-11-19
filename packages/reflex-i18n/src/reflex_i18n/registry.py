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
# Messages built while no I18nPlugin was configured: they render the source
# text for good, even if a plugin is configured afterwards.
_untranslated: dict[MessageKey, None] = {}
# (context, message) -> plural. gettext keys entries by msgctxt + msgid, so
# one msgid cannot carry both a singular and a plural (or two plurals).
_plural_by_msgid: dict[tuple[str | None, str], str | None] = {}


def register(key: MessageKey, *, translated: bool = True) -> None:
    """Record a message used by the app.

    Args:
        key: The message to record.
        translated: False if the message was built without an I18nPlugin and
            so renders its source text.

    Raises:
        ValueError: If the message or context contains the gettext context
            separator, or the same msgid (and context) was already registered
            with a different plural form.
    """
    if CONTEXT_SEPARATOR in key.message or CONTEXT_SEPARATOR in (key.context or ""):
        # The client-side catalog key is "context\x04msgid", so a separator in
        # either half would let two distinct entries collide on one key.
        msg = (
            "Translatable messages and contexts must not contain the gettext "
            f"context separator (U+0004): {key.message!r}."
        )
        raise ValueError(msg)
    previous = _plural_by_msgid.setdefault((key.context, key.message), key.plural)
    if previous != key.plural:
        msg = (
            f"Message {key.message!r} is used both with plural {previous!r} and "
            f"{key.plural!r}; gettext keys catalog entries by msgid, so a message "
            "must be either singular or plural. Disambiguate with context=."
        )
        raise ValueError(msg)
    _collected[key] = None
    if not translated:
        _untranslated[key] = None


def collected_messages() -> tuple[MessageKey, ...]:
    """Get all messages registered so far, in first-use order.

    Returns:
        The registered messages.
    """
    return tuple(_collected)


def untranslated_messages() -> tuple[MessageKey, ...]:
    """Get the messages built without an I18nPlugin, in first-use order.

    Returns:
        The messages that render their source text.
    """
    return tuple(_untranslated)


def format_message_list(keys: tuple[MessageKey, ...] | list[MessageKey]) -> str:
    """List messages for a console warning, at most ten of them.

    Args:
        keys: The messages to list.

    Returns:
        One indented line per message, then a count of the ones left out.
    """
    lines = [f"  {key.message!r}" for key in keys[:10]]
    if len(keys) > 10:
        lines.append(f"  ... and {len(keys) - 10} more")
    return "\n".join(lines)


def clear_messages() -> None:
    """Clear the registry. Only intended for tests."""
    _collected.clear()
    _untranslated.clear()
    _plural_by_msgid.clear()
