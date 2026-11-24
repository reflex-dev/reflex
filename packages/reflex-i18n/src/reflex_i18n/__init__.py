"""Internationalization (i18n) for Reflex apps.

Static (component) content is translated with :func:`t`; dynamic (state)
content is translated server-side with :func:`gettext` / :func:`ngettext` /
:func:`pgettext`. Configure locales with :class:`I18nPlugin` in
``rx.Config(plugins=[...])``.
"""

from typing import TYPE_CHECKING, Any

from .config import (
    LOCALE_COOKIE_NAME,
    I18nConfig,
    configured_locales,
    normalize_locale,
    source_locale,
    validate_locale,
)

# date/datetime/time use the alias form and are omitted from __all__ so
# `from reflex_i18n import *` cannot shadow the stdlib names; they remain
# available as rx.i18n.date / .time / .datetime (prefer attribute access).
from .format import currency, language_name, number, percent, weekday
from .format import date as date
from .format import datetime as datetime
from .format import time as time
from .nav import language_switcher, locale_url
from .plugin import I18nPlugin
from .routing import PathPrefixRouting
from .runtime import (
    fallback_chain,
    format_currency,
    format_date,
    format_datetime,
    format_decimal,
    format_language,
    format_number,
    format_percent,
    format_time,
    format_weekday,
    get_locale,
    gettext,
    gettext_noop,
    match_locale,
    ngettext,
    pgettext,
    pick_translation,
    pick_translation_locale,
    use_locale,
)
from .vars import pick, pick_locale, t

if TYPE_CHECKING:
    from reflex_base.vars.sequence import StringVar

    from .state import I18nState, set_locale

    # The active locale as a client-side var; resolved lazily (see below).
    locale: StringVar

# The conventional gettext shorthands: ``_`` translates, ``N_`` only marks.
_ = gettext
N_ = gettext_noop

# "date", "datetime" and "time" are intentionally omitted (see the import
# above): reachable as rx.i18n.date/.time/.datetime but excluded from
# `import *` so they cannot shadow the stdlib names. "locale" is omitted for a
# different reason: `import *` resolves every exported name, and that one
# depends on whether an I18nPlugin is configured by the time it is built.
__all__ = [
    "LOCALE_COOKIE_NAME",
    "N_",
    "I18nConfig",
    "I18nPlugin",
    "I18nState",
    "PathPrefixRouting",
    "configured_locales",
    "currency",
    "fallback_chain",
    "format_currency",
    "format_date",
    "format_datetime",
    "format_decimal",
    "format_language",
    "format_number",
    "format_percent",
    "format_time",
    "format_weekday",
    "get_locale",
    "gettext",
    "gettext_noop",
    "language_name",
    "language_switcher",
    "locale_url",
    "match_locale",
    "ngettext",
    "normalize_locale",
    "number",
    "percent",
    "pgettext",
    "pick",
    "pick_locale",
    "pick_translation",
    "pick_translation_locale",
    "set_locale",
    "source_locale",
    "t",
    "use_locale",
    "validate_locale",
    "weekday",
]

# Importing ``.state`` registers ``I18nState`` as a substate (a global side
# effect). Defer it so merely importing this package (e.g. the reflex CLI
# loading the ``reflex i18n`` command) does not attach i18n state to apps
# that never use i18n; opting in via ``I18nPlugin`` or accessing these names
# does.
_LAZY_STATE_ATTRS = frozenset({"I18nState", "set_locale"})


def __getattr__(name: str) -> Any:
    """Lazily resolve state-registering attributes.

    Args:
        name: The attribute name.

    Returns:
        The resolved attribute.

    Raises:
        AttributeError: If the attribute is not part of the public API.
    """
    if name in _LAZY_STATE_ATTRS:
        from . import state

        return getattr(state, name)
    if name == "locale":
        from .format import locale_var

        return locale_var()
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
