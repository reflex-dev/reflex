"""Client-side, locale-aware number and date formatting vars.

``rx.i18n.number`` / ``rx.i18n.currency`` / ``rx.i18n.date`` (and friends)
format a value in the active locale using the browser's ``Intl`` API,
reactively reformatting when the locale changes. To format inside state
(server-side), use the ``format_*`` helpers in :mod:`reflex_i18n.runtime`.
"""

from __future__ import annotations

import functools
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from reflex_base.utils.imports import ImportVar
from reflex_base.vars.base import LiteralVar, Var, VarData
from reflex_base.vars.function import FunctionStringVar, FunctionVar, ReflexCallable
from reflex_base.vars.sequence import StringVar

from .component import _PROVIDER_PRIORITY, I18nProvider
from .config import get_active_i18n_config

if TYPE_CHECKING:
    # Aliased so the `date`/`time`/`datetime` functions below don't shadow it.
    import datetime as _datetime


def _require_config() -> None:
    """Ensure the i18n plugin is configured.

    Raises:
        RuntimeError: If no I18nPlugin is configured.
    """
    if get_active_i18n_config() is None:
        msg = (
            "rx.i18n formatting requires the i18n plugin. Add "
            "I18nPlugin(locales=[...]) to rx.Config(plugins=[...])."
        )
        raise RuntimeError(msg)


@functools.cache
def _format_var_data() -> VarData:
    """VarData injecting the ``useFormat`` hook and the provider.

    Returns:
        The shared VarData for number/date formatting vars.
    """
    return VarData(
        imports={"$/utils/i18n": [ImportVar(tag="useFormat")]},
        hooks={"const [ fmtNumber, fmtDate ] = useFormat()": None},
        app_wraps=((_PROVIDER_PRIORITY, I18nProvider.create()),),
    )


@functools.cache
def _locale_var_data() -> VarData:
    """VarData injecting the ``useLocale`` hook and the provider.

    Returns:
        The shared VarData for the active-locale var.
    """
    return VarData(
        imports={"$/utils/i18n": [ImportVar(tag="useLocale")]},
        hooks={"const i18nLocale = useLocale()": None},
        app_wraps=((_PROVIDER_PRIORITY, I18nProvider.create()),),
    )


# ``useFormat`` destructures to ``[fmtNumber, fmtDate]``; each takes the value
# to format and an ``Intl`` options object, and returns the formatted string.
_Formatter = ReflexCallable[[Any, Mapping[str, Any]], str]


@functools.cache
def _fmt_number() -> FunctionVar[_Formatter]:
    """The client-side number formatter for the active locale.

    Returns:
        The ``fmtNumber`` hook function as a callable Var.
    """
    return FunctionStringVar.create(
        "fmtNumber", _var_type=_Formatter, _var_data=_format_var_data()
    )


@functools.cache
def _fmt_date() -> FunctionVar[_Formatter]:
    """The client-side date formatter for the active locale.

    Returns:
        The ``fmtDate`` hook function as a callable Var.
    """
    return FunctionStringVar.create(
        "fmtDate", _var_type=_Formatter, _var_data=_format_var_data()
    )


def _number_options(
    *,
    style: str | None = None,
    currency: str | None = None,
    min_fraction_digits: int | None = None,
    max_fraction_digits: int | None = None,
    grouping: bool | None = None,
    compact: bool = False,
    options: dict[str, Any] | None = None,
) -> Var[Mapping[str, Any]]:
    """Build the ``Intl.NumberFormat`` options object from curated kwargs.

    Args:
        style: The Intl number style (``decimal``/``currency``/``percent``).
        currency: The ISO 4217 currency code (for ``style="currency"``).
        min_fraction_digits: Minimum fraction digits.
        max_fraction_digits: Maximum fraction digits.
        grouping: Whether to show the grouping (thousands) separator.
        compact: Whether to use compact notation (e.g. ``1.2M``).
        options: Raw ``Intl.NumberFormat`` options, merged last.

    Returns:
        The Intl options object as a Var.
    """
    opts: dict[str, Any] = {}
    if style is not None:
        opts["style"] = style
    if currency is not None:
        opts["currency"] = currency
    if min_fraction_digits is not None:
        opts["minimumFractionDigits"] = min_fraction_digits
    if max_fraction_digits is not None:
        opts["maximumFractionDigits"] = max_fraction_digits
    if grouping is not None:
        opts["useGrouping"] = grouping
    if compact:
        opts["notation"] = "compact"
    if options:
        opts.update(options)
    return LiteralVar.create(opts)


def number(
    value: Var[Any] | int | float,
    *,
    min_fraction_digits: int | None = None,
    max_fraction_digits: int | None = None,
    grouping: bool | None = None,
    compact: bool = False,
    options: dict[str, Any] | None = None,
) -> StringVar:
    """Format a number in the active locale.

    Args:
        value: The number to format.
        min_fraction_digits: Minimum fraction digits.
        max_fraction_digits: Maximum fraction digits.
        grouping: Whether to show the grouping separator.
        compact: Whether to use compact notation (e.g. ``1.2M``).
        options: Raw ``Intl.NumberFormat`` options, merged last.

    Returns:
        A StringVar resolving to the localized number.
    """
    _require_config()
    opts = _number_options(
        min_fraction_digits=min_fraction_digits,
        max_fraction_digits=max_fraction_digits,
        grouping=grouping,
        compact=compact,
        options=options,
    )
    return _fmt_number().call(value, opts).to(str)


def currency(
    value: Var[Any] | int | float,
    currency: str,
    *,
    min_fraction_digits: int | None = None,
    max_fraction_digits: int | None = None,
    grouping: bool | None = None,
    compact: bool = False,
    options: dict[str, Any] | None = None,
) -> StringVar:
    """Format a currency amount in the active locale.

    Args:
        value: The amount to format.
        currency: The ISO 4217 currency code (e.g. ``"EUR"``).
        min_fraction_digits: Minimum fraction digits.
        max_fraction_digits: Maximum fraction digits.
        grouping: Whether to show the grouping separator.
        compact: Whether to use compact notation.
        options: Raw ``Intl.NumberFormat`` options, merged last.

    Returns:
        A StringVar resolving to the localized currency amount.
    """
    _require_config()
    opts = _number_options(
        style="currency",
        currency=currency,
        min_fraction_digits=min_fraction_digits,
        max_fraction_digits=max_fraction_digits,
        grouping=grouping,
        compact=compact,
        options=options,
    )
    return _fmt_number().call(value, opts).to(str)


def percent(
    value: Var[Any] | int | float,
    *,
    min_fraction_digits: int | None = None,
    max_fraction_digits: int | None = None,
    grouping: bool | None = None,
    options: dict[str, Any] | None = None,
) -> StringVar:
    """Format a ratio as a percentage in the active locale (``0.15`` -> ``15%``).

    Args:
        value: The ratio to format (``1`` == 100%).
        min_fraction_digits: Minimum fraction digits.
        max_fraction_digits: Maximum fraction digits.
        grouping: Whether to show the grouping separator.
        options: Raw ``Intl.NumberFormat`` options, merged last.

    Returns:
        A StringVar resolving to the localized percentage.
    """
    _require_config()
    opts = _number_options(
        style="percent",
        min_fraction_digits=min_fraction_digits,
        max_fraction_digits=max_fraction_digits,
        grouping=grouping,
        options=options,
    )
    return _fmt_number().call(value, opts).to(str)


# ``Intl.DateTimeFormat`` throws when ``dateStyle``/``timeStyle`` are combined
# with any of these per-component options, so the curated ``length`` gives way
# when the escape hatch spells the format out field by field.
_DATE_COMPONENT_OPTIONS = frozenset({
    "weekday",
    "era",
    "year",
    "month",
    "day",
    "dayPeriod",
    "hour",
    "minute",
    "second",
    "fractionalSecondDigits",
    "timeZoneName",
})


def _date_options(
    *,
    date_style: str | None = None,
    time_style: str | None = None,
    options: dict[str, Any] | None = None,
) -> Var[Mapping[str, Any]]:
    """Build the ``Intl.DateTimeFormat`` options object from curated kwargs.

    Args:
        date_style: The Intl ``dateStyle`` (``short``/``medium``/``long``/``full``).
        time_style: The Intl ``timeStyle``.
        options: Raw ``Intl.DateTimeFormat`` options, merged last.

    Returns:
        The Intl options object as a Var.
    """
    opts: dict[str, Any] = {}
    if not (options and _DATE_COMPONENT_OPTIONS.intersection(options)):
        if date_style is not None:
            opts["dateStyle"] = date_style
        if time_style is not None:
            opts["timeStyle"] = time_style
    if options:
        opts.update(options)
    return LiteralVar.create(opts)


def date(
    value: Var[Any] | _datetime.date | str,
    *,
    length: str = "medium",
    options: dict[str, Any] | None = None,
) -> StringVar:
    """Format a date in the active locale.

    Args:
        value: The date to format (a Var or ISO string).
        length: The date length (``short``/``medium``/``long``/``full``).
        options: Raw ``Intl.DateTimeFormat`` options, merged last.

    Returns:
        A StringVar resolving to the localized date.
    """
    _require_config()
    return (
        _fmt_date()
        .call(value, _date_options(date_style=length, options=options))
        .to(str)
    )


def time(
    value: Var[Any] | _datetime.time | str,
    *,
    length: str = "medium",
    options: dict[str, Any] | None = None,
) -> StringVar:
    """Format a time in the active locale.

    Args:
        value: The time to format (a Var or ISO string).
        length: The time length (``short``/``medium``/``long``/``full``).
        options: Raw ``Intl.DateTimeFormat`` options, merged last.

    Returns:
        A StringVar resolving to the localized time.
    """
    _require_config()
    return (
        _fmt_date()
        .call(value, _date_options(time_style=length, options=options))
        .to(str)
    )


def datetime(
    value: Var[Any] | _datetime.datetime | str,
    *,
    length: str = "medium",
    options: dict[str, Any] | None = None,
) -> StringVar:
    """Format a date and time in the active locale.

    Args:
        value: The datetime to format (a Var or ISO string).
        length: The length (``short``/``medium``/``long``/``full``).
        options: Raw ``Intl.DateTimeFormat`` options, merged last.

    Returns:
        A StringVar resolving to the localized date and time.
    """
    _require_config()
    opts = _date_options(date_style=length, time_style=length, options=options)
    return _fmt_date().call(value, opts).to(str)


@functools.cache
def _locale_var() -> StringVar:
    """Build the active-locale var (cached singleton).

    Returns:
        A StringVar resolving to the active locale code.
    """
    _require_config()
    return Var(_js_expr="i18nLocale", _var_data=_locale_var_data()).to(str)
