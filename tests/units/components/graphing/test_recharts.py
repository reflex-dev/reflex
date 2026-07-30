from typing import get_type_hints

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
    ScatterChart,
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


def test_sankey_chart_accepts_unannotated_state_data():
    class SankeyState(rx.State):
        data = {
            "nodes": [{"name": "A"}, {"name": "B"}],
            "links": [{"source": 0, "target": 1, "value": 1}],
        }

    sc = SankeyChart.create(data=SankeyState.data)
    assert isinstance(sc, ResponsiveContainer)


def test_sankey_link_payload_matches_recharts():
    # Recharts delivers the payload as {...link, source: sourceNode, target:
    # targetNode} with index only on the outer props and thickness under dy.
    # https://github.com/reflex-dev/reflex/pull/6708#discussion_r3679088777
    hints = get_type_hints(SankeyLinkPayload)
    assert hints["source"] is SankeyNodePayload
    assert hints["target"] is SankeyNodePayload
    assert "index" not in hints
    assert "width" not in hints
    assert {"value", "dy", "sy", "ty"} <= hints.keys()
    assert "index" in get_type_hints(SankeyLinkProps)


def test_sankey_link_props_var_access():
    link = rx.Var("link").to(SankeyLinkProps)
    source_name = link.payload.source.name
    assert source_name._var_type is str
    assert str(source_name) == 'link?.["payload"]?.["source"]?.["name"]'
    assert link.payload.dy._var_type == (int | float)
    # Custom pass-through keys on the payload remain reachable via a dict cast.
    assert str(link.payload.source.to(dict)["fill"]) == (
        'link?.["payload"]?.["source"]?.["fill"]'
    )


def test_use_chart_width():
    width = use_chart_width()
    assert width._var_type == (int | None)
    var_data = width._get_all_var_data()
    assert var_data is not None
    assert var_data.hooks == (f"const {width!s} = useChartWidth();",)
    assert dict(var_data.imports)[Recharts.library or ""] == (
        rx.ImportVar(tag="useChartWidth"),
    )
