import pytest
from reflex_base.vars.base import VarData
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

import reflex as rx


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


def test_xaxis_tick_formatter_rejects_python_callable():
    with pytest.raises(TypeError):
        XAxis.create(
            tick_formatter=lambda value: value  # pyright: ignore [reportArgumentType]
        )


def test_xaxis_tick_formatter_literal_string_var():
    x_axis = XAxis.create(tick_formatter=rx.Var.create("(value) => value.toFixed(2)"))
    props = x_axis.render()["props"]
    assert "tickFormatter:(value) => value.toFixed(2)" in props


@pytest.mark.parametrize("axis", [XAxis, YAxis])
def test_axis_tick_formatter_function_string_var(axis):
    var_data = VarData(hooks=("const formatterHook = useFormatter();",))
    formatter = rx.vars.FunctionStringVar.create(
        "((value) => value.toFixed(2))", _var_data=var_data
    )

    axis_component = axis.create(tick_formatter=formatter)

    assert axis_component.tick_formatter is formatter
    assert "tickFormatter:((value) => value.toFixed(2))" in (
        axis_component.render()["props"]
    )
    assert axis_component.tick_formatter._get_all_var_data() == var_data


@pytest.mark.parametrize("axis", [XAxis, YAxis])
def test_axis_tick_formatter_preserves_partial_metadata(axis):
    var_data = VarData(
        imports={"some-package": ["some-import"]},
        hooks=("const formatterHook = useFormatter();",),
    )
    partial_arg = rx.Var(_js_expr='"!"', _var_type=str, _var_data=var_data)
    formatter = rx.vars.FunctionStringVar.create(
        "((value, suffix) => value + suffix)"
    ).partial(partial_arg)

    axis_component = axis.create(tick_formatter=formatter)

    assert axis_component.tick_formatter is formatter
    assert axis_component.tick_formatter._get_all_var_data() == var_data


@pytest.mark.parametrize("axis", [XAxis, YAxis])
def test_axis_tick_formatter_rejects_dynamic_string_var(axis):
    formatter = rx.Var(_js_expr="state.formatter", _var_type=str)
    with pytest.raises(TypeError, match="dynamic string Var"):
        axis.create(tick_formatter=formatter)


@pytest.mark.parametrize("axis", [XAxis, YAxis])
def test_axis_tick_formatter_rejects_non_string_var(axis):
    formatter = rx.Var(_js_expr="state.formatter", _var_type=int)
    with pytest.raises(TypeError, match="FunctionVar or JavaScript string"):
        axis.create(tick_formatter=formatter)


@pytest.mark.parametrize("axis", [XAxis, YAxis])
def test_axis_tick_formatter_rejects_untyped_var(axis):
    formatter = rx.Var("((value) => value)")
    with pytest.raises(TypeError, match="FunctionVar or JavaScript string"):
        axis.create(tick_formatter=formatter)


def test_scatter():
    scatter = Scatter.create().render()
    assert scatter["name"] == "RechartsScatter"
