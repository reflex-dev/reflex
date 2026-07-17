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
        gettext,
        ngettext,
        pgettext,
        set_locale,
        t,
    )
except ImportError as e:  # pragma: no cover
    msg = (
        "The `reflex-i18n` package is required for i18n features (rx.t, "
        'rx.i18n). Install it with `pip install "reflex-i18n"`.'
    )
    raise ImportError(msg) from e

_ = gettext

__all__ = [
    "I18nConfig",
    "I18nPlugin",
    "I18nState",
    "gettext",
    "ngettext",
    "pgettext",
    "set_locale",
    "t",
]
