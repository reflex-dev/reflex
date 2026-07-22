from reflex_components_recharts.charts import (
    AreaChart,
    BarChart,
    LineChart,
    PieChart,
    RadarChart,
    RadialBarChart,
    SankeyChart,
    ScatterChart,
)
from reflex_components_recharts.general import ResponsiveContainer

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
