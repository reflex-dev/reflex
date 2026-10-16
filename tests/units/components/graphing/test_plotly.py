import json
import shutil
import subprocess

import numpy as np
import plotly.graph_objects as go
import pytest
from pytest_mock import MockerFixture
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
    component = rx.plotly(data=plotly_fig, config={"displaylogo": False})
    assert '["displaylogo"] : false' in str(component._render().props["config"])


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


def test_plotly_id_renders_as_div_id(plotly_fig: go.Figure):
    """Test that `id` reaches the DOM via react-plotly.js's `divId` prop.

    Args:
        plotly_fig: The figure to display.
    """
    rendered = rx.plotly(data=plotly_fig, id="the-plot")._render()

    assert "id" not in rendered.props
    assert "the-plot" in str(rendered.props["divId"])


def test_plotly_without_id_has_no_div_id(plotly_fig: go.Figure):
    """Test that no `divId` is emitted when no `id` was given.

    Args:
        plotly_fig: The figure to display.
    """
    rendered = rx.plotly(data=plotly_fig)._render()

    assert "divId" not in rendered.props


def test_plotly_normalizes_string_layout_title(plotly_fig: go.Figure):
    """Normalize string layout titles for Plotly.js."""
    rendered = rx.plotly(
        data=plotly_fig,
        layout={"title": "layout title", "height": 300},
    )._render()

    layout_prop = str(rendered.special_props)
    assert "_rxNormalizePlotlyLayout" in layout_prop
    assert '["title"] : "layout title"' in layout_prop


def test_plotly_preserves_object_layout_title(plotly_fig: go.Figure):
    """Preserve object-form Plotly layout titles."""
    rendered = rx.plotly(
        data=plotly_fig,
        layout={"title": {"text": "layout title"}, "height": 300},
    )._render()

    assert '["title"] : ({ ["text"] : "layout title" })' in str(rendered.special_props)


def test_plotly_layout_var_data_is_preserved(plotly_fig: go.Figure):
    """Preserve state metadata when embedding a dynamic layout."""

    class PlotlyState(rx.State):
        layout: dict = {"title": "layout title"}

    layout = rx.Var.create(PlotlyState.layout)
    rendered = rx.plotly(data=plotly_fig, layout=layout)._render()
    var_data = layout._get_all_var_data()

    assert var_data is not None
    assert "layout" in var_data.field_name
    assert str(layout) in str(rendered.special_props[-1])


def test_plotly_map_imports_and_locale(plotly_fig: go.Figure):
    """The map variant loads its own bundle alongside inherited locale support."""
    component = rx.plotly.map(data=plotly_fig, locale="de", id="map")
    imports = component._get_all_imports()

    assert "plotly.js-map-dist-min@4.0.0" in imports
    assert "plotly.js-locales@4.0.0" in imports
    assert "mergician" in imports
    assert "import('plotly.js-map-dist-min')" in component._get_dynamic_imports()
    assert any(
        var.tag == "createPlotlyComponent" and var.package_path == "/factory"
        for var in imports["react-plotly.js"]
    )
    rendered = component._render()
    assert '"map"' in str(rendered.props["divId"])
    assert "_rxGetPlotlyLocaleConfig" in str(rendered.props["config"])


def test_plotly_mapbox_deprecation_preserves_bundle(
    plotly_fig: go.Figure, mocker: MockerFixture
):
    """Legacy maps warn without losing the bundle or inherited locale support."""
    deprecate = mocker.patch("reflex_base.utils.console.deprecate")
    component = rx.plotly.mapbox(data=plotly_fig, locale="fr")

    deprecate.assert_called_once()
    assert deprecate.call_args.kwargs["feature_name"] == "rx.plotly.mapbox"
    assert "rx.plotly.map" in deprecate.call_args.kwargs["reason"]
    assert deprecate.call_args.kwargs["removal_version"] == "1.0"
    assert deprecate.call_args.kwargs["deprecation_version"] == "0.10.0"
    imports = component._get_all_imports()
    assert "plotly.js-mapbox-dist-min@3.7.0" in imports
    assert "plotly.js-mapbox-dist-min@4.0.0" not in imports
    assert "plotly.js-locales@4.0.0" in imports
    assert "import('plotly.js-mapbox-dist-min')" in component._get_dynamic_imports()


@pytest.mark.parametrize(
    ("figure", "warns"),
    [
        ({"data": [{"type": "scattermapbox"}]}, True),
        ({"data": [{"type": "choroplethmapbox"}]}, True),
        ({"data": [{"type": "densitymapbox"}]}, True),
        ({"layout": {"mapbox": {}}}, True),
        ({"layout": {"mapbox2": {}}}, True),
        ({"data": [{"type": "scattermap"}], "layout": {"map": {}}}, False),
        ({"data": [{"x": [1], "y": [2]}]}, False),
        ({}, False),
        (None, False),
    ],
)
@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is unavailable")
def test_plotly_mapbox_warning(figure: dict | None, warns: bool):
    """Warn once for removed Mapbox inputs without changing the figure."""
    component = rx.plotly()
    code = next(
        code for code in component.add_custom_code() if "_rxWarnPlotlyMapbox" in code
    )
    script = rf"""
const assert = require('node:assert/strict');
const warnings = [];
console.warn = message => warnings.push(message);
{code}
assert.equal(_rxWarnPlotlyMapbox(undefined), undefined);
const figure = {json.dumps(figure)};
assert.equal(_rxWarnPlotlyMapbox(figure), figure);
assert.equal(_rxWarnPlotlyMapbox(figure), figure);
assert.deepEqual(figure, {json.dumps(figure)});
assert.equal(warnings.length, {int(warns)});
if (warnings.length) {{
    assert.match(warnings[0], /rx\.plotly\.map/);
    assert.match(warnings[0], /layout\.map/);
}}
"""
    subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
