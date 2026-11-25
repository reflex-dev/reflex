"""The Reflex plugin that wires i18n into an app's compilation."""

from __future__ import annotations

import dataclasses
import logging
import os
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, get_args

from reflex_base.plugins.base import (
    CommonContext,
    ExpandRoutesContext,
    Plugin,
    PostBuildContext,
    PreCompileContext,
)
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
from .runtime import active_locale, gettext
from .vars import (
    _i18n_var_data,
    _pick,
    _pick_locale,
    _pick_var_data,
    _translate,
    _translate_plural,
)

if TYPE_CHECKING:
    from reflex_base.components.component import Component
    from reflex_base.plugins.compiler import PageContext

    from reflex.app import UnevaluatedPage

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

# The page context key naming the locale a fanned-out route renders in.
_PAGE_LOCALE_KEY = "i18n_locale"

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


def _localized_page(component: Any, locale: str) -> Any:
    """Wrap a page component so it renders in a fixed locale (static catalog).

    Args:
        component: The original page component or component callable.
        locale: The locale to render this route in.

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

        # The page function runs in its route's locale, also where a backend
        # evaluates pages without the compiler's hooks.
        with active_locale(locale):
            page = into_component(component)
        # Auto-memoization already gives each stateful component a function
        # below LocaleRoute; sealing the whole page would undo its per-component
        # re-renders.
        if not get_config().auto_memoize:
            page = LocalePage.create(page)
        return LocaleRoute.create(page, locale=locale, catalog=_catalog_var(locale))

    return render


def _translate_text(value: Any) -> Any:
    """Translate a page's head text if it is a plain string.

    Args:
        value: The text, or a Var, None or anything else left as is.

    Returns:
        The translated text, or the value unchanged.
    """
    # gettext("") would return the catalog's header.
    return gettext(value) if isinstance(value, str) and value else value


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
            for locale in self.locales:
                localized = self.routing.localize(
                    base_path, locale, self.default_locale
                )
                if localized == base_path:
                    # Default-at-root: the app's own page already serves this.
                    continue
                add_page(
                    _localized_page(page.component, locale),
                    route=localized,
                    title=page.title,
                    description=page.description,
                    image=page.image,
                    on_load=page.on_load,
                    meta=page.meta,
                    context={**(page.context or {}), _PAGE_LOCALE_KEY: locale},
                )

    def eval_page(
        self, page_fn: Any, /, *, page: UnevaluatedPage, **kwargs: Any
    ) -> PageContext | None:
        """Evaluate a page in the locale its route serves, when URL routing is on.

        The page function, and so ``get_locale()`` and ``gettext``, run in
        that locale, and a plain string ``title``, ``description`` or meta tag
        ``content`` is translated into it; the page is otherwise evaluated as
        usual.

        Args:
            page_fn: The page component or component callable.
            page: The page being evaluated.
            kwargs: The compiler context, passed on.

        Returns:
            The evaluated page, or None without URL routing.
        """
        if self.routing is None:
            return None
        from reflex.compiler.plugins.builtin import DefaultPagePlugin

        locale = (page.context or {}).get(_PAGE_LOCALE_KEY, self.default_locale)
        with active_locale(locale):
            page = dataclasses.replace(
                page,
                title=_translate_text(page.title),
                description=_translate_text(page.description),
                meta=[_translate_meta(meta) for meta in page.meta],
            )
            return DefaultPagePlugin().eval_page(page_fn, page=page, **kwargs)

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
