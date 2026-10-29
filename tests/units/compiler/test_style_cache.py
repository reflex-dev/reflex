"""Tests for page-local shared style normalization."""

from typing import Any

import pytest
from reflex_base.breakpoints import Breakpoints, breakpoints_values
from reflex_base.style import Style
from reflex_base.utils.imports import ImportVar
from reflex_base.vars import VarData
from reflex_base.vars.base import Var

from reflex.compiler.plugins._style import _AppStyleCache


def test_shared_style_observes_nested_mutations() -> None:
    """Changing a raw nested mapping or responsive list invalidates conversion."""
    rule = {"_hover": {"color": "red"}, "padding": ["1px", "2px"]}
    cache = _AppStyleCache()
    first = cache(rule)
    rule["_hover"]["color"] = "blue"
    rule["padding"].append("3px")
    second = cache(rule)

    assert str(first["_hover"]["color"]) == '"red"'
    assert str(second["_hover"]["color"]) == '"blue"'
    assert len(first["padding"]) == 2
    assert len(second["padding"]) == 3


def test_shared_style_preserves_literal_types() -> None:
    """Equal Python values with different literal types must not share results."""
    rule: dict[str, Any] = {"opacity": True}
    cache = _AppStyleCache()
    first = cache(rule)
    rule["opacity"] = 1
    second = cache(rule)

    assert str(first["opacity"]) == "true"
    assert str(second["opacity"]) == "1"


@pytest.mark.parametrize("encoded", [False, True])
def test_shared_style_preserves_var_metadata(encoded: bool) -> None:
    """Dynamic style rules retain hook and import metadata after changes."""
    old_data = VarData(imports={"old-library": [ImportVar("oldColor")]})
    new_data = VarData(imports={"new-library": [ImportVar("newColor")]})
    old_color = Var("oldColor", _var_type=str, _var_data=old_data)
    new_color = Var("newColor", _var_type=str, _var_data=new_data)
    rule = {"_hover": {"color": f"{old_color}" if encoded else old_color}}
    cache = _AppStyleCache()
    first = cache(rule)
    rule["_hover"]["color"] = f"{new_color}" if encoded else new_color
    second = cache(rule)

    assert first._var_data == old_data
    assert second._var_data == new_data
    assert str(second["_hover"]["color"]) == "newColor"


def test_shared_style_observes_breakpoint_configuration(monkeypatch) -> None:
    """Breakpoint names are factorized against the current configuration."""
    rule = {"padding": Breakpoints({"xs": "10px"})}
    cache = _AppStyleCache()
    first = cache(rule)
    monkeypatch.setattr(
        "reflex_base.breakpoints.breakpoints_values", ["123em", *breakpoints_values[1:]]
    )
    second = cache(rule)

    assert list(first["padding"]) == [breakpoints_values[0]]
    assert list(second["padding"]) == ["123em"]


def test_shared_style_preserves_custom_mapping_behavior() -> None:
    """Custom mappings keep their dynamic conversion behavior."""

    class DynamicStyle(dict):
        color = "red"

        def items(self):
            return [("color", self.color)]

    rule = DynamicStyle(color="ignored")
    cache = _AppStyleCache()
    first = cache(rule)
    rule.color = "blue"
    second = cache(rule)

    assert str(first["color"]) == '"red"'
    assert str(second["color"]) == '"blue"'


@pytest.mark.parametrize(
    "rule",
    [
        {"padding_x": "3px", "font_family": "Inter"},
        {"_hover": {"color": "red"}, "padding": ["1px", "2px"]},
        {"_hover": [{"color": "red"}, {"color": "blue"}]},
        {"--color": "red", "display": None},
    ],
)
def test_shared_style_matches_uncached_conversion(rule: dict[str, Any]) -> None:
    """Static rules render identically before and after reuse."""
    cache = _AppStyleCache()
    for _ in range(2):
        normalized = cache(rule)
        expected = Style(rule)
        assert str(Var.create(normalized)) == str(Var.create(expected))
        assert normalized._var_data == expected._var_data


def test_shared_style_preserves_signed_zero() -> None:
    """Equal float values with different signs retain their JavaScript spelling."""
    rule = {"opacity": -0.0}
    cache = _AppStyleCache()
    first = cache(rule)
    rule["opacity"] = 0.0
    second = cache(rule)

    assert str(first["opacity"]) != str(second["opacity"])
    assert str(second["opacity"]) == str(Style(rule)["opacity"])


def test_shared_style_does_not_cache_custom_metaclass_equality() -> None:
    """Custom type equality cannot turn a mutable value into a literal key."""

    class EqualToInt(type):
        def __eq__(cls, other):
            return other is int

        __hash__ = type.__hash__

    class DynamicColor(metaclass=EqualToInt):
        color = "red"

        def _as_var(self):
            """Convert the current mutable color to a Var.

            Returns:
                The color at the time of conversion.
            """
            return Var.create(self.color)

    color = DynamicColor()
    rule = {"color": color}
    cache = _AppStyleCache()
    first = cache(rule)
    color.color = "blue"
    second = cache(rule)

    assert str(first["color"]) == '"red"'
    assert str(second["color"]) == '"blue"'
