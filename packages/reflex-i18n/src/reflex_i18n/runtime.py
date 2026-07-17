"""Server-side translation of dynamic (state) content via gettext.

Event handlers and computed vars call :func:`gettext` (aliased ``_``) to
translate strings in the active locale. The active locale is held in a
contextvar set per client while events are processed; translating in a
computed var means the string is retranslated and re-pushed as a delta
whenever the locale changes.
"""

from __future__ import annotations

import gettext as _gettext_module
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path

from .config import get_active_catalog_dir

# The locale in effect for the current client while an event is processed.
_active_locale: ContextVar[str | None] = ContextVar(
    "reflex_active_locale", default=None
)

# Lazily-built gettext translators, keyed by locale.
_translations: dict[str, _gettext_module.NullTranslations] = {}


@contextmanager
def use_locale(locale: str | None) -> Iterator[None]:
    """Set the active locale for the duration of the context.

    Args:
        locale: The locale to activate, or None to leave translations
            untranslated.

    Yields:
        None
    """
    token = _active_locale.set(locale)
    try:
        yield
    finally:
        _active_locale.reset(token)


def get_locale() -> str | None:
    """Get the locale active for the current client.

    Returns:
        The active locale, or None if none is set.
    """
    return _active_locale.get()


def _catalog_path(locale: str) -> Path | None:
    """Find the ``.po`` catalog for a locale.

    Args:
        locale: The locale to find a catalog for.

    Returns:
        The path of the catalog file, or None if the app has no i18n config
        or the file does not exist.
    """
    catalog_dir = get_active_catalog_dir()
    if catalog_dir is None:
        return None
    path = catalog_dir / f"{locale}.po"
    return path if path.exists() else None


def _get_translations(locale: str) -> _gettext_module.NullTranslations:
    """Get (and cache) the gettext translator for a locale.

    Args:
        locale: The locale to translate into.

    Returns:
        A gettext translator; a null (pass-through) translator if no catalog
        exists for the locale.
    """
    cached = _translations.get(locale)
    if cached is not None:
        return cached

    path = _catalog_path(locale)
    if path is None:
        translations: _gettext_module.NullTranslations = (
            _gettext_module.NullTranslations()
        )
    else:
        import io

        from babel.messages.mofile import write_mo
        from babel.messages.pofile import read_po

        with path.open("r", encoding="utf-8") as po_file:
            catalog = read_po(po_file)
        buffer = io.BytesIO()
        write_mo(buffer, catalog)
        buffer.seek(0)
        translations = _gettext_module.GNUTranslations(buffer)

    _translations[locale] = translations
    return translations


def clear_translations_cache() -> None:
    """Drop cached translators. Intended for tests and hot reload."""
    _translations.clear()


def gettext(message: str) -> str:
    """Translate a message into the active locale.

    Args:
        message: The source-locale message.

    Returns:
        The translated message, or the source message if untranslated or no
        locale is active.
    """
    locale = _active_locale.get()
    if locale is None:
        return message
    return _get_translations(locale).gettext(message)


def ngettext(singular: str, plural: str, n: int) -> str:
    """Translate a message with plural forms into the active locale.

    Args:
        singular: The source-locale singular message.
        plural: The source-locale plural message.
        n: The quantity selecting the form.

    Returns:
        The translated message for ``n``, or the appropriate source message
        if untranslated or no locale is active.
    """
    locale = _active_locale.get()
    if locale is None:
        return singular if n == 1 else plural
    return _get_translations(locale).ngettext(singular, plural, n)


def pgettext(context: str, message: str) -> str:
    """Translate a context-qualified message into the active locale.

    Args:
        context: The gettext message context (msgctxt).
        message: The source-locale message.

    Returns:
        The translated message, or the source message if untranslated or no
        locale is active.
    """
    locale = _active_locale.get()
    if locale is None:
        return message
    return _get_translations(locale).pgettext(context, message)


def negotiate_locale(
    accept_language: str, supported: Sequence[str], default: str
) -> str:
    """Choose the best supported locale for an Accept-Language header.

    Args:
        accept_language: The raw ``Accept-Language`` header value.
        supported: The locales the app supports.
        default: The locale to return if none match.

    Returns:
        The best matching supported locale, or ``default``.
    """
    supported_set = set(supported)
    by_language: dict[str, str] = {}
    for locale in supported:
        by_language.setdefault(locale.split("-")[0], locale)

    ranked: list[tuple[float, int, str]] = []
    for index, entry in enumerate(accept_language.split(",")):
        tag, _, params = entry.strip().partition(";")
        tag = tag.strip().replace("_", "-")
        if not tag or tag == "*":
            continue
        quality = 1.0
        if params.strip().startswith("q="):
            try:
                quality = float(params.strip()[2:])
            except ValueError:
                quality = 0.0
        if quality <= 0.0:
            # q=0 means "not acceptable" (RFC 7231 §5.3.1); exclude it.
            continue
        # Sort by quality descending, then by original order for ties.
        ranked.append((-quality, index, tag))

    for _, _, tag in sorted(ranked):
        if tag in supported_set:
            return tag
        language = tag.split("-")[0]
        if language in by_language:
            return by_language[language]
    return default
