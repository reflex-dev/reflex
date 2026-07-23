"""App-level i18n configuration."""

from __future__ import annotations

import dataclasses
from collections.abc import Sequence
from pathlib import Path

# Cookie persisting the user's chosen locale; read by both the client
# runtime and the server-side locale resolution.
LOCALE_COOKIE_NAME = "reflex_locale"


@dataclasses.dataclass(frozen=True)
class I18nConfig:
    """Internationalization configuration held by :class:`I18nPlugin`."""

    # Locales the app supports, e.g. ("en", "de"). Order is preserved for
    # Accept-Language negotiation ties.
    locales: tuple[str, ...]

    # The locale the source-text msgids are written in.
    default_locale: str = "en"

    # Directory (relative to the app root) containing {locale}.po catalogs.
    catalog_dir: str = "locales"

    def __init__(
        self,
        locales: Sequence[str],
        default_locale: str = "en",
        catalog_dir: str = "locales",
    ):
        """Initialize and validate the i18n configuration.

        Args:
            locales: Locales the app supports, e.g. ``["en", "de"]``.
            default_locale: The locale the source-text msgids are written in.
            catalog_dir: Directory (relative to the app root) containing
                ``{locale}.po`` catalogs.

        Raises:
            ValueError: If no locales are given or the default locale is not
                among them.
        """
        locales_tuple = tuple(locales)
        if not locales_tuple:
            msg = "I18nConfig.locales must contain at least one locale."
            raise ValueError(msg)
        if default_locale not in locales_tuple:
            msg = (
                f"I18nConfig.default_locale {default_locale!r} must be one of "
                f"the configured locales {locales_tuple!r}."
            )
            raise ValueError(msg)
        object.__setattr__(self, "locales", locales_tuple)
        object.__setattr__(self, "default_locale", default_locale)
        object.__setattr__(self, "catalog_dir", catalog_dir)


_active_config: I18nConfig | None = None

# Absolute catalog directory, captured when the app is constructed (cwd is the
# app root then). Used at compile and request time so catalog loading does not
# depend on the process cwd, which is not guaranteed to be the app root later.
_active_catalog_dir: Path | None = None


def set_active_i18n_config(config: I18nConfig | None) -> None:
    """Set the i18n configuration of the running app.

    Called by ``rx.App`` so server-side translation helpers can resolve
    locales without a reference to the app instance. Must be called while the
    current working directory is the app root (it is during app construction).

    Args:
        config: The configuration to activate, or None to deactivate.
    """
    global _active_config, _active_catalog_dir
    _active_config = config
    _active_catalog_dir = (
        (Path.cwd() / config.catalog_dir).resolve() if config is not None else None
    )


def get_active_i18n_config() -> I18nConfig | None:
    """Get the i18n configuration of the running app.

    Returns:
        The active configuration, or None if the app has no i18n config.
    """
    return _active_config


def get_active_catalog_dir() -> Path | None:
    """Get the absolute catalog directory of the running app.

    Returns:
        The absolute catalog directory, or None if i18n is not configured.
    """
    return _active_catalog_dir
