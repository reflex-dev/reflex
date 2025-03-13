"""Integration tests for client side storage."""

from __future__ import annotations

from typing import Generator

import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver

from reflex.testing import AppHarness

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
        last_result: int = 0

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
        def reset_(self):
            yield rx.call_script("inline_counter = 0; external_counter = 0")
            self.reset()

    app = rx.App(_state=rx.State)
    Path("assets/external.js").write_text(external_scripts)

    @app.add_page
    def index():
        return rx.vstack(
            rx.input(
                value=CallScriptState.inline_counter.to(str),
                id="inline_counter",
                read_only=True,
            ),
            rx.input(
                value=CallScriptState.external_counter.to(str),
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
                value=CallScriptState.last_result,
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


@pytest.fixture
def driver(call_script: AppHarness) -> Generator[WebDriver, None, None]:
    """Get an instance of the browser open to the call_script app.

    Args:
        call_script: harness for CallScript app

    Yields:
        WebDriver instance.
    """
    assert call_script.app_instance is not None, "app is not running"
    driver = call_script.frontend()
    try:
        yield driver
    finally:
        driver.quit()


def assert_token(driver: WebDriver) -> str:
    """Get the token associated with backend state.

    Args:
        driver: WebDriver instance.

    Returns:
        The token visible in the driver browser.
    """
    ss = SessionStorage(driver)
    assert AppHarness._poll_for(lambda: ss.get("token") is not None), "token not found"
    return ss.get("token")


@pytest.mark.parametrize("script", ["inline", "external"])
def test_call_script(
    call_script: AppHarness,
    driver: WebDriver,
    script: str,
):
    """Test calling javascript functions from python.

    Args:
        call_script: harness for CallScript app.
        driver: WebDriver instance.
        script: The type of script to test.
    """
    assert_token(driver)
    reset_button = driver.find_element(By.ID, "reset")
    update_counter_button = driver.find_element(By.ID, f"update_{script}_counter")
    counter = driver.find_element(By.ID, f"{script}_counter")
    results = driver.find_element(By.ID, "results")
    yield_button = driver.find_element(By.ID, f"{script}_yield")
    return_button = driver.find_element(By.ID, f"{script}_return")
    yield_callback_button = driver.find_element(By.ID, f"{script}_yield_callback")
    return_callback_button = driver.find_element(By.ID, f"{script}_return_callback")
    return_lambda_button = driver.find_element(By.ID, f"{script}_return_lambda")

    yield_button.click()
    update_counter_button.click()
    assert call_script.poll_for_value(counter, exp_not_equal="0") == "4"
    reset_button.click()
    assert call_script.poll_for_value(counter, exp_not_equal="4") == "0"
    return_button.click()
    update_counter_button.click()
    assert call_script.poll_for_value(counter, exp_not_equal="0") == "1"
    reset_button.click()
    assert call_script.poll_for_value(counter, exp_not_equal="1") == "0"

    yield_callback_button.click()
    update_counter_button.click()
    assert call_script.poll_for_value(counter, exp_not_equal="0") == "4"
    assert (
        call_script.poll_for_value(results, exp_not_equal="[]")
        == '["%s1",null,{"%s3":42,"a":[1,2,3],"s":"js","o":{"a":1,"b":2}},"async %s4"]'
        % (
            script,
            script,
            script,
        )
    )
    reset_button.click()
    assert call_script.poll_for_value(counter, exp_not_equal="4") == "0"

    return_callback_button.click()
    update_counter_button.click()
    assert call_script.poll_for_value(counter, exp_not_equal="0") == "1"
    assert (
        call_script.poll_for_value(results, exp_not_equal="[]")
        == '[{"%s3":42,"a":[1,2,3],"s":"js","o":{"a":1,"b":2}}]' % script
    )
    reset_button.click()
    assert call_script.poll_for_value(counter, exp_not_equal="1") == "0"

    return_lambda_button.click()
    update_counter_button.click()
    assert call_script.poll_for_value(counter, exp_not_equal="0") == "1"
    assert (
        call_script.poll_for_value(results, exp_not_equal="[]") == '[["lambda",null]]'
    )
    reset_button.click()
    assert call_script.poll_for_value(counter, exp_not_equal="1") == "0"

    # Check that triggering script from event trigger calls callback
    update_value_button = driver.find_element(By.ID, "update_value")
    update_value_button.click()

    assert (
        call_script.poll_for_content(update_value_button, exp_not_equal="Initial")
        == "updated"
    )


def test_call_script_w_var(
    call_script: AppHarness,
    driver: WebDriver,
):
    """Test evaluating javascript expressions containing Vars.

    Args:
        call_script: harness for CallScript app.
        driver: WebDriver instance.
    """
    assert_token(driver)
    last_result = driver.find_element(By.ID, "last_result")
    assert last_result.get_attribute("value") == "0"

    inline_return_button = driver.find_element(By.ID, "inline_return")

    call_with_var_f_string_button = driver.find_element(By.ID, "call_with_var_f_string")
    call_with_var_str_cast_button = driver.find_element(By.ID, "call_with_var_str_cast")
    call_with_var_f_string_wrapped_button = driver.find_element(
        By.ID, "call_with_var_f_string_wrapped"
    )
    call_with_var_str_cast_wrapped_button = driver.find_element(
        By.ID, "call_with_var_str_cast_wrapped"
    )
    call_with_var_f_string_inline_button = driver.find_element(
        By.ID, "call_with_var_f_string_inline"
    )
    call_with_var_str_cast_inline_button = driver.find_element(
        By.ID, "call_with_var_str_cast_inline"
    )
    call_with_var_f_string_wrapped_inline_button = driver.find_element(
        By.ID, "call_with_var_f_string_wrapped_inline"
    )
    call_with_var_str_cast_wrapped_inline_button = driver.find_element(
        By.ID, "call_with_var_str_cast_wrapped_inline"
    )

    inline_return_button.click()
    call_with_var_f_string_button.click()
    assert call_script.poll_for_value(last_result, exp_not_equal="") == "1"

    inline_return_button.click()
    call_with_var_str_cast_button.click()
    assert call_script.poll_for_value(last_result, exp_not_equal="1") == "2"

    inline_return_button.click()
    call_with_var_f_string_wrapped_button.click()
    assert call_script.poll_for_value(last_result, exp_not_equal="2") == "3"

    inline_return_button.click()
    call_with_var_str_cast_wrapped_button.click()
    assert call_script.poll_for_value(last_result, exp_not_equal="3") == "4"

    inline_return_button.click()
    call_with_var_f_string_inline_button.click()
    assert call_script.poll_for_value(last_result, exp_not_equal="4") == "9"

    inline_return_button.click()
    call_with_var_str_cast_inline_button.click()
    assert call_script.poll_for_value(last_result, exp_not_equal="9") == "6"

    inline_return_button.click()
    call_with_var_f_string_wrapped_inline_button.click()
    assert call_script.poll_for_value(last_result, exp_not_equal="6") == "13"

    inline_return_button.click()
    call_with_var_str_cast_wrapped_inline_button.click()
    assert call_script.poll_for_value(last_result, exp_not_equal="13") == "8"
