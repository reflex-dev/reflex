"""The ``rx.t`` translation var for static component content."""

from __future__ import annotations

import functools
from typing import Any

from reflex_base.utils.imports import ImportVar
from reflex_base.vars.base import LiteralVar, Var, VarData
from reflex_base.vars.function import FunctionVar
from reflex_base.vars.sequence import StringVar

from .component import I18nProvider
from .config import get_active_i18n_config
from .registry import MessageKey, register

# Outside the ErrorBoundary (55) so error fallback UI can translate too.
_PROVIDER_PRIORITY = 58


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
        app_wraps=((_PROVIDER_PRIORITY, I18nProvider.create()),),
    )


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
    client-side from ``params``, so params may be state Vars.

    Args:
        message: The message in the default locale. Must be a literal string
            so it can be extracted into catalogs at compile time.
        plural: The plural form of the message in the default locale.
        count: The quantity selecting the plural form. Required with
            ``plural``, and implicitly available as the ``{count}``
            placeholder.
        context: Optional gettext msgctxt to disambiguate identical messages.
        **params: Values for ``{name}`` placeholders in the message.

    Returns:
        A StringVar resolving to the translated, interpolated message.

    Raises:
        TypeError: If message or plural is not a literal string.
        ValueError: If only one of ``plural`` and ``count`` is given.
        RuntimeError: If no I18nPlugin is configured.
    """
    if get_active_i18n_config() is None:
        msg = (
            "rx.t() requires the i18n plugin. Add "
            "I18nPlugin(locales=[...]) to rx.Config(plugins=[...])."
        )
        raise RuntimeError(msg)
    if isinstance(message, Var) or not isinstance(message, str):
        msg = (
            "rx.t() requires a literal string message so it can be extracted "
            "into translation catalogs at compile time. To translate dynamic "
            "content, translate it server-side in state instead "
            "(see reflex.i18n)."
        )
        raise TypeError(msg)
    if plural is not None and (isinstance(plural, Var) or not isinstance(plural, str)):
        msg = "rx.t() requires a literal string for plural."
        raise TypeError(msg)
    if (plural is None) != (count is None):
        msg = "rx.t() requires count and plural to be passed together."
        raise ValueError(msg)

    key = MessageKey(message=message, plural=plural, context=context)
    register(key)

    if plural is not None:
        params.setdefault("count", count)
    params_var = LiteralVar.create(params)
    var_data = _i18n_var_data()

    if plural is None:
        translate = Var(_js_expr="t_", _var_data=var_data).to(FunctionVar)
        return translate.call(key.catalog_key, params_var).to(str)

    translate_plural = Var(_js_expr="tp_", _var_data=var_data).to(FunctionVar)
    return translate_plural.call(key.catalog_key, plural, count, params_var).to(str)
