"""Integration tests for ``rx.element_observer`` in a browser.

The observers report into client state, in an app without a backend, so every
value on the page comes from the browser alone.
"""

import re
from collections.abc import Generator

import pytest
from playwright.sync_api import Page, expect

from reflex.testing import AppHarness


def ElementObserverApp():
    """App whose client state follows what element observers report."""
    import reflex as rx

    wide = rx.client_state(False, name="wide")
    width = rx.client_state(0.0, name="width")
    tracking = rx.client_state(True, name="tracking")
    top = rx.client_state(0.0, name="top")
    visible = rx.client_state(False, name="visible")
    expanded = rx.client_state(False, name="expanded")
    ended = rx.client_state("", name="ended")
    item_widths = rx.client_state("", name="item_widths")
    shown = rx.client_state(False, name="shown")
    late_width = rx.client_state(0.0, name="late_width")
    squeezed = rx.client_state(False, name="squeezed")
    narrow = rx.client_state(False, name="narrow")
    watching = rx.client_state(False, name="watching")
    first_ratio = rx.client_state(0.0, name="first_ratio")
    later_ratio = rx.client_state(0.0, name="later_ratio")

    def readout(label: str, value: rx.Var) -> rx.Component:
        return rx.el.p(value, id=label)

    def index() -> rx.Component:
        return rx.el.div(
            rx.el.div(
                readout("width", width.value),
                readout("top", top.value),
                readout("visible", rx.cond(visible.value, "visible", "hidden")),
                readout("ended", ended.value),
                readout("item_widths", item_widths.value),
                readout("late_width", late_width.value),
                readout("direction", rx.cond(narrow.value, "column", "row")),
                readout("first_ratio", first_ratio.value),
                readout("later_ratio", later_ratio.value),
                rx.el.button("Watch", id="watch", on_click=watching.set(True)),
                style={"position": "fixed", "right": "0", "top": "0"},
            ),
            rx.el.button("Widen", id="widen", on_click=wide.set(True)),
            rx.el.button("Stop", id="stop", on_click=tracking.set(False)),
            rx.el.button("Expand", id="expand", on_click=expanded.set(True)),
            rx.el.button("Show", id="show", on_click=shown.set(True)),
            rx.el.button("Squeeze", id="squeeze", on_click=squeezed.set(True)),
            rx.element_observer(
                rx.el.div(
                    id="box",
                    style={
                        "width": rx.cond(wide.value, "300px", "100px"),
                        "height": "50px",
                    },
                ),
                on_resize=lambda w, h: width.set(w),
            ),
            rx.element_observer(
                target="box",
                on_move=lambda x, y: top.set(y),
                disabled=~tracking.value,
            ),
            rx.element_observer(
                rx.el.div(
                    # Its own transition ends first and must not count.
                    rx.el.div(
                        "Panel",
                        style={
                            "opacity": rx.cond(expanded.value, "0.5", "1"),
                            "transition": "opacity 50ms",
                        },
                    ),
                    style={
                        "height": rx.cond(expanded.value, "80px", "20px"),
                        "transition": "height 150ms",
                    },
                ),
                on_transition_end=lambda name: ended.set(
                    lambda names: names.to(str) + name + ";"
                ),
            ),
            rx.element_observer(
                target="late", on_resize=lambda w, h: late_width.set(w)
            ),
            rx.cond(
                shown.value,
                rx.el.div(id="late", style={"width": "70px", "height": "10px"}),
            ),
            rx.foreach(
                rx.Var.create([40, 60]),
                lambda item_width: rx.element_observer(
                    rx.el.div(
                        style={
                            "width": item_width.to_string() + "px",
                            "height": "10px",
                        }
                    ),
                    on_resize=lambda w, h: item_widths.set(
                        lambda widths: widths.to(str) + w.to_string() + ";"
                    ),
                ),
            ),
            # Stacks its items once narrower than 400px, which makes it taller.
            rx.element_observer(
                rx.el.div(
                    rx.el.div("One", style={"width": "150px"}),
                    rx.el.div("Two", style={"width": "150px"}),
                    style={
                        "display": "flex",
                        "flexDirection": rx.cond(narrow.value, "column", "row"),
                        "width": rx.cond(squeezed.value, "300px", "500px"),
                    },
                ),
                on_resize=lambda w, h: narrow.set(w.to(float) < 400),
            ),
            rx.element_observer(
                rx.el.div(id="ratio_box", style={"height": "100px"}),
                on_intersect=lambda v, ratio: first_ratio.set(ratio),
            ),
            # Joins the observer above on the same element.
            rx.cond(
                watching.value,
                rx.element_observer(
                    target="ratio_box",
                    on_intersect=lambda v, ratio: later_ratio.set(ratio),
                ),
            ),
            rx.el.div(style={"height": "200vh"}),
            rx.element_observer(
                rx.el.div("Footer", id="footer"), on_intersect=visible.set
            ),
        )

    app = rx.App(enable_state=False)
    app.add_page(index)


@pytest.fixture(scope="module")
def element_observer_app(
    app_harness_env: type[AppHarness], tmp_path_factory: pytest.TempPathFactory
) -> Generator[AppHarness, None, None]:
    """Run the element observer app.

    Args:
        app_harness_env: The dev or prod harness.
        tmp_path_factory: pytest tmp_path_factory fixture.

    Yields:
        The running harness.
    """
    with app_harness_env.create(
        root=tmp_path_factory.mktemp("element_observer_app"),
        app_source=ElementObserverApp,
    ) as harness:
        yield harness


@pytest.fixture
def observer_page(element_observer_app: AppHarness, page: Page) -> Page:
    """Open the app's index page with its observers reporting.

    Args:
        element_observer_app: The running harness.
        page: A Playwright page.

    Returns:
        The page.
    """
    assert element_observer_app.frontend_url is not None
    page.goto(element_observer_app.frontend_url)
    expect(page.locator("#width")).to_have_text("100")
    return page


def _top_of_box(page: Page) -> str:
    """The box's top as javascript prints it.

    Args:
        page: The page.

    Returns:
        The box's top relative to the viewport.
    """
    return page.evaluate(
        "String(document.getElementById('box').getBoundingClientRect().top)"
    )


def test_on_resize_reports_size_changes(observer_page: Page):
    """on_resize reports the size when observing starts and after a change."""
    observer_page.click("#widen")
    expect(observer_page.locator("#width")).to_have_text("300")


def test_on_resize_resizing_its_element_raises_no_error(
    element_observer_app: AppHarness, page: Page
):
    """A report that resizes its own element raises no ResizeObserver loop error."""
    page.add_init_script(
        "window.__errors = [];"
        "window.addEventListener('error', (event) => window.__errors.push(event.message));"
    )
    assert element_observer_app.frontend_url is not None
    page.goto(element_observer_app.frontend_url)
    expect(page.locator("#direction")).to_have_text("row")
    page.click("#squeeze")
    expect(page.locator("#direction")).to_have_text("column")
    # The loop error is raised at the end of the frame the element resized in.
    page.evaluate(
        "new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)))"
    )
    assert page.evaluate("window.__errors") == []


def test_on_move_follows_scrolling_until_disabled(observer_page: Page):
    """on_move reports the position after every scroll, and nothing once disabled."""
    start = _top_of_box(observer_page)
    expect(observer_page.locator("#top")).to_have_text(start)
    observer_page.evaluate("window.scrollTo(0, 120)")
    observer_page.wait_for_function("window.scrollY === 120")
    assert float(_top_of_box(observer_page)) == pytest.approx(float(start) - 120)
    expect(observer_page.locator("#top")).to_have_text(_top_of_box(observer_page))

    stopped_at = _top_of_box(observer_page)
    observer_page.click("#stop")
    observer_page.evaluate("window.scrollTo(0, 0)")
    observer_page.wait_for_function("window.scrollY === 0")
    expect(observer_page.locator("#top")).to_have_text(stopped_at)


def test_on_intersect_reports_entering_the_viewport(observer_page: Page):
    """on_intersect reports whether the element is in view."""
    expect(observer_page.locator("#visible")).to_have_text("hidden")
    observer_page.locator("#footer").scroll_into_view_if_needed()
    expect(observer_page.locator("#visible")).to_have_text("visible")


def test_on_transition_end_ignores_transitions_of_descendants(observer_page: Page):
    """Only the transition of the observed element itself fires on_transition_end."""
    observer_page.click("#expand")
    expect(observer_page.locator("#ended")).to_have_text("height;")


def test_items_of_a_loop_observe_their_own_child(observer_page: Page):
    """Every item of rx.foreach reports the size of its own child."""
    # React's StrictMode starts the observers twice in dev mode.
    expect(observer_page.locator("#item_widths")).to_have_text(
        re.compile(r"^(40;60;)+$")
    )


def test_target_shown_later_is_observed_once_shown(observer_page: Page):
    """An observer whose target rx.cond shows later reports it once it is shown."""
    expect(observer_page.locator("#late_width")).to_have_text("0")
    observer_page.click("#show")
    expect(observer_page.locator("#late_width")).to_have_text("70")


def test_an_observer_joining_another_gets_the_current_ratio(observer_page: Page):
    """An observer of an element observed already reports what is in view now."""
    expect(observer_page.locator("#first_ratio")).to_have_text("1")
    # Scrolls the top half of the box out of view, which crosses no threshold.
    observer_page.evaluate(
        "window.scrollTo(0, document.getElementById('ratio_box')"
        ".getBoundingClientRect().top + window.scrollY + 50)"
    )
    observer_page.wait_for_function(
        "document.getElementById('ratio_box').getBoundingClientRect().top === -50"
    )
    # Clicked without scrolling to the button.
    observer_page.locator("#watch").dispatch_event("click")
    expect(observer_page.locator("#later_ratio")).to_have_text("0.5")
    expect(observer_page.locator("#first_ratio")).to_have_text("1")
