import numpy as np
import plotly.graph_objects as go
import pytest
from plotly.io.json import config as plotly_json_config
from reflex_base.utils.serializers import (
    serialize,
    serialize_figure,
    serialize_template,
)

import reflex as rx

# Wider than the 64-bit range orjson parses exactly.
BIG_INT = 2**80 + 1


@pytest.fixture
def plotly_fig() -> go.Figure:
    """Get a plotly figure.

    Returns:
        A random plotly figure.
    """
    # Generate random data.
    rng = np.random.default_rng()
    data = rng.integers(0, 10, size=(10, 4))
    trace = go.Scatter(
        x=list(range(len(data))), y=data[:, 0], mode="lines", name="Trace 1"
    )

    # Create a graph.
    return go.Figure(data=[trace])


def test_serialize_plotly(plotly_fig: go.Figure):
    """Test that serializing a plotly figure works.

    Args:
        plotly_fig: The figure to serialize.
    """
    value = serialize(plotly_fig)
    assert isinstance(value, dict)
    assert value == serialize_figure(plotly_fig)


def test_plotly_config_option(plotly_fig: go.Figure):
    """Test that the plotly component can be created with a config option.

    Args:
        plotly_fig: The figure to display.
    """
    # This tests just confirm that the component can be created with a config option.
    _ = rx.plotly(data=plotly_fig, config={"showLink": True})


def test_plotly_locale_option_merges_into_config(plotly_fig: go.Figure):
    """Test that locale is passed through plot config.

    Args:
        plotly_fig: The figure to display.
    """
    component = rx.plotly(data=plotly_fig, locale="de")
    rendered = component._render()

    config_var = rendered.props.get("config")
    assert config_var is not None
    assert "locale" not in rendered.props
    assert "_rxGetPlotlyLocaleConfig" in str(config_var)
    assert "de" in str(config_var)


def test_plotly_basic_locale_option_merges_into_config(plotly_fig: go.Figure):
    """Test that locale works for dynamic plotly dist variants too.

    Args:
        plotly_fig: The figure to display.
    """
    component = rx.plotly.basic(data=plotly_fig, locale="fr")
    rendered = component._render()

    config_var = rendered.props.get("config")
    assert config_var is not None
    assert "locale" not in rendered.props
    assert "_rxGetPlotlyLocaleConfig" in str(config_var)
    assert "fr" in str(config_var)


def test_serialize_figure_preserves_wide_integers(monkeypatch: pytest.MonkeyPatch):
    """A customdata id wider than 64 bits survives plotly's stdlib engine.

    Args:
        monkeypatch: The pytest monkeypatch fixture.
    """
    monkeypatch.setattr(plotly_json_config, "default_engine", "json")
    fig = go.Figure(data=[go.Scatter(x=[1], y=[2], customdata=[BIG_INT])])

    assert serialize_figure(fig)["data"][0]["customdata"] == [BIG_INT]


def test_serialize_template_preserves_wide_integers(monkeypatch: pytest.MonkeyPatch):
    """Template data keeps integers wider than 64 bits on plotly's stdlib engine.

    Args:
        monkeypatch: The pytest monkeypatch fixture.
    """
    monkeypatch.setattr(plotly_json_config, "default_engine", "json")
    template = go.layout.Template(data={"scatter": [go.Scatter(customdata=[BIG_INT])]})

    serialized = serialize_template(template)

    assert serialized["data"]["scatter"][0]["customdata"] == [BIG_INT]
