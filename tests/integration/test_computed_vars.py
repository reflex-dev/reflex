"""Test computed vars."""

from __future__ import annotations

import time
from collections.abc import Generator

import pytest
from playwright.sync_api import Page, expect

from reflex.testing import AppHarness

from . import utils


def ComputedVars():
    """Test app for computed vars."""
    import reflex as rx

    class StateMixin(rx.State, mixin=True):
        pass

    class State(StateMixin, rx.State):
        count: int = 0

        # cached var with dep on count
        @rx.var(interval=15)
        def count1(self) -> int:
            return self.count

        # cached backend var with dep on count
        @rx.var(interval=15, backend=True)
        def count1_backend(self) -> int:
            return self.count

        # same as above but implicit backend with `_` prefix
        @rx.var(interval=15)
        def _count1_backend(self) -> int:
            return self.count

        # explicit disabled auto_deps
        @rx.var(interval=15, auto_deps=False)
        def count3(self) -> int:
            # this will not add deps, because auto_deps is False
            print(self.count1)

            return self.count

        # explicit dependency on count var
        @rx.var(deps=["count"], auto_deps=False)
        def depends_on_count(self) -> int:
            return self.count

        # explicit dependency on count1 var
        @rx.var(deps=[count1], auto_deps=False)
        def depends_on_count1(self) -> int:
            return self.count

        @rx.var(
            deps=[count3],
            auto_deps=False,
        )
        def depends_on_count3(self) -> int:
            return self.count

        # special floats should be properly decoded on the frontend
        @rx.var(cache=True, initial_value=[])
        def special_floats(self) -> list[float]:
            return [42.9, float("nan"), float("inf"), float("-inf")]

        @rx.event
        def increment(self):
            self.count += 1

        @rx.event
        def mark_dirty(self):
            self._mark_dirty()

    assert State.backend_vars == {"_reflex_internal_links": None}

    def index() -> rx.Component:
        return rx.center(
            rx.vstack(
                rx.input(
                    id="token",
                    value=State.router.session.client_token,
                    is_read_only=True,
                ),
                rx.button("Increment", on_click=State.increment, id="increment"),
                rx.button("Do nothing", on_click=State.mark_dirty, id="mark_dirty"),
                rx.text("count:"),
                rx.text(State.count, id="count"),
                rx.text("count1:"),
                rx.text(State.count1, id="count1"),
                rx.text("count1_backend:"),
                rx.text(State.count1_backend, id="count1_backend"),
                rx.text("_count1_backend:"),
                rx.text(State._count1_backend, id="_count1_backend"),
                rx.text("count3:"),
                rx.text(State.count3, id="count3"),
                rx.text("depends_on_count:"),
                rx.text(
                    State.depends_on_count,
                    id="depends_on_count",
                ),
                rx.text("depends_on_count1:"),
                rx.text(
                    State.depends_on_count1,
                    id="depends_on_count1",
                ),
                rx.text("depends_on_count3:"),
                rx.text(
                    State.depends_on_count3,
                    id="depends_on_count3",
                ),
                rx.text("special_floats:"),
                rx.text(
                    State.special_floats.join(", "),
                    id="special_floats",
                ),
            ),
        )

    app = rx.App()
    app.add_page(index)


@pytest.fixture(scope="module")
def computed_vars(
    tmp_path_factory: pytest.TempPathFactory,
) -> Generator[AppHarness, None, None]:
    """Start ComputedVars app at tmp_path via AppHarness.

    Args:
        tmp_path_factory: pytest tmp_path_factory fixture

    Yields:
        running AppHarness instance
    """
    with AppHarness.create(
        root=tmp_path_factory.mktemp("computed_vars"),
        app_source=ComputedVars,
    ) as harness:
        yield harness


def test_computed_vars(
    computed_vars: AppHarness,
    page: Page,
):
    """Test that computed vars are working as expected.

    Args:
        computed_vars: harness for ComputedVars app.
        page: Playwright page.
    """
    assert computed_vars.frontend_url is not None
    page.goto(computed_vars.frontend_url)

    assert computed_vars.app_instance is not None
    utils.poll_for_token(page)

    # test that backend var is not rendered
    count1_backend = page.locator("#count1_backend")
    expect(count1_backend).to_have_text("")
    count1_backend_ = page.locator("#_count1_backend")
    expect(count1_backend_).to_have_text("")

    count = page.locator("#count")
    expect(count).to_have_text("0")

    count1 = page.locator("#count1")
    expect(count1).to_have_text("0")

    count3 = page.locator("#count3")
    expect(count3).to_have_text("0")

    depends_on_count = page.locator("#depends_on_count")
    expect(depends_on_count).to_have_text("0")

    depends_on_count1 = page.locator("#depends_on_count1")
    expect(depends_on_count1).to_have_text("0")

    depends_on_count3 = page.locator("#depends_on_count3")
    expect(depends_on_count3).to_have_text("0")

    special_floats = page.locator("#special_floats")
    expect(special_floats).to_have_text("42.9, NaN, Infinity, -Infinity")

    increment = page.locator("#increment")
    expect(increment).to_be_enabled()

    mark_dirty = page.locator("#mark_dirty")
    expect(mark_dirty).to_be_enabled()

    mark_dirty.click()

    increment.click()
    expect(count).to_have_text("1", timeout=2000)
    expect(count1).to_have_text("1", timeout=2000)
    expect(depends_on_count).to_have_text("1", timeout=2000)

    mark_dirty.click()
    with pytest.raises(AssertionError):
        expect(count3).not_to_have_text("0", timeout=5000)

    time.sleep(10)
    expect(count3).to_have_text("0")
    expect(depends_on_count3).to_have_text("0")
    mark_dirty.click()
    expect(count3).to_have_text("1", timeout=2000)
    expect(depends_on_count3).to_have_text("1")
