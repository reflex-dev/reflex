import pytest
from reflex_base.vars.base import VarData
from reflex_components_recharts import XAxis, YAxis

import reflex as rx


@pytest.mark.parametrize("axis", [XAxis, YAxis])
def test_axis_tick_formatter_function_string_var(axis):
    var_data = VarData(hooks=("const formatterHook = useFormatter();",))
    formatter = rx.vars.FunctionStringVar.create(
        "((value) => value.toFixed(2))", _var_data=var_data
    )

    axis_component = axis.create(tick_formatter=formatter)

    assert axis_component.tick_formatter is formatter
    assert (
        "tickFormatter:((value) => value.toFixed(2))"
        in axis_component.render()["props"]
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
