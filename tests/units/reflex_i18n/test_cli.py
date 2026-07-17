"""Tests for the reflex i18n CLI helpers and command discovery."""

from pathlib import Path

import pytest
from babel.messages.pofile import read_po, write_po
from reflex_i18n.cli import (
    LocaleStats,
    _catalog_stats,
    check_command,
    extract_catalog,
    extract_command,
    i18n_cli,
    init_command,
    merge_into_locale,
)
from reflex_i18n.registry import MessageKey


def _write_app_source(app_dir: Path) -> None:
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


def test_extract_catalog_records_gettext_locations(tmp_path: Path):
    app_dir = tmp_path / "myapp"
    _write_app_source(app_dir)

    catalog = extract_catalog(app_dir, ())
    message = catalog.get("Server hello")
    assert message is not None
    assert message.locations  # source location captured for gettext calls


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


def test_catalog_stats_counts_missing_and_obsolete(tmp_path: Path):
    app_dir = tmp_path / "myapp"
    _write_app_source(app_dir)
    template = extract_catalog(app_dir, ())

    po_path = tmp_path / "de.po"
    merge_into_locale(template, po_path, "de")
    with po_path.open("rb") as f:
        catalog = read_po(f, locale="de")

    stats = _catalog_stats(catalog, "de")
    assert stats.missing == 2  # both extracted messages untranslated
    assert stats.locale == "de"


def test_locale_stats_incomplete():
    assert LocaleStats("de", missing=1).incomplete
    assert LocaleStats("de", fuzzy=1).incomplete
    assert not LocaleStats("de", obsolete=3).incomplete


def test_cli_group_registered():
    # The command group and its subcommands are wired up.
    assert set(i18n_cli.commands) == {"extract", "init", "check"}


def test_cli_group_discovered_by_reflex():
    from reflex.reflex import cli

    assert "i18n" in cli.commands


@pytest.mark.parametrize("command", [extract_command, init_command, check_command])
def test_commands_are_click_commands(command):
    import click

    assert isinstance(command, click.Command)
