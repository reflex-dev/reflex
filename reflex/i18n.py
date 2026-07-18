"""Public internationalization API (provided by the ``reflex-i18n`` package).

Static component content is translated with ``rx.t``; dynamic (state) content
is translated server-side with ``gettext``/``ngettext``/``pgettext`` (aliased
``_``). Configure locales with ``I18nPlugin`` in ``rx.Config(plugins=[...])``.

Requires ``reflex-i18n`` to be installed (``pip install reflex-i18n``).
"""

try:
    from reflex_i18n import (
        I18nConfig,
        I18nPlugin,
        I18nState,
        currency,
        format_currency,
        format_date,
        format_datetime,
        format_decimal,
        format_number,
        format_percent,
        format_time,
        gettext,
        locale,
        ngettext,
        number,
        percent,
        pgettext,
        set_locale,
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

_ = gettext

# "date", "datetime" and "time" are intentionally omitted: they are available
# as rx.i18n.date/.time/.datetime but excluded from `import *` so they cannot
# shadow the stdlib names.
__all__ = [
    "I18nConfig",
    "I18nPlugin",
    "I18nState",
    "currency",
    "format_currency",
    "format_date",
    "format_datetime",
    "format_decimal",
    "format_number",
    "format_percent",
    "format_time",
    "gettext",
    "locale",
    "ngettext",
    "number",
    "percent",
    "pgettext",
    "set_locale",
    "t",
]
