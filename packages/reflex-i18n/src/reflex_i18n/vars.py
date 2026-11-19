"""The ``rx.t`` translation var for static content and ``rx.i18n.pick`` for data."""

from __future__ import annotations

import functools
from collections.abc import Mapping
from typing import Any

from reflex_base.utils.imports import ImportVar
from reflex_base.vars.base import LiteralVar, Var, VarData
from reflex_base.vars.function import FunctionStringVar, FunctionVar, ReflexCallable
from reflex_base.vars.sequence import StringVar

from .component import _PROVIDER_PRIORITY, _provider
from .config import UNCONFIGURED_LOCALE, get_active_i18n_config
from .registry import MessageKey, register


@functools.cache
def _i18n_var_data() -> VarData:
    """VarData shared by all translation vars.

    Injects the ``useTranslation`` hook into any component using a
    translation and drags the ``I18nProvider`` into the app shell.

    Returns:
        The shared VarData.
    """
    return VarData(
        imports={"$/utils/i18n": [ImportVar(tag="useTranslation")]},
        hooks={"const [ t_, tp_ ] = useTranslation()": None},
        app_wraps=((_PROVIDER_PRIORITY, _provider()),),
    )


# ``useTranslation`` destructures to ``[t_, tp_]``; both take the catalog key
# and the ``{name}`` interpolation params, the plural form also taking the
# default-locale plural message and the count selecting it.
_Translate = ReflexCallable[[str, Mapping[str, Any]], str]
_TranslatePlural = ReflexCallable[[str, str, Any, Mapping[str, Any]], str]


@functools.cache
def _translate() -> FunctionVar[_Translate]:
    """The client-side message translator.

    Returns:
        The ``t_`` hook function as a callable Var.
    """
    return FunctionStringVar.create(
        "t_", _var_type=_Translate, _var_data=_i18n_var_data()
    )


@functools.cache
def _translate_plural() -> FunctionVar[_TranslatePlural]:
    """The client-side plural message translator.

    Returns:
        The ``tp_`` hook function as a callable Var.
    """
    return FunctionStringVar.create(
        "tp_", _var_type=_TranslatePlural, _var_data=_i18n_var_data()
    )


# Without an I18nPlugin there is no client runtime: pick the source form by the
# generic plural rule and interpolate like the runtime does.
_InterpolateSource = ReflexCallable[[str, str | None, Any, Mapping[str, Any]], str]
_INTERPOLATE_SOURCE: FunctionVar[_InterpolateSource] = FunctionStringVar.create(
    "((message, plural, count, params) => "
    "(plural !== null && count != 1 ? plural : message)"
    ".replace(/\\{(\\w+)\\}/g, (match, name) => "
    "name in params ? String(params[name]) : match))",
    _var_type=_InterpolateSource,
)


def _source_text(
    message: str, plural: str | None, count: Any, params: dict[str, Any]
) -> StringVar:
    """The message as an app without an I18nPlugin renders it.

    Args:
        message: The singular source message.
        plural: The plural source message, if any.
        count: The quantity selecting the plural form, if any.
        params: Values for ``{name}`` placeholders, including ``count``.

    Returns:
        The source text, interpolated client-side when it has parameters.
    """
    if plural is None and not params:
        return LiteralVar.create(message).to(str)
    return _INTERPOLATE_SOURCE.call(
        message, plural, count, LiteralVar.create(params)
    ).to(str)


def t(
    message: str,
    /,
    *,
    plural: str | None = None,
    count: int | Var[int] | None = None,
    context: str | None = None,
    **params: Any,
) -> StringVar:
    """Translate a static message via the client-side locale catalog.

    The message text is the msgid in the default locale; translations are
    looked up at runtime from the active locale's catalog, falling back to
    the message itself. ``{name}``-style placeholders are interpolated
    client-side from ``params``, so params may be state Vars. Without an
    I18nPlugin (e.g. a library used by an app that does not translate), the
    source text renders as is.

    Args:
        message: The message in the default locale. Must be a string known
            when the component is built (not a Var) so it is collected into
            catalogs at compile time; a constant marked with ``N_`` works.
        plural: The plural form of the message in the default locale.
        count: The quantity selecting the plural form. Required with
            ``plural``, and implicitly available as the ``{count}``
            placeholder.
        context: Optional gettext msgctxt to disambiguate identical messages.
        **params: Values for ``{name}`` placeholders in the message.

    Returns:
        A StringVar resolving to the translated, interpolated message.

    Raises:
        TypeError: If message, plural or context is not a literal string.
        ValueError: If only one of ``plural`` and ``count`` is given, or the
            message was already used with a different plural form.
    """
    if isinstance(message, Var) or not isinstance(message, str):
        msg = (
            "rx.t() requires a literal string message so it can be extracted "
            "into translation catalogs at compile time. To translate dynamic "
            "content, translate it server-side in state instead "
            "(see reflex.i18n)."
        )
        raise TypeError(msg)
    for name, value in (("plural", plural), ("context", context)):
        if value is not None and (isinstance(value, Var) or not isinstance(value, str)):
            msg = f"rx.t() requires a literal string for {name}."
            raise TypeError(msg)
    if (plural is None) != (count is None):
        msg = "rx.t() requires count and plural to be passed together."
        raise ValueError(msg)

    # An empty context is no context (gettext has no empty msgctxt).
    key = MessageKey(message=message, plural=plural, context=context or None)
    translated = get_active_i18n_config() is not None
    register(key, translated=translated)

    if plural is not None:
        params.setdefault("count", count)
    if not translated:
        return _source_text(message, plural, count, params)
    params_var = LiteralVar.create(params)

    if plural is None:
        return _translate().call(key.catalog_key, params_var).to(str)

    return _translate_plural().call(key.catalog_key, plural, count, params_var).to(str)


@functools.cache
def _pick_var_data() -> VarData:
    """VarData for the pick vars: the ``usePick`` hook and the provider.

    Returns:
        The shared VarData.
    """
    return VarData(
        imports={"$/utils/i18n": [ImportVar(tag="usePick")]},
        hooks={"const [ pick_, pickLocale_ ] = usePick()": None},
        app_wraps=((_PROVIDER_PRIORITY, _provider()),),
    )


# ``usePick`` destructures to ``[pick_, pickLocale_]``; both take the
# ``{locale: text}`` mapping and the wanted locale (null for the active one).
_Pick = ReflexCallable[[Mapping[str, str], str | None], str]


@functools.cache
def _pick() -> FunctionVar[_Pick]:
    """The client-side text picker.

    Returns:
        The ``pick_`` hook function as a callable Var.
    """
    return FunctionStringVar.create(
        "pick_", _var_type=_Pick, _var_data=_pick_var_data()
    )


@functools.cache
def _pick_locale() -> FunctionVar[_Pick]:
    """The client-side picker of the locale whose text to show.

    Returns:
        The ``pickLocale_`` hook function as a callable Var.
    """
    return FunctionStringVar.create(
        "pickLocale_", _var_type=_Pick, _var_data=_pick_var_data()
    )


# Without an I18nPlugin there is no client runtime: pick as
# pick_translation_locale does, from the fallback chain of the wanted locale
# alone, which is all that chain holds without a configuration.
_SOURCE_PICK_LOCALE_JS = (
    "((translations, locale) => { "
    "const keys = Object.keys(translations ?? {}).filter("
    '(key) => String(translations[key] ?? "").trim() !== ""); '
    f'const wanted = String(locale ?? "{UNCONFIGURED_LOCALE}").toLowerCase(); '
    "return keys.find((key) => key.toLowerCase() === wanted) "
    '?? keys.find((key) => key.toLowerCase().split("-")[0] === wanted.split("-")[0]) '
    '?? keys[0] ?? ""; })'
)
_SOURCE_PICK_LOCALE: FunctionVar[_Pick] = FunctionStringVar.create(
    _SOURCE_PICK_LOCALE_JS, _var_type=_Pick
)
_SOURCE_PICK: FunctionVar[_Pick] = FunctionStringVar.create(
    "((translations, locale) => { "
    f"const key = {_SOURCE_PICK_LOCALE_JS}(translations, locale); "
    'return key === "" ? "" : translations[key]; })',
    _var_type=_Pick,
)


def pick(
    translations: Var[Mapping[str, str]] | Mapping[str, str],
    locale: Var[str] | str | None = None,
) -> StringVar:
    """Show the text of a ``{locale: text}`` mapping in the active locale.

    For translated data, such as a database field holding a text per
    language. Falls back along the locale's fallback chain like
    :func:`~reflex_i18n.runtime.pick_translation`, and re-picks instantly when
    the locale changes.

    Args:
        translations: The texts by locale.
        locale: The wanted locale; the active one if None.

    Returns:
        A StringVar resolving to the picked text, or ``""`` if there is none.
    """
    function = _pick() if get_active_i18n_config() is not None else _SOURCE_PICK
    return function.call(translations, locale).to(str)


def pick_locale(
    translations: Var[Mapping[str, str]] | Mapping[str, str],
    locale: Var[str] | str | None = None,
) -> StringVar:
    """The locale whose text :func:`pick` shows, e.g. for an element's ``lang``.

    Args:
        translations: The texts by locale.
        locale: The wanted locale; the active one if None.

    Returns:
        A StringVar resolving to the picked locale, or ``""`` if there is no
        text.
    """
    function = (
        _pick_locale() if get_active_i18n_config() is not None else _SOURCE_PICK_LOCALE
    )
    return function.call(translations, locale).to(str)
