"""Tests for the reflex i18n CLI helpers and command discovery."""

import logging
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import click
import pytest
from babel.messages.pofile import read_po, write_po
from reflex_base.config import get_config
from reflex_base.utils.exceptions import ConfigError
from reflex_i18n import I18nPlugin
from reflex_i18n.cli import (
    LocaleStats,
    _app_source_dir,
    _catalog_stats,
    _report,
    _resolve_plugin,
    check_command,
    extract_catalog,
    extract_command,
    i18n_cli,
    init_command,
    merge_into_locale,
    scan_sources,
)
from reflex_i18n.config import set_active_i18n_config
from reflex_i18n.registry import MessageKey


def _write_app_source(app_dir: Path) -> None:
    """Write an app module with a gettext and an ngettext call.

    Args:
        app_dir: The app directory, created if missing.
    """
    app_dir.mkdir(parents=True, exist_ok=True)
    (app_dir / "app.py").write_text(
        "from reflex_i18n import gettext as _\n"
        'x = _("Server hello")\n'
        'y = ngettext("{n} file", "{n} files", 2)\n',
        encoding="utf-8",
    )


def test_extract_catalog_unions_both_sources(tmp_path: Path):
    app_dir = tmp_path / "myapp"
    _write_app_source(app_dir)
    used = (
        MessageKey("Static hello"),
        MessageKey("{count} item", plural="{count} items"),
        MessageKey("Open", context="menu"),
    )

    catalog = extract_catalog(app_dir, used)
    ids = [m.id for m in catalog if m.id]

    # From gettext source extraction.
    assert "Server hello" in ids
    assert ("{n} file", "{n} files") in ids
    # From the rx.t registry.
    assert "Static hello" in ids
    assert ("{count} item", "{count} items") in ids
    # Context-qualified message is keyed by (id, context).
    assert catalog.get("Open", context="menu") is not None


@pytest.mark.parametrize("layout", ["myapp", "src/myapp"])
def test_extract_catalog_records_gettext_locations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, layout: str
):
    # Locations resolve from the project root the CLI runs in, src layouts too.
    monkeypatch.chdir(tmp_path)
    app_dir = tmp_path / layout
    _write_app_source(app_dir)

    catalog = extract_catalog(app_dir, ())
    message = catalog.get("Server hello")
    assert message is not None
    assert message.locations == [(f"{layout}/app.py", 2)]


def test_extract_catalog_picks_up_noop_markers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(tmp_path)
    app_dir = tmp_path / "myapp"
    app_dir.mkdir()
    (app_dir / "labels.py").write_text(
        "from reflex_i18n import N_, gettext_noop\n"
        'LABELS = {1: N_("Refill"), 2: gettext_noop("Removal")}\n',
        encoding="utf-8",
    )

    catalog = extract_catalog(app_dir, ())

    assert [(m.id, m.locations) for m in catalog if m.id] == [
        ("Refill", [("myapp/labels.py", 2)]),
        ("Removal", [("myapp/labels.py", 2)]),
    ]


def test_merge_preserves_existing_translation(tmp_path: Path):
    app_dir = tmp_path / "myapp"
    _write_app_source(app_dir)
    po_path = tmp_path / "locales" / "de.po"

    # First extraction seeds the catalog untranslated.
    template = extract_catalog(app_dir, (MessageKey("Static hello"),))
    merge_into_locale(template, po_path, "de")

    # Translate one message, then re-merge.
    with po_path.open("rb") as f:
        catalog = read_po(f)
    message = catalog.get("Static hello")
    assert message is not None
    message.string = "Statisch hallo"
    with po_path.open("wb") as f:
        write_po(f, catalog)

    stats = merge_into_locale(template, po_path, "de")
    with po_path.open("rb") as f:
        merged = read_po(f)
    # Translation survived the re-merge.
    merged_message = merged.get("Static hello")
    assert merged_message is not None
    assert merged_message.string == "Statisch hallo"
    # "Server hello" and the plural remain untranslated.
    assert stats.missing == 2


@pytest.mark.parametrize(
    ("locale", "plural_forms"),
    [("pt-BR", "nplurals=2; plural=(n > 1);"), ("zh-Hant", "nplurals=1; plural=0;")],
)
def test_merge_into_locale_accepts_region_and_script_tags(
    tmp_path: Path, locale: str, plural_forms: str
):
    # Configured tags are hyphenated; Babel only parses its underscore form,
    # both for a new catalog and for reading an existing one back.
    template = extract_catalog(tmp_path, (MessageKey("Static hello"),))
    po_path = tmp_path / "locales" / f"{locale}.po"

    merge_into_locale(template, po_path, locale)
    stats = merge_into_locale(template, po_path, locale)

    assert stats.missing == 1
    assert plural_forms in po_path.read_text(encoding="utf-8")


def test_catalog_stats_counts_missing_and_obsolete(tmp_path: Path):
    app_dir = tmp_path / "myapp"
    _write_app_source(app_dir)
    po_path = tmp_path / "de.po"
    # An earlier extraction still had a message the app no longer uses.
    merge_into_locale(
        extract_catalog(app_dir, (MessageKey("Removed message"),)), po_path, "de"
    )
    merge_into_locale(extract_catalog(app_dir, ()), po_path, "de")
    with po_path.open("rb") as f:
        catalog = read_po(f, locale="de")

    stats = _catalog_stats(catalog, "de")
    assert stats.missing == 2  # both extracted messages untranslated
    assert stats.obsolete == 1
    assert stats.locale == "de"


def test_init_rejects_a_locale_that_is_not_a_language_tag():
    from click.testing import CliRunner

    # The argument becomes a catalog filename, so it is validated before any
    # path is built from it (and before the app is compiled).
    result = CliRunner().invoke(i18n_cli, ["init", "../../escape"])
    assert result.exit_code != 0
    assert "Invalid locale" in result.output


def test_report_marks_the_default_locale_as_the_source_catalog(
    caplog: pytest.LogCaptureFixture,
):
    # The default locale's empty msgstr entries are the source text, not a
    # translation gap, so they must not be reported as missing.
    caplog.set_level(logging.INFO)
    _report(LocaleStats("en", missing=7), is_source=True)
    output = caplog.text
    assert "source catalog" in output
    assert "missing" not in output


def test_locale_stats_incomplete():
    assert LocaleStats("de", missing=1).incomplete
    assert LocaleStats("de", fuzzy=1).incomplete
    assert not LocaleStats("de", obsolete=3).incomplete


def test_cli_group_registered():
    # The command group and its subcommands are wired up.
    assert set(i18n_cli.commands) == {"extract", "init", "check"}


def test_cli_group_discovered_by_reflex():
    import click

    from reflex.reflex import _LazyCommand, cli

    ctx = click.Context(cli)
    command = cli.get_command(ctx, "i18n")
    assert isinstance(command, _LazyCommand)
    assert command._resolve() is i18n_cli
    assert "i18n" in cli.list_commands(ctx)


@pytest.mark.parametrize("command", [extract_command, init_command, check_command])
def test_commands_are_click_commands(command):
    import click

    assert isinstance(command, click.Command)


def test_app_source_dir_resolves_from_imported_module(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    # An app_module_import / src layout scans the imported package, not
    # <cwd>/<app_name>.
    pkg_dir = tmp_path / "src" / "mypkg"
    pkg_dir.mkdir(parents=True)
    module = types.ModuleType("mypkg")
    module.__path__ = [str(pkg_dir)]
    monkeypatch.setitem(sys.modules, "mypkg", module)
    monkeypatch.setattr(
        "reflex_i18n.cli.get_config",
        lambda: SimpleNamespace(module="mypkg.app", app_name="otherdir"),
    )
    assert _app_source_dir() == pkg_dir


def test_app_source_dir_falls_back_to_app_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delitem(sys.modules, "missingmod", raising=False)
    monkeypatch.setattr(
        "reflex_i18n.cli.get_config",
        lambda: SimpleNamespace(module="missingmod.app", app_name="myapp"),
    )
    assert _app_source_dir() == tmp_path / "myapp"


def test_scan_sources_finds_literal_rx_t_calls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(tmp_path)
    lib = tmp_path / "mylib"
    lib.mkdir()
    (lib / "ui.py").write_text(
        "import reflex as rx\n"
        "import reflex_i18n\n"
        "from reflex.i18n import t as tr\n"
        "from reflex_i18n import gettext as _\n"
        'a = rx.t("Save")\n'
        'b = rx.i18n.t("{count} row", plural="{count} rows", count=n)\n'
        'c = tr("Open", context="menu")\n'
        'd = reflex_i18n.t("{count} file", plural="{count} files", count=n, context="disk")\n'
        "e = rx.t(label)\n"
        'f = rx.t("Copy", plural=plural, count=n)\n'
        'g = other.t("Not reflex")\n'
        'h = _("Server")\n',
        encoding="utf-8",
    )

    catalog = scan_sources(lib)

    # gettext calls first, then the rx.t calls of the same file; computed
    # messages, plurals and foreign `.t` calls are skipped.
    assert [(m.id, m.context, m.locations) for m in catalog if m.id] == [
        ("Server", None, [("mylib/ui.py", 12)]),
        ("Save", None, [("mylib/ui.py", 5)]),
        (("{count} row", "{count} rows"), None, [("mylib/ui.py", 6)]),
        ("Open", "menu", [("mylib/ui.py", 7)]),
        (("{count} file", "{count} files"), "disk", [("mylib/ui.py", 8)]),
    ]


@pytest.mark.parametrize(
    ("imports", "call"),
    [
        ("import reflex as rx", "rx.t"),
        ("import reflex as rx", "rx.i18n.t"),
        ("import reflex", "reflex.t"),
        ("import reflex.i18n", "reflex.i18n.t"),
        ("import reflex.i18n as i18n", "i18n.t"),
        ("from reflex import i18n", "i18n.t"),
        ("from reflex import t", "t"),
        ("from reflex.i18n import t as tr", "tr"),
        ("import reflex_i18n", "reflex_i18n.t"),
        ("import reflex_i18n.vars", "reflex_i18n.vars.t"),
        ("import reflex_i18n.vars as v", "v.t"),
        ("from reflex_i18n import vars as v", "v.t"),
        ("from reflex_i18n.vars import t", "t"),
    ],
)
def test_scan_sources_finds_rx_t_under_every_import(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, imports: str, call: str
):
    monkeypatch.chdir(tmp_path)
    lib = tmp_path / "mylib"
    lib.mkdir()
    (lib / "ui.py").write_text(
        f'{imports}\nlabel = {call}("Save")\nother = t2("Not reflex")\n',
        encoding="utf-8",
    )

    catalog = scan_sources(lib)

    assert [(m.id, m.locations) for m in catalog if m.id] == [
        ("Save", [("mylib/ui.py", 2)])
    ]


def test_scan_sources_records_absolute_locations_across_drives(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    # Windows: relpath raises for a directory on another drive than the cwd.
    def relpath(path: str, start: str | None = None) -> str:
        """Fail like os.path.relpath on Windows for paths on different drives.

        Args:
            path: The path to make relative.
            start: The directory to make it relative to.

        Raises:
            ValueError: Always.
        """
        msg = "path is on mount 'C:', start on mount 'D:'"
        raise ValueError(msg)

    # Only the CLI's own binding: Babel also calls os.path.relpath per file.
    monkeypatch.setattr(
        "reflex_i18n.cli.os", SimpleNamespace(path=SimpleNamespace(relpath=relpath))
    )
    lib = tmp_path / "mylib"
    lib.mkdir()
    (lib / "ui.py").write_text(
        'from reflex_i18n import N_\nLABEL = N_("Refill")\n', encoding="utf-8"
    )

    catalog = scan_sources(lib)

    assert [(m.id, m.locations) for m in catalog if m.id] == [
        ("Refill", [((lib / "ui.py").as_posix(), 2)])
    ]


def test_extract_catalog_leaves_package_messages_to_the_package(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(tmp_path)
    app_dir = tmp_path / "myapp"
    app_dir.mkdir()
    (app_dir / "app.py").write_text(
        "import reflex as rx\n"
        "from reflex_i18n import gettext as _\n"
        'x = _("App text")\n'
        'y = rx.t("Save")\n',
        encoding="utf-8",
    )
    lib = tmp_path / "mylib"
    lib.mkdir()
    (lib / "ui.py").write_text(
        "import reflex as rx\n"
        "from reflex_i18n import N_\n"
        'LABEL = N_("Refill")\n'
        'save = rx.t("Save")\n',
        encoding="utf-8",
    )
    # The registry also holds the library's rx.t messages and a label the
    # library built from the app's data.
    used = (MessageKey("Save"), MessageKey("Refill"), MessageKey("Machine name"))

    catalog = extract_catalog(app_dir, used, [lib])

    assert [m.id for m in catalog if m.id] == ["App text", "Machine name"]


def _write_package(site: Path, source: str) -> Path:
    """Write a mylib package with the given source.

    Args:
        site: The directory to create the package in.
        source: The source of the package's __init__.py.

    Returns:
        The package directory.
    """
    package_dir = site / "mylib"
    package_dir.mkdir(parents=True, exist_ok=True)
    (package_dir / "__init__.py").write_text(source, encoding="utf-8")
    return package_dir


def _po_strings(po_path: Path) -> dict[object, object]:
    """Read the translations of a .po file.

    Args:
        po_path: The .po file.

    Returns:
        The translation of every message by its msgid.
    """
    with po_path.open("rb") as f:
        return {m.id: m.string for m in read_po(f) if m.id}


def test_package_mode_manages_the_catalogs_a_package_ships(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from click.testing import CliRunner

    monkeypatch.chdir(tmp_path)
    monkeypatch.syspath_prepend(str(tmp_path / "src"))
    package_dir = _write_package(
        tmp_path / "src", 'from reflex_i18n import N_\nLABEL = N_("Refill")\n'
    ).resolve()
    catalog_dir = package_dir / "locales"
    runner = CliRunner()

    result = runner.invoke(i18n_cli, ["check", "--package", "mylib"])
    assert result.exit_code == 1
    assert result.output == f"Error: 'mylib' ships no catalogs in {catalog_dir}.\n"

    result = runner.invoke(i18n_cli, ["init", "de", "--package", "mylib"])
    assert result.exit_code == 0, result.output
    assert _po_strings(catalog_dir / "de.po") == {"Refill": ""}
    assert runner.invoke(i18n_cli, ["check", "--package", "mylib"]).exit_code == 1

    (catalog_dir / "de.po").write_text(
        (catalog_dir / "de.po")
        .read_text(encoding="utf-8")
        .replace(
            'msgid "Refill"\nmsgstr ""', 'msgid "Refill"\nmsgstr "Bef\u00fcllung"'
        ),
        encoding="utf-8",
    )
    assert runner.invoke(i18n_cli, ["check", "--package", "mylib"]).exit_code == 0

    _write_package(
        tmp_path / "src",
        'from reflex_i18n import N_\nLABEL = N_("Refill")\nOTHER = N_("Removal")\n',
    )
    result = runner.invoke(i18n_cli, ["extract", "--package", "mylib"])
    assert result.exit_code == 0, result.output
    assert _po_strings(catalog_dir / "de.po") == {
        "Refill": "Bef\u00fcllung",
        "Removal": "",
    }
    assert _po_strings(catalog_dir / "messages.pot") == {"Refill": "", "Removal": ""}
    assert runner.invoke(i18n_cli, ["check", "--package", "mylib"]).exit_code == 1


def test_package_mode_rejects_an_uninstalled_package():
    from click.testing import CliRunner

    result = CliRunner().invoke(
        i18n_cli, ["extract", "--package", "no_such_i18n_package"]
    )
    assert result.exit_code == 1
    assert result.output == (
        "Error: Cannot find the package 'no_such_i18n_package': it is not installed.\n"
    )


def test_resolve_plugin_requires_exactly_one_i18n_plugin(
    monkeypatch: pytest.MonkeyPatch,
):
    # The commands manage one plugin's catalogs, so a duplicate fails as it
    # does for get_plugin() everywhere else rather than picking the first.
    plugin = I18nPlugin(locales=["en"])
    try:
        monkeypatch.setattr(get_config(), "plugins", [plugin])
        assert _resolve_plugin() is plugin

        duplicate = I18nPlugin(locales=["de"], default_locale="de")
        monkeypatch.setattr(get_config(), "plugins", [plugin, duplicate])
        with pytest.raises(ConfigError) as config_error:
            _resolve_plugin()
        assert str(config_error.value) == (
            "Multiple I18nPlugin instances are configured, but get_plugin() "
            "requires an unambiguous match. Request a more specific type or "
            "remove duplicate entries from the rxconfig plugins list."
        )

        monkeypatch.setattr(get_config(), "plugins", [])
        with pytest.raises(click.ClickException) as click_error:
            _resolve_plugin()
        assert click_error.value.message == (
            "No I18nPlugin configured. Add I18nPlugin(locales=[...]) to "
            "rx.Config(plugins=[...]) in rxconfig.py."
        )
    finally:
        set_active_i18n_config(None)
