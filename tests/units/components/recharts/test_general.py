from reflex_components_recharts import Layer, Rectangle


def test_layer():
    layer = Layer.create().render()
    assert layer["name"] == "RechartsLayer"


def test_layer_with_children():
    layer = Layer.create(Rectangle.create()).render()
    assert layer["name"] == "RechartsLayer"
    assert layer["children"][0]["name"] == "RechartsRectangle"


def test_rectangle():
    rectangle = Rectangle.create().render()
    assert rectangle["name"] == "RechartsRectangle"


def test_rectangle_props():
    rectangle = Rectangle.create(
        x=10,
        y=20.5,
        width=100,
        height=50,
        radius=[4, 4, 0, 0],
        fill="#5192ca",
        fill_opacity=0.8,
        stroke="none",
        stroke_width=2,
        is_animation_active=False,
    ).render()
    props = rectangle["props"]
    assert "x:10" in props
    assert "y:20.5" in props
    assert "width:100" in props
    assert "height:50" in props
    assert "radius:[4, 4, 0, 0]" in props
    assert 'fill:"#5192ca"' in props
    assert "fillOpacity:0.8" in props
    assert 'stroke:"none"' in props
    assert "strokeWidth:2" in props
    assert "isAnimationActive:false" in props
