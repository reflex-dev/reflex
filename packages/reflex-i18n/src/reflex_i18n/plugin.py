"""The Reflex plugin that wires i18n into an app's compilation."""

from __future__ import annotations

import dataclasses
import re
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any

from reflex_base.plugins.base import (
    CommonContext,
    ExpandRoutesContext,
    Plugin,
    PreCompileContext,
)
from reflex_base.utils import console
from reflex_base.utils.exceptions import RouteValueError
from reflex_base.utils.imports import ImportVar
from reflex_base.vars.base import Var, VarData
from typing_extensions import Unpack

from .catalog import (
    compile_catalog_module,
    compile_index_module,
    default_plural_expr_js,
    read_po_catalog,
)
from .component import HreflangLinks, LocaleRoute
from .config import I18nConfig, set_active_i18n_config
from .registry import collected_messages
from .routing import PathPrefixRouting

if TYPE_CHECKING:
    from reflex_base.components.component import Component
    from reflex_base.plugins.compiler import PageContext

# The compiled catalog modules are written under ``.web/i18n``.
_I18N_WEB_DIR = "i18n"
# The client runtime is written to ``.web/utils/i18n.js`` (the ``$/utils/i18n``
# import specifier used by the provider and translation vars).
_RUNTIME_WEB_PATH = "utils/i18n.js"
_RUNTIME_SOURCE = Path(__file__).parent / "_web" / "i18n.js"

# Priority for the hreflang app-wrap; any position inside the router tree works.
_HREFLANG_PRIORITY = 57


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


def _localized_page(component: Any, locale: str) -> Any:
    """Wrap a page component so it renders in a fixed locale (static catalog).

    Args:
        component: The original page component or component callable.
        locale: The locale to render this route in.

    Returns:
        A component callable producing the locale-wrapped tree.
    """

    def render() -> Component:
        # into_component normalizes the page exactly as an un-fanned page
        # would be (handles callables, ComponentState, memo).
        from reflex.compiler.compiler import into_component

        return LocaleRoute.create(
            into_component(component),
            locale=locale,
            catalog=_catalog_var(locale),
        )

    return render


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
    catalog_dir: str = "locales"
    routing: PathPrefixRouting | None = None

    def _config(self) -> I18nConfig:
        """Build the i18n configuration from the plugin's fields.

        Returns:
            The validated configuration.
        """
        return I18nConfig(
            locales=self.locales,
            default_locale=self.default_locale,
            catalog_dir=self.catalog_dir,
        )

    def __post_init__(self):
        """Activate the i18n config and register framework state.

        Raises:
            TypeError: If ``routing`` is not a PathPrefixRouting.
        """
        from reflex_base.registry import RegistrationContext

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
        # Registers I18nState (substate) and the event-scope locale provider.
        # Imported here rather than at module top so an app opting in triggers
        # it, but the package's other import paths (e.g. the reflex CLI loading
        # the i18n entry point) don't register state.
        from . import state

        # I18nState registers as a root substate on first import of .state. A
        # second app in one process (tests, dev hot-reload) is built under a
        # fresh RegistrationContext that lacks it, so re-register when absent
        # (guarded: re-registering a known substate raises).
        ctx = RegistrationContext.ensure_context()
        if state.I18nState.get_full_name() not in ctx.base_states:
            ctx.register_base_state(state.I18nState)

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
            if head in self.locales:
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
                    context={**(page.context or {}), "i18n_locale": locale},
                )

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

    def pre_compile(self, **context: Unpack[PreCompileContext]) -> None:
        """Register the catalog-emission task.

        Args:
            context: The pre-compile context.
        """
        context["add_save_task"](self._compile_catalogs)

    def _compile_catalogs(self) -> list[tuple[str, str]]:
        """Compile per-locale catalog modules from the app's ``.po`` files.

        Returns:
            Pairs of (``.web``-relative path, module code).
        """
        from reflex_base.config import get_config

        config = self._config()
        used_messages = collected_messages()
        catalog_dir = Path.cwd() / self.catalog_dir
        default_at_root = bool(getattr(self.routing, "default_at_root", True))
        deploy_url = get_config().deploy_url or ""

        default_po = catalog_dir / f"{config.default_locale}.po"
        default_catalog = read_po_catalog(default_po) if default_po.exists() else None

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
                po_path = catalog_dir / f"{locale}.po"
                catalog = read_po_catalog(po_path) if po_path.exists() else None
                if catalog is None:
                    console.warn(
                        f"No translation catalog found for locale {locale!r} "
                        f"(expected {po_path})."
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
