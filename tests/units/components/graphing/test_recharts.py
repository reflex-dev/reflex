from reflex.components.recharts.charts import (
    AreaChart,
    BarChart,
    LineChart,
    PieChart,
    RadarChart,
    RadialBarChart,
    ScatterChart,
)
from reflex.components.recharts.general import ResponsiveContainer


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
