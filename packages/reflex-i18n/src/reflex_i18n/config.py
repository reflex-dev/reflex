"""App-level i18n configuration."""

from __future__ import annotations

import contextlib
import dataclasses
import importlib.util
import os
import re
from collections.abc import Iterator, Sequence
from pathlib import Path

# Cookie persisting the user's chosen locale; read by both the client
# runtime and the server-side locale resolution.
LOCALE_COOKIE_NAME = "reflex_locale"

# The locale an app without an I18nPlugin renders and formats in, server-side
# and client-side alike.
UNCONFIGURED_LOCALE = "en"

# The directory inside a package holding the catalogs it ships.
PACKAGE_CATALOG_DIR = "locales"

# A BCP 47-shaped tag: alphabetic language, optional alphanumeric subtags.
# Locales double as URL path segments, JS catalog identifiers and `Intl` /
# `Accept-Language` tags, all of which are hyphen-separated, so the underscore
# spelling is rejected rather than normalized in each of those places. Babel's
# underscore form is derived internally where it is needed.
_LOCALE_RE = re.compile(r"^[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*$")


def validate_locale(locale: str) -> None:
    """Check that a locale is a usable language tag.

    Args:
        locale: The locale to check.

    Raises:
        ValueError: If the locale is not a hyphen-separated language tag.
    """
    if not _LOCALE_RE.fullmatch(locale):
        msg = (
            f"Invalid locale {locale!r}: expected a hyphen-separated language "
            "tag such as 'en', 'pt-BR' or 'zh-Hant'."
        )
        raise ValueError(msg)


@dataclasses.dataclass(frozen=True)
class I18nConfig:
    """Internationalization configuration held by :class:`I18nPlugin`."""

    # Locales the app supports, e.g. ("en", "de"). Order is preserved for
    # Accept-Language negotiation ties.
    locales: tuple[str, ...]

    # The locale the source-text msgids are written in.
    default_locale: str = "en"

    # Directory containing {locale}.po catalogs, relative to the app root (the
    # working directory reflex runs in) unless absolute.
    catalog_dir: str = "locales"

    # The locale for a visitor whose browser asks for none of the configured
    # ones (Accept-Language negotiation); the default locale unless set.
    fallback_locale: str = "en"

    # Installed packages whose own catalogs (<package>/locales/{locale}.po)
    # translate their messages; the app's catalogs take precedence.
    catalog_packages: tuple[str, ...] = ()

    def __init__(
        self,
        locales: Sequence[str],
        default_locale: str = "en",
        catalog_dir: str | os.PathLike[str] = "locales",
        fallback_locale: str | None = None,
        catalog_packages: Sequence[str] = (),
    ):
        """Initialize and validate the i18n configuration.

        Args:
            locales: Locales the app supports, e.g. ``["en", "de"]``.
            default_locale: The locale the source-text msgids are written in.
            catalog_dir: Directory containing ``{locale}.po`` catalogs,
                relative to the app root unless absolute.
            fallback_locale: The locale for a visitor whose browser asks for
                none of the configured ones. Defaults to ``default_locale``.
            catalog_packages: Installed packages whose own catalogs
                (``<package>/locales/{locale}.po``) translate their messages.

        Raises:
            ValueError: If no locales are given, a locale is repeated in any
                case, a locale is not a language tag, or the default or fallback
                locale is not among them.
        """
        locales_tuple = tuple(locales)
        if not locales_tuple:
            msg = "I18nConfig.locales must contain at least one locale."
            raise ValueError(msg)
        if len({locale.lower() for locale in locales_tuple}) != len(locales_tuple):
            # Tags are case-insensitive, like the router and catalog lookups, so
            # "en" and "EN" would claim one route and catalog module twice.
            msg = (
                "I18nConfig.locales must not repeat a locale (tags are "
                f"case-insensitive): {locales_tuple!r}."
            )
            raise ValueError(msg)
        for locale in locales_tuple:
            validate_locale(locale)
        if fallback_locale is None:
            fallback_locale = default_locale
        for name, locale in (
            ("default_locale", default_locale),
            ("fallback_locale", fallback_locale),
        ):
            if locale not in locales_tuple:
                msg = (
                    f"I18nConfig.{name} {locale!r} must be one of the "
                    f"configured locales {locales_tuple!r}."
                )
                raise ValueError(msg)
        object.__setattr__(self, "locales", locales_tuple)
        object.__setattr__(self, "default_locale", default_locale)
        object.__setattr__(self, "catalog_dir", os.fspath(catalog_dir))
        object.__setattr__(self, "fallback_locale", fallback_locale)
        object.__setattr__(self, "catalog_packages", tuple(catalog_packages))


def find_package_dir(package: str) -> Path:
    """Locate an installed package's directory, importing only its parents.

    Args:
        package: The importable package name, e.g. ``"my_lib"`` or
            ``"my_lib.ui"``.

    Returns:
        The absolute package directory.

    Raises:
        ValueError: If no package of that name is installed.
    """
    msg = f"Cannot find the package {package!r}: it is not installed."
    try:
        # A dotted name imports its parent, which raises if that is missing.
        spec = importlib.util.find_spec(package)
    except ModuleNotFoundError as exc:
        raise ValueError(msg) from exc
    if spec is None or not spec.submodule_search_locations:
        raise ValueError(msg)
    return Path(next(iter(spec.submodule_search_locations))).resolve()


_active_config: I18nConfig | None = None

# Absolute catalog directories, captured when the app is constructed (cwd is
# the app root then): the app's first, then each catalog package's. Used at
# compile and request time so catalog loading does not depend on the process
# cwd, which is not guaranteed to be the app root later.
_active_catalog_dirs: tuple[Path, ...] = ()


def set_active_i18n_config(config: I18nConfig | None) -> None:
    """Set the i18n configuration of the running app.

    Called by ``rx.App`` so server-side translation helpers can resolve
    locales without a reference to the app instance. Must be called while the
    current working directory is the app root (it is during app construction).

    Args:
        config: The configuration to activate, or None to deactivate.
    """
    catalog_dirs = (
        (
            (Path.cwd() / config.catalog_dir).resolve(),
            *(
                find_package_dir(package) / PACKAGE_CATALOG_DIR
                for package in config.catalog_packages
            ),
        )
        if config is not None
        else ()
    )
    _activate(config, catalog_dirs)


def _activate(config: I18nConfig | None, catalog_dirs: tuple[Path, ...]) -> None:
    """Make a configuration and its resolved catalog directories the active ones.

    Args:
        config: The configuration, or None.
        catalog_dirs: Its absolute catalog directories.
    """
    # Inline to avoid a circular import; runtime imports from this module.
    from .runtime import clear_translations_cache

    global _active_config, _active_catalog_dirs
    _active_config = config
    _active_catalog_dirs = catalog_dirs
    # Drop translators built from the previous catalog dir (or from catalogs
    # edited before a dev hot reload re-activated the config).
    clear_translations_cache()


def get_active_i18n_config() -> I18nConfig | None:
    """Get the i18n configuration of the running app.

    Returns:
        The active configuration, or None if the app has no i18n config.
    """
    return _active_config


@contextlib.contextmanager
def active_i18n_config(config: I18nConfig | None) -> Iterator[I18nConfig | None]:
    """Activate an i18n configuration for a block, e.g. in a test.

    Args:
        config: The configuration to activate, or None for an app without i18n.

    Yields:
        The activated configuration.
    """
    # The directories the previous configuration was resolved to, as the working
    # directory may have changed since.
    previous = (_active_config, _active_catalog_dirs)
    set_active_i18n_config(config)
    try:
        yield config
    finally:
        _activate(*previous)


def _subtag_case(subtag: str) -> str:
    """The conventional case of a non-initial subtag (RFC 5646 section 2.1.1).

    Args:
        subtag: A subtag after the language, e.g. ``"hant"`` or ``"br"``.

    Returns:
        Title case for a script, upper case for a region, else lower case.
    """
    if len(subtag) == 4 and subtag.isalpha():
        return subtag.title()
    if (len(subtag) == 2 and subtag.isalpha()) or (
        len(subtag) == 3 and subtag.isdigit()
    ):
        return subtag.upper()
    return subtag.lower()


def normalize_locale(locale: str) -> str:
    """Spell a language tag canonically.

    A tag naming a configured locale (tags are case-insensitive) takes the
    configured spelling; any other tag its conventional case.

    Args:
        locale: The tag to normalize, e.g. ``"PT-br"``.

    Returns:
        The canonical spelling, e.g. ``"pt-BR"``.

    Raises:
        ValueError: If the locale is not a hyphen-separated language tag.
    """
    validate_locale(locale)
    return spell_locale(locale)


def spell_locale(locale: str) -> str:
    """Spell a language tag canonically, like :func:`normalize_locale`, unvalidated.

    Args:
        locale: The tag to spell.

    Returns:
        The configured spelling, else the conventional case.
    """
    lowered = locale.lower()
    if _active_config is not None:
        for configured in _active_config.locales:
            if configured.lower() == lowered:
                return configured
    language, *subtags = lowered.split("-")
    cased = [language]
    # From a singleton on (an extension such as "u-ca-gregory" or private use
    # "x-..."), subtags are not scripts or regions and stay lowercase.
    in_extension = False
    for subtag in subtags:
        in_extension = in_extension or len(subtag) == 1
        cased.append(subtag if in_extension else _subtag_case(subtag))
    return "-".join(cased)


def source_locale() -> str:
    """The language the app's source text is written in.

    Returns:
        The configured default locale, or ``UNCONFIGURED_LOCALE`` without an
        I18nPlugin.
    """
    if _active_config is None:
        return UNCONFIGURED_LOCALE
    return _active_config.default_locale


def configured_locales() -> tuple[str, ...]:
    """The locales the app is offered in.

    Returns:
        The configured locales in their configured order, or only the source
        locale without an I18nPlugin.
    """
    if _active_config is None:
        return (UNCONFIGURED_LOCALE,)
    return _active_config.locales


def check_configured_locale(locale: str) -> None:
    """Check that a locale is one of the running app's configured locales.

    Args:
        locale: The locale to check.

    Raises:
        ValueError: If i18n is configured and the locale is not among its
            locales.
    """
    config = _active_config
    if config is not None and locale not in config.locales:
        msg = (
            f"Locale {locale!r} is not configured. Configured locales: "
            f"{list(config.locales)}."
        )
        raise ValueError(msg)


def get_active_catalog_dirs() -> tuple[Path, ...]:
    """Get the absolute catalog directories of the running app, by precedence.

    Returns:
        The app's catalog directory, then each catalog package's; empty if i18n
        is not configured.
    """
    return _active_catalog_dirs
