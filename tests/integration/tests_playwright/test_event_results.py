"""Integration tests for event handler values streamed back to the frontend caller."""

from collections.abc import Generator

import pytest
from playwright.sync_api import Page, expect

from reflex.testing import AppHarness


def EventResultsApp():
    """App exposing event triggers to the page, as an async callback prop would."""
    import asyncio

    import reflex as rx

    class ResultsState(rx.State):
        count: int = 0
        echo_calls: int = 0

        @rx.event
        def stream(self, prefix: str):
            self.count = 1
            yield f"{prefix}1"
            self.count = 2
            yield f"{prefix}2"
            return f"{prefix}3"  # noqa: B901

        @rx.event
        async def fail(self):
            yield "partial"
            msg = "bad page"
            raise ValueError(msg)

        @rx.event(background=True)
        async def slow_echo(self, value: str):
            # The first request finishes last, so their results interleave.
            await asyncio.sleep(0.4 if value == "first" else 0.05)
            yield f"{value}:a"
            await asyncio.sleep(0.05)
            yield f"{value}:b"

        @rx.event
        def echo(self, value: str) -> str:
            self.echo_calls += 1
            return value

    class Triggers(rx.Fragment):
        """Publishes its event triggers on window.__events for the test to call."""

        on_stream: rx.EventHandler[rx.event.passthrough_event_spec(str)]
        on_fail: rx.EventHandler[rx.event.no_args_event_spec]
        on_slow_echo: rx.EventHandler[rx.event.passthrough_event_spec(str)]
        on_echo: rx.EventHandler[rx.event.passthrough_event_spec(str)]

        def add_hooks(self) -> list[str | rx.Var]:
            events = rx.Var.create(dict(self.event_triggers))
            return [
                rx.Var(
                    f"window.__events = {events._js_expr};",
                    _var_data=events._get_all_var_data(),
                )
            ]

    def index():
        return rx.box(
            rx.input(
                value=ResultsState.router.session.client_token,
                read_only=True,
                id="token",
            ),
            rx.text(ResultsState.count, id="count"),
            rx.text(ResultsState.echo_calls, id="echo-calls"),
            Triggers.create(
                on_stream=ResultsState.stream,
                on_fail=ResultsState.fail,
                on_slow_echo=ResultsState.slow_echo,
                on_echo=ResultsState.echo.debounce(300),
            ),
        )

    app = rx.App()
    app.add_page(index)


@pytest.fixture(scope="module")
def event_results_app(tmp_path_factory) -> Generator[AppHarness, None, None]:
    """Start EventResultsApp via AppHarness.

    Args:
        tmp_path_factory: pytest fixture for creating temporary directories.

    Yields:
        Running AppHarness instance.
    """
    with AppHarness.create(
        root=tmp_path_factory.mktemp("event_results_app"),
        app_source=EventResultsApp,
    ) as harness:
        assert harness.app_instance is not None, "app is not running"
        yield harness


@pytest.fixture
def results_page(event_results_app: AppHarness, page: Page) -> Page:
    """A page of the app, connected to the backend.

    Args:
        event_results_app: The running app.
        page: A Playwright page.

    Returns:
        The page, once its client token is set.
    """
    assert event_results_app.frontend_url is not None
    page.goto(event_results_app.frontend_url)
    expect(page.locator("#token")).not_to_have_value("")
    return page


def test_stream_yields_each_value_and_awaits_to_the_last(results_page: Page):
    """`for await` sees each value in order; `await` resolves with the return value.

    Args:
        results_page: The connected page.
    """
    values = results_page.evaluate(
        """async () => {
            const values = [];
            for await (const value of window.__events.on_stream("x")) {
                values.push(value);
            }
            return values;
        }"""
    )
    assert values == ["x1", "x2", "x3"]
    expect(results_page.locator("#count")).to_have_text("2")
    assert results_page.evaluate('() => window.__events.on_stream("y")') == "y3"


@pytest.mark.ignore_console_error
def test_raising_handler_rejects_after_its_values(results_page: Page):
    """A handler that raises rejects the stream with its error, after its values.

    Args:
        results_page: The connected page.
    """
    outcome = results_page.evaluate(
        """async () => {
            const values = [];
            try {
                for await (const value of window.__events.on_fail()) {
                    values.push(value);
                }
                return { values };
            } catch (error) {
                return { values, error: error.message };
            }
        }"""
    )
    assert outcome == {"values": ["partial"], "error": "ValueError: bad page"}


def test_concurrent_requests_keep_their_own_values(results_page: Page):
    """Two requests in flight on one connection do not receive each other's values.

    Args:
        results_page: The connected page.
    """
    results = results_page.evaluate(
        """async () => {
            const collect = async (stream) => {
                const values = [];
                for await (const value of stream) values.push(value);
                return values;
            };
            return await Promise.all([
                collect(window.__events.on_slow_echo("first")),
                collect(window.__events.on_slow_echo("second")),
            ]);
        }"""
    )
    assert results == [["first:a", "first:b"], ["second:a", "second:b"]]


def test_debounced_calls_share_the_dispatch_that_fires(results_page: Page):
    """Every call in one debounce window gets the result of the call that was sent.

    Args:
        results_page: The connected page.
    """
    outcome = results_page.evaluate(
        """async () => {
            const first = window.__events.on_echo("a");
            const second = window.__events.on_echo("ab");
            return {
                same: first === second,
                results: await Promise.all([first, second]),
            };
        }"""
    )
    assert outcome == {"same": True, "results": ["ab", "ab"]}
    expect(results_page.locator("#echo-calls")).to_have_text("1")
