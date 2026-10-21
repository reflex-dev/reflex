"""URL-based locale routing strategies for :class:`~reflex_i18n.plugin.I18nPlugin`.

A strategy maps between a base (locale-agnostic) URL path and its per-locale
URL, so the plugin can fan pages out into concrete, prerenderable per-locale
routes and emit reciprocal ``hreflang`` links. Enable one via
``I18nPlugin(routing=PathPrefixRouting())``; omitting it (the default) keeps the
cookie-based single-URL behavior.

Paths here are browser URL paths (leading ``/``, ``"/"`` for the index), not
Reflex's normalized route keys — the plugin converts between the two.
"""

from __future__ import annotations

import abc
import dataclasses
from collections.abc import Sequence


class LocaleRouting(abc.ABC):
    """Maps base URL paths to per-locale URLs (and back)."""

    @abc.abstractmethod
    def localize(self, path: str, locale: str, default_locale: str) -> str:
        """Return the URL path for a base path in a given locale.

        Args:
            path: The base (locale-agnostic) URL path, e.g. ``"/pricing"``.
            locale: The target locale.
            default_locale: The app's default locale.

        Returns:
            The localized URL path.
        """

    @abc.abstractmethod
    def delocalize(self, path: str, locales: Sequence[str]) -> str:
        """Return the base (locale-agnostic) URL path for a URL path.

        Args:
            path: A (possibly localized) URL path.
            locales: The app's configured locales.

        Returns:
            The base URL path with any locale marker removed.
        """

    @abc.abstractmethod
    def locale_of(self, path: str, locales: Sequence[str], default_locale: str) -> str:
        """Return the locale a URL path belongs to.

        Args:
            path: A URL path.
            locales: The app's configured locales.
            default_locale: The locale to assume when the path carries none.

        Returns:
            The locale for the path.
        """

    def alternates(
        self, path: str, locales: Sequence[str], default_locale: str
    ) -> dict[str, str]:
        """Return the locale -> URL-path map for a path (for ``hreflang``).

        Args:
            path: Any (localized or base) URL path.
            locales: The app's configured locales.
            default_locale: The app's default locale.

        Returns:
            A mapping of each locale to its URL path for this page.
        """
        base = self.delocalize(path, locales)
        return {loc: self.localize(base, loc, default_locale) for loc in locales}


@dataclasses.dataclass
class PathPrefixRouting(LocaleRouting):
    """Serve each locale under a path prefix, e.g. ``/de/pricing``.

    Args:
        default_at_root: If True (default), the default locale is served at the
            unprefixed path (``/pricing``) and only other locales are prefixed
            (``/de/pricing``). If False, every locale is prefixed.
    """

    default_at_root: bool = True

    def localize(self, path: str, locale: str, default_locale: str) -> str:
        """Prefix the path with the locale (unless it's the default at root).

        Args:
            path: The base URL path.
            locale: The target locale.
            default_locale: The app's default locale.

        Returns:
            The localized URL path.
        """
        base = path if path.startswith("/") else f"/{path}"
        if locale == default_locale and self.default_at_root:
            return base
        return f"/{locale}" if base == "/" else f"/{locale}{base}"

    def delocalize(self, path: str, locales: Sequence[str]) -> str:
        """Strip a leading ``/<locale>`` segment if present.

        Args:
            path: A (possibly localized) URL path.
            locales: The app's configured locales.

        Returns:
            The base URL path.
        """
        head, _, rest = path.lstrip("/").partition("/")
        if head in locales:
            return f"/{rest}" if rest else "/"
        return path if path.startswith("/") else f"/{path}"

    def locale_of(self, path: str, locales: Sequence[str], default_locale: str) -> str:
        """Return the locale named by the leading path segment, else default.

        Args:
            path: A URL path.
            locales: The app's configured locales.
            default_locale: The locale to assume when the path carries none.

        Returns:
            The locale for the path.
        """
        head = path.lstrip("/").partition("/")[0]
        return head if head in locales else default_locale
