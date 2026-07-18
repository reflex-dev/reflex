"""Server-side translation of dynamic (state) content via gettext.

Event handlers and computed vars call :func:`gettext` (aliased ``_``) to
translate strings in the active locale. The active locale is held in a
contextvar set per client while events are processed; translating in a
computed var means the string is retranslated and re-pushed as a delta
whenever the locale changes.
"""

from __future__ import annotations

import copy
import gettext as _gettext_module
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import TYPE_CHECKING

from reflex_base.vars.dep_tracking import register_implicit_dependency

from .config import get_active_catalog_dir, get_active_i18n_config

if TYPE_CHECKING:
    import datetime
    import decimal

    from reflex_base.vars.base import Var

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

        from .catalog import read_po_catalog

        catalog = read_po_catalog(path)
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


def _format_locale() -> str:
    """The locale to format in: active locale, else the default, else ``en``.

    Returns:
        The locale code for server-side formatting.
    """
    locale = _active_locale.get()
    if locale is not None:
        return locale
    config = get_active_i18n_config()
    return config.default_locale if config is not None else "en"


def _babel_locale() -> str:
    """The active format locale, normalized for Babel.

    Returns:
        The locale with ``-`` replaced by ``_`` (Babel rejects ``en-US``).
    """
    return _format_locale().replace("-", "_")


def _apply_number(
    kind: str,
    number: float | decimal.Decimal,
    *,
    min_fraction_digits: int | None,
    max_fraction_digits: int | None,
    grouping: bool,
    currency: str | None = None,
) -> str:
    """Format a number with the locale's own pattern.

    Using the locale's ``NumberPattern`` keeps locale-specific affixes and
    grouping (the ``%`` spacing, currency symbol position, non-Western grouping)
    that a hand-built pattern would lose; the requested fraction digits are
    applied by overriding the pattern's ``frac_prec``.

    Args:
        kind: ``"decimal"``, ``"percent"`` or ``"currency"``.
        number: The number to format.
        min_fraction_digits: Minimum fraction digits, or None for the default.
        max_fraction_digits: Maximum fraction digits, or None for the default.
        grouping: Whether to show the grouping separator.
        currency: The ISO 4217 currency code (for ``kind="currency"``).

    Returns:
        The localized number.
    """
    from babel import Locale

    locale = Locale.parse(_babel_locale())
    if kind == "currency":
        pattern = locale.currency_formats["standard"]
    elif kind == "percent":
        pattern = locale.percent_formats[None]
    else:
        pattern = locale.decimal_formats[None]

    # Default: use the pattern's own fraction digits (currency_digits for
    # currency). If digits are requested, override frac_prec on a copy so the
    # shared locale pattern is untouched, and drop currency_digits so the
    # override takes effect.
    currency_digits = True
    if min_fraction_digits is not None or max_fraction_digits is not None:
        low = min_fraction_digits if min_fraction_digits is not None else 0
        high = (
            max_fraction_digits
            if max_fraction_digits is not None
            else max(low, pattern.frac_prec[1])
        )
        pattern = copy.copy(pattern)
        pattern.frac_prec = (low, high)
        currency_digits = False

    return pattern.apply(
        number,
        locale,
        currency=currency,
        currency_digits=currency_digits,
        group_separator=grouping,
    )


def format_number(
    number: float | decimal.Decimal,
    *,
    min_fraction_digits: int | None = None,
    max_fraction_digits: int | None = None,
    grouping: bool = True,
    compact: bool = False,
) -> str:
    """Format a number in the active locale (server-side).

    Args:
        number: The number to format.
        min_fraction_digits: Minimum fraction digits.
        max_fraction_digits: Maximum fraction digits.
        grouping: Whether to show the grouping separator.
        compact: Whether to use compact notation (e.g. ``1.2M``); honors
            ``max_fraction_digits`` only.

    Returns:
        The localized number.
    """
    if compact:
        from babel import numbers

        return numbers.format_compact_decimal(
            float(number),
            locale=_babel_locale(),
            fraction_digits=max_fraction_digits or 0,
        )
    return _apply_number(
        "decimal",
        number,
        min_fraction_digits=min_fraction_digits,
        max_fraction_digits=max_fraction_digits,
        grouping=grouping,
    )


# Babel's canonical name; ``format_number`` is the friendlier alias.
format_decimal = format_number


def format_currency(
    number: float | decimal.Decimal,
    currency: str,
    *,
    min_fraction_digits: int | None = None,
    max_fraction_digits: int | None = None,
    grouping: bool = True,
) -> str:
    """Format a currency amount in the active locale (server-side).

    Args:
        number: The amount to format.
        currency: The ISO 4217 currency code (e.g. ``"EUR"``).
        min_fraction_digits: Minimum fraction digits (default: the currency's).
        max_fraction_digits: Maximum fraction digits (default: the currency's).
        grouping: Whether to show the grouping separator.

    Returns:
        The localized currency amount.
    """
    return _apply_number(
        "currency",
        number,
        min_fraction_digits=min_fraction_digits,
        max_fraction_digits=max_fraction_digits,
        grouping=grouping,
        currency=currency,
    )


def format_percent(
    number: float | decimal.Decimal,
    *,
    min_fraction_digits: int | None = None,
    max_fraction_digits: int | None = None,
    grouping: bool = True,
) -> str:
    """Format a ratio as a percentage in the active locale (``0.15`` -> ``15%``).

    Args:
        number: The ratio to format (``1`` == 100%).
        min_fraction_digits: Minimum fraction digits.
        max_fraction_digits: Maximum fraction digits.
        grouping: Whether to show the grouping separator.

    Returns:
        The localized percentage.
    """
    return _apply_number(
        "percent",
        number,
        min_fraction_digits=min_fraction_digits,
        max_fraction_digits=max_fraction_digits,
        grouping=grouping,
    )


def format_date(value: datetime.date, *, length: str = "medium") -> str:
    """Format a date in the active locale (server-side).

    Args:
        value: The ``date``/``datetime`` to format.
        length: The date length (``short``/``medium``/``long``/``full``).

    Returns:
        The localized date.
    """
    from babel import dates

    return dates.format_date(value, format=length, locale=_babel_locale())


def format_time(
    value: datetime.time | datetime.datetime, *, length: str = "medium"
) -> str:
    """Format a time in the active locale (server-side).

    Args:
        value: The ``time``/``datetime`` to format.
        length: The time length (``short``/``medium``/``long``/``full``).

    Returns:
        The localized time.
    """
    from babel import dates

    return dates.format_time(value, format=length, locale=_babel_locale())


def format_datetime(value: datetime.datetime, *, length: str = "medium") -> str:
    """Format a date and time in the active locale (server-side).

    Args:
        value: The ``datetime`` to format.
        length: The length (``short``/``medium``/``long``/``full``).

    Returns:
        The localized date and time.
    """
    from babel import dates

    return dates.format_datetime(value, format=length, locale=_babel_locale())


def _locale_dependency() -> Var | None:
    """The var a gettext-family call implies a dependency on.

    Returns:
        The active-locale var backing dynamic retranslation.
    """
    # Lazy import: registering this provider must not itself import .state (and
    # register I18nState); state is only needed once a real gettext computed
    # var invokes this during dependency scanning.
    from .state import I18nState

    return I18nState.locale


# Registered here rather than in :mod:`.state` so a computed var that calls
# gettext (or a ``format_*`` helper) gains its dependency on the active locale
# as soon as the app imports it — before (and independently of) I18nPlugin
# construction, which in a backend worker can happen after the getter's
# dependencies are scanned and cached. Registering only populates a dict; the
# provider imports state lazily. ``format_decimal`` is ``format_number``, so
# the tuple dedupes it.
register_implicit_dependency(
    (
        gettext,
        ngettext,
        pgettext,
        format_number,
        format_decimal,
        format_currency,
        format_percent,
        format_date,
        format_time,
        format_datetime,
    ),
    _locale_dependency,
)
