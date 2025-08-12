from reflex.components.recharts import (
    Pie,
    PolarAngleAxis,
    PolarGrid,
    PolarRadiusAxis,
    Radar,
    RadialBar,
)


def test_pie():
    pie = Pie.create().render()
    assert pie["name"] == "RechartsPie"


def test_radar():
    radar = Radar.create().render()
    assert radar["name"] == "RechartsRadar"


def test_radialbar():
    radialbar = RadialBar.create().render()
    assert radialbar["name"] == "RechartsRadialBar"


def test_polarangleaxis():
    polarangleaxis = PolarAngleAxis.create().render()
    assert polarangleaxis["name"] == "RechartsPolarAngleAxis"


def test_polargrid():
    polargrid = PolarGrid.create().render()
    assert polargrid["name"] == "RechartsPolarGrid"


def test_polarradiusaxis():
    polarradiusaxis = PolarRadiusAxis.create().render()
    assert polarradiusaxis["name"] == "RechartsPolarRadiusAxis"
