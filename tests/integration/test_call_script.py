"""Integration tests for client side storage."""

from __future__ import annotations

from collections.abc import Generator

import pytest
from playwright.sync_api import Page, expect

from reflex.testing import AppHarness

from . import utils
from .utils import SessionStorage


def CallScript():
    """A test app for browser javascript integration."""
    from pathlib import Path

    import reflex as rx

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
    with AppHarness.create(
        root=tmp_path_factory.mktemp("call_script"),
        app_source=CallScript,
    ) as harness:
        yield harness


def assert_token(page: Page) -> str:
    """Get the token associated with backend state.

    Args:
        page: Playwright page.

    Returns:
        The token visible in the page's session storage.
    """
    ss = SessionStorage(page)
    assert AppHarness._poll_for(lambda: ss.get("token") is not None), "token not found"
    assert AppHarness._poll_for(
        lambda: page.evaluate("typeof external4 !== 'undefined'")
    ), "scripts not loaded"
    token = ss.get("token")
    assert token is not None
    return token


@pytest.mark.parametrize("script", ["inline", "external"])
def test_call_script(
    call_script: AppHarness,
    page: Page,
    script: str,
):
    """Test calling javascript functions from python.

    Args:
        call_script: harness for CallScript app.
        page: Playwright page.
        script: The type of script to test.
    """
    assert call_script.frontend_url is not None
    page.goto(call_script.frontend_url)

    utils.poll_for_token(page)
    assert_token(page)

    reset_button = page.locator("#reset")
    update_counter_button = page.locator(f"#update_{script}_counter")
    counter = page.locator(f"#{script}_counter")
    results = page.locator("#results")
    yield_button = page.locator(f"#{script}_yield")
    return_button = page.locator(f"#{script}_return")
    yield_callback_button = page.locator(f"#{script}_yield_callback")
    return_callback_button = page.locator(f"#{script}_return_callback")
    return_lambda_button = page.locator(f"#{script}_return_lambda")

    yield_button.click()
    update_counter_button.click()
    expect(counter).to_have_value("4")
    reset_button.click()
    expect(counter).to_have_value("0")
    return_button.click()
    update_counter_button.click()
    expect(counter).to_have_value("1")
    reset_button.click()
    expect(counter).to_have_value("0")

    yield_callback_button.click()
    update_counter_button.click()
    expect(counter).to_have_value("4")
    expect(results).to_have_value(
        f'["{script}1",null,{{"{script}3":42,"a":[1,2,3],"s":"js","o":{{"a":1,"b":2}}}},"async {script}4"]'
    )
    reset_button.click()
    expect(counter).to_have_value("0")

    return_callback_button.click()
    update_counter_button.click()
    expect(counter).to_have_value("1")
    expect(results).to_have_value(
        f'[{{"{script}3":42,"a":[1,2,3],"s":"js","o":{{"a":1,"b":2}}}}]'
    )
    reset_button.click()
    expect(counter).to_have_value("0")

    return_lambda_button.click()
    update_counter_button.click()
    expect(counter).to_have_value("1")
    expect(results).to_have_value('[["lambda",null]]')
    reset_button.click()
    expect(counter).to_have_value("0")

    # Check that triggering script from event trigger calls callback
    update_value_button = page.locator("#update_value")
    update_value_button.click()

    expect(update_value_button).to_have_text("updated")


def test_call_script_w_var(
    call_script: AppHarness,
    page: Page,
):
    """Test evaluating javascript expressions containing Vars.

    Args:
        call_script: harness for CallScript app.
        page: Playwright page.
    """
    assert call_script.frontend_url is not None
    page.goto(call_script.frontend_url)

    utils.poll_for_token(page)
    assert_token(page)

    last_result = page.locator("#last_result")
    expect(last_result).to_have_value("0")

    inline_return_button = page.locator("#inline_return")

    call_with_var_f_string_button = page.locator("#call_with_var_f_string")
    call_with_var_str_cast_button = page.locator("#call_with_var_str_cast")
    call_with_var_f_string_wrapped_button = page.locator(
        "#call_with_var_f_string_wrapped"
    )
    call_with_var_str_cast_wrapped_button = page.locator(
        "#call_with_var_str_cast_wrapped"
    )
    call_with_var_f_string_inline_button = page.locator(
        "#call_with_var_f_string_inline"
    )
    call_with_var_str_cast_inline_button = page.locator(
        "#call_with_var_str_cast_inline"
    )
    call_with_var_f_string_wrapped_inline_button = page.locator(
        "#call_with_var_f_string_wrapped_inline"
    )
    call_with_var_str_cast_wrapped_inline_button = page.locator(
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
