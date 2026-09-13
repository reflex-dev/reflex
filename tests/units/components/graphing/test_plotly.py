import numpy as np
import plotly.graph_objects as go
import pytest
from reflex_base.utils.serializers import serialize, serialize_figure

import reflex as rx


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


def test_plotly_id_is_forwarded_as_div_id(plotly_fig: go.Figure):
    """Test that the id prop reaches the DOM through react-plotly.js's divId.

    Plot only forwards divId to the div it renders, so a plain id prop is
    silently dropped and document.getElementById never finds the chart.

    Args:
        plotly_fig: The figure to display.
    """
    component = rx.plotly(data=plotly_fig, id="the-plot")
    rendered = component._render()

    assert "id" not in rendered.props
    assert str(rendered.props["divId"]) == '"the-plot"'
    # The ref still points at the same element, so rx.get_ref keeps working.
    assert "ref" in rendered.props


def test_plotly_without_id_sets_no_div_id(plotly_fig: go.Figure):
    """Test that the divId prop is only emitted when an id was given.

    Args:
        plotly_fig: The figure to display.
    """
    rendered = rx.plotly(data=plotly_fig)._render()

    assert "divId" not in rendered.props
    assert "id" not in rendered.props


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
