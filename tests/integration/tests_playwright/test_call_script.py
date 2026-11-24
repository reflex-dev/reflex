"""Integration tests for Reflex's browser call_script API."""

from __future__ import annotations

from collections.abc import Generator

import pytest
from playwright.sync_api import Page, expect

from reflex.config import get_config
from reflex.testing import AppHarness


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

    import importlib

    # A JavaScript module beside the app, imported from Python.
    Path(__file__).with_name("page_script.js").write_text(
        'import { reflex } from "$/utils/reflex";\n'
        "export function setText(id, text) {\n"
        "  document.getElementById(id).textContent = text;\n"
        "}\n"
        "export async function report(handler, value) {\n"
        "  await Promise.resolve();\n"
        "  reflex.addEvents([reflex.event(handler, { value })]);\n"
        "}\n"
    )
    page_script = importlib.import_module(__name__.rpartition(".")[0] + ".page_script")

    class CallScriptState(rx.State):
        results: rx.Field[list[str | dict | list | None]] = rx.field([])
        inline_counter: rx.Field[int] = rx.field(0)
        external_counter: rx.Field[int] = rx.field(0)
        value: str = "Initial"
        last_result: rx.Field[int] = rx.field(0)
        reflex_result: str = ""

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
        def set_reflex_result(self, value: str):
            self.reflex_result = value

        @rx.event
        def js_module_backend(self):
            """Call a JavaScript module's function from a backend event.

            Returns:
                The call.
            """
            return page_script.setText("js_module_text", "from the backend")

        @rx.event
        def js_module_then_script(self):
            """Call a module's function, then a script that reads what it did.

            Yields:
                The call, then the script.
            """
            # Each yield is a message of its own, and the script must see what
            # the module's function did.
            yield page_script.setText("js_module_text", "written by the module")
            yield rx.call_script(
                "document.getElementById('js_module_text').textContent",
                callback=CallScriptState.set_reflex_result,
            )

        @rx.event
        def ref_from_backend(self):
            return rx.run_script(
                rx.js.ref("reflex_target").current.value,
                callback=CallScriptState.set_reflex_result,
            )

        @rx.event
        def upload_url_from_backend(self):
            return rx.call_script(
                rx.get_upload_url("a.png"), callback=CallScriptState.set_reflex_result
            )

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
            rx.input(id="reflex_target", default_value="from the ref"),
            rx.input(
                value=CallScriptState.reflex_result, id="reflex_result", read_only=True
            ),
            rx.button(
                "ref_from_string",
                on_click=rx.call_script(
                    "reflex.ref('reflex_target').current.value",
                    callback=CallScriptState.set_reflex_result,
                ),
                id="ref_from_string",
            ),
            rx.button(
                "add_events_from_string",
                on_click=rx.call_script(
                    "reflex.addEvents([reflex.event("
                    f"'{CallScriptState.get_full_name()}.set_reflex_result', "
                    "{value: 'addEvents from a script'})])"
                ),
                id="add_events_from_string",
            ),
            rx.button(
                "ref_from_backend",
                on_click=CallScriptState.ref_from_backend,
                id="ref_from_backend",
            ),
            rx.button(
                "upload_url_from_backend",
                on_click=CallScriptState.upload_url_from_backend,
                id="upload_url_from_backend",
            ),
            rx.text("", id="js_module_text"),
            rx.button(
                "js_module_frontend",
                on_click=page_script.setText("js_module_text", "from a trigger"),
                id="js_module_frontend",
            ),
            rx.button(
                "js_module_backend",
                on_click=CallScriptState.js_module_backend,
                id="js_module_backend",
            ),
            rx.button(
                "js_module_then_script",
                on_click=CallScriptState.js_module_then_script,
                id="js_module_then_script",
            ),
            rx.button(
                "js_module_report",
                on_click=page_script.report(
                    CallScriptState.set_reflex_result, "from a module"
                ),
                id="js_module_report",
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


def test_reflex_api(call_script_page: Page):
    """Scripts reach Reflex through `reflex`, from strings and from `rx.js`.

    Args:
        call_script_page: Playwright page.
    """
    result = call_script_page.locator("#reflex_result")

    call_script_page.locator("#ref_from_string").click()
    expect(result).to_have_value("from the ref")

    call_script_page.locator("#add_events_from_string").click()
    expect(result).to_have_value("addEvents from a script")

    call_script_page.locator("#reflex_target").fill("typed, read by the backend")
    call_script_page.locator("#ref_from_backend").click()
    expect(result).to_have_value("typed, read by the backend")

    # A script from the backend still reads `env` from env.json.
    call_script_page.locator("#upload_url_from_backend").click()
    expect(result).to_have_value(f"{get_config().api_url}/_upload/a.png")


def test_js_module(call_script_page: Page):
    """Functions of a JavaScript module imported from Python run by name.

    Args:
        call_script_page: Playwright page.
    """
    text = call_script_page.locator("#js_module_text")

    call_script_page.locator("#js_module_frontend").click()
    expect(text).to_have_text("from a trigger")

    call_script_page.locator("#js_module_backend").click()
    expect(text).to_have_text("from the backend")

    call_script_page.locator("#js_module_report").click()
    expect(call_script_page.locator("#reflex_result")).to_have_value("from a module")

    call_script_page.locator("#js_module_then_script").click()
    expect(call_script_page.locator("#reflex_result")).to_have_value(
        "written by the module"
    )
