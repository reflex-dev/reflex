"""Tests for page-local shared style normalization."""

from typing import Any

import pytest
from reflex_base import style as style_module
from reflex_base.breakpoints import Breakpoints
from reflex_base.style import Style
from reflex_base.utils.imports import ImportVar
from reflex_base.vars import VarData
from reflex_base.vars.base import Var

from reflex.compiler.plugins._style import _AppStyleCache

DYNAMIC_COLOR = Var(
    "dynamicColor",
    _var_type=str,
    _var_data=VarData(imports={"color-lib": [ImportVar("dynamicColor")]}),
)


@pytest.mark.parametrize(
    "rule",
    [
        {"color": "red", "_hover": {"color": "blue"}, "padding": ["1px", "2px"]},
        {"color": DYNAMIC_COLOR, "padding": ["1px", "2px"]},
        {"outline": f"1px solid {DYNAMIC_COLOR}"},
    ],
)
def test_shared_style_normalizes_each_rule_once(
    rule: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A rule object is normalized once per cache, literal or dynamic."""
    original_convert = style_module.convert
    normalized_rules = []

    def track_convert(style_dict):
        if style_dict is rule:
            normalized_rules.append(style_dict)
        return original_convert(style_dict)

    monkeypatch.setattr(style_module, "convert", track_convert)
    cache = _AppStyleCache()
    for _ in range(3):
        cache(rule)

    assert len(normalized_rules) == 1


def test_shared_style_returns_independent_containers() -> None:
    """Each result owns its nested containers; the rule stays unchanged."""
    rule = {
        "_hover": {"color": "red"},
        "padding": ["1px", "2px"],
        "margin": Breakpoints({"xs": "1px", "md": "2px"}),
    }
    cache = _AppStyleCache()
    first = cache(rule)
    second = cache(rule)
    first["_hover"]["color"] = "pink"
    first["padding"][0] = "5px"
    first["margin"].clear()

    assert str(second["_hover"]["color"]) == '"red"'
    assert str(second["padding"][0]) == '"1px"'
    assert type(second["margin"]) is Breakpoints
    assert len(second["margin"]) == 2
    assert len(cache(rule)["margin"]) == 2
    assert rule["_hover"] == {"color": "red"}
    assert rule["padding"] == ["1px", "2px"]


def test_shared_style_observes_replaced_rule() -> None:
    """A new rule object is normalized again, even after the old one is freed."""
    cache = _AppStyleCache()
    first = cache({"color": "red"})
    second = cache({"color": "blue"})

    assert str(first["color"]) == '"red"'
    assert str(second["color"]) == '"blue"'


@pytest.mark.parametrize(
    "rule",
    [
        {"padding_x": "3px", "font_family": "Inter"},
        {"_hover": {"color": "red"}, "padding": ["1px", "2px"]},
        {"_hover": [{"color": "red"}, {"color": "blue"}]},
        {"--color": "red", "display": None},
        {"color": DYNAMIC_COLOR, "_hover": {"outline": f"1px solid {DYNAMIC_COLOR}"}},
        {"padding": Breakpoints({"xs": "10px", "md": "20px"})},
    ],
)
def test_shared_style_matches_uncached_conversion(rule: dict[str, Any]) -> None:
    """Rules render identically, with the same metadata, before and after reuse."""
    cache = _AppStyleCache()
    for _ in range(2):
        normalized = cache(rule)
        expected = Style(rule)
        assert str(Var.create(normalized)) == str(Var.create(expected))
        assert normalized._var_data == expected._var_data
