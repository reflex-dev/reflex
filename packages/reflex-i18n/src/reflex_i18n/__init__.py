"""Internationalization (i18n) for Reflex apps.

Static (component) content is translated with :func:`t`; dynamic (state)
content is translated server-side with :func:`gettext` / :func:`ngettext` /
:func:`pgettext`. Configure locales with :class:`I18nPlugin` in
``rx.Config(plugins=[...])``.
"""

from .config import LOCALE_COOKIE_NAME, I18nConfig
from .plugin import I18nPlugin
from .runtime import gettext, ngettext, pgettext
from .state import I18nState, set_locale
from .vars import t

# gettext alias, the conventional shorthand for marking translatable strings.
_ = gettext

__all__ = [
    "LOCALE_COOKIE_NAME",
    "I18nConfig",
    "I18nPlugin",
    "I18nState",
    "gettext",
    "ngettext",
    "pgettext",
    "set_locale",
    "t",
]
