"""The Reflex plugin that wires i18n into an app's compilation."""

from __future__ import annotations

import contextlib
import dataclasses
import logging
import os
import re
from collections.abc import Iterator, Mapping, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, get_args
from urllib.parse import urlsplit, urlunsplit
from xml.etree import ElementTree as ET

from reflex_base.plugins.base import (
    CommonContext,
    ExpandRoutesContext,
    Plugin,
    PostBuildContext,
    PreCompileContext,
    get_plugin,
)
from reflex_base.plugins.sitemap import Constants as SitemapConstants
from reflex_base.plugins.sitemap import SitemapPlugin
from reflex_base.utils.exceptions import RouteValueError
from reflex_base.utils.imports import ImportVar
from reflex_base.vars.base import Var, VarData
from typing_extensions import Unpack

from .catalog import (
    compile_catalog_module,
    compile_index_module,
    default_plural_expr_js,
    load_catalog,
)
from .component import HreflangLinks, LocalePage, LocaleRoute, _provider
from .config import I18nConfig, get_active_catalog_dirs, set_active_i18n_config
from .format import (
    _fmt_date,
    _fmt_language,
    _fmt_number,
    _format_var_data,
    _locale_var,
    _locale_var_data,
)
from .registry import collected_messages, format_message_list, untranslated_messages
from .routing import PathPrefixRouting, segment_locale
from .runtime import active_locale, translate
from .vars import (
    _i18n_var_data,
    _pick,
    _pick_locale,
    _pick_var_data,
    _translate,
    _translate_plural,
)

if TYPE_CHECKING:
    from contextlib import AbstractContextManager

    from reflex_base.components.component import Component
    from reflex_base.plugins.compiler import PageContext, PageDefinition

logger = logging.getLogger(__name__)

# The compiled catalog modules are written under ``.web/i18n``.
_I18N_WEB_DIR = "i18n"
# The client runtime is written to ``.web/utils/i18n.js`` (the ``$/utils/i18n``
# import specifier used by the provider and translation vars).
_RUNTIME_WEB_PATH = "utils/i18n.js"
_RUNTIME_SOURCE = Path(__file__).parent / "_web" / "i18n.js"

# Priority for the hreflang app-wrap; any position inside the router tree works.
_HREFLANG_PRIORITY = 57

# Language subtags written right-to-left, as in the client runtime.
_RTL_LANGUAGES = frozenset({
    "ar",
    "arc",
    "ckb",
    "dv",
    "fa",
    "he",
    "ks",
    "ps",
    "sd",
    "ug",
    "ur",
    "yi",
})

_HTML_TAG = re.compile(r"<html\b[^>]*>", re.IGNORECASE)

# The namespace of a sitemap's hreflang alternates.
_XHTML_NAMESPACE = "http://www.w3.org/1999/xhtml"

# The page context key naming the locale a fanned-out route renders in.
_PAGE_LOCALE_KEY = "i18n_locale"

# The page context key mapping locales to the page's own path in them.
PAGE_PATHS_KEY = "i18n_paths"

# What the ``#:`` comments of a written catalog entry name: each source line,
# each source file, or nothing.
CatalogLocations = Literal["line", "file", "none"]


def _catalog_ident(locale: str) -> str:
    """A JS identifier for a locale's statically-imported catalog namespace.

    Args:
        locale: The locale code (may contain hyphens).

    Returns:
        A safe identifier, e.g. ``en_USCatalog``.
    """
    return re.sub(r"\W", "_", locale) + "Catalog"


def _catalog_var(locale: str) -> Var:
    """A Var referencing a static ``import * as <locale>Catalog`` namespace.

    Args:
        locale: The locale whose catalog module to import.

    Returns:
        A Var carrying the static import, usable as the ``catalog`` prop.
    """
    ident = _catalog_ident(locale)
    return Var(
        _js_expr=ident,
        _var_data=VarData(
            imports={
                f"$/{_I18N_WEB_DIR}/{locale}.js": [
                    ImportVar(tag="*", alias=ident, is_default=True)
                ]
            }
        ),
    )


def _reset_provider() -> None:
    """Drop the cached provider and the client vars carrying it.

    They are rebuilt on first use for the plugin configured then, whose
    routing decides whether the provider reports a switch to the server.
    """
    for cached in (
        _provider,
        _i18n_var_data,
        _translate,
        _translate_plural,
        _format_var_data,
        _locale_var_data,
        _fmt_number,
        _fmt_date,
        _fmt_language,
        _locale_var,
        _pick_var_data,
        _pick,
        _pick_locale,
    ):
        cached.cache_clear()


def _localized_page(
    component: Any, locale: str, source_module: str | None = None
) -> Any:
    """Wrap a page component so it renders in a fixed locale (static catalog).

    Args:
        component: The original page component or component callable.
        locale: The locale to render this route in.
        source_module: The module the page is defined in, if known.

    Returns:
        A component callable producing the locale-wrapped tree.
    """

    def render() -> Component:
        """Render the page in its fixed locale.

        Returns:
            The page wrapped with its locale and catalog.
        """
        # into_component normalizes the page exactly as an un-fanned page
        # would be (handles callables, ComponentState, memo).
        from reflex_base.config import get_config

        from reflex.compiler.compiler import into_component

        page = into_component(component)
        # Auto-memoization already gives each stateful component a function
        # below LocaleRoute; sealing the whole page would undo its per-component
        # re-renders.
        if not get_config().auto_memoize:
            page = LocalePage.create(page)
        return LocaleRoute.create(page, locale=locale, catalog=_catalog_var(locale))

    if source_module is not None:
        # The page's memos are compiled into a module named after the page
        # callable's: one per page and locale, next to the page's own, instead
        # of one for every localized page that each of them would load.
        render.__module__ = f"{source_module}.{locale}"
    return render


def _translate_text(value: Any) -> Any:
    """Translate a page's head text if it is a plain string, as :func:`translate` does.

    Args:
        value: The text, or a Var, None or anything else left as is.

    Returns:
        The translated text, or the value unchanged.
    """
    return translate(value) if isinstance(value, str) else value


def _split_frontend_path(path: str) -> tuple[str, str] | None:
    """Split a URL path into the ``frontend_path`` prefix and the page path after it.

    Args:
        path: A URL path, e.g. a sitemap ``loc``'s.

    Returns:
        The prefix (``""`` without a ``frontend_path``) and the page path, or None
        for a path outside the ``frontend_path``.
    """
    from reflex_base.config import get_config

    frontend_path = get_config().frontend_path.strip("/")
    prefix = f"/{frontend_path}" if frontend_path else ""
    if prefix and path != prefix and not path.startswith(prefix + "/"):
        return None
    return prefix, path[len(prefix) :] or "/"


def _sitemap_loc(sitemap: Any) -> str | None:
    """The ``loc`` a page's ``sitemap`` context configures, if any.

    Args:
        sitemap: The page's ``sitemap`` context entry.

    Returns:
        The configured location, or None.
    """
    return sitemap.get("loc") if isinstance(sitemap, Mapping) else None


def _translate_meta(meta: Any) -> Any:
    """Translate the text content of a page's meta tag.

    Args:
        meta: A meta tag, as a mapping of its attributes or a component.

    Returns:
        The tag with a plain string ``content`` translated.
    """
    if isinstance(meta, Mapping) and "content" in meta:
        return {**meta, "content": _translate_text(meta["content"])}
    return meta


@contextlib.contextmanager
def _page_in_locale(page: PageDefinition, locale: str) -> Iterator[Any]:
    """Evaluate a page in a locale, with its plain string head texts in it.

    Args:
        page: The page about to be evaluated.
        locale: The locale its route serves.

    Yields:
        A copy of the page with its title, description and meta tag content
        translated, or None for a page that is not an app page.
    """
    from reflex.app import UnevaluatedPage

    with active_locale(locale):
        if not isinstance(page, UnevaluatedPage):
            yield None
            return
        yield dataclasses.replace(
            page,
            title=_translate_text(page.title),
            description=_translate_text(page.description),
            meta=[_translate_meta(meta) for meta in page.meta],
        )


def _text_direction(locale: str) -> str:
    """Return the writing direction of a locale's language.

    Args:
        locale: A locale tag (case-insensitive).

    Returns:
        ``rtl`` or ``ltr``.
    """
    language = locale.partition("-")[0].lower()
    return "rtl" if language in _RTL_LANGUAGES else "ltr"


def _set_document_locale(document: str, locale: str) -> str:
    """Set ``lang`` and ``dir`` on the ``<html>`` tag of a rendered page.

    Args:
        document: The page's HTML.
        locale: The locale the page is rendered in.

    Returns:
        The HTML with the locale's language and direction on its root.
    """
    match = _HTML_TAG.search(document)
    if match is None:
        return document
    tag = match.group()
    for name, value in (("lang", locale), ("dir", _text_direction(locale))):
        attribute = f' {name}="{value}"'
        # Validated locale tags hold no backslashes, so this is a literal repl.
        tag, found = re.subn(rf'\s{name}="[^"]*"', attribute, tag, count=1)
        if not found:
            tag = f"{tag[:-1]}{attribute}>"
    return document[: match.start()] + tag + document[match.end() :]


@dataclasses.dataclass
class I18nPlugin(Plugin):
    """Enables ``rx.t`` translations and compiles per-locale catalogs.

    Add to ``rx.Config(plugins=[I18nPlugin(locales=[...])])``. Set ``routing``
    to a :class:`~reflex_i18n.routing.PathPrefixRouting` for opt-in URL-based
    locales + ``hreflang`` (SEO); omit it for the default cookie-based,
    single-URL behavior.
    """

    locales: Sequence[str]
    default_locale: str = "en"
    fallback_locale: str | None = None
    catalog_dir: str | os.PathLike[str] = "locales"
    catalog_packages: Sequence[str] = ()
    routing: PathPrefixRouting | None = None
    # The width ``reflex i18n`` wraps catalog lines at; 0 keeps each on one line.
    catalog_width: int = 76
    catalog_locations: CatalogLocations = "line"
    # The translated paths of the app's pages: base path -> {locale: path}.
    _page_paths: dict[str, dict[str, str]] = dataclasses.field(
        default_factory=dict, init=False, repr=False, compare=False
    )
    # The lookups below match paths case-insensitively, as the router does.
    # Lowered base path -> {locale: path}.
    _paths_by_base: dict[str, dict[str, str]] = dataclasses.field(
        default_factory=dict, init=False, repr=False, compare=False
    )
    # (locale, lowered translated path) -> base path.
    _base_paths: dict[tuple[str, str], str] = dataclasses.field(
        default_factory=dict, init=False, repr=False, compare=False
    )
    # The lowered URL path of every page in every locale.
    _page_urls: set[str] = dataclasses.field(
        default_factory=set, init=False, repr=False, compare=False
    )
    # The lowered page path of every sitemap ``loc`` a page configures, per locale.
    _sitemap_paths: set[str] = dataclasses.field(
        default_factory=set, init=False, repr=False, compare=False
    )

    def _config(self) -> I18nConfig:
        """Build the i18n configuration from the plugin's fields.

        Returns:
            The validated configuration.
        """
        return I18nConfig(
            locales=self.locales,
            default_locale=self.default_locale,
            catalog_dir=self.catalog_dir,
            fallback_locale=self.fallback_locale,
            catalog_packages=self.catalog_packages,
        )

    def __post_init__(self):
        """Activate the i18n config and register framework state.

        Raises:
            TypeError: If ``routing`` is not a PathPrefixRouting.
            ValueError: If ``catalog_locations`` is not a known choice.
        """
        if self.catalog_locations not in get_args(CatalogLocations):
            msg = (
                f"I18nPlugin.catalog_locations must be one of "
                f"{get_args(CatalogLocations)!r}; got {self.catalog_locations!r}."
            )
            raise ValueError(msg)
        if self.routing is not None and not isinstance(self.routing, PathPrefixRouting):
            # The shipped client runtime (hreflang, language switcher, locale
            # detection) only understands path-prefix URLs.
            msg = (
                "I18nPlugin.routing must be a PathPrefixRouting (or None); "
                f"got {type(self.routing).__name__}. Custom locale-routing "
                "strategies are not supported by the client runtime yet."
            )
            raise TypeError(msg)
        set_active_i18n_config(self._config())
        # A provider built for another plugin may disagree on its routing.
        _reset_provider()
        # Registers I18nState (substate) and the event-scope locale provider.
        # Imported here rather than at module top so an app opting in triggers
        # it, but the package's other import paths (e.g. the reflex CLI loading
        # the ``reflex i18n`` command) don't register state.
        from . import state

        state._register_in_active_context()

    def get_static_assets(
        self, **context: Unpack[CommonContext]
    ) -> Sequence[tuple[Path, str | bytes]]:
        """Ship the client i18n runtime.

        Args:
            context: The plugin context (unused).

        Returns:
            The client runtime written to ``.web/utils/i18n.js``.
        """
        return [(Path(_RUNTIME_WEB_PATH), _RUNTIME_SOURCE.read_text(encoding="utf-8"))]

    def expand_routes(self, **context: Unpack[ExpandRoutesContext]) -> None:
        """Fan each app page out into one route per non-default locale.

        Each fanned page renders in its locale from a static catalog; the
        default locale keeps the app's original route.

        Args:
            context: The route-expansion context.

        Raises:
            RouteValueError: If an app route starts with a configured locale.
        """
        if self.routing is None:
            return
        add_page = context["add_page"]
        self._page_paths = {}
        self._paths_by_base = {}
        self._base_paths = {}
        self._page_urls = set()
        self._sitemap_paths = set()
        for page in context["pages"]:
            base_path = "/" if page.route == "index" else f"/{page.route}"
            head = base_path.lstrip("/").partition("/")[0]
            if segment_locale(head, self.locales) is not None:
                # Such a route would be indistinguishable from the localized
                # URLs this plugin generates (and shadow or collide with them).
                msg = (
                    f"App route {base_path!r} starts with configured locale "
                    f"{head!r}; locale-prefixed URLs are reserved by "
                    f"I18nPlugin routing. Rename the route or drop the locale."
                )
                raise RouteValueError(msg)
            if paths := self._translated_paths(base_path, page.context or {}):
                self._add_page_paths(base_path, paths)
            sitemap = (page.context or {}).get("sitemap")
            for locale in self.locales:
                localized = self._localize(base_path, locale)
                self._page_urls.add(localized.lower())
                localized_sitemap = self._localized_sitemap(sitemap, locale)
                if (loc := _sitemap_loc(localized_sitemap)) is not None:
                    self._sitemap_paths.add(self._sitemap_page_path(loc))
                if localized == base_path:
                    # Default-at-root: the app's own page already serves this.
                    continue
                page_context = {**(page.context or {}), _PAGE_LOCALE_KEY: locale}
                if localized_sitemap is not sitemap:
                    page_context["sitemap"] = localized_sitemap
                add_page(
                    _localized_page(
                        page.component,
                        locale,
                        getattr(page, "_source_module", None),
                    ),
                    route=localized,
                    title=page.title,
                    description=page.description,
                    image=page.image,
                    on_load=page.on_load,
                    meta=page.meta,
                    context=page_context,
                )

    def _translated_paths(
        self, base_path: str, page_context: Mapping[str, Any]
    ) -> dict[str, str]:
        """Read and check the paths a page has in other locales.

        Args:
            base_path: The page's own path, which its default locale serves.
            page_context: The page's context, mapping ``i18n_paths`` to them.

        Returns:
            Each locale's path for the page, with one leading slash.

        Raises:
            RouteValueError: If a path is given for the default or an
                unconfigured locale, or for or as a dynamic route.
        """
        paths = page_context.get(PAGE_PATHS_KEY) or {}
        result: dict[str, str] = {}
        for locale, path in paths.items():
            normalized = "/" + path.strip("/")
            if locale not in self.locales or locale == self.default_locale:
                msg = (
                    f"Page {base_path!r} gives a path for {locale!r}, which is "
                    "not one of the other locales "
                    f"{[loc for loc in self.locales if loc != self.default_locale]}; "
                    "the page's own route is its default-locale path."
                )
                raise RouteValueError(msg)
            if "[" in base_path or "[" in normalized:
                msg = (
                    f"Page {base_path!r} cannot have the {locale!r} path "
                    f"{normalized!r}: only static routes have translated paths."
                )
                raise RouteValueError(msg)
            result[locale] = normalized
        return result

    def _add_page_paths(self, base_path: str, paths: dict[str, str]) -> None:
        """Record the paths a page has in other locales.

        Args:
            base_path: The page's own path, which its default locale serves.
            paths: Each other locale's path for the page.
        """
        self._page_paths[base_path] = paths
        self._paths_by_base[base_path.lower()] = paths
        for locale, path in paths.items():
            self._base_paths[locale, path.lower()] = base_path

    def _localize(self, path: str, locale: str) -> str:
        """The URL path of a page in a locale, under its translated path if any.

        Args:
            path: The page's base path.
            locale: The locale.

        Returns:
            The localized URL path.
        """
        assert self.routing is not None
        translated = self._paths_by_base.get(path.lower(), {}).get(locale, path)
        return self.routing.localize(translated, locale, self.default_locale)

    def _localized_sitemap(self, sitemap: Any, locale: str) -> Any:
        """A page's ``sitemap`` context for its route in ``locale``.

        A configured ``loc`` moves to the locale, as the route does; the
        configuration is returned as is without one.

        Args:
            sitemap: The page's ``sitemap`` context entry.
            locale: The locale of the route.

        Returns:
            The configuration with the ``loc`` in ``locale``.
        """
        if (loc := _sitemap_loc(sitemap)) is None:
            return sitemap
        parts = urlsplit(loc)
        split = _split_frontend_path(parts.path or "/")
        prefix, path = split if split is not None else ("", parts.path or "/")
        slash = "/" if path != "/" and path.endswith("/") else ""
        localized = self._localize(path.rstrip("/") or "/", locale)
        if localized != "/":
            localized += slash
        return {**sitemap, "loc": urlunsplit(parts._replace(path=prefix + localized))}

    @staticmethod
    def _sitemap_page_path(loc: str) -> str:
        """The lowered page path of a sitemap ``loc``, as ``_page_urls`` holds them.

        Args:
            loc: The location, a path or a URL.

        Returns:
            Its path after the ``frontend_path``, without a trailing slash.
        """
        path = urlsplit(loc).path or "/"
        split = _split_frontend_path(path)
        page_path = split[1] if split is not None else path
        return (page_path.rstrip("/") or "/").lower()

    def _alternates(self, path: str) -> dict[str, str]:
        """The URL path of the page at a path in each locale, as hreflang names it.

        Args:
            path: A URL path, relative to ``frontend_path``.

        Returns:
            Each locale's path for the page, then ``x-default``'s.
        """
        assert self.routing is not None
        locale = self.routing.locale_of(path, self.locales, self.default_locale)
        rest = self.routing.delocalize(path, self.locales)
        base_path = self._base_paths.get((locale, rest.lower()), rest)
        alternates = {loc: self._localize(base_path, loc) for loc in self.locales}
        alternates["x-default"] = alternates[self.default_locale]
        return alternates

    def _add_sitemap_alternates(self, sitemap: str) -> str:
        """Name each sitemap URL's page in every locale, as its hreflang links do.

        Args:
            sitemap: The sitemap XML the SitemapPlugin generated.

        Returns:
            The sitemap with an ``xhtml:link`` alternate per locale on each
            page's URL.
        """
        from reflex.route import get_router

        dynamic_page = get_router([
            url.strip("/") for url in self._page_urls if "[" in url
        ])
        urlset = ET.fromstring(sitemap)
        namespace = urlset.tag.partition("}")[0].removeprefix("{")
        # Written back with the literal names the SitemapPlugin writes.
        for element in urlset.iter():
            element.tag = element.tag.rpartition("}")[2]
        urlset.set("xmlns", namespace)
        urlset.set("xmlns:xhtml", _XHTML_NAMESPACE)
        for url in urlset.iter("url"):
            loc = urlsplit(url.findtext("loc", ""))
            split = _split_frontend_path(loc.path)
            if split is None:
                # Not one of the app's pages, e.g. a custom loc on another path.
                continue
            prefix, path = split
            page_path = (path.rstrip("/") or "/").lower()
            if (
                page_path not in self._page_urls
                and page_path not in self._sitemap_paths
                and dynamic_page(path) is None
            ):
                # No page's URL or configured loc in any locale, e.g. a feed's.
                continue
            slash = "/" if path != "/" and path.endswith("/") else ""
            for locale, alternate in self._alternates(path).items():
                if alternate != "/":
                    alternate += slash
                ET.SubElement(
                    url,
                    "xhtml:link",
                    rel="alternate",
                    hreflang=locale,
                    # a configured loc's query names the page as much as its path
                    href=urlunsplit((
                        loc.scheme,
                        loc.netloc,
                        prefix + alternate,
                        loc.query,
                        "",
                    )),
                )
        ET.indent(urlset, "  ")
        return ET.tostring(urlset, encoding="utf-8", xml_declaration=True).decode(
            "utf-8"
        )

    def _path_redirects(self) -> dict[str, str]:
        """Map each translated page's path in one locale under another to its own.

        A path that is another page's own URL is left to that page.

        Returns:
            Source path -> target path, both relative to ``frontend_path``.
        """
        assert self.routing is not None
        redirects: dict[str, str] = {}
        for base_path, paths in self._page_paths.items():
            for locale in self.locales:
                target = self._localize(base_path, locale)
                for path in (base_path, *paths.values()):
                    source = self.routing.localize(path, locale, self.default_locale)
                    if source != target and source.lower() not in self._page_urls:
                        redirects[source] = target
        return redirects

    def eval_page_scope(
        self, page: PageDefinition, /, **kwargs: Any
    ) -> AbstractContextManager[Any] | None:
        """Build a page in the locale its route serves, when URL routing is on.

        The page function, and so ``get_locale()``, ``gettext`` and
        :func:`~reflex_i18n.nav.localized_url`, run in that locale, and a plain
        string ``title``, ``description`` or meta tag ``content`` is a message
        translated into it.

        Args:
            page: The page about to be evaluated.
            kwargs: The compiler context (unused).

        Returns:
            The route's locale scope, or None without URL routing.
        """
        if self.routing is None:
            return None
        context = getattr(page, "context", None) or {}
        return _page_in_locale(page, context.get(_PAGE_LOCALE_KEY, self.default_locale))

    def compile_page(self, page_ctx: PageContext, /, **kwargs: Any) -> None:
        """Inject the hreflang app-wrap on every page when URL routing is on.

        Args:
            page_ctx: The page being compiled.
            kwargs: Additional compiler context (unused).
        """
        if self.routing is None:
            return
        page_ctx.app_wrap_components[_HREFLANG_PRIORITY, "HreflangLinks"] = (
            HreflangLinks.create()
        )

    def get_html_lang(self, **context: Unpack[CommonContext]) -> str | None:
        """The default locale, the language pages are prerendered in.

        Args:
            context: The plugin context.

        Returns:
            The default locale.
        """
        return self.default_locale

    def pre_compile(self, **context: Unpack[PreCompileContext]) -> None:
        """Register the catalog-emission task.

        Args:
            context: The pre-compile context.
        """
        untranslated = untranslated_messages()
        if untranslated:
            # Built while the config was still loading, e.g. by a module
            # rxconfig.py imports before constructing this plugin.
            logger.warning(
                f"{len(untranslated)} rx.t message(s) were built before "
                "I18nPlugin was configured and always render their source "
                "text:\n"
                f"{format_message_list(untranslated)}\n"
                "Build them inside a page or component function instead."
            )
        context["add_save_task"](self._compile_catalogs)
        if self.routing is not None and get_plugin(SitemapPlugin) is not None:
            context["add_modify_task"](
                str(SitemapConstants.FILE_PATH), self._add_sitemap_alternates
            )

    def post_build(self, **context: Unpack[PostBuildContext]) -> None:
        """Give the prerendered pages of each prefixed locale its ``lang``/``dir``.

        The document root is compiled once for the whole app, so every page is
        prerendered with the app-wide ``html_lang``; without this the locale's
        language and direction would only apply on hydration.

        Args:
            context: The post-build context.
        """
        from reflex_base.config import get_config

        if self.routing is None:
            return
        pages_dir = Path(context["static_dir"]) / get_config().frontend_path.strip("/")
        for locale in self.locales:
            prefix = self.routing.localize("/", locale, self.default_locale).strip("/")
            if not prefix:
                # Default-at-root pages keep the app's html_lang.
                continue
            for page in (
                pages_dir / f"{prefix}.html",
                *(pages_dir / prefix).rglob("*.html"),
            ):
                if page.is_file():
                    page.write_text(
                        _set_document_locale(page.read_text(encoding="utf-8"), locale),
                        encoding="utf-8",
                    )

    def _compile_catalogs(self) -> list[tuple[str, str]]:
        """Compile the per-locale catalog modules from the ``.po`` catalogs.

        Returns:
            Pairs of (``.web``-relative path, module code).
        """
        from reflex_base.config import get_config

        config = self._config()
        used_messages = collected_messages()
        # The absolute directories captured when the app was constructed: the
        # process cwd is not guaranteed to still be the app root at compile.
        catalog_dirs = get_active_catalog_dirs()
        app_catalog_dir = (
            catalog_dirs[0] if catalog_dirs else Path.cwd() / self.catalog_dir
        )
        default_at_root = bool(getattr(self.routing, "default_at_root", True))
        deploy_url = get_config().deploy_url or ""

        default_catalog = load_catalog(config.default_locale)

        results: list[tuple[str, str]] = [
            (
                f"{_I18N_WEB_DIR}/index.js",
                compile_index_module(
                    config,
                    url_routing=self.routing is not None,
                    default_at_root=default_at_root,
                    deploy_url=deploy_url,
                    default_plural_expr=default_plural_expr_js(
                        default_catalog, config.default_locale
                    ),
                    page_paths=self._page_paths,
                ),
            )
        ]
        for locale in config.locales:
            if locale == config.default_locale:
                catalog = default_catalog
            else:
                catalog = load_catalog(locale)
                if catalog is None:
                    logger.warning(
                        f"No translation catalog found for locale {locale!r} "
                        f"(expected {app_catalog_dir / f'{locale}.po'})."
                    )
            results.append((
                f"{_I18N_WEB_DIR}/{locale}.js",
                compile_catalog_module(
                    catalog,
                    used_messages,
                    locale,
                    is_default_locale=locale == config.default_locale,
                ),
            ))
        return results
