"""Integration tests for the plotly graphing component's locale support."""

from collections.abc import Generator

import pytest
from playwright.sync_api import Page, expect

from reflex.testing import AppHarness


def PlotlyLocaleApp():
    """App rendering a plotly figure with no locale, two locales, and a state config."""
    import plotly.graph_objects as go

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
