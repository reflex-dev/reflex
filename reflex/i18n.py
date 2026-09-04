"""Public internationalization API (provided by the ``reflex-i18n`` package).

Static component content is translated with ``rx.t``; dynamic (state) content
is translated server-side with ``gettext``/``ngettext``/``pgettext`` (aliased
``_``). Configure locales with ``I18nPlugin`` in ``rx.Config(plugins=[...])``.

Requires ``reflex-i18n`` to be installed (``pip install reflex-i18n``).
"""

from typing import TYPE_CHECKING, Any

try:
    from reflex_i18n import (
        LOCALE_COOKIE_NAME,
        I18nConfig,
        I18nPlugin,
        PathPrefixRouting,
        currency,
        format_currency,
        format_date,
        format_datetime,
        format_decimal,
        format_number,
        format_percent,
        format_time,
        gettext,
        language_switcher,
        locale_url,
        ngettext,
        number,
        percent,
        pgettext,
        t,
    )

    # Accessed as rx.i18n.date / .time / .datetime. Kept out of __all__ (below)
    # so `from reflex.i18n import *` cannot shadow the stdlib names; the alias
    # form marks these as intentional re-exports. Prefer attribute access.
    from reflex_i18n import date as date
    from reflex_i18n import datetime as datetime
    from reflex_i18n import time as time
except ImportError as e:  # pragma: no cover
    msg = (
        "The `reflex-i18n` package is required for i18n features (rx.t, "
        'rx.i18n). Install it with `pip install "reflex-i18n"`.'
    )
    raise ImportError(msg) from e

if TYPE_CHECKING:
    from reflex_i18n import I18nState as I18nState
    from reflex_i18n import locale as locale
    from reflex_i18n import set_locale as set_locale

_ = gettext

# "date", "datetime" and "time" are intentionally omitted: they are available
# as rx.i18n.date/.time/.datetime but excluded from `import *` so they cannot
# shadow the stdlib names.
__all__ = [
    "LOCALE_COOKIE_NAME",
    "I18nConfig",
    "I18nPlugin",
    "I18nState",
    "PathPrefixRouting",
    "currency",
    "format_currency",
    "format_date",
    "format_datetime",
    "format_decimal",
    "format_number",
    "format_percent",
    "format_time",
    "gettext",
    "language_switcher",
    "locale",
    "locale_url",
    "ngettext",
    "number",
    "percent",
    "pgettext",
    "set_locale",
    "t",
]

# reflex_i18n defers these so importing it does not import
# ``reflex_i18n.state`` (which registers ``I18nState`` as a global substate);
# mirror the deferral so importing this module stays side-effect free too.
_LAZY_ATTRS = frozenset({"I18nState", "locale", "set_locale"})


def __getattr__(name: str) -> Any:
    """Lazily resolve attributes deferred by the reflex_i18n package.

    Args:
        name: The attribute name.

    Returns:
        The resolved attribute.

    Raises:
        AttributeError: If the attribute is not part of the public API.
    """
    if name in _LAZY_ATTRS:
        import reflex_i18n

        return getattr(reflex_i18n, name)
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
