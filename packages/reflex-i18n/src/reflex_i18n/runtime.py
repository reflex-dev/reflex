"""Server-side translation of dynamic (state) content via gettext.

Event handlers and computed vars call :func:`gettext` (aliased ``_``) to
translate strings in the active locale. The active locale is held in a
contextvar set per client while events are processed; translating in a
computed var means the string is retranslated and re-pushed as a delta
whenever the locale changes.
"""

from __future__ import annotations

import copy
import functools
import gettext as _gettext_module
import io
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from contextlib import AbstractContextManager, contextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING, Literal

from reflex_base.vars.dep_tracking import register_implicit_dependency

from .config import check_configured_locale, get_active_i18n_config, source_locale

if TYPE_CHECKING:
    import datetime
    import decimal

    from babel.messages.catalog import Catalog
    from reflex_base.vars.base import Var

# The locale in effect for the current client while an event is processed.
_active_locale: ContextVar[str | None] = ContextVar(
    "reflex_active_locale", default=None
)

# Lazily-built gettext translators, keyed by locale.
_translations: dict[str, _gettext_module.NullTranslations] = {}


@contextmanager
def active_locale(locale: str | None) -> Iterator[None]:
    """Set the active locale for the duration of the context, unchecked.

    The event scope enters a client's resolved locale with it; a client session
    may still hold a locale a later deploy removed from the config.

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


def use_locale(locale: str | None) -> AbstractContextManager[None]:
    """Translate and format in a locale for the duration of the context.

    Events already run in their client's locale; use this where there is no
    client, e.g. a background job writing a report for a user.

    Args:
        locale: The locale to activate, or None to leave translations
            untranslated.

    Returns:
        A context manager activating the locale.

    Raises:
        ValueError: If the locale is not one of the configured locales.
    """
    if locale is not None:
        check_configured_locale(locale)
    return active_locale(locale)


def get_locale() -> str | None:
    """Get the active locale: the client's during an event, else ``use_locale``'s.

    Returns:
        The active locale, or None if none is set.
    """
    return _active_locale.get()


class _CatalogTranslations(_gettext_module.GNUTranslations):
    """A catalog's translator, picking plurals by the rule the client compiles."""

    def __init__(self, catalog: Catalog) -> None:
        """Compile the catalog into a gettext translator.

        Args:
            catalog: The catalog from ``load_catalog``.
        """
        from babel.messages.mofile import write_mo

        buffer = io.BytesIO()
        write_mo(buffer, catalog)
        buffer.seek(0)
        super().__init__(buffer)
        # Babel leaves Plural-Forms out of the .mo for a locale it has no data for.
        self.plural = _gettext_module.c2py(catalog.plural_expr)


class _SourceTranslations(_gettext_module.NullTranslations):
    """Pass-through translator picking source plurals by the default locale's rule.

    The source messages are written in the default locale, and the client picks
    an untranslated plural by that rule too (``defaultPlural``).
    """

    def __init__(self, plural: Callable[[int], int]) -> None:
        """Create the translator.

        Args:
            plural: The default locale's plural rule, from n to a form index.
        """
        super().__init__()
        self._plural = plural

    def ngettext(self, msgid1: str, msgid2: str, n: int) -> str:
        """Pick a source message by the default locale's plural rule.

        Args:
            msgid1: The singular source message.
            msgid2: The plural source message.
            n: The quantity selecting the form.

        Returns:
            The singular message for form 0, else the plural one.
        """
        return msgid1 if self._plural(n) == 0 else msgid2


@functools.cache
def _source_translations() -> _SourceTranslations:
    """The fallback for messages no catalog translates.

    Returns:
        A pass-through translator using the default locale's plural rule.
    """
    from .catalog import default_plural_expr_js, load_catalog

    locale = source_locale()
    catalog = load_catalog(locale)
    # The expression the client's defaultPlural evaluates, in C syntax.
    plural = _gettext_module.c2py(default_plural_expr_js(catalog, locale))
    return _SourceTranslations(plural)


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

    from .catalog import load_catalog

    catalog = load_catalog(locale)
    translations = (
        _gettext_module.NullTranslations()
        if catalog is None
        else _CatalogTranslations(catalog)
    )

    translations.add_fallback(_source_translations())
    _translations[locale] = translations
    return translations


def clear_translations_cache() -> None:
    """Drop cached translators. Intended for tests and hot reload."""
    _translations.clear()
    _source_translations.cache_clear()


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
        The translated message for ``n``, or the source message the default
        locale's plural rule picks if untranslated or no locale is active.
    """
    locale = _active_locale.get()
    translations = (
        _source_translations() if locale is None else _get_translations(locale)
    )
    return translations.ngettext(singular, plural, n)


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


def gettext_noop(message: str) -> str:
    """Mark a message for extraction without translating it (aliased ``N_``).

    For text defined before any locale is known, such as a module-level
    constant or an enum label: ``reflex i18n extract`` picks the literal up
    here, and the code translates the value later with ``gettext`` or ``rx.t``.

    Args:
        message: The source-locale message.

    Returns:
        The message, unchanged.
    """
    return message


def match_locale(requested: Iterable[str], supported: Iterable[str]) -> str | None:
    """Find the supported locale that best serves a list of requested ones.

    For each requested tag in turn: the supported locale with the same tag,
    else the first one with the same primary language (``de-AT`` -> ``de``).
    Tags compare case-insensitively (RFC 5646).

    Args:
        requested: The wanted locales, most wanted first.
        supported: The locales on offer.

    Returns:
        The matching locale in its supported spelling, or None.
    """
    by_tag: dict[str, str] = {}
    by_language: dict[str, str] = {}
    for locale in supported:
        tag = locale.lower()
        by_tag[tag] = locale
        by_language.setdefault(tag.split("-")[0], locale)
    for tag in requested:
        lowered = tag.lower()
        match = by_tag.get(lowered) or by_language.get(lowered.split("-")[0])
        if match is not None:
            return match
    return None


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
    ranked: list[tuple[float, int, str]] = []
    for index, entry in enumerate(accept_language.split(",")):
        tag, _, params = entry.strip().partition(";")
        tag = tag.strip().replace("_", "-").lower()
        if not tag or tag == "*":
            continue
        quality = 1.0
        params = params.strip()
        # The parameter name is case-insensitive (RFC 7231 §5.3.1).
        if params[:2].lower() == "q=":
            try:
                quality = float(params[2:])
            except ValueError:
                quality = 0.0
        if not 0.0 < quality <= 1.0:
            # q=0 means "not acceptable" (RFC 7231 §5.3.1); anything outside
            # 0..1 (or NaN) is malformed. Exclude both.
            continue
        # Sort by quality descending, then by original order for ties.
        ranked.append((-quality, index, tag))

    return match_locale((tag for _, _, tag in sorted(ranked)), supported) or default


def fallback_chain(locale: str | None = None) -> tuple[str, ...]:
    """The locales to try, in order, for content wanted in a locale.

    The locale itself, then the source locale, the fallback locale and the
    other configured locales.

    Args:
        locale: The wanted locale; the active one (else the source locale) if
            None.

    Returns:
        The locales, without case-insensitive duplicates.
    """
    wanted = locale or get_locale() or source_locale()
    config = get_active_i18n_config()
    if config is None:
        return (wanted,)
    chain: dict[str, str] = {}
    for candidate in (
        wanted,
        config.default_locale,
        config.fallback_locale,
        *config.locales,
    ):
        chain.setdefault(candidate.lower(), candidate)
    return tuple(chain.values())


def pick_translation_locale(
    translations: Mapping[str, str], locale: str | None = None
) -> str | None:
    """The locale whose text to show from a ``{locale: text}`` mapping.

    The best match for the fallback chain of the wanted locale among the
    locales with text, else the first locale with text.

    Args:
        translations: The texts by locale, e.g. a translated database field.
        locale: The wanted locale; the active one (else the source locale) if
            None.

    Returns:
        A key of ``translations``, or None if no text is there.
    """
    available = [key for key, text in translations.items() if text.strip()]
    if not available:
        return None
    return match_locale(fallback_chain(locale), available) or available[0]


def pick_translation(
    translations: Mapping[str, str], locale: str | None = None
) -> str | None:
    """The text to show from a ``{locale: text}`` mapping.

    Args:
        translations: The texts by locale, e.g. a translated database field.
        locale: The wanted locale; the active one (else the source locale) if
            None.

    Returns:
        The text :func:`pick_translation_locale` chooses, or None.
    """
    key = pick_translation_locale(translations, locale)
    return None if key is None else translations[key]


def _format_locale() -> str:
    """The locale to format in: active locale, else the default, else ``en``.

    Returns:
        The locale code for server-side formatting.
    """
    locale = _active_locale.get()
    return locale if locale is not None else source_locale()


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
            number,
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


def format_language(locale: str) -> str:
    """Name a language in the active locale (server-side), e.g. ``Englisch``.

    Args:
        locale: The language tag to name, e.g. ``"pt-BR"``.

    Returns:
        The language's name, e.g. ``Portugiesisch (Brasilien)``, or the tag
        itself for a language Babel does not know.
    """
    from babel import Locale, UnknownLocaleError

    try:
        name = Locale.parse(locale.replace("-", "_")).get_display_name(_babel_locale())
    except (ValueError, UnknownLocaleError):
        return locale
    return name or locale


# The lengths of a weekday's name, as ``Intl.DateTimeFormat``'s ``weekday``
# option spells them.
WeekdayLength = Literal["long", "short", "narrow"]

# The Babel width of each weekday length.
_WEEKDAY_WIDTHS: dict[WeekdayLength, Literal["wide", "abbreviated", "narrow"]] = {
    "long": "wide",
    "short": "abbreviated",
    "narrow": "narrow",
}


def format_weekday(day: int, *, length: WeekdayLength = "long") -> str:
    """Name a weekday in the active locale (server-side), e.g. ``Montag``.

    Args:
        day: The weekday, 0 for Monday as ``datetime.date.weekday()`` counts.
        length: ``long``, ``short`` or ``narrow``.

    Returns:
        The weekday's name as it stands on its own (not inside a date).
    """
    from babel import dates

    names = dates.get_day_names(
        _WEEKDAY_WIDTHS[length], context="stand-alone", locale=_babel_locale()
    )
    return names[day]


def _locale_dependency() -> Var | None:
    """The var a gettext-family call implies a dependency on.

    Returns:
        The active-locale var backing dynamic retranslation.
    """
    # Lazy import: registering this provider must not itself import .state (and
    # register I18nState); state is only needed once a real gettext computed
    # var invokes this during dependency scanning.
    from .state import I18nState, _register_in_active_context

    # A getter can be scanned before this app's I18nPlugin is built, under a
    # context the plugin has not registered I18nState in yet.
    _register_in_active_context()
    return I18nState.locale


# Registered here rather than in :mod:`.state` so a computed var that calls
# gettext (or a ``format_*`` or pick helper) gains its dependency on the active locale
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
        fallback_chain,
        pick_translation,
        pick_translation_locale,
        format_number,
        format_decimal,
        format_currency,
        format_percent,
        format_date,
        format_time,
        format_datetime,
        format_language,
        format_weekday,
    ),
    _locale_dependency,
)
