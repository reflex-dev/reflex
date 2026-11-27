"""Tests for the allowlist of the parity harness."""

import pytest
import reflex_components_ui
from reflex_base.components.component import ComponentNamespace
from ui_parity import allowlist
from ui_parity.allowlist import (
    Allowlist,
    AllowlistError,
    ApiEntry,
    ContractEntry,
    LookEntry,
)

# The accepted differences the first component waves bring, in the file's form.
DOCUMENT = {
    "api": [
        {
            "component": "select",
            "kind": "prop",
            "names": ["position"],
            "reason": "Select has no item-aligned positioning.",
        }
    ],
    "contract": [
        {
            "component": "dialog",
            "step": "Tab stays inside the dialog",
            "reason": "A native modal dialog lets Tab reach the browser's own UI.",
        },
        {
            "component": "switch",
            "step": "Enter toggles",
            "system": "rx.ui",
            "engines": ["firefox", "webkit"],
            "reason": "A switch toggles on Space but not Enter.",
        },
    ],
    "look": [
        {
            "component": "tooltip",
            "check": "pixels",
            "cells": "*@open",
            "reason": "Tooltips have no arrow.",
        },
        {
            "component": "select",
            "check": "style",
            "properties": ["top", "left"],
            "engines": ["webkit"],
            "reason": "Select has no item-aligned positioning.",
        },
    ],
}

ENTRIES = Allowlist(
    api=(
        ApiEntry(
            component="select",
            kind="prop",
            names=("position",),
            reason="Select has no item-aligned positioning.",
        ),
    ),
    contract=(
        ContractEntry(
            component="dialog",
            step="Tab stays inside the dialog",
            system="rx.ui",
            engines=(),
            reason="A native modal dialog lets Tab reach the browser's own UI.",
        ),
        ContractEntry(
            component="switch",
            step="Enter toggles",
            system="rx.ui",
            engines=("firefox", "webkit"),
            reason="A switch toggles on Space but not Enter.",
        ),
    ),
    look=(
        LookEntry(
            component="tooltip",
            check="pixels",
            cells="*@open",
            properties=(),
            engines=(),
            reason="Tooltips have no arrow.",
        ),
        LookEntry(
            component="select",
            check="style",
            cells="*",
            properties=("top", "left"),
            engines=("webkit",),
            reason="Select has no item-aligned positioning.",
        ),
    ),
)


def test_parse_reads_every_table_with_its_defaults():
    assert allowlist.parse(DOCUMENT) == ENTRIES
    assert allowlist.parse({}) == Allowlist()


@pytest.mark.parametrize(
    ("document", "message"),
    [
        ({"pixels": []}, "Unknown allowlist tables: ['pixels']."),
        (
            {"api": [{"component": "box", "kind": "prop", "names": ["a"]}]},
            (
                "[[api]] entry {'component': 'box', 'kind': 'prop', 'names': ['a']} "
                "is missing: ['reason']."
            ),
        ),
        (
            {"contract": [{"component": "box", "step": "s", "reason": " "}]},
            (
                "[[contract]] entry {'component': 'box', 'step': 's', 'reason': ' '} "
                "needs a reason."
            ),
        ),
        (
            {
                "look": [
                    {"component": "box", "check": "pixels", "cell": "*", "reason": "r"}
                ]
            },
            (
                "[[look]] entry {'component': 'box', 'check': 'pixels', 'cell': '*', "
                "'reason': 'r'} has unknown keys: ['cell']."
            ),
        ),
        (
            {
                "api": [
                    {"component": "box", "kind": "props", "names": [], "reason": "r"}
                ]
            },
            "[[api]] kind = \"props\" is not one of ['prop', 'type', 'event'].",
        ),
        (
            {
                "contract": [
                    {"component": "b", "step": "s", "system": "ui", "reason": "r"}
                ]
            },
            "[[contract]] system = \"ui\" is not one of ['rx', 'rx.ui'].",
        ),
        (
            {"look": [{"component": "box", "check": "color", "reason": "r"}]},
            "[[look]] check = \"color\" is not one of ['pixels', 'style', 'a11y'].",
        ),
    ],
)
def test_parse_rejects_what_it_does_not_understand(document: dict, message: str):
    with pytest.raises(AllowlistError) as error:
        allowlist.parse(document)
    assert str(error.value) == message


def test_contract_entry_covers_its_system_and_engines():
    everywhere, some = ENTRIES.contract
    step = "Tab stays inside the dialog"
    assert [
        everywhere.covers("dialog", step, system, engine)
        for system in ("rx.ui", "rx")
        for engine in ("chromium", "webkit")
    ] == [True, True, False, False]
    assert everywhere.covers("dialog", "Escape closes", "rx.ui", "chromium") is False
    assert everywhere.covers("select", step, "rx.ui", "chromium") is False
    assert [
        some.covers("switch", "Enter toggles", "rx.ui", engine)
        for engine in ("chromium", "firefox", "webkit")
    ] == [False, True, True]


def test_look_entry_covers_its_check_cells_and_engines():
    arrow, position = ENTRIES.look
    assert [
        arrow.covers("tooltip", check, cell, "firefox")
        for check in ("pixels", "style")
        for cell in ("base@open", "side-top@dark@open", "base")
    ] == [True, True, False, False, False, False]
    assert [
        position.covers("select", "style", "base", engine)
        for engine in ("chromium", "webkit")
    ] == [False, True]


def test_differences_markdown_lists_every_entry_by_component():
    assert allowlist.differences_markdown(ENTRIES) == (
        "### dialog\n"
        "\n"
        '- behaviour, `rx.ui`, "Tab stays inside the dialog": A native modal '
        "dialog lets Tab reach the browser's own UI.\n"
        "\n"
        "### select\n"
        "\n"
        "- prop `position`: Select has no item-aligned positioning.\n"
        "- style in webkit, `top`, `left`: Select has no item-aligned positioning.\n"
        "\n"
        "### switch\n"
        "\n"
        '- behaviour, `rx.ui` in firefox, webkit, "Enter toggles": A switch '
        "toggles on Space but not Enter.\n"
        "\n"
        "### tooltip\n"
        "\n"
        "- pixels, *@open: Tooltips have no arrow."
    )


def test_committed_allowlist_names_only_rx_ui_components():
    components = set(reflex_components_ui.__all__)
    # A member of a namespace is listed by its own name: "kbd" is text.kbd.
    for name in reflex_components_ui.__all__:
        value = getattr(reflex_components_ui, name)
        if isinstance(value, ComponentNamespace):
            components.update(
                member for member in dir(value) if not member.startswith("_")
            )
    entries = allowlist.load()
    listed = {
        entry.component for entry in (*entries.api, *entries.contract, *entries.look)
    }
    assert sorted(listed - components) == []
