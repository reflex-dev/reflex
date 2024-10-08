from reflex.components.el.elements.media import (
    Circle,
    Defs,
    Ellipse,
    Line,
    LinearGradient,
    Path,
    Polygon,
    RadialGradient,
    Rect,
    Stop,
    Svg,
    Text,
)


def test_circle():
    circle = Circle.create().render()
    assert circle["name"] == "circle"


def test_defs():
    defs = Defs.create().render()
    assert defs["name"] == "defs"


def test_ellipse():
    ellipse = Ellipse.create().render()
    assert ellipse["name"] == "ellipse"


def test_line():
    line = Line.create().render()
    assert line["name"] == "line"


def test_linear_gradient():
    linear_gradient = LinearGradient.create().render()
    assert linear_gradient["name"] == "linearGradient"


def test_path():
    path = Path.create().render()
    assert path["name"] == "path"


def test_polygon():
    polygon = Polygon.create().render()
    assert polygon["name"] == "polygon"


def test_radial_gradient():
    radial_gradient = RadialGradient.create().render()
    assert radial_gradient["name"] == "radialGradient"


def test_rect():
    rect = Rect.create().render()
    assert rect["name"] == "rect"


def test_svg():
    svg = Svg.create().render()
    assert svg["name"] == "svg"


def test_text():
    text = Text.create().render()
    assert text["name"] == "text"


def test_stop():
    stop = Stop.create().render()
    assert stop["name"] == "stop"
