"""Integration tests for the plotly graphing component."""

from collections.abc import Generator

import pytest
from playwright.sync_api import Page, expect

from reflex.testing import AppHarness


def PlotlyLocaleApp():
    """App rendering a plotly figure with no locale, two locales, and a state config."""
    import plotly.graph_objects as go
    from reflex_components_plotly.plotly import Point

    import reflex as rx

    figure = go.Figure(
        data=[
            go.Scatter(
                x=[1, 2, 3, 4],
                y=[10, 15, 13, 17],
                mode="lines+markers",
                name="Trace 1",
            )
        ]
    )

    class PlotlyConfigState(rx.State):
        # A user-supplied plotly config delivered through state. The locale
        # setting must be merged on top of this without discarding its options.
        plotly_config: dict = {"modeBarButtonsToRemove": ["lasso2d"]}

    class PlotlyLayoutState(rx.State):
        plotly_layout: dict = {"title": "State title", "height": 240}

        @rx.event
        def change_title(self):
            self.plotly_layout = {"title": "Updated state title", "height": 240}

    class PlotlyMapState(rx.State):
        latitude: float = 37.77
        clicks: int = 0

        @rx.var
        def map_figure(self) -> go.Figure:
            """Build a map whose marker moves with the state.

            Returns:
                A figure with a marker at the current latitude.
            """
            return go.Figure(
                go.Scattermap(
                    lat=[self.latitude],
                    lon=[-122.42],
                    mode="markers",
                    marker={"size": 24, "color": "red"},
                )
            )

        @rx.event
        def move_marker(self):
            """Move the map marker without replacing the map component."""
            self.latitude = 37.78

        @rx.event
        def click_marker(self, points: list[Point]):
            """Record a browser click delivered with map point data."""
            if points and points[0].get("lat") == self.latitude:
                self.clicks += 1

    app = rx.App()

    def plot_box(plot_id: str, **plotly_props) -> "rx.Component":
        return rx.box(
            rx.plotly(data=figure, width="100%", height="100%", **plotly_props),
            id=plot_id,
            width="600px",
            height="300px",
        )

    @app.add_page
    def index():
        return rx.vstack(
            plot_box("plot_default"),
            plot_box("plot_de", locale="de"),
            plot_box("plot_fr", locale="fr"),
            plot_box("plot_config", config=PlotlyConfigState.plotly_config),
            plot_box(
                "plot_config_de",
                config=PlotlyConfigState.plotly_config,
                locale="de",
            ),
            plot_box(
                "plot_config_fr",
                config=PlotlyConfigState.plotly_config,
                locale="fr",
            ),
            plot_box("plot_title_string", layout={"title": "Literal title"}),
            plot_box("plot_title_object", layout={"title": {"text": "Object title"}}),
            plot_box("plot_title_state", layout=PlotlyLayoutState.plotly_layout),
            rx.button(
                "Update title",
                id="update_plot_title",
                on_click=PlotlyLayoutState.change_title,
            ),
        )

    @app.add_page
    def maps():
        """Render modern and legacy map bundles together without external tiles.

        Returns:
            The maps and controls used to exercise updates and events.
        """
        map_layout = {
            "style": "white-bg",
            "center": {"lat": 37.77, "lon": -122.42},
            "zoom": 10,
        }
        return rx.vstack(
            rx.plotly.map(
                data=PlotlyMapState.map_figure,
                layout={"map": map_layout, "margin": {"l": 0, "r": 0, "t": 0, "b": 0}},
                locale="de",
                on_click=PlotlyMapState.click_marker,
                id="modern-map",
                width="600px",
                height="300px",
            ),
            rx.plotly.mapbox(
                data=go.Figure(
                    go.Scattermapbox(lat=[37.77], lon=[-122.42], mode="markers")
                ),
                layout={"mapbox": map_layout},
                locale="fr",
                id="legacy-map",
                width="600px",
                height="300px",
            ),
            rx.button(
                "Move marker", id="move-marker", on_click=PlotlyMapState.move_marker
            ),
            rx.text(PlotlyMapState.clicks, id="map-clicks"),
        )


@pytest.fixture(scope="module")
def plotly_locale_app(
    app_harness_env: type[AppHarness], tmp_path_factory
) -> Generator[AppHarness, None, None]:
    """Start PlotlyLocaleApp at tmp_path via AppHarness.

    Args:
        app_harness_env: The AppHarness environment to use for the test.
        tmp_path_factory: pytest tmp_path_factory fixture

    Yields:
        running AppHarness instance
    """
    with app_harness_env.create(
        root=tmp_path_factory.mktemp("plotly_locale"),
        app_name=f"plotlylocaleapp_{app_harness_env.__name__.lower()}",
        app_source=PlotlyLocaleApp,
    ) as harness:
        assert harness.app_instance is not None, "app is not running"
        yield harness


# (plot box id, expected "Autoscale" modebar title, expected "Pan" modebar title).
# The default plot has no locale (English); the others request a specific locale,
# and the expected titles come straight from the `plotly.js-locales` dictionaries.
EXPECTED_MODEBAR_TITLES = (
    ("plot_default", "Autoscale", "Pan"),
    ("plot_de", "Automatische Skalierung", "Verschieben"),
    ("plot_fr", "Échelle automatique", "Translation"),
)


def test_plotly_locale_modebar_titles(page: Page, plotly_locale_app: AppHarness):
    """Each plot localizes its modebar tooltips according to its `locale` prop.

    Plotly translates modebar button tooltips via the chart config's locale data,
    rendering the result into each button's ``data-title`` attribute. The buttons
    are located by their stable ``data-attr``/``data-val`` (which do not change
    with locale) so the asserted ``data-title`` reflects only the locale.

    Args:
        page: Playwright page instance.
        plotly_locale_app: Harness for PlotlyLocaleApp.
    """
    assert plotly_locale_app.frontend_url is not None
    page.goto(plotly_locale_app.frontend_url)

    autoscale_titles: list[str | None] = []
    for plot_id, expected_autoscale, expected_pan in EXPECTED_MODEBAR_TITLES:
        box = page.locator(f"#{plot_id}")
        # The figure is loaded via a dynamic import, so allow time for first render.
        expect(box.locator(".js-plotly-plot")).to_be_visible(timeout=60_000)

        autoscale = box.locator('.modebar-btn[data-attr="zoom"][data-val="auto"]')
        pan = box.locator('.modebar-btn[data-attr="dragmode"][data-val="pan"]')

        expect(autoscale).to_have_attribute("data-title", expected_autoscale)
        expect(pan).to_have_attribute("data-title", expected_pan)

        autoscale_titles.append(autoscale.get_attribute("data-title"))

    # The default locale and the two requested locales each rendered distinctly.
    assert len(set(autoscale_titles)) == 3, (
        f"locales did not produce distinct rendering: {autoscale_titles}"
    )


# (plot box id, expected "Autoscale" modebar title) for the plots whose `config`
# is supplied via a state var. The config removes the lasso button; where a locale
# is also set, the tooltips must still be localized, proving locale is merged with
# the given config rather than replacing it.
EXPECTED_CONFIG_MERGE = (
    ("plot_config", "Autoscale"),
    ("plot_config_de", "Automatische Skalierung"),
    ("plot_config_fr", "Échelle automatique"),
)


def test_plotly_locale_merges_with_state_config(
    page: Page, plotly_locale_app: AppHarness
):
    """A state-driven `config` is preserved when the `locale` setting is merged in.

    Each plot receives its plotly config from a state var that removes the lasso
    modebar button. The locale is then merged on top of that config: the lasso
    button stays removed (config honored) while the remaining tooltips are
    localized (locale honored), confirming the two are merged rather than one
    overwriting the other.

    Args:
        page: Playwright page instance.
        plotly_locale_app: Harness for PlotlyLocaleApp.
    """
    assert plotly_locale_app.frontend_url is not None
    page.goto(plotly_locale_app.frontend_url)

    for plot_id, expected_autoscale in EXPECTED_CONFIG_MERGE:
        box = page.locator(f"#{plot_id}")
        # The figure is loaded via a dynamic import, so allow time for first render.
        expect(box.locator(".js-plotly-plot")).to_be_visible(timeout=60_000)

        # The state-supplied config removed only the lasso button...
        expect(
            box.locator('.modebar-btn[data-attr="dragmode"][data-val="lasso"]')
        ).to_have_count(0)
        # ...while leaving the other modebar buttons (e.g. box select) intact.
        expect(
            box.locator('.modebar-btn[data-attr="dragmode"][data-val="select"]')
        ).to_have_count(1)
        # The locale is merged on top of that config and still localizes tooltips.
        expect(
            box.locator('.modebar-btn[data-attr="zoom"][data-val="auto"]')
        ).to_have_attribute("data-title", expected_autoscale)


def test_plotly_layout_titles(page: Page, plotly_locale_app: AppHarness):
    """String titles render and state-driven titles update without altering object titles."""
    assert plotly_locale_app.frontend_url is not None
    page.goto(plotly_locale_app.frontend_url)

    for plot_id, title in (
        ("plot_title_string", "Literal title"),
        ("plot_title_object", "Object title"),
        ("plot_title_state", "State title"),
    ):
        expect(page.locator(f"#{plot_id} .gtitle")).to_have_text(title, timeout=60_000)

    page.locator("#update_plot_title").click()
    expect(page.locator("#plot_title_state .gtitle")).to_have_text(
        "Updated state title"
    )


def test_plotly_map_bundles(page: Page, plotly_locale_app: AppHarness):
    """Both map bundles render together with locales, updates and click events."""
    assert plotly_locale_app.frontend_url is not None
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(f"{plotly_locale_app.frontend_url.rstrip('/')}/maps")

    for plot_id, subplot, trace_type, locale, pan_title in (
        ("modern-map", "map", "scattermap", "de", "Verschieben"),
        ("legacy-map", "mapbox", "scattermapbox", "fr", "Translation"),
    ):
        page.wait_for_function(
            """([id, subplot]) => {
                const plot = document.getElementById(id);
                return plot?._fullLayout?.[subplot]?._subplot?.map?.loaded();
            }""",
            arg=[plot_id, subplot],
            timeout=60_000,
        )
        plot = page.locator(f"#{plot_id}")
        expect(plot.get_by_role("region", name="Map", exact=True)).to_be_visible()
        assert plot.evaluate("plot => plot._fullData[0].type") == trace_type
        assert plot.evaluate("plot => plot._context.locale") == locale
        expect(
            plot.locator('.modebar-btn[data-attr="dragmode"][data-val="pan"]')
        ).to_have_attribute("data-title", pan_title)

    page.locator("#move-marker").click()
    page.wait_for_function(
        """() => {
            const plot = document.getElementById('modern-map');
            const map = plot._fullLayout.map._subplot.map;
            return plot._fullData[0].lat[0] === 37.78 && map.loaded() &&
                map.queryRenderedFeatures(map.project([-122.42, 37.78])).length > 0;
        }"""
    )
    page.locator("#modern-map").scroll_into_view_if_needed()
    point = page.locator("#modern-map").evaluate(
        """plot => {
            const map = plot._fullLayout.map._subplot.map;
            const point = map.project([-122.42, 37.78]);
            const rect = map.getCanvas().getBoundingClientRect();
            return {x: rect.x + point.x, y: rect.y + point.y};
        }"""
    )
    page.mouse.click(point["x"], point["y"])
    expect(page.locator("#map-clicks")).to_have_text("1")
    assert not errors
