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


def test_plotly_extract_points_bbox_z_source(plotly_fig: go.Figure):
    """Test that the point extractor reads the z-bbox from the z fields.

    The generated ``extractPoints`` helper must source the ``z0``/``z1`` bounding
    box members from ``point.bbox.z0``/``point.bbox.z1`` so 3D-plot event data
    reports the real z-extent instead of duplicating the y-extent.

    Args:
        plotly_fig: The figure to display.
    """
    component = rx.plotly(data=plotly_fig)
    custom_code = "\n".join(component.add_custom_code())

    assert "z0: point.bbox.z0" in custom_code
    assert "z1: point.bbox.z1" in custom_code
    assert "z0: point.bbox.y0" not in custom_code
    assert "z1: point.bbox.y1" not in custom_code
