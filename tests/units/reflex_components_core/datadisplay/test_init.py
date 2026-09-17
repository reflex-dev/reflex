"""Tests for the lazily loaded reflex_components_core.datadisplay namespace."""

import importlib

import pytest
import reflex_components_core.datadisplay as datadisplay


@pytest.mark.parametrize("name", datadisplay.__all__)
def test_lazy_attribute_resolves(name: str):
    """Every exported name must actually be importable."""
    assert getattr(datadisplay, name) is not None


@pytest.mark.parametrize(
    ("module", "name"),
    [
        ("reflex.components.datadisplay.code", "code_block"),
        ("reflex.components.datadisplay.dataeditor", "data_editor"),
    ],
)
def test_split_out_components_still_reachable(module: str, name: str):
    """The components that moved out keep working through reflex.components."""
    assert getattr(importlib.import_module(module), name) is not None
