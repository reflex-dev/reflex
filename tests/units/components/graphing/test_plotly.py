import json
import shutil
import subprocess

import numpy as np
import plotly.graph_objects as go
import pytest
from pytest_mock import MockerFixture
from reflex_base.utils.serializers import serialize, serialize_figure
from reflex_components_plotly.plotly import (
    _MAPBOX_TO_MAP_JS,
    Plotly,
    PlotlyBasic,
    PlotlyMap,
    PlotlyMapbox,
    PlotlyStrict,
)

import reflex as rx

MAP_DYNAMIC_IMPORT = """
const MapPlotlyPlot = ClientSide(() =>
    import('plotly.js-map-dist-min').then((mod) => createPlotlyComponent(mod))
, "MapPlotlyPlot")
"""

MAPBOX_WARNING = (
    "Plotly.js 4 removed Mapbox traces and layout.mapbox. Reflex renames them to "
    "scattermap, choroplethmap, densitymap and layout.map until Reflex 1.0. "
    "Use the MapLibre names in the figure instead."
)


class CustomMapbox(PlotlyMapbox):
    """A user subclass of the deprecated Mapbox component."""


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
    assert str(component._render().props["config"]) == '({ ["displaylogo"] : false })'


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

    assert "plotly.js-map-dist-min@4.3.0" in imports
    assert "plotly.js-locales@4.3.0" in imports
    assert "mergician" in imports
    assert component._get_dynamic_imports() == MAP_DYNAMIC_IMPORT
    assert any(
        var.tag == "createPlotlyComponent" and var.package_path == "/factory"
        for var in imports["react-plotly.js"]
    )
    rendered = component._render()
    assert str(rendered.props["divId"]) == '"map"'
    assert (
        str(rendered.props["config"])
        == '_rxGetPlotlyLocaleConfig(({  }),"de",plotlyLocales)'
    )


def test_plotly_mapbox_deprecation_uses_map_bundle(
    plotly_fig: go.Figure, mocker: MockerFixture
):
    """Legacy maps warn and render through the Plotly.js 4 MapLibre bundle."""
    deprecate = mocker.patch("reflex_base.utils.console.deprecate")
    component = rx.plotly.mapbox(data=plotly_fig, locale="fr")

    deprecate.assert_called_once()
    assert deprecate.call_args.kwargs["feature_name"] == "rx.plotly.mapbox"
    assert (
        deprecate.call_args.kwargs["reason"]
        == "Use rx.plotly.map with MapLibre traces and layout.map instead"
    )
    assert deprecate.call_args.kwargs["removal_version"] == "1.0"
    assert deprecate.call_args.kwargs["deprecation_version"] == "0.11.1"
    imports = component._get_all_imports()
    assert "plotly.js-map-dist-min@4.3.0" in imports
    assert not any("mapbox-dist-min" in lib for lib in imports)
    assert "plotly.js-locales@4.3.0" in imports
    assert component._get_dynamic_imports() == MAP_DYNAMIC_IMPORT


@pytest.mark.parametrize(
    "component_cls",
    [Plotly, PlotlyBasic, PlotlyMap, PlotlyStrict, PlotlyMapbox, CustomMapbox],
)
def test_plotly_renames_mapbox_in_every_variant(
    component_cls: type[Plotly], plotly_fig: go.Figure
):
    """Every Plotly component and subclass passes its figure through the rename."""
    component = component_cls.create(data=plotly_fig, template=None)
    assert (
        str(component._render().special_props[-1])
        == f"_rxPlotlyMapboxToMap({rx.Var.create(plotly_fig).to(dict)!s})"
    )
    assert _MAPBOX_TO_MAP_JS in component._get_all_custom_code()


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is unavailable")
def test_plotly_mapbox_renames_to_map():
    """Rename trace types, subplots and layout keys in the figure and its frames only."""
    geojson = {
        "type": "FeatureCollection",
        "features": [{"type": "Feature", "properties": {"mapbox": "a"}}],
    }
    template = {
        "data": {"scattermapbox": [{"marker": {"size": 4}}]},
        "layout": {"mapbox": {"style": "light"}},
    }
    updatemenus = [
        {
            "buttons": [
                {"method": "animate", "args": [["mapbox"]]},
                {
                    "method": "relayout",
                    "args": ["mapbox.style", "dark"],
                    "args2": [{"mapbox.zoom": 5}],
                },
            ]
        }
    ]
    figure = {
        "data": [
            {"type": "scattermapbox", "lat": [1, 2], "customdata": [{"mapbox": 1}]},
            {
                "type": "choroplethmapbox",
                "subplot": "mapbox2",
                "geojson": geojson,
                "featureidkey": "properties.mapbox",
            },
            {"type": "densitymapbox", "subplot": "mapbox"},
            {"x": [1]},
        ],
        "layout": {
            "mapbox": {"zoom": 3},
            "mapbox2": {},
            "xaxis": {"type": "log"},
            "template": template,
            "updatemenus": updatemenus,
        },
        "frames": [
            {
                "name": "mapbox",
                "data": [{"type": "scattermapbox", "subplot": "mapbox2"}],
                "layout": {"mapbox": {"zoom": 4}},
            }
        ],
    }
    expected = {
        "data": [
            {"type": "scattermap", "lat": [1, 2], "customdata": [{"mapbox": 1}]},
            {
                "type": "choroplethmap",
                "subplot": "map2",
                "geojson": geojson,
                "featureidkey": "properties.mapbox",
            },
            {"type": "densitymap", "subplot": "map"},
            {"x": [1]},
        ],
        "layout": {
            "map": {"zoom": 3},
            "map2": {},
            "xaxis": {"type": "log"},
            "template": template,
            "updatemenus": updatemenus,
        },
        "frames": [
            {
                "name": "mapbox",
                "data": [{"type": "scattermap", "subplot": "map2"}],
                "layout": {"map": {"zoom": 4}},
            }
        ],
    }
    script = rf"""
const assert = require('node:assert/strict');
console.warn = () => {{}};
{_MAPBOX_TO_MAP_JS}
const figure = {json.dumps(figure)};
const converted = _rxPlotlyMapboxToMap(figure);
assert.deepEqual(converted, {json.dumps(expected)});
assert.equal(converted.data[0].lat, figure.data[0].lat);
assert.deepEqual(figure, {json.dumps(figure)});
"""
    subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)


@pytest.mark.parametrize(
    ("figure", "expected"),
    [
        ({"data": [{"type": "scattermapbox"}]}, {"data": [{"type": "scattermap"}]}),
        (
            {"data": [{"type": "choroplethmapbox"}]},
            {"data": [{"type": "choroplethmap"}]},
        ),
        ({"data": [{"type": "densitymapbox"}]}, {"data": [{"type": "densitymap"}]}),
        ({"layout": {"mapbox": {}}}, {"layout": {"map": {}}}),
        ({"layout": {"mapbox2": {}}}, {"layout": {"map2": {}}}),
        ({"data": [{"type": "scattermap"}], "layout": {"map": {}}}, None),
        ({"data": [{"x": [1], "y": [2]}]}, None),
        (
            {"data": [{"x": [1]}], "layout": {"template": {"layout": {"mapbox": {}}}}},
            None,
        ),
        ({}, None),
        (None, None),
    ],
)
@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is unavailable")
def test_plotly_mapbox_warning(figure: dict | None, expected: dict | None):
    """Warn once and rename Mapbox figures; return other figures unchanged."""
    script = rf"""
const assert = require('node:assert/strict');
const warnings = [];
console.warn = message => warnings.push(message);
{_MAPBOX_TO_MAP_JS}
assert.equal(_rxPlotlyMapboxToMap(undefined), undefined);
const figure = {json.dumps(figure)};
const expected = {json.dumps(expected)};
for (let i = 0; i < 2; i++) {{
    const converted = _rxPlotlyMapboxToMap(figure);
    if (expected === null) assert.equal(converted, figure);
    else assert.deepEqual(converted, expected);
}}
assert.deepEqual(figure, {json.dumps(figure)});
assert.deepEqual(warnings, expected === null ? [] : [{json.dumps(MAPBOX_WARNING)}]);
"""
    subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
