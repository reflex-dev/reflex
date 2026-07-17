"""The Reflex plugin that wires i18n into an app's compilation."""

from __future__ import annotations

import dataclasses
from collections.abc import Sequence
from pathlib import Path

from reflex_base.plugins.base import CommonContext, Plugin, PreCompileContext
from reflex_base.utils import console
from typing_extensions import Unpack

from .catalog import compile_catalog_module, compile_index_module, read_po_catalog
from .config import I18nConfig, set_active_i18n_config
from .registry import collected_messages

# The compiled catalog modules are written under ``.web/i18n``.
_I18N_WEB_DIR = "i18n"
# The client runtime is written to ``.web/utils/i18n.js`` (the ``$/utils/i18n``
# import specifier used by the provider and translation vars).
_RUNTIME_WEB_PATH = "utils/i18n.js"
_RUNTIME_SOURCE = Path(__file__).parent / "_web" / "i18n.js"


@dataclasses.dataclass
class I18nPlugin(Plugin):
    """Enables ``rx.t`` translations and compiles per-locale catalogs.

    Add to ``rx.Config(plugins=[I18nPlugin(locales=[...])])``.
    """

    locales: Sequence[str]
    default_locale: str = "en"
    catalog_dir: str = "locales"

    def __post_init__(self):
        """Activate the i18n configuration and register framework state.

        Runs when the plugin is constructed (from ``rxconfig.py``), before the
        app compiles, so ``rx.t`` and server-side translation are wired and
        ``I18nState`` is registered as a substate.
        """
        set_active_i18n_config(
            I18nConfig(
                locales=self.locales,
                default_locale=self.default_locale,
                catalog_dir=self.catalog_dir,
            )
        )
        # Importing registers I18nState (substate), the event-scope locale
        # provider, and the gettext implicit-dependency hook. Import here
        # rather than at module top to keep it lazy until the plugin is used.
        from . import state  # noqa: F401

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

    def pre_compile(self, **context: Unpack[PreCompileContext]) -> None:
        """Register the catalog-emission task.

        Args:
            context: The pre-compile context.
        """
        context["add_save_task"](self._compile_catalogs)

    def _compile_catalogs(self) -> list[tuple[str, str]]:
        """Compile per-locale catalog modules from the app's ``.po`` files.

        Runs after page compilation, so the message registry holds every
        ``rx.t`` key the app uses; catalogs are filtered to those keys.

        Returns:
            Pairs of (``.web``-relative path, module code).
        """
        config = I18nConfig(
            locales=self.locales,
            default_locale=self.default_locale,
            catalog_dir=self.catalog_dir,
        )
        used_messages = collected_messages()
        catalog_dir = Path.cwd() / self.catalog_dir

        results: list[tuple[str, str]] = [
            (f"{_I18N_WEB_DIR}/index.js", compile_index_module(config))
        ]
        for locale in config.locales:
            po_path = catalog_dir / f"{locale}.po"
            catalog = read_po_catalog(po_path) if po_path.exists() else None
            if catalog is None and locale != config.default_locale:
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
