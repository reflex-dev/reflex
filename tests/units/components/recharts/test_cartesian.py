import pytest
from reflex_components_recharts import (
    Area,
    Bar,
    Brush,
    Line,
    ReferenceLine,
    Scatter,
    XAxis,
    YAxis,
    ZAxis,
)


def test_xaxis():
    x_axis = XAxis.create("x").render()
    assert x_axis["name"] == "RechartsXAxis"


def test_yaxis():
    x_axis = YAxis.create("y").render()
    assert x_axis["name"] == "RechartsYAxis"


def test_zaxis():
    x_axis = ZAxis.create("z").render()
    assert x_axis["name"] == "RechartsZAxis"


def test_brush():
    brush = Brush.create().render()
    assert brush["name"] == "RechartsBrush"


def test_area():
    area = Area.create().render()
    assert area["name"] == "RechartsArea"


def test_bar():
    bar = Bar.create().render()
    assert bar["name"] == "RechartsBar"


def test_line():
    line = Line.create().render()
    assert line["name"] == "RechartsLine"


def test_reference_line_stroke_dasharray():
    reference_line = ReferenceLine.create(stroke_dasharray="8 8")
    assert "strokeDasharray" not in reference_line.style
    props = reference_line.render()["props"]
    assert 'strokeDasharray:"8 8"' in props
    assert not any("wrapperStyle" in prop for prop in props)


def test_xaxis_tick_formatter():
    x_axis = XAxis.create(tick_formatter="(value) => value.toFixed(2)")
    assert "tickFormatter" not in x_axis.style
    props = x_axis.render()["props"]
    assert "tickFormatter:(value) => value.toFixed(2)" in props
    assert not any("wrapperStyle" in prop for prop in props)


def test_yaxis_tick_formatter():
    y_axis = YAxis.create(tick_formatter="(value) => value.toFixed(2)")
    assert "tickFormatter" not in y_axis.style
    props = y_axis.render()["props"]
    assert "tickFormatter:(value) => value.toFixed(2)" in props
    assert not any("wrapperStyle" in prop for prop in props)


def test_xaxis_tick_formatter_rejects_non_callable():
    with pytest.raises(TypeError):
        XAxis.create(tick_formatter=123)  # pyright: ignore [reportArgumentType]


def test_scatter():
    scatter = Scatter.create().render()
    assert scatter["name"] == "RechartsScatter"
