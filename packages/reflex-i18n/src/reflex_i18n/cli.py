"""The ``reflex i18n`` command group: extract, init, and check catalogs.

Attached to the ``reflex`` CLI via the ``reflex.cli`` entry point.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import TYPE_CHECKING

import click
from reflex_base.config import get_config
from reflex_base.utils import console

from .plugin import I18nPlugin
from .registry import MessageKey, collected_messages

if TYPE_CHECKING:
    from babel.messages.catalog import Catalog

# Call names extracted for server-side (dynamic) translation. Matched
# syntactically by Babel, so the conventional ``gettext as _`` alias works.
_GETTEXT_KEYWORDS = {
    "_": None,
    "gettext": None,
    "ngettext": (1, 2),
    "pgettext": ((1, "c"), 2),
}

_POT_FILENAME = "messages.pot"


@dataclasses.dataclass
class LocaleStats:
    """Per-locale translation completeness, for reporting and ``check``."""

    locale: str
    missing: int = 0
    fuzzy: int = 0
    obsolete: int = 0

    @property
    def incomplete(self) -> bool:
        """Whether the locale has untranslated or fuzzy messages.

        Returns:
            True if any message is missing or fuzzy.
        """
        return bool(self.missing or self.fuzzy)


def _resolve_plugin() -> I18nPlugin:
    """Find the active I18nPlugin in the loaded config.

    Returns:
        The configured plugin.

    Raises:
        click.ClickException: If no I18nPlugin is configured.
    """
    plugin = next((p for p in get_config().plugins if isinstance(p, I18nPlugin)), None)
    if plugin is None:
        msg = (
            "No I18nPlugin configured. Add I18nPlugin(locales=[...]) to "
            "rx.Config(plugins=[...]) in rxconfig.py."
        )
        raise click.ClickException(msg)
    return plugin


def _extract_template() -> tuple[I18nPlugin, Catalog, Path]:
    """Dry-compile the app and extract every message into a template catalog.

    Compiling populates the ``rx.t`` registry; the template then unions those
    static messages with the dynamic gettext calls in the app source.

    Returns:
        The configured plugin, the freshly extracted template, and the
        absolute catalog directory.
    """
    from reflex.utils import prerequisites

    prerequisites.get_compiled_app(dry_run=True, use_rich=False)
    plugin = _resolve_plugin()
    template = extract_catalog(_app_source_dir(), collected_messages())
    return plugin, template, Path.cwd() / plugin.catalog_dir


def extract_catalog(app_dir: Path, used_messages: tuple[MessageKey, ...]) -> Catalog:
    """Build a message-template catalog from both translation sources.

    Args:
        app_dir: The app source directory to scan for gettext calls.
        used_messages: Static ``rx.t`` messages from the compile registry.

    Returns:
        A catalog holding every extracted message (untranslated template).
    """
    from babel.messages.catalog import Catalog
    from babel.messages.extract import extract_from_dir

    catalog = Catalog()

    # Dynamic content: gettext-family calls in the app source (with locations).
    for filename, lineno, message, _comments, context in extract_from_dir(
        app_dir, keywords=_GETTEXT_KEYWORDS
    ):
        catalog.add(
            message,
            locations=[(str(Path(app_dir.name) / filename), lineno)],
            context=context,
        )

    # Static content: rx.t messages collected during compilation.
    for key in used_messages:
        catalog.add(key.msgid, context=key.context)

    return catalog


def _read_or_new_catalog(po_path: Path, locale: str) -> Catalog:
    """Read an existing ``.po`` file or create an empty catalog for a locale.

    Args:
        po_path: The path of the ``.po`` file.
        locale: The locale identifier.

    Returns:
        The loaded or newly created catalog.
    """
    from babel.messages.catalog import Catalog
    from babel.messages.pofile import read_po

    if po_path.exists():
        with po_path.open("rb") as f:
            return read_po(f, locale=locale)
    return Catalog(locale=locale)


def _write_catalog(catalog: Catalog, path: Path) -> None:
    """Write a catalog to a ``.po``/``.pot`` file.

    Args:
        catalog: The catalog to write.
        path: The destination path.
    """
    from babel.messages.pofile import write_po

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as f:
        write_po(f, catalog, omit_header=False)


def merge_into_locale(template: Catalog, po_path: Path, locale: str) -> LocaleStats:
    """Merge the template into a locale catalog, preserving translations.

    Args:
        template: The freshly extracted message template.
        po_path: The locale's ``.po`` file path.
        locale: The locale identifier.

    Returns:
        Stats describing the merged catalog.
    """
    catalog = _read_or_new_catalog(po_path, locale)
    catalog.update(template)
    _write_catalog(catalog, po_path)
    return _catalog_stats(catalog, locale)


def _catalog_stats(catalog: Catalog, locale: str) -> LocaleStats:
    """Count untranslated, fuzzy, and obsolete messages in a catalog.

    Args:
        catalog: The catalog to inspect.
        locale: The locale identifier.

    Returns:
        The computed stats.
    """
    stats = LocaleStats(locale=locale, obsolete=len(catalog.obsolete))
    for message in catalog:
        if not message.id:  # the header entry
            continue
        if "fuzzy" in message.flags:
            stats.fuzzy += 1
        elif not message.string or (
            isinstance(message.string, (list, tuple)) and not all(message.string)
        ):
            stats.missing += 1
    return stats


def _report(stats: LocaleStats) -> None:
    """Print a one-line summary for a locale.

    Args:
        stats: The locale stats to report.
    """
    detail = f"{stats.missing} missing, {stats.fuzzy} fuzzy, {stats.obsolete} obsolete"
    if stats.incomplete:
        console.warn(f"  {stats.locale}: {detail}")
    else:
        console.success(f"  {stats.locale}: complete ({stats.obsolete} obsolete)")


def _app_source_dir() -> Path:
    """The app's Python source directory.

    Returns:
        The directory scanned for gettext calls.
    """
    return Path.cwd() / get_config().app_name


@click.group()
def i18n_cli():
    """Manage translation catalogs for the app."""


@i18n_cli.command(name="extract")
def extract_command():
    """Extract messages and update every locale's ``.po`` catalog."""
    plugin, template, catalog_dir = _extract_template()

    _write_catalog(template, catalog_dir / _POT_FILENAME)
    console.info(f"Extracted {len(template)} messages.")
    for locale in plugin.locales:
        _report(merge_into_locale(template, catalog_dir / f"{locale}.po", locale))
    console.success("Catalogs updated.")


@i18n_cli.command(name="init")
@click.argument("locale")
def init_command(locale: str):
    """Create a new ``.po`` catalog for LOCALE.

    Args:
        locale: The locale to initialize (e.g. ``de``).

    Raises:
        ClickException: If the catalog already exists.
    """
    plugin, template, catalog_dir = _extract_template()
    po_path = catalog_dir / f"{locale}.po"
    if po_path.exists():
        msg = f"Catalog already exists: {po_path}. Use `reflex i18n extract`."
        raise click.ClickException(msg)

    stats = merge_into_locale(template, po_path, locale)
    console.success(f"Created {po_path} with {stats.missing} messages to translate.")
    if locale not in plugin.locales:
        console.info(
            f"Add {locale!r} to I18nPlugin(locales=[...]) in rxconfig.py to ship it."
        )


@i18n_cli.command(name="check")
def check_command():
    """Fail if any non-default locale has untranslated or fuzzy messages."""
    plugin, template, catalog_dir = _extract_template()

    incomplete = False
    for locale in plugin.locales:
        if locale == plugin.default_locale:
            continue
        catalog = _read_or_new_catalog(catalog_dir / f"{locale}.po", locale)
        catalog.update(template)
        stats = _catalog_stats(catalog, locale)
        _report(stats)
        incomplete = incomplete or stats.incomplete

    if incomplete:
        msg = "Some locales have untranslated or fuzzy messages."
        raise click.ClickException(msg)
    console.success("All locales are complete.")
