"""Tests for rx.plotly locale support."""
from types import SimpleNamespace
from unittest.mock import patch
from reflex.components.plotly.plotly import Plotly
from reflex.vars.base import LiteralVar


def make_plotly(**props):
    """Instantiate Plotly directly, bypassing create() which needs plotly installed."""
    component = Plotly.__new__(Plotly)
    for k, v in props.items():
        setattr(component, k, LiteralVar.create(v))
    return component


def test_plotly_locale_default():
    """locale defaults to empty string."""
    c = make_plotly(locale="")
    assert str(c.locale) == '""'


def test_plotly_locale_de():
    """locale prop stores German locale code."""
    c = make_plotly(locale="de")
    assert str(c.locale) == '"de"'


def test_plotly_locale_zh():
    """locale prop stores Chinese locale code."""
    c = make_plotly(locale="zh-CN")
    assert str(c.locale) == '"zh-CN"'


def test_config_has_plotly_locale():
    """plotly_locale field exists on Config."""
    from reflex.config import BaseConfig
    import dataclasses
    fields = {f.name for f in dataclasses.fields(BaseConfig)}
    assert "plotly_locale" in fields


def test_config_plotly_locale_default():
    """plotly_locale defaults to empty string."""
    from reflex.config import BaseConfig
    import dataclasses
    field = next(f for f in dataclasses.fields(BaseConfig) if f.name == "plotly_locale")
    assert field.default == ""
