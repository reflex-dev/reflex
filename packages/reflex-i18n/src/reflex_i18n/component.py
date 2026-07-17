"""The app-wrap provider component backing client-side translations."""

from __future__ import annotations

from reflex_base.components.component import Component


class I18nProvider(Component):
    """Provides the active locale and message catalog via React context.

    Implemented in the static web template ``utils/i18n.js``; pulled into the
    app shell automatically (via ``VarData.app_wraps``) whenever ``rx.t`` is
    used.
    """

    library = "$/utils/i18n"

    tag = "I18nProvider"
