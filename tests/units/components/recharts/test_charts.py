import pytest
from reflex_components_recharts.charts import (
    AreaChart,
    BarChart,
    ComposedChart,
    FunnelChart,
    LineChart,
    PieChart,
    RadarChart,
    RadialBarChart,
    ScatterChart,
)
from reflex_components_recharts.general import Layer, Rectangle

CHART_CLASSES = [
    AreaChart,
    BarChart,
    LineChart,
    ComposedChart,
    PieChart,
    RadarChart,
    RadialBarChart,
    ScatterChart,
    FunnelChart,
]


@pytest.mark.parametrize("chart_cls", CHART_CLASSES)
def test_charts_allow_layer_and_rectangle_children(chart_cls):
    assert "Layer" in chart_cls._valid_children
    assert "Rectangle" in chart_cls._valid_children
    chart_cls.create(Layer.create(Rectangle.create()))
