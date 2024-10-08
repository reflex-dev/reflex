from reflex.components.recharts import (
    Area,
    Bar,
    Brush,
    Line,
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


def test_scatter():
    scatter = Scatter.create().render()
    assert scatter["name"] == "RechartsScatter"
