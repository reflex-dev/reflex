"""Internationalization (i18n) for Reflex apps.

Static (component) content is translated with :func:`t`; dynamic (state)
content is translated server-side with :func:`gettext` / :func:`ngettext` /
:func:`pgettext`. Configure locales with :class:`I18nPlugin` in
``rx.Config(plugins=[...])``.
"""

from typing import TYPE_CHECKING, Any

from .config import LOCALE_COOKIE_NAME, I18nConfig
from .plugin import I18nPlugin
from .runtime import gettext, ngettext, pgettext
from .vars import t

if TYPE_CHECKING:
    from .state import I18nState, set_locale

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

# Importing ``.state`` registers ``I18nState`` as a substate (a global side
# effect). Defer it so merely importing this package (e.g. the reflex CLI
# loading the ``reflex i18n`` entry point) does not attach i18n state to apps
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
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
