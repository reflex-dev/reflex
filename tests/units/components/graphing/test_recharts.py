from typing import get_type_hints

import pytest
from reflex_base.components.component import (
    ComponentNamespace,
    evaluate_style_namespaces,
)
from reflex_components_recharts.charts import (
    AreaChart,
    BarChart,
    LineChart,
    PieChart,
    RadarChart,
    RadialBarChart,
    SankeyChart,
    SankeyLinkPayload,
    SankeyLinkProps,
    SankeyNodePayload,
    SankeyNodeProps,
    ScatterChart,
    sankey_chart,
)
from reflex_components_recharts.general import ResponsiveContainer, use_chart_width
from reflex_components_recharts.recharts import Recharts

import reflex as rx


def test_area_chart():
    ac = AreaChart.create()
    assert isinstance(ac, ResponsiveContainer)
    assert isinstance(ac.children[0], AreaChart)


def test_bar_chart():
    bc = BarChart.create()
    assert isinstance(bc, ResponsiveContainer)
    assert isinstance(bc.children[0], BarChart)


def test_line_chart():
    lc = LineChart.create()
    assert isinstance(lc, ResponsiveContainer)
    assert isinstance(lc.children[0], LineChart)


def test_pie_chart():
    pc = PieChart.create()
    assert isinstance(pc, ResponsiveContainer)
    assert isinstance(pc.children[0], PieChart)


def test_radar_chart():
    rc = RadarChart.create()
    assert isinstance(rc, ResponsiveContainer)
    assert isinstance(rc.children[0], RadarChart)


def test_radial_bar_chart():
    rbc = RadialBarChart.create()
    assert isinstance(rbc, ResponsiveContainer)
    assert isinstance(rbc.children[0], RadialBarChart)


def test_scatter_chart():
    sc = ScatterChart.create()
    assert isinstance(sc, ResponsiveContainer)
    assert isinstance(sc.children[0], ScatterChart)


def test_sankey_chart():
    sc = SankeyChart.create()
    assert isinstance(sc, ResponsiveContainer)
    assert isinstance(sc.children[0], SankeyChart)
    assert sc.children[0].render()["name"] == "RechartsSankeyChart"
    assert "link_width" not in SankeyChart.get_props()


def test_sankey_chart_namespace_can_be_used_as_style_key():
    assert isinstance(sankey_chart, ComponentNamespace)
    assert evaluate_style_namespaces({sankey_chart: {"height": "20rem"}}) == {
        SankeyChart.create: {"height": "20rem"}
    }


def test_sankey_chart_accepts_unannotated_state_data():
    class SankeyState(rx.State):
        data = {
            "nodes": [{"name": "A"}, {"name": "B"}],
            "links": [{"source": 0, "target": 1, "value": 1}],
        }

    sc = SankeyChart.create(data=SankeyState.data)
    assert isinstance(sc, ResponsiveContainer)


def test_sankey_link_payload_matches_recharts_runtime_shape():
    link_payload_hints = get_type_hints(SankeyLinkPayload)
    assert link_payload_hints["source"] is SankeyNodePayload
    assert link_payload_hints["target"] is SankeyNodePayload
    assert "dy" in link_payload_hints
    assert "width" not in link_payload_hints
    assert "index" not in link_payload_hints

    link_props_hints = get_type_hints(SankeyLinkProps)
    assert link_props_hints["index"] is int
    assert link_props_hints["linkWidth"] == (int | float)


def test_sankey_renderer_decorators_accept_deferred_annotations():
    namespace = {
        "rx": rx,
        "SankeyLinkProps": SankeyLinkProps,
        "SankeyNodeProps": SankeyNodeProps,
    }
    exec(
        """
from __future__ import annotations


def custom_node(node: rx.Var[SankeyNodeProps]) -> rx.Component:
    return rx.fragment()


def custom_link(link: rx.Var[SankeyLinkProps]) -> rx.Component:
    return rx.fragment()
""",
        namespace,
    )

    assert callable(sankey_chart.node(namespace["custom_node"]))
    assert callable(sankey_chart.link(namespace["custom_link"]))


def test_sankey_renderer_decorator_rejects_positional_only_parameter():
    def custom_node(node: rx.Var[SankeyNodeProps], /) -> rx.Component:
        return rx.fragment()

    with pytest.raises(TypeError, match="keyword"):
        sankey_chart.node(custom_node)


def test_use_chart_width():
    width = use_chart_width()
    assert width._var_type == (int | None)
    var_data = width._get_all_var_data()
    assert var_data is not None
    hook_alias = f"useChartWidth_{width!s}"
    assert var_data.hooks == (f"const {width!s} = {hook_alias}();",)
    assert dict(var_data.imports)[Recharts.library or ""] == (
        rx.ImportVar(tag="useChartWidth", alias=hook_alias),
    )
