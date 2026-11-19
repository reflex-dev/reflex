"""The ``rx.t`` translation var for static component content."""

from __future__ import annotations

import functools
from collections.abc import Mapping
from typing import Any

from reflex_base.utils.imports import ImportVar
from reflex_base.vars.base import LiteralVar, Var, VarData
from reflex_base.vars.function import FunctionStringVar, FunctionVar, ReflexCallable
from reflex_base.vars.sequence import StringVar

from .component import _PROVIDER_PRIORITY, _provider
from .config import get_active_i18n_config
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
