"""Integration tests for Reflex's browser call_script API."""

from __future__ import annotations

from collections.abc import Generator

import pytest
from playwright.sync_api import Page, expect

from reflex.testing import AppHarness

# Seconds an awaited call waits for its tab to reconnect, short for the tests
# that wait it out.
GRACE_PERIOD = 2.0


def CallScript():
    """A test app for browser javascript integration."""
    from pathlib import Path

    import reflex as rx
    from reflex.utils.exceptions import (
        BrowserDisconnectedError,
        BrowserResultSerializationError,
        BrowserScriptError,
    )

    inline_scripts = """
    let inline_counter = 0
    function inline1() {
        inline_counter += 1
        return "inline1"
    }
    function inline2() {
        inline_counter += 1
        console.log("inline2")
    }
    function inline3() {
        inline_counter += 1
        return {inline3: 42, a: [1, 2, 3], s: 'js', o: {a: 1, b: 2}}
    }
    async function inline4() {
        inline_counter += 1
        return "async inline4"
    }
    """

    external_scripts = inline_scripts.replace("inline", "external")

    class CallScriptState(rx.State):
        results: rx.Field[list[str | dict | list | None]] = rx.field([])
        inline_counter: rx.Field[int] = rx.field(0)
        external_counter: rx.Field[int] = rx.field(0)
        value: str = "Initial"
        last_result: rx.Field[int] = rx.field(0)
        awaited: rx.Field[list[str]] = rx.field([])

        @rx.event(background=True)
        async def await_results(self):
            seen: list[str] = [
                repr(await rx.call_script("inline3()")),
                repr(await rx.call_script("inline4()")),
                repr(await rx.call_function("() => [1, 'two', undefined]")),
                repr(await rx.call_script("undefined")),
            ]
            for code, expected in (
                ("missing_function()", BrowserScriptError),
                ("document.body", BrowserResultSerializationError),
            ):
                try:
                    await rx.call_script(code)
                except expected as e:
                    seen.append(f"{type(e).__name__}: {e}")
            try:
                await rx.call_script("new Promise(() => {})", timeout=0.5)
            except TimeoutError as e:
                seen.append(f"TimeoutError: {e}")
            async with self:
                self.awaited = seen

        @rx.event(background=True)
        async def await_user(self):
            # Settled by the test, which may first drop the socket or reload.
            try:
                answer = repr(
                    await rx.call_script(
                        "new Promise((resolve) => { window.answerAwaited = resolve })"
                    )
                )
            except BrowserDisconnectedError as e:
                answer = f"BrowserDisconnectedError: {e}"
            async with self:
                self.awaited = [answer]

        @rx.event
        def call_script_callback(self, result):
            self.results.append(result)

        @rx.event
        def call_script_callback_other_arg(self, result, other_arg):
            self.results.append([other_arg, result])

        @rx.event
        def call_scripts_inline_yield(self):
            yield rx.call_script("inline1()")
            yield rx.call_script("inline2()")
            yield rx.call_script("inline3()")
            yield rx.call_script("inline4()")

        @rx.event
        def call_script_inline_return(self):
            return rx.call_script("inline2()")

        @rx.event
        def call_scripts_inline_yield_callback(self):
            yield rx.call_script(
                "inline1()", callback=CallScriptState.call_script_callback
            )
            yield rx.call_script(
                "inline2()", callback=CallScriptState.call_script_callback
            )
            yield rx.call_script(
                "inline3()", callback=CallScriptState.call_script_callback
            )
            yield rx.call_script(
                "inline4()", callback=CallScriptState.call_script_callback
            )

        @rx.event
        def call_script_inline_return_callback(self):
            return rx.call_script(
                "inline3()", callback=CallScriptState.call_script_callback
            )

        @rx.event
        def call_script_inline_return_lambda(self):
            return rx.call_script(
                "inline2()",
                callback=lambda result: CallScriptState.call_script_callback_other_arg(
                    result, "lambda"
                ),
            )

        @rx.event
        def get_inline_counter(self):
            return rx.call_script(
                "inline_counter",
                callback=CallScriptState.setvar("inline_counter"),
            )

        @rx.event
        def call_scripts_external_yield(self):
            yield rx.call_script("external1()")
            yield rx.call_script("external2()")
            yield rx.call_script("external3()")
            yield rx.call_script("external4()")

        @rx.event
        def call_script_external_return(self):
            return rx.call_script("external2()")

        @rx.event
        def call_scripts_external_yield_callback(self):
            yield rx.call_script(
                "external1()", callback=CallScriptState.call_script_callback
            )
            yield rx.call_script(
                "external2()", callback=CallScriptState.call_script_callback
            )
            yield rx.call_script(
                "external3()", callback=CallScriptState.call_script_callback
            )
            yield rx.call_script(
                "external4()", callback=CallScriptState.call_script_callback
            )

        @rx.event
        def call_script_external_return_callback(self):
            return rx.call_script(
                "external3()", callback=CallScriptState.call_script_callback
            )

        @rx.event
        def call_script_external_return_lambda(self):
            return rx.call_script(
                "external2()",
                callback=lambda result: CallScriptState.call_script_callback_other_arg(
                    result, "lambda"
                ),
            )

        @rx.event
        def get_external_counter(self):
            return rx.call_script(
                "external_counter",
                callback=CallScriptState.setvar("external_counter"),
            )

        @rx.event
        def call_with_var_f_string(self):
            return rx.call_script(
                f"{rx.Var('inline_counter')} + {rx.Var('external_counter')}",
                callback=CallScriptState.setvar("last_result"),
            )

        @rx.event
        def call_with_var_str_cast(self):
            return rx.call_script(
                f"{rx.Var('inline_counter')!s} + {rx.Var('external_counter')!s}",
                callback=CallScriptState.setvar("last_result"),
            )

        @rx.event
        def call_with_var_f_string_wrapped(self):
            return rx.call_script(
                rx.Var(f"{rx.Var('inline_counter')} + {rx.Var('external_counter')}"),
                callback=CallScriptState.setvar("last_result"),
            )

        @rx.event
        def call_with_var_str_cast_wrapped(self):
            return rx.call_script(
                rx.Var(
                    f"{rx.Var('inline_counter')!s} + {rx.Var('external_counter')!s}"
                ),
                callback=CallScriptState.setvar("last_result"),
            )

        @rx.event
        def set_inline_counter(self, value: str):
            self.inline_counter = int(value)

        @rx.event
        def set_external_counter(self, value: str):
            self.external_counter = int(value)

        @rx.event
        def set_last_result(self, value: str):
            self.last_result = int(value)

        @rx.event
        def set_value(self, value: str):
            self.value = value

        @rx.event
        def reset_(self):
            yield rx.call_script("inline_counter = 0; external_counter = 0")
            self.reset()

    app = rx.App()
    Path("assets/external.js").write_text(external_scripts)

    @app.add_page
    def index():
        return rx.vstack(
            rx.input(
                value=CallScriptState.inline_counter.to_string(),
                id="inline_counter",
                read_only=True,
            ),
            rx.input(
                value=CallScriptState.external_counter.to_string(),
                id="external_counter",
                read_only=True,
            ),
            rx.text_area(
                value=CallScriptState.results.to_string(),
                id="results",
                read_only=True,
            ),
            rx.script(inline_scripts),
            rx.script(src="/external.js"),
            rx.button(
                "call_scripts_inline_yield",
                on_click=CallScriptState.call_scripts_inline_yield,
                id="inline_yield",
            ),
            rx.button(
                "call_script_inline_return",
                on_click=CallScriptState.call_script_inline_return,
                id="inline_return",
            ),
            rx.button(
                "call_scripts_inline_yield_callback",
                on_click=CallScriptState.call_scripts_inline_yield_callback,
                id="inline_yield_callback",
            ),
            rx.button(
                "call_script_inline_return_callback",
                on_click=CallScriptState.call_script_inline_return_callback,
                id="inline_return_callback",
            ),
            rx.button(
                "call_script_inline_return_lambda",
                on_click=CallScriptState.call_script_inline_return_lambda,
                id="inline_return_lambda",
            ),
            rx.button(
                "call_scripts_external_yield",
                on_click=CallScriptState.call_scripts_external_yield,
                id="external_yield",
            ),
            rx.button(
                "call_script_external_return",
                on_click=CallScriptState.call_script_external_return,
                id="external_return",
            ),
            rx.button(
                "call_scripts_external_yield_callback",
                on_click=CallScriptState.call_scripts_external_yield_callback,
                id="external_yield_callback",
            ),
            rx.button(
                "call_script_external_return_callback",
                on_click=CallScriptState.call_script_external_return_callback,
                id="external_return_callback",
            ),
            rx.button(
                "call_script_external_return_lambda",
                on_click=CallScriptState.call_script_external_return_lambda,
                id="external_return_lambda",
            ),
            rx.button(
                "Update Inline Counter",
                on_click=CallScriptState.get_inline_counter,
                id="update_inline_counter",
            ),
            rx.button(
                "Update External Counter",
                on_click=CallScriptState.get_external_counter,
                id="update_external_counter",
            ),
            rx.button(
                CallScriptState.value,
                on_click=rx.call_script(
                    "'updated'",
                    callback=CallScriptState.setvar("value"),
                ),
                id="update_value",
            ),
            rx.button("Reset", id="reset", on_click=CallScriptState.reset_),
            rx.button(
                "await_results",
                on_click=CallScriptState.await_results,
                id="await_results",
            ),
            rx.button(
                "await_user", on_click=CallScriptState.await_user, id="await_user"
            ),
            rx.button(
                "drop_connection",
                on_click=rx.call_script(
                    "socket.disconnect();"
                    "setTimeout(() => socket.connect(), window.reconnectAfterMs)"
                ),
                id="drop_connection",
            ),
            rx.button(
                "set_value_busy",
                on_click=CallScriptState.set_value("busy"),
                id="set_value_busy",
            ),
            rx.text(CallScriptState.value, id="value"),
            rx.text_area(
                value=CallScriptState.awaited.join("\n"),
                id="awaited",
                read_only=True,
            ),
            rx.input(
                value=CallScriptState.last_result.to_string(),
                id="last_result",
                read_only=True,
                on_click=CallScriptState.setvar("last_result", 0),
            ),
            rx.button(
                "call_with_var_f_string",
                on_click=CallScriptState.call_with_var_f_string,
                id="call_with_var_f_string",
            ),
            rx.button(
                "call_with_var_str_cast",
                on_click=CallScriptState.call_with_var_str_cast,
                id="call_with_var_str_cast",
            ),
            rx.button(
                "call_with_var_f_string_wrapped",
                on_click=CallScriptState.call_with_var_f_string_wrapped,
                id="call_with_var_f_string_wrapped",
            ),
            rx.button(
                "call_with_var_str_cast_wrapped",
                on_click=CallScriptState.call_with_var_str_cast_wrapped,
                id="call_with_var_str_cast_wrapped",
            ),
            rx.button(
                "call_with_var_f_string_inline",
                on_click=rx.call_script(
                    f"{rx.Var('inline_counter')} + {CallScriptState.last_result}",
                    callback=CallScriptState.setvar("last_result"),
                ),
                id="call_with_var_f_string_inline",
            ),
            rx.button(
                "call_with_var_str_cast_inline",
                on_click=rx.call_script(
                    f"{rx.Var('inline_counter')!s} + {rx.Var('external_counter')!s}",
                    callback=CallScriptState.setvar("last_result"),
                ),
                id="call_with_var_str_cast_inline",
            ),
            rx.button(
                "call_with_var_f_string_wrapped_inline",
                on_click=rx.call_script(
                    rx.Var(
                        f"{rx.Var('inline_counter')} + {CallScriptState.last_result}"
                    ),
                    callback=CallScriptState.setvar("last_result"),
                ),
                id="call_with_var_f_string_wrapped_inline",
            ),
            rx.button(
                "call_with_var_str_cast_wrapped_inline",
                on_click=rx.call_script(
                    rx.Var(
                        f"{rx.Var('inline_counter')!s} + {rx.Var('external_counter')!s}"
                    ),
                    callback=CallScriptState.setvar("last_result"),
                ),
                id="call_with_var_str_cast_wrapped_inline",
            ),
        )


@pytest.fixture(scope="module")
def call_script(tmp_path_factory) -> Generator[AppHarness, None, None]:
    """Start CallScript app at tmp_path via AppHarness.

    Args:
        tmp_path_factory: pytest tmp_path_factory fixture

    Yields:
        running AppHarness instance
    """
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setenv("REFLEX_BROWSER_CALL_GRACE_PERIOD", str(GRACE_PERIOD))
        with AppHarness.create(
            root=tmp_path_factory.mktemp("call_script"),
            app_source=CallScript,
        ) as harness:
            yield harness


@pytest.fixture
def call_script_page(call_script: AppHarness, page: Page) -> Page:
    """Open the app and wait for its session and external scripts.

    Args:
        call_script: harness for the call_script app.
        page: Playwright page.

    Returns:
        The connected Playwright page.
    """
    assert call_script.frontend_url is not None
    page.goto(call_script.frontend_url)
    page.wait_for_function("() => sessionStorage.getItem('token') !== null")
    page.wait_for_function("() => typeof external4 !== 'undefined'")
    return page


@pytest.mark.parametrize("script", ["inline", "external"])
def test_call_script(
    call_script: AppHarness,
    call_script_page: Page,
    script: str,
):
    """Test calling javascript functions from python.

    Args:
        call_script: harness for CallScript app.
        call_script_page: Playwright page.
        script: The type of script to test.
    """
    reset_button = call_script_page.locator("#reset")
    update_counter_button = call_script_page.locator(f"#update_{script}_counter")
    counter = call_script_page.locator(f"#{script}_counter")
    results = call_script_page.locator("#results")
    yield_button = call_script_page.locator(f"#{script}_yield")
    return_button = call_script_page.locator(f"#{script}_return")
    yield_callback_button = call_script_page.locator(f"#{script}_yield_callback")
    return_callback_button = call_script_page.locator(f"#{script}_return_callback")
    return_lambda_button = call_script_page.locator(f"#{script}_return_lambda")

    yield_button.click()
    update_counter_button.click()
    expect(counter).to_have_value("4", timeout=15_000)
    reset_button.click()
    expect(counter).to_have_value("0", timeout=15_000)
    return_button.click()
    update_counter_button.click()
    expect(counter).to_have_value("1", timeout=15_000)
    reset_button.click()
    expect(counter).to_have_value("0", timeout=15_000)

    yield_callback_button.click()
    update_counter_button.click()
    expect(counter).to_have_value("4", timeout=15_000)
    expect(results).to_have_value(
        f'["{script}1",null,{{"{script}3":42,"a":[1,2,3],"s":"js","o":{{"a":1,"b":2}}}},"async {script}4"]',
        timeout=15_000,
    )
    reset_button.click()
    expect(counter).to_have_value("0", timeout=15_000)

    return_callback_button.click()
    update_counter_button.click()
    expect(counter).to_have_value("1", timeout=15_000)
    expect(results).to_have_value(
        f'[{{"{script}3":42,"a":[1,2,3],"s":"js","o":{{"a":1,"b":2}}}}]',
        timeout=15_000,
    )
    reset_button.click()
    expect(counter).to_have_value("0", timeout=15_000)

    return_lambda_button.click()
    update_counter_button.click()
    expect(counter).to_have_value("1", timeout=15_000)
    expect(results).to_have_value('[["lambda",null]]', timeout=15_000)
    reset_button.click()
    expect(counter).to_have_value("0", timeout=15_000)

    # Check that triggering script from event trigger calls callback
    update_value_button = call_script_page.locator("#update_value")
    update_value_button.click()

    expect(update_value_button).to_have_text("updated", timeout=15_000)


def test_call_script_w_var(
    call_script: AppHarness,
    call_script_page: Page,
):
    """Test evaluating javascript expressions containing Vars.

    Args:
        call_script: harness for CallScript app.
        call_script_page: Playwright page.
    """
    last_result = call_script_page.locator("#last_result")
    expect(last_result).to_have_value("0")
    inline_return_button = call_script_page.locator("#inline_return")
    call_with_var_f_string_button = call_script_page.locator("#call_with_var_f_string")
    call_with_var_str_cast_button = call_script_page.locator("#call_with_var_str_cast")
    call_with_var_f_string_wrapped_button = call_script_page.locator(
        "#call_with_var_f_string_wrapped"
    )
    call_with_var_str_cast_wrapped_button = call_script_page.locator(
        "#call_with_var_str_cast_wrapped"
    )
    call_with_var_f_string_inline_button = call_script_page.locator(
        "#call_with_var_f_string_inline"
    )
    call_with_var_str_cast_inline_button = call_script_page.locator(
        "#call_with_var_str_cast_inline"
    )
    call_with_var_f_string_wrapped_inline_button = call_script_page.locator(
        "#call_with_var_f_string_wrapped_inline"
    )
    call_with_var_str_cast_wrapped_inline_button = call_script_page.locator(
        "#call_with_var_str_cast_wrapped_inline"
    )

    inline_return_button.click()
    call_with_var_f_string_button.click()
    expect(last_result).to_have_value("1")

    inline_return_button.click()
    call_with_var_str_cast_button.click()
    expect(last_result).to_have_value("2")

    inline_return_button.click()
    call_with_var_f_string_wrapped_button.click()
    expect(last_result).to_have_value("3")

    inline_return_button.click()
    call_with_var_str_cast_wrapped_button.click()
    expect(last_result).to_have_value("4")

    inline_return_button.click()
    call_with_var_f_string_inline_button.click()
    expect(last_result).to_have_value("9")

    inline_return_button.click()
    call_with_var_str_cast_inline_button.click()
    expect(last_result).to_have_value("6")

    inline_return_button.click()
    call_with_var_f_string_wrapped_inline_button.click()
    expect(last_result).to_have_value("13")

    inline_return_button.click()
    call_with_var_str_cast_wrapped_inline_button.click()
    expect(last_result).to_have_value("8")


def test_await_call_script(call_script: AppHarness, call_script_page: Page):
    """A background handler awaits the value, error or timeout of a browser script.

    Args:
        call_script: harness for CallScript app.
        call_script_page: Playwright page.
    """
    expected_lines = (
        "{'inline3': 42, 'a': [1, 2, 3], 's': 'js', 'o': {'a': 1, 'b': 2}}",
        "'async inline4'",
        "[1, 'two', None]",
        "None",
        "BrowserScriptError: ReferenceError: missing_function is not defined",
        (
            "BrowserResultSerializationError: TypeError: The script returned a DOM "
            "node or window, which JSON cannot carry; return the data you need from "
            "it instead."
        ),
        (
            "TimeoutError: The browser did not return a result for `_call_script` "
            "within 0.5 seconds. If the script needs longer, pass a longer "
            "`timeout=` to the call (or `timeout=None` to wait without a limit) or "
            "raise `browser_call_timeout` in rxconfig.py; if it returns a promise, "
            "make sure the promise settles."
        ),
    )
    call_script_page.locator("#await_results").click()
    expect(call_script_page.locator("#awaited")).to_have_value(
        "\n".join(expected_lines), timeout=15_000
    )


def _await_user(page: Page) -> None:
    """Start the awaited script that waits for the test to answer.

    Args:
        page: Playwright page.
    """
    page.locator("#await_user").click()
    page.wait_for_function("() => typeof window.answerAwaited === 'function'")


def test_awaited_script_does_not_hold_up_other_events(
    call_script: AppHarness, call_script_page: Page
):
    """While an awaited script waits on the user, the tab's other events still run.

    Args:
        call_script: harness for CallScript app.
        call_script_page: Playwright page.
    """
    _await_user(call_script_page)
    call_script_page.locator("#set_value_busy").click()
    expect(call_script_page.locator("#value")).to_have_text("busy")
    call_script_page.evaluate("window.answerAwaited({answer: 'yes'})")
    expect(call_script_page.locator("#awaited")).to_have_value("{'answer': 'yes'}")


def _drop_connection(page: Page, reconnect_after_ms: int) -> None:
    """Drop the tab's socket and connect it again after a delay.

    Args:
        page: Playwright page.
        reconnect_after_ms: Milliseconds until the socket connects again.
    """
    page.evaluate(f"window.reconnectAfterMs = {reconnect_after_ms}")
    page.locator("#drop_connection").click()


def test_awaited_result_arrives_after_a_reconnect_within_the_grace_period(
    call_script: AppHarness, call_script_page: Page
):
    """A result sent while the socket is down reaches the backend once it reconnects in time.

    Args:
        call_script: harness for CallScript app.
        call_script_page: Playwright page.
    """
    _await_user(call_script_page)
    _drop_connection(call_script_page, 300)
    call_script_page.evaluate("window.answerAwaited('after the drop')")
    expect(call_script_page.locator("#awaited")).to_have_value("'after the drop'")


def test_awaited_call_fails_when_the_tab_stays_away_past_the_grace_period(
    call_script: AppHarness, call_script_page: Page
):
    """A tab that reconnects only after the grace period has its call failed.

    Args:
        call_script: harness for CallScript app.
        call_script_page: Playwright page.
    """
    _await_user(call_script_page)
    _drop_connection(call_script_page, int(GRACE_PERIOD * 1000) + 1500)
    expect(call_script_page.locator("#awaited")).to_have_value(
        "BrowserDisconnectedError: The browser tab did not reconnect to this "
        "backend worker within browser_call_grace_period "
        f"({GRACE_PERIOD} seconds), so the script's result is lost: the tab was "
        "closed, lost its connection for longer, or reconnected to another "
        "backend worker, which cannot pass the result on. Catch "
        "BrowserDisconnectedError where the user may close the tab, raise "
        "`browser_call_grace_period` in rxconfig.py if connections drop for "
        "longer, and with several backend workers route each tab to one worker "
        "(sticky sessions).",
        timeout=10_000,
    )


def test_awaited_call_fails_at_once_when_the_page_reloads(
    call_script: AppHarness, call_script_page: Page
):
    """Reloading the page stops the script, so the call fails without waiting out the grace period.

    Args:
        call_script: harness for CallScript app.
        call_script_page: Playwright page.
    """
    _await_user(call_script_page)
    call_script_page.reload()
    expect(call_script_page.locator("#awaited")).to_have_value(
        "BrowserDisconnectedError: The browser tab reloaded or left the page "
        "before the script returned a result, so the script stopped. Catch "
        "BrowserDisconnectedError where the user may reload or leave the page "
        "while the script runs."
    )
