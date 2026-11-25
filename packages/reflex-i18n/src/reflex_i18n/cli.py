"""The ``reflex i18n`` command group: extract, init, and check catalogs.

Registered lazily as ``reflex i18n`` by ``reflex.reflex`` when this package is
installed.
"""

from __future__ import annotations

import ast
import dataclasses
import logging
import os
import sys
from collections.abc import Collection, Iterator, Sequence
from pathlib import Path
from typing import IO, TYPE_CHECKING

import click
from reflex_base.config import get_config
from reflex_base.plugins.base import get_plugin
from reflex_base.utils import log

from .catalog import is_left_untranslated
from .config import PACKAGE_CATALOG_DIR, find_package_dir, validate_locale
from .plugin import I18nPlugin
from .registry import MessageKey, collected_messages

if TYPE_CHECKING:
    from babel.messages.catalog import Catalog
    from babel.messages.extract import _ExtractionResult, _PyOptions

logger = logging.getLogger(__name__)

# An rx.t call as Babel extraction methods report one: line, keyword, messages,
# comments.
_TCall = tuple[int, str, tuple[str, ...], list[str]]

# Call names extracted for server-side (dynamic) translation, and the markers
# for text translated later. Matched syntactically by Babel, so the
# conventional ``gettext as _`` and ``gettext_noop as N_`` aliases work.
_GETTEXT_KEYWORDS = {
    "_": None,
    "N_": None,
    "gettext": None,
    "gettext_noop": None,
    "ngettext": (1, 2),
    "pgettext": ((1, "c"), 2),
}

# Babel keyword specs for the literal rx.t calls _extract_python reports, under
# names no real call has. The context variant passes the context first, as
# pgettext does.
_T_KEYWORD = "rx.t"
_T_CONTEXT_KEYWORD = "rx.t(context)"
_KEYWORDS = {
    **_GETTEXT_KEYWORDS,
    _T_KEYWORD: {1: (1,), 2: (1, 2)},
    _T_CONTEXT_KEYWORD: {2: ((1, "c"), 2), 3: ((1, "c"), 2, 3)},
}

# The attribute paths rx.t is reachable under from each module that exposes it.
_T_PATHS = {
    "reflex": ("t", "i18n.t"),
    "reflex.i18n": ("t",),
    "reflex_i18n": ("t", "vars.t"),
    "reflex_i18n.vars": ("t",),
}

_POT_FILENAME = "messages.pot"

_PACKAGE_OPTION = click.option(
    "--package",
    default=None,
    help=(
        "Manage the catalogs an installed package ships in its "
        f"{PACKAGE_CATALOG_DIR}/ directory instead of the app's."
    ),
)


@dataclasses.dataclass
class LocaleStats:
    """Per-locale translation completeness, for reporting and ``check``."""

    locale: str
    missing: int = 0
    fuzzy: int = 0
    obsolete: int = 0
    # Untranslated on purpose: flagged read-only, so not missing.
    left_untranslated: int = 0

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
    plugin = get_plugin(I18nPlugin)
    if plugin is None:
        msg = (
            "No I18nPlugin configured. Add I18nPlugin(locales=[...]) to "
            "rx.Config(plugins=[...]) in rxconfig.py."
        )
        raise click.ClickException(msg)
    return plugin


def _extract_template() -> tuple[I18nPlugin, Catalog, Path]:
    """Dry-compile the app and extract every message into a template catalog.

    Returns:
        The plugin, the extracted template, and the catalog directory.
    """
    from reflex.utils import prerequisites

    prerequisites.get_compiled_app(dry_run=True, use_rich=False)
    plugin = _resolve_plugin()
    template = extract_catalog(
        _app_source_dir(),
        collected_messages(),
        [_package_dir(package) for package in plugin.catalog_packages],
    )
    return plugin, template, Path.cwd() / plugin.catalog_dir


def _package_dir(package: str) -> Path:
    """Locate an installed package for the CLI.

    Args:
        package: The importable package name.

    Returns:
        The package directory.

    Raises:
        click.ClickException: If the package is not installed.
    """
    try:
        return find_package_dir(package)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc


def _dotted_name(node: ast.expr) -> str | None:
    """The dotted name a call target spells, e.g. ``rx.i18n.t``.

    Args:
        node: The call's ``func`` expression.

    Returns:
        The dotted name, or None if it is not a plain (attribute) name.
    """
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if not isinstance(node, ast.Name):
        return None
    parts.append(node.id)
    return ".".join(reversed(parts))


def _t_call_names(tree: ast.Module) -> set[str]:
    """The dotted names rx.t is reachable under in a module, from its imports.

    Args:
        tree: The parsed module.

    Returns:
        The names a call to rx.t is spelled as, e.g. ``{"rx.t", "rx.i18n.t"}``.
    """
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                # `import a.b as x` binds the submodule; `import a.b` binds `a`.
                module = alias.name if alias.asname else alias.name.split(".")[0]
                bound = alias.asname or module
                names.update(f"{bound}.{path}" for path in _T_PATHS.get(module, ()))
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            for alias in node.names:
                bound = alias.asname or alias.name
                if alias.name == "t" and node.module in _T_PATHS:
                    names.add(bound)
                else:
                    paths = _T_PATHS.get(f"{node.module}.{alias.name}", ())
                    names.update(f"{bound}.{path}" for path in paths)
    return names


def _string_literal(node: ast.expr) -> str | None:
    """The value of a string literal.

    Args:
        node: The expression.

    Returns:
        The string, or None if the expression is not a string literal.
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _t_calls(tree: ast.Module) -> Iterator[_TCall]:
    """Find the rx.t calls whose message, plural and context are literals.

    Args:
        tree: The parsed module.

    Yields:
        Babel extraction results, in source order.
    """
    names = _t_call_names(tree)
    if not names:
        return
    calls = sorted(
        (
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and _dotted_name(node.func) in names
        ),
        key=lambda call: (call.lineno, call.col_offset),
    )
    for call in calls:
        message = _string_literal(call.args[0]) if call.args else None
        if message is None:
            continue
        options = {
            keyword.arg: _string_literal(keyword.value)
            for keyword in call.keywords
            if keyword.arg in ("plural", "context")
        }
        if None in options.values():
            # A computed plural or context cannot be extracted reliably.
            continue
        plural = options.get("plural")
        forms = (message,) if plural is None else (message, plural)
        if context := options.get("context"):
            yield call.lineno, _T_CONTEXT_KEYWORD, (context, *forms), []
        else:
            yield call.lineno, _T_KEYWORD, forms, []


def _extract_python(
    fileobj: IO[bytes],
    keywords: Collection[str],
    comment_tags: Collection[str],
    options: _PyOptions,
) -> Iterator[_ExtractionResult | _TCall]:
    """Babel extraction method: gettext-family calls plus literal rx.t calls.

    Args:
        fileobj: The source file.
        keywords: The gettext-family call names to extract.
        comment_tags: Comment tags to collect as translator comments.
        options: Babel extraction options.

    Yields:
        Babel extraction results.
    """
    from babel.messages.extract import extract_python

    # Babel hands a method the keyword names only; the specs apply afterwards.
    yield from extract_python(fileobj, dict.fromkeys(keywords), comment_tags, options)
    fileobj.seek(0)
    try:
        tree = ast.parse(fileobj.read())
    except (SyntaxError, ValueError):
        # Babel tokenizes what it can; a module Python cannot parse has no
        # rx.t calls to add.
        return
    yield from _t_calls(tree)


def scan_sources(source_dir: Path) -> Catalog:
    """Extract the messages marked in a source tree: gettext, N_ and rx.t calls.

    Args:
        source_dir: The directory to scan. Source locations are recorded
            relative to the working directory, the project root.

    Returns:
        A catalog holding every message found (untranslated template).
    """
    from babel.messages.catalog import Catalog
    from babel.messages.extract import extract_from_dir

    catalog = Catalog()
    try:
        location_root = Path(os.path.relpath(source_dir))
    except ValueError:
        # On Windows a directory on another drive than the project (a temp
        # dir, an installed package) has no relative path.
        location_root = source_dir
    for filename, lineno, message, _comments, context in extract_from_dir(
        source_dir,
        method_map=[("**.py", f"{__name__}:{_extract_python.__name__}")],
        keywords=_KEYWORDS,
    ):
        catalog.add(
            message,
            locations=[((location_root / filename).as_posix(), lineno)],
            context=context,
        )
    return catalog


def extract_catalog(
    app_dir: Path,
    used_messages: tuple[MessageKey, ...],
    package_dirs: Sequence[Path] = (),
) -> Catalog:
    """Build the app's message template from its sources and its rx.t registry.

    Args:
        app_dir: The app source directory to scan.
        used_messages: Static ``rx.t`` messages from the compile registry,
            including computed ones the source scan cannot see.
        package_dirs: Catalog packages' directories; the messages they mark
            are translated by the packages' own catalogs, not the app's.

    Returns:
        A catalog holding every message the app translates (untranslated
        template).
    """
    catalog = scan_sources(app_dir)
    for key in used_messages:
        catalog.add(key.msgid, context=key.context)
    for package_dir in package_dirs:
        for message in scan_sources(package_dir):
            if message.id:
                catalog.delete(message.id, message.context)
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

    # Babel parses only the underscore form of a hyphenated tag (pt-BR).
    babel_locale = locale.replace("-", "_")
    if po_path.exists():
        with po_path.open("rb") as f:
            return read_po(f, locale=babel_locale)
    return Catalog(locale=babel_locale)


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
        elif is_left_untranslated(message):
            stats.left_untranslated += 1
        elif not message.string or (
            isinstance(message.string, (list, tuple)) and not all(message.string)
        ):
            stats.missing += 1
    return stats


def _report(stats: LocaleStats, *, is_source: bool = False) -> None:
    """Print a one-line summary for a locale.

    Args:
        stats: The locale stats to report.
        is_source: Whether this is the default locale, whose catalog holds the
            source text and is expected to have empty ``msgstr`` entries.
    """
    rest = f"{stats.obsolete} obsolete"
    if stats.left_untranslated:
        rest = f"{stats.left_untranslated} left untranslated, {rest}"
    if is_source:
        logger.info(f"  {stats.locale}: source catalog ({stats.obsolete} obsolete)")
    elif stats.incomplete:
        logger.warning(
            f"  {stats.locale}: {stats.missing} missing, {stats.fuzzy} fuzzy, {rest}"
        )
    else:
        logger.log(log.SUCCESS, f"  {stats.locale}: complete ({rest})")


def _app_source_dir() -> Path:
    """The app's Python source directory.

    Resolved from the imported app module (the dry compile imported it), so
    ``app_module_import`` and src layouts scan the real package; falls back to
    ``<cwd>/<app_name>`` when the module cannot be found.

    Returns:
        The directory scanned for gettext calls.
    """
    config = get_config()
    top_module = sys.modules.get(config.module.partition(".")[0])
    pkg_paths = getattr(top_module, "__path__", None)
    if pkg_paths:
        return Path(next(iter(pkg_paths)))
    module_file = getattr(top_module, "__file__", None)
    if module_file:
        return Path(module_file).parent
    return Path.cwd() / config.app_name


def _managed_catalogs(
    package: str | None,
) -> tuple[Catalog, Path, tuple[str, ...], str | None]:
    """The catalogs a command manages: the app's, or a package's own.

    Args:
        package: The package whose catalogs to manage, or None for the app's.

    Returns:
        The message template, the catalog directory, the locales it holds
        catalogs for, and the source locale (the app's default; a package has
        no source catalog).

    Raises:
        click.ClickException: If a package catalog is not named after a locale.
    """
    if package is None:
        plugin, template, catalog_dir = _extract_template()
        return template, catalog_dir, tuple(plugin.locales), plugin.default_locale
    package_dir = _package_dir(package)
    catalog_dir = package_dir / PACKAGE_CATALOG_DIR
    locales = tuple(sorted(path.stem for path in catalog_dir.glob("*.po")))
    for locale in locales:
        try:
            validate_locale(locale)
        except ValueError as exc:
            raise click.ClickException(str(exc)) from exc
    return scan_sources(package_dir), catalog_dir, locales, None


@click.group()
def i18n_cli():
    """Manage translation catalogs for the app."""


@i18n_cli.command(name="extract")
@_PACKAGE_OPTION
def extract_command(package: str | None):
    """Extract messages and update every locale's ``.po`` catalog.

    Args:
        package: The package whose catalogs to update, or None for the app's.
    """
    template, catalog_dir, locales, source_locale = _managed_catalogs(package)

    _write_catalog(template, catalog_dir / _POT_FILENAME)
    logger.info(f"Extracted {len(template)} messages.")
    if not locales:
        logger.info(
            f"No catalogs yet: create one with `reflex i18n init <locale> "
            f"--package {package}`."
        )
        return
    for locale in locales:
        _report(
            merge_into_locale(template, catalog_dir / f"{locale}.po", locale),
            is_source=locale == source_locale,
        )
    logger.log(log.SUCCESS, "Catalogs updated.")


@i18n_cli.command(name="init")
@click.argument("locale")
@_PACKAGE_OPTION
def init_command(locale: str, package: str | None):
    """Create a new ``.po`` catalog for LOCALE.

    Args:
        locale: The locale to initialize (e.g. ``de``).
        package: The package to create the catalog in, or None for the app.

    Raises:
        ClickException: If the locale is not a language tag, or the catalog
            already exists.
    """
    try:
        validate_locale(locale)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    template, catalog_dir, locales, _ = _managed_catalogs(package)
    po_path = catalog_dir / f"{locale}.po"
    if po_path.exists():
        msg = f"Catalog already exists: {po_path}. Use `reflex i18n extract`."
        raise click.ClickException(msg)

    stats = merge_into_locale(template, po_path, locale)
    logger.log(
        log.SUCCESS, f"Created {po_path} with {stats.missing} messages to translate."
    )
    if package is None and locale not in locales:
        logger.info(
            f"Add {locale!r} to I18nPlugin(locales=[...]) in rxconfig.py to ship it."
        )


@i18n_cli.command(name="check")
@_PACKAGE_OPTION
def check_command(package: str | None):
    """Fail if any non-default locale has untranslated or fuzzy messages.

    Args:
        package: The package whose catalogs to check, or None for the app's.

    Raises:
        ClickException: If a catalog is incomplete, or the package ships none.
    """
    template, catalog_dir, locales, source_locale = _managed_catalogs(package)
    if not locales:
        msg = f"{package!r} ships no catalogs in {catalog_dir}."
        raise click.ClickException(msg)

    incomplete = False
    for locale in locales:
        if locale == source_locale:
            continue
        catalog = _read_or_new_catalog(catalog_dir / f"{locale}.po", locale)
        catalog.update(template)
        stats = _catalog_stats(catalog, locale)
        _report(stats)
        incomplete = incomplete or stats.incomplete

    if incomplete:
        msg = "Some locales have untranslated or fuzzy messages."
        raise click.ClickException(msg)
    logger.log(log.SUCCESS, "All locales are complete.")
